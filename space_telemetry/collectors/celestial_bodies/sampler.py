"""Celestial-body (fixed star) sampling: one sampler per observer -> StarSnapshot.

Alt/az for every tracked star is computed in a single vectorised Skyfield call. Rise/set
uses the closed-form hour angle at the horizon (stars are fixed on the sky, so there is
no need for an event search): a star of declination δ seen from latitude φ reaches the
mask altitude h0 at hour angle H where cos H = (sin h0 − sinφ sinδ)/(cosφ cosδ)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from skyfield.api import Star

from ...geometry import altaz
from ...observer import Observer
from .stars import tracked_stars

_SIDEREAL = 86164.0905 / 86400.0  # one sidereal hour in solar hours


@dataclass
class StarState:
    star: str
    altitude_deg: float
    azimuth_deg: float
    above_horizon: bool
    magnitude: float
    distance_ly: Optional[float] = None
    spectral: str = ""
    constellation: str = ""
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
        self._cat = tracked_stars(settings.star_max_magnitude, settings.stars)
        self._ra = np.array([s[2] for s in self._cat])       # RA, hours
        self._dec = np.array([s[3] for s in self._cat])      # Dec, degrees
        self._star = Star(ra_hours=self._ra, dec_degrees=self._dec) if self._cat else None

    def _rise_set(self, t):
        """Vectorised next rise/set UNIX timestamps; NaN where circumpolar or never rises."""
        phi = np.radians(self.observer.latitude_deg)
        dec = np.radians(self._dec)
        h0 = np.radians(self.settings.min_elevation_deg)
        cos_h = (np.sin(h0) - np.sin(phi) * np.sin(dec)) / (np.cos(phi) * np.cos(dec))
        valid = np.abs(cos_h) <= 1.0
        hour_angle = np.zeros_like(cos_h)
        hour_angle[valid] = np.degrees(np.arccos(np.clip(cos_h[valid], -1.0, 1.0))) / 15.0  # hours
        lst_now = (t.gast + self.observer.longitude_deg / 15.0) % 24.0  # local sidereal, hours
        now_ts = t.utc_datetime().timestamp()

        def next_ts(target_lst):  # next solar time the sky reaches this local sidereal time
            return now_ts + ((target_lst - lst_now) % 24.0) * _SIDEREAL * 3600.0

        rise = next_ts((self._ra - hour_angle) % 24.0)
        set_ = next_ts((self._ra + hour_angle) % 24.0)
        rise[~valid] = np.nan
        set_[~valid] = np.nan
        return rise, set_

    def sample(self, now=None) -> StarSnapshot:
        t = now if now is not None else self.ts.now()
        taken = t.utc_datetime().timestamp()
        if not self._cat:
            return StarSnapshot(self.observer, taken, [])
        alt, az, _dist = altaz(self._site, t, self._star)
        alts = np.atleast_1d(alt)
        azs = np.atleast_1d(az)
        rise, set_ = self._rise_set(t)
        mask = self.settings.min_elevation_deg
        states: list[StarState] = []
        for i, s in enumerate(self._cat):
            states.append(StarState(
                s[1], round(float(alts[i]), 2), round(float(azs[i]), 1),
                bool(alts[i] > mask), s[4], s[5], s[6], s[7],
                None if np.isnan(rise[i]) else float(rise[i]),
                None if np.isnan(set_[i]) else float(set_[i]),
            ))
        return StarSnapshot(self.observer, taken, states)
