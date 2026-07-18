"""Solar-system body sampling: one sampler per observer -> BodySnapshot.

Fast-moving values (alt/az/distance) are recomputed every call; slow rise/set
values are cached for ``pass_cache_ttl_s`` seconds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Optional

from ...geometry import altaz
from ...observer import Observer
from ...passes import next_rise_set
from .ephemeris import target_for
from .lunar import illuminated_fraction, phase_degrees


@dataclass
class BodyState:
    body: str
    altitude_deg: float
    azimuth_deg: float
    distance_m: float
    above_horizon: bool
    next_rise_ts: Optional[float] = None
    next_set_ts: Optional[float] = None
    illuminated_fraction: Optional[float] = None  # Moon only
    phase_deg: Optional[float] = None             # Moon only


@dataclass
class BodySnapshot:
    observer: Observer
    taken_at: float
    bodies: list[BodyState] = field(default_factory=list)


class BodySampler:
    def __init__(self, eph, observer: Observer, ts, settings):
        self.eph = eph
        self.observer = observer
        self.ts = ts
        self.settings = settings
        self._site = eph["earth"] + observer.topos()
        self._topos = observer.topos()
        self._pass_cache: dict[str, tuple] = {}

    def _rise_set(self, name, target, t):
        cached = self._pass_cache.get(name)
        now = monotonic()
        if cached is not None and now - cached[0] < self.settings.pass_cache_ttl_s:
            return cached[1], cached[2]
        rise, set_ = next_rise_set(self.eph, self._topos, target, self.ts, t,
                                   horizon_deg=self.settings.min_elevation_deg)
        self._pass_cache[name] = (now, rise, set_)
        return rise, set_

    def sample(self, now=None) -> BodySnapshot:
        t = now if now is not None else self.ts.now()
        mask = self.settings.min_elevation_deg
        states: list[BodyState] = []
        for name in self.settings.bodies:
            target = target_for(self.eph, name)
            alt, az, dist = altaz(self._site, t, target)
            rise, set_ = self._rise_set(name, target, t)
            state = BodyState(name, alt, az, dist, alt > mask, rise, set_)
            if name == "moon":
                state.illuminated_fraction = illuminated_fraction(self.eph, t)
                state.phase_deg = phase_degrees(self.eph, t)
            states.append(state)
        return BodySnapshot(self.observer, t.utc_datetime().timestamp(), states)
