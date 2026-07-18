"""Prometheus collector for the sky module: solar-system bodies + celestial bodies.

Takes one ``SkySampler`` per observer and emits a series per (target, observer).
"""

from __future__ import annotations

from time import perf_counter

from prometheus_client.core import GaugeMetricFamily

_BODY_L = ["body", "observer"]
_STAR_L = ["star", "observer"]


class SkyCollector:
    def __init__(self, samplers):
        self.samplers = list(samplers)

    def collect(self):
        start = perf_counter()

        alt = GaugeMetricFamily("body_altitude_degrees", "Apparent altitude above the horizon (degrees).", labels=_BODY_L)
        az = GaugeMetricFamily("body_azimuth_degrees", "Apparent azimuth, degrees clockwise from north.", labels=_BODY_L)
        dist = GaugeMetricFamily("body_distance_meters", "Distance from observer to body (metres).", labels=_BODY_L)
        above = GaugeMetricFamily("body_above_horizon", "1 if the body is above the configured horizon mask.", labels=_BODY_L)
        rise = GaugeMetricFamily("body_next_rise_timestamp_seconds", "Next rise time (UNIX seconds).", labels=_BODY_L)
        set_ = GaugeMetricFamily("body_next_set_timestamp_seconds", "Next set time (UNIX seconds).", labels=_BODY_L)
        frac = GaugeMetricFamily("moon_illuminated_fraction", "Fraction of the lunar disc illuminated (0..1).", labels=["observer"])
        phase = GaugeMetricFamily("moon_phase_degrees", "Moon phase angle (0=new, 90=first quarter, 180=full).", labels=["observer"])

        salt = GaugeMetricFamily("star_altitude_degrees", "Apparent altitude above the horizon (degrees).", labels=_STAR_L)
        saz = GaugeMetricFamily("star_azimuth_degrees", "Apparent azimuth, degrees clockwise from north.", labels=_STAR_L)
        sabove = GaugeMetricFamily("star_above_horizon", "1 if the star is above the configured horizon mask.", labels=_STAR_L)
        smag = GaugeMetricFamily("star_magnitude", "Apparent visual magnitude (catalog, static).", labels=_STAR_L)
        srise = GaugeMetricFamily("star_next_rise_timestamp_seconds", "Next rise time (UNIX seconds).", labels=_STAR_L)
        sset = GaugeMetricFamily("star_next_set_timestamp_seconds", "Next set time (UNIX seconds).", labels=_STAR_L)

        info = GaugeMetricFamily(
            "sky_observer_info", "Observer location (value always 1; detail in labels).",
            labels=["observer", "latitude_deg", "longitude_deg", "elevation_m"],
        )

        for sampler in self.samplers:
            snap = sampler.sample()
            obs = snap.observer.name
            for b in snap.bodies:
                lv = [b.body, obs]
                alt.add_metric(lv, b.altitude_deg)
                az.add_metric(lv, b.azimuth_deg)
                dist.add_metric(lv, b.distance_m)
                above.add_metric(lv, 1.0 if b.above_horizon else 0.0)
                if b.next_rise_ts is not None:
                    rise.add_metric(lv, b.next_rise_ts)
                if b.next_set_ts is not None:
                    set_.add_metric(lv, b.next_set_ts)
                if b.body == "moon":
                    if b.illuminated_fraction is not None:
                        frac.add_metric([obs], b.illuminated_fraction)
                    if b.phase_deg is not None:
                        phase.add_metric([obs], b.phase_deg)
            for s in snap.stars:
                lv = [s.star, obs]
                salt.add_metric(lv, s.altitude_deg)
                saz.add_metric(lv, s.azimuth_deg)
                sabove.add_metric(lv, 1.0 if s.above_horizon else 0.0)
                smag.add_metric(lv, s.magnitude)
                if s.next_rise_ts is not None:
                    srise.add_metric(lv, s.next_rise_ts)
                if s.next_set_ts is not None:
                    sset.add_metric(lv, s.next_set_ts)
            o = snap.observer
            info.add_metric([obs, f"{o.latitude_deg:.4f}", f"{o.longitude_deg:.4f}", f"{o.elevation_m:.1f}"], 1.0)

        yield from (alt, az, dist, above, rise, set_, frac, phase,
                    salt, saz, sabove, smag, srise, sset, info)

        duration = GaugeMetricFamily("sky_scrape_duration_seconds",
                                     "Seconds spent building the sky snapshot for this scrape.")
        duration.add_metric([], perf_counter() - start)
        yield duration
