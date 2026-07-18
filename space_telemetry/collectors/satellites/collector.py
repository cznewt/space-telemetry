"""Prometheus collector for the satellites module.

Takes one ``SatelliteProvider`` per observer (per-satellite geometry + Doppler)
plus the shared updater for observer-independent catalog + pipeline health.
"""

from __future__ import annotations

from time import perf_counter, time

from prometheus_client.core import GaugeMetricFamily

_SAT_L = ["norad", "name", "observer"]
_TX_L = ["norad", "uuid", "mode", "status"]
_C = 299_792_458.0  # speed of light, m/s


class SatelliteCollector:
    def __init__(self, providers, updater):
        self.providers = list(providers)
        self.updater = updater

    def collect(self):
        start = perf_counter()
        now = time()
        # Propagate once per observer; reuse the states for every metric below.
        per_observer = [(p.observer.name, p.states()) for p in self.providers]

        def sat_gauge(name, help_):
            return GaugeMetricFamily(name, help_, labels=_SAT_L)

        elev = sat_gauge("satellite_elevation_degrees", "Elevation above the horizon (degrees).")
        az = sat_gauge("satellite_azimuth_degrees", "Azimuth, degrees clockwise from north.")
        rng = sat_gauge("satellite_range_meters", "Slant range observer->satellite (metres).")
        rate = sat_gauge("satellite_range_rate_meters_per_second", "Range rate (+receding); drives Doppler.")
        sublat = sat_gauge("satellite_subpoint_latitude_degrees", "Sub-satellite point latitude (degrees).")
        sublon = sat_gauge("satellite_subpoint_longitude_degrees", "Sub-satellite point longitude (degrees).")
        salt = sat_gauge("satellite_altitude_meters", "Satellite height above the ellipsoid (metres).")
        vel = sat_gauge("satellite_velocity_meters_per_second", "Orbital speed (metres/second).")
        above = sat_gauge("satellite_above_horizon", "1 if above the horizon mask, else 0.")
        sun = sat_gauge("satellite_sunlit", "1 if the satellite is in sunlight, else 0.")
        epoch = sat_gauge("satellite_tle_epoch_timestamp_seconds", "Element-set epoch (UNIX seconds).")
        age = sat_gauge("satellite_tle_age_seconds", "Age of the current element set (seconds).")
        aos = sat_gauge("satellite_next_pass_aos_timestamp_seconds", "Next pass AOS (UNIX seconds).")
        los = sat_gauge("satellite_next_pass_los_timestamp_seconds", "Next pass LOS (UNIX seconds).")
        maxel = sat_gauge("satellite_next_pass_max_elevation_degrees", "Next pass peak elevation (degrees).")

        # Transmitter frequencies/baud are properties of the satellite (observer-independent).
        downlink = GaugeMetricFamily("satellite_transmitter_downlink_hertz",
                                     "Transmitter downlink frequency (Hz).", labels=_TX_L)
        uplink = GaugeMetricFamily("satellite_transmitter_uplink_hertz",
                                   "Transmitter uplink frequency (Hz).", labels=_TX_L)
        baud = GaugeMetricFamily("satellite_transmitter_baud",
                                 "Transmitter symbol rate (baud).", labels=_TX_L)
        # Doppler depends on the observer's range rate.
        doppler = GaugeMetricFamily("satellite_doppler_hertz",
                                    "Doppler shift on the downlink at the current range rate (Hz).",
                                    labels=["norad", "uuid", "observer"])

        seen_tx: set = set()
        for obs, states in per_observer:
            for s in states:
                lv = [str(s.norad_id), s.name, obs]
                elev.add_metric(lv, s.elevation_deg)
                az.add_metric(lv, s.azimuth_deg)
                rng.add_metric(lv, s.range_m)
                rate.add_metric(lv, s.range_rate_m_s)
                sublat.add_metric(lv, s.subpoint_lat_deg)
                sublon.add_metric(lv, s.subpoint_lon_deg)
                salt.add_metric(lv, s.altitude_m)
                vel.add_metric(lv, s.velocity_m_s)
                above.add_metric(lv, 1.0 if s.above_horizon else 0.0)
                if s.sunlit is not None:
                    sun.add_metric(lv, 1.0 if s.sunlit else 0.0)
                epoch.add_metric(lv, s.tle_epoch_ts)
                age.add_metric(lv, now - s.tle_epoch_ts)
                if s.next_aos_ts is not None:
                    aos.add_metric(lv, s.next_aos_ts)
                if s.next_los_ts is not None:
                    los.add_metric(lv, s.next_los_ts)
                if s.next_max_elev_deg is not None:
                    maxel.add_metric(lv, s.next_max_elev_deg)
                for tx in s.transmitters:
                    if tx.downlink_hz is not None:
                        doppler.add_metric([str(s.norad_id), tx.uuid, obs],
                                           -s.range_rate_m_s / _C * tx.downlink_hz)
                    key = (s.norad_id, tx.uuid)
                    if key in seen_tx:
                        continue
                    seen_tx.add(key)
                    txlv = [str(s.norad_id), tx.uuid, tx.mode or "", tx.status or ""]
                    if tx.downlink_hz is not None:
                        downlink.add_metric(txlv, tx.downlink_hz)
                    if tx.uplink_hz is not None:
                        uplink.add_metric(txlv, tx.uplink_hz)
                    if tx.baud is not None:
                        baud.add_metric(txlv, tx.baud)

        yield from (elev, az, rng, rate, sublat, sublon, salt, vel, above, sun,
                    epoch, age, aos, los, maxel, downlink, uplink, baud, doppler)

        total, with_tx = self.providers[0].catalog().stats() if self.providers else (0, 0)
        size = GaugeMetricFamily("satellite_catalog_size", "Satellites in the offline catalog.")
        size.add_metric([], float(total))
        with_tx_g = GaugeMetricFamily("satellite_catalog_with_transmitters",
                                      "Catalog satellites that have at least one transmitter.")
        with_tx_g.add_metric([], float(with_tx))
        tracked = GaugeMetricFamily("satellite_tracked_count",
                                    "Satellites tracked live (per observer).", labels=["observer"])
        for obs, states in per_observer:
            tracked.add_metric([obs], float(len(states)))
        yield from (size, with_tx_g, tracked)

        updated = GaugeMetricFamily("satellite_data_update_timestamp_seconds",
                                    "Last successful fetch per source (UNIX seconds).", labels=["source"])
        ok = GaugeMetricFamily("satellite_data_update_success",
                               "1 if the source's last fetch attempt succeeded.", labels=["source"])
        data_age = GaugeMetricFamily("satellite_data_age_seconds",
                                     "Seconds since the source's last successful fetch.", labels=["source"])
        fetch_dur = GaugeMetricFamily("satellite_data_fetch_duration_seconds",
                                      "Duration of the source's last fetch (seconds).", labels=["source"])
        for h in self.updater.health():
            ok.add_metric([h.source], 1.0 if h.success else 0.0)
            if h.last_success_ts is not None:
                updated.add_metric([h.source], h.last_success_ts)
            if h.age_s is not None:
                data_age.add_metric([h.source], h.age_s)
            if h.fetch_duration_s is not None:
                fetch_dur.add_metric([h.source], h.fetch_duration_s)
        yield from (updated, ok, data_age, fetch_dur)

        duration = GaugeMetricFamily("satellite_scrape_duration_seconds",
                                     "Seconds spent building the satellite snapshot for this scrape.")
        duration.add_metric([], perf_counter() - start)
        yield duration
