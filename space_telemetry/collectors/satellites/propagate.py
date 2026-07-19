"""SGP4 position provider: satellite geometry, pass prediction, tracked-set sampling.

Mirrors ``bodies.ephemeris`` as a position provider, but satellites use
``(satellite - topos).at(t)`` rather than ``.observe()``. Range rate (for Doppler)
is the radial component of the topocentric velocity.
"""

from __future__ import annotations

import math
from time import monotonic

import numpy as np
from skyfield.api import wgs84
from skyfield.framelib import itrs

from .model import CatalogHolder, SatelliteState

_C = 299_792_458.0  # speed of light, m/s
_R_EARTH_KM = 6371.0  # mean Earth radius


def footprint_radius_km(altitude_m: float, mask_deg: float = 0.0) -> float:
    """Ground radius (km) of a satellite's reception footprint: the great-circle distance
    from the sub-satellite point out to where the satellite sits at elevation ``mask_deg``.
    Inside this circle the satellite is above the mask, so its signal can be received. It
    grows with altitude; at the horizon (mask 0) it is R·arccos(R/(R+h))."""
    h = max(altitude_m, 0.0) / 1000.0
    eps = math.radians(mask_deg)
    lam = math.acos((_R_EARTH_KM / (_R_EARTH_KM + h)) * math.cos(eps)) - eps
    return _R_EARTH_KM * max(lam, 0.0)


def subpoint_at(earthsat, t):
    """(latitude_deg, longitude_deg) of the sub-satellite point at time *t*."""
    sub = wgs84.subpoint(earthsat.at(t))
    return sub.latitude.degrees, sub.longitude.degrees


def offset_label(minutes):
    """Human label for a track offset: 0 -> 'now', 60 -> '+1h', -5 -> '-5m'."""
    if minutes == 0:
        return "now"
    sign = "+" if minutes > 0 else "-"
    m = abs(int(minutes))
    return f"{sign}{m // 60}h" if m % 60 == 0 else f"{sign}{m}m"


def group_label(sat):
    """A friendly group for the map/legend: the ISS and CSS station complexes are
    split out by name; otherwise the most specific CelesTrak group the satellite is
    in (weather/noaa/goes before the catch-all stations)."""
    name = sat.name.upper()
    if name.startswith("ISS"):
        return "iss"
    if name.startswith("CSS"):
        return "css"
    for g in ("weather", "noaa", "goes", "stations"):
        if g in sat.groups:
            return g
    return next(iter(sat.groups), "other")


def topocentric_state(earthsat, topos, eph, t) -> dict:
    geocentric = earthsat.at(t)
    subpoint = wgs84.subpoint(geocentric)
    topocentric = (earthsat - topos).at(t)
    alt, az, distance = topocentric.altaz()

    r = topocentric.position.km
    v = topocentric.velocity.km_per_s
    rng = float(np.linalg.norm(r))
    range_rate = float(np.dot(r, v) / rng) if rng else 0.0
    speed = float(np.linalg.norm(geocentric.velocity.km_per_s))
    try:
        sunlit = bool(geocentric.is_sunlit(eph))
    except Exception:
        sunlit = None

    return {
        "elevation_deg": alt.degrees,
        "azimuth_deg": az.degrees,
        "range_m": distance.m,
        "range_rate_m_s": range_rate * 1000.0,
        "subpoint_lat_deg": subpoint.latitude.degrees,
        "subpoint_lon_deg": subpoint.longitude.degrees,
        "altitude_m": subpoint.elevation.m,
        "velocity_m_s": speed * 1000.0,
        "sunlit": sunlit,
    }


def next_pass(earthsat, topos, ts, t0, hours, mask_deg):
    """Return ``(aos_ts, los_ts, max_elevation_deg)`` for the next pass that *starts*
    within *hours* of *t0*. Elements are ``None`` if no such pass is found."""
    t1 = ts.tt_jd(t0.tt + hours / 24.0)
    times, events = earthsat.find_events(topos, t0, t1, altitude_degrees=mask_deg)

    aos = culm = los = None
    for t, event in zip(times, events):
        if aos is None and event == 0:          # rise
            aos = t
        elif aos is not None and culm is None and event == 1:  # culminate
            culm = t
        elif aos is not None and event == 2:    # set
            los = t
            break

    max_elev = None
    if culm is not None:
        alt, _, _ = (earthsat - topos).at(culm).altaz()
        max_elev = alt.degrees
    return (
        aos.utc_datetime().timestamp() if aos is not None else None,
        los.utc_datetime().timestamp() if los is not None else None,
        max_elev,
    )


class SatelliteProvider:
    """Produces ``SatelliteState`` for the tracked set (watchlist ∪ selected groups)."""

    def __init__(self, holder: CatalogHolder, observer, eph, ts, settings):
        self.holder = holder
        self.observer = observer
        self.eph = eph
        self.ts = ts
        self.settings = settings
        self._topos = observer.topos()
        self._pass_cache: dict[int, tuple[float, tuple]] = {}

    def _tracked(self, catalog):
        groups = set(self.settings.sat_groups)
        watch = set(self.settings.sat_watchlist)
        for sat in catalog.satellites.values():
            if sat.norad_id in watch or (sat.groups & groups):
                yield sat

    def _pass(self, sat, t):
        cached = self._pass_cache.get(sat.norad_id)
        now = monotonic()
        if cached is not None and now - cached[0] < self.settings.sat_pass_cache_ttl_s:
            return cached[1]
        result = next_pass(sat.earthsat, self._topos, self.ts, t,
                           self.settings.pass_lookahead_hours, self.settings.min_elevation_deg)
        self._pass_cache[sat.norad_id] = (now, result)
        return result

    def states(self) -> list[SatelliteState]:
        catalog = self.holder.get()
        t = self.ts.now()
        mask = self.settings.min_elevation_deg
        out: list[SatelliteState] = []
        for sat in self._tracked(catalog):
            try:
                geo = topocentric_state(sat.earthsat, self._topos, self.eph, t)
                aos, los, max_elev = self._pass(sat, t)
            except Exception:
                continue
            out.append(SatelliteState(
                norad_id=sat.norad_id, name=sat.name,
                elevation_deg=geo["elevation_deg"], azimuth_deg=geo["azimuth_deg"],
                range_m=geo["range_m"], range_rate_m_s=geo["range_rate_m_s"],
                subpoint_lat_deg=geo["subpoint_lat_deg"], subpoint_lon_deg=geo["subpoint_lon_deg"],
                altitude_m=geo["altitude_m"], velocity_m_s=geo["velocity_m_s"],
                above_horizon=geo["elevation_deg"] > mask, sunlit=geo["sunlit"],
                tle_epoch_ts=sat.epoch_ts,
                next_aos_ts=aos, next_los_ts=los, next_max_elev_deg=max_elev,
                group=group_label(sat),
                transmitters=sat.transmitters,
            ))
        return out

    def tracks(self):
        """Ground track for the tracked set: (norad, name, offset_label, lat, lon) at
        each configured time offset. Observer-independent, so the collector emits it once."""
        catalog = self.holder.get()
        now = self.ts.now()
        out = []
        for sat in self._tracked(catalog):
            for minutes in self.settings.sat_track_offsets_minutes:
                t = self.ts.tt_jd(now.tt + minutes / 1440.0)
                try:
                    lat, lon = subpoint_at(sat.earthsat, t)
                except Exception:
                    continue
                out.append((sat.norad_id, sat.name, offset_label(minutes), lat, lon))
        return out

    def infos(self):
        """(norad, name, group) for the tracked set. Observer-independent, emitted once."""
        catalog = self.holder.get()
        return [(sat.norad_id, sat.name, group_label(sat))
                for sat in self._tracked(catalog)]

    def ground_tracks(self, orbits=10, points=240, nominal_period_min=95.0):
        """Forward ground track per tracked sat, for the /map view: from now out over
        ~`orbits` orbital periods, sampled in `points` steps. All satellites share ONE
        time grid (a nominal LEO period), so Earth orientation is computed once instead of
        per satellite — each sat's own period only changes how many loops it completes over
        the fixed span, which is fine for a map. Sub-points use the spherical (geocentric)
        latitude: visually identical at map scale but far cheaper than the iterative
        geodetic solve. {norad: [[lat, lon], ...]}."""
        catalog = self.holder.get()
        now = self.ts.now()
        offsets_min = np.linspace(0.0, orbits * nominal_period_min, points + 1)
        t = self.ts.tt_jd(now.tt + offsets_min / 1440.0)  # one grid, shared by all sats
        out: dict[int, list] = {}
        for sat in self._tracked(catalog):
            try:
                x, y, z = sat.earthsat.at(t).frame_xyz(itrs).km
                lat = np.degrees(np.arctan2(z, np.sqrt(x * x + y * y)))
                lon = np.degrees(np.arctan2(y, x))
                # 2 dp ≈ 1 km on the ground: plenty for a world map, half the payload
                out[sat.norad_id] = np.round(np.column_stack([lat, lon]), 2).tolist()
            except Exception:
                continue
        return out

    def positions(self, offset_min=0.0):
        """Lightweight sub-satellite positions for the /map feed: subpoint, altitude,
        elevation, sunlit, group and footprint radius, with NO pass prediction — states()
        runs find_events (seconds, cold) which the map does not need. ``offset_min`` shifts
        the evaluation time from now (the /map time scrubber, ±1 day). Keeps /map cheap on
        every scrape. [{norad, name, group, lat, lon, alt_m, elevation, sunlit, footprint_km}]."""
        catalog = self.holder.get()
        t = self.ts.tt_jd(self.ts.now().tt + offset_min / 1440.0) if offset_min else self.ts.now()
        out = []
        for sat in self._tracked(catalog):
            try:
                geo = topocentric_state(sat.earthsat, self._topos, self.eph, t)
            except Exception:
                continue
            out.append({
                "norad": sat.norad_id, "name": sat.name, "group": group_label(sat),
                "lat": geo["subpoint_lat_deg"], "lon": geo["subpoint_lon_deg"],
                "alt_m": geo["altitude_m"], "elevation": geo["elevation_deg"],
                "sunlit": geo["sunlit"],
                "footprint_km": footprint_radius_km(geo["altitude_m"], self.settings.min_elevation_deg),
            })
        return out

    def catalog(self):
        return self.holder.get()
