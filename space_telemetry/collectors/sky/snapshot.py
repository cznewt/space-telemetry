"""Pure sampling core for the sky collector: solar-system bodies + celestial bodies.

``SkySampler.sample()`` returns a ``SkySnapshot`` for "now" (or a supplied time).
Fast-moving values (alt/az/distance) are recomputed every call; rise/set values
change slowly and are cached for ``pass_cache_ttl_s`` seconds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Optional

from ...observer import Observer
from .celestial_bodies.stars import star_targets
from .geometry import altaz
from .passes import next_rise_set
from .solar_system_bodies.ephemeris import target_for
from .solar_system_bodies.lunar import illuminated_fraction, phase_degrees


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
class StarState:
    star: str
    altitude_deg: float
    azimuth_deg: float
    above_horizon: bool
    magnitude: float
    next_rise_ts: Optional[float] = None
    next_set_ts: Optional[float] = None


@dataclass
class SkySnapshot:
    observer: Observer
    taken_at: float  # UNIX seconds
    bodies: list[BodyState] = field(default_factory=list)
    stars: list[StarState] = field(default_factory=list)


class SkySampler:
    def __init__(self, eph, observer: Observer, ts, settings):
        self.eph = eph
        self.observer = observer
        self.ts = ts
        self.settings = settings
        self._site = eph["earth"] + observer.topos()
        self._topos = observer.topos()
        self._pass_cache: dict[str, tuple] = {}
        self._star_pass_cache: dict[str, tuple] = {}
        self._stars = star_targets({s.lower() for s in settings.stars})

    def _rise_set(self, key: str, target, t, cache: dict):
        cached = cache.get(key)
        now = monotonic()
        if cached is not None and now - cached[0] < self.settings.pass_cache_ttl_s:
            return cached[1], cached[2]
        rise, set_ = next_rise_set(self.eph, self._topos, target, self.ts, t,
                                   horizon_deg=self.settings.min_elevation_deg)
        cache[key] = (now, rise, set_)
        return rise, set_

    def sample(self, now=None) -> SkySnapshot:
        t = now if now is not None else self.ts.now()
        mask = self.settings.min_elevation_deg

        bodies: list[BodyState] = []
        for name in self.settings.bodies:
            target = target_for(self.eph, name)
            alt, az, dist = altaz(self._site, t, target)
            rise, set_ = self._rise_set(name, target, t, self._pass_cache)
            state = BodyState(name, alt, az, dist, alt > mask, rise, set_)
            if name == "moon":
                state.illuminated_fraction = illuminated_fraction(self.eph, t)
                state.phase_deg = phase_degrees(self.eph, t)
            bodies.append(state)

        stars: list[StarState] = []
        for name, (target, magnitude) in self._stars.items():
            alt, az, _distance = altaz(self._site, t, target)
            rise, set_ = self._rise_set(f"*{name}", target, t, self._star_pass_cache)
            stars.append(StarState(name, alt, az, alt > mask, magnitude, rise, set_))

        return SkySnapshot(self.observer, t.utc_datetime().timestamp(), bodies, stars)
