"""Rise/set search (shared).

Uses ``skyfield.almanac.risings_and_settings`` + ``find_discrete`` — a stable API
across Skyfield versions. The satellites family will use ``EarthSatellite.
find_events`` for AOS/LOS instead.
"""

from __future__ import annotations

from typing import Optional

from skyfield import almanac


def next_rise_set(eph, topos, target, ts, t0, hours: float = 24.0, horizon_deg: float = 0.0):
    """Next ``(rise_ts, set_ts)`` as UNIX seconds within *hours* of *t0*.

    Either element is ``None`` if that event does not occur in the window (e.g. a
    circumpolar body, or one that never rises at this latitude).
    """
    t1 = ts.tt_jd(t0.tt + hours / 24.0)
    fn = almanac.risings_and_settings(eph, target, topos, horizon_degrees=horizon_deg)
    times, events = almanac.find_discrete(t0, t1, fn)

    rise_ts: Optional[float] = None
    set_ts: Optional[float] = None
    for t, is_rise in zip(times, events):
        if is_rise and rise_ts is None:
            rise_ts = t.utc_datetime().timestamp()
        elif not is_rise and set_ts is None:
            set_ts = t.utc_datetime().timestamp()
        if rise_ts is not None and set_ts is not None:
            break
    return rise_ts, set_ts
