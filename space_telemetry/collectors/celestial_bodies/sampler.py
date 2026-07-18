"""Celestial-body (fixed star) sampling: one sampler per observer -> StarSnapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Optional

from ...geometry import altaz
from ...observer import Observer
from ...passes import next_rise_set
from .stars import star_targets


@dataclass
class StarState:
    star: str
    altitude_deg: float
    azimuth_deg: float
    above_horizon: bool
    magnitude: float
    next_rise_ts: Optional[float] = None
    next_set_ts: Optional[float] = None


@dataclass
class StarSnapshot:
    observer: Observer
    taken_at: float
    stars: list[StarState] = field(default_factory=list)


class StarSampler:
    def __init__(self, eph, observer: Observer, ts, settings):
        self.eph = eph
        self.observer = observer
        self.ts = ts
        self.settings = settings
        self._site = eph["earth"] + observer.topos()
        self._topos = observer.topos()
        self._pass_cache: dict[str, tuple] = {}
        self._stars = star_targets({s.lower() for s in settings.stars})

    def _rise_set(self, name, target, t):
        cached = self._pass_cache.get(name)
        now = monotonic()
        if cached is not None and now - cached[0] < self.settings.pass_cache_ttl_s:
            return cached[1], cached[2]
        rise, set_ = next_rise_set(self.eph, self._topos, target, self.ts, t,
                                   horizon_deg=self.settings.min_elevation_deg)
        self._pass_cache[name] = (now, rise, set_)
        return rise, set_

    def sample(self, now=None) -> StarSnapshot:
        t = now if now is not None else self.ts.now()
        mask = self.settings.min_elevation_deg
        states: list[StarState] = []
        for name, (target, magnitude) in self._stars.items():
            alt, az, _distance = altaz(self._site, t, target)
            rise, set_ = self._rise_set(name, target, t)
            states.append(StarState(name, alt, az, alt > mask, magnitude, rise, set_))
        return StarSnapshot(self.observer, t.utc_datetime().timestamp(), states)
