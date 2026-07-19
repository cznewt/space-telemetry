"""Prometheus collector for celestial bodies / fixed stars (star_*)."""

from __future__ import annotations

from time import perf_counter

from prometheus_client.core import GaugeMetricFamily

_L = ["star", "observer"]


class StarCollector:
    def __init__(self, samplers):
        self.samplers = list(samplers)

    def collect(self):
        start = perf_counter()

        alt = GaugeMetricFamily("star_altitude_degrees", "Apparent altitude above the horizon (degrees).", labels=_L)
        az = GaugeMetricFamily("star_azimuth_degrees", "Apparent azimuth, degrees clockwise from north.", labels=_L)
        above = GaugeMetricFamily("star_above_horizon", "1 if the star is above the configured horizon mask.", labels=_L)
        mag = GaugeMetricFamily("star_magnitude", "Apparent visual magnitude (catalog, static).", labels=_L)
        rise = GaugeMetricFamily("star_next_rise_timestamp_seconds", "Next rise time (UNIX seconds).", labels=_L)
        set_ = GaugeMetricFamily("star_next_set_timestamp_seconds", "Next set time (UNIX seconds).", labels=_L)
        dist = GaugeMetricFamily("star_distance_light_years", "Distance from the Sun (light-years).", labels=_L)
        info = GaugeMetricFamily("star_info", "Static star info; value is 1, detail is in the labels.",
                                 labels=["star", "constellation", "spectral"])

        seen: set = set()
        for sampler in self.samplers:
            snap = sampler.sample()
            obs = snap.observer.name
            for s in snap.stars:
                lv = [s.star, obs]
                alt.add_metric(lv, s.altitude_deg)
                az.add_metric(lv, s.azimuth_deg)
                above.add_metric(lv, 1.0 if s.above_horizon else 0.0)
                mag.add_metric(lv, s.magnitude)
                if s.distance_ly is not None:
                    dist.add_metric(lv, s.distance_ly)
                if s.next_rise_ts is not None:
                    rise.add_metric(lv, s.next_rise_ts)
                if s.next_set_ts is not None:
                    set_.add_metric(lv, s.next_set_ts)
                if s.star not in seen:  # static info, observer-independent -> emit once
                    seen.add(s.star)
                    info.add_metric([s.star, s.constellation, s.spectral or ""], 1.0)

        yield from (alt, az, above, mag, dist, rise, set_, info)

        duration = GaugeMetricFamily("star_scrape_duration_seconds",
                                     "Seconds spent building the celestial-body snapshot for this scrape.")
        duration.add_metric([], perf_counter() - start)
        yield duration
