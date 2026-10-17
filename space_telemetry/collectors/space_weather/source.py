"""NOAA SWPC products: URLs + parsers that extract the latest value(s).

Each parser takes the raw JSON bytes and returns ``{metric_name: float}`` for the
most recent observation, skipping any null fields. All these products are a JSON
list; the latest observation is the last element. ``forecasts()`` lists the
forecast products behind /forecast, whose parsers return values per UTC day instead.
"""

from __future__ import annotations

import json

SWPC_BASE = "https://services.swpc.noaa.gov"


def products():
    """(key, url, filename, parser) for every product we scrape."""
    return [
        ("kp", f"{SWPC_BASE}/products/noaa-planetary-k-index.json", "kp.json", parse_kp),
        ("wind", f"{SWPC_BASE}/products/summary/solar-wind-speed.json", "wind.json", parse_wind),
        ("mag", f"{SWPC_BASE}/products/summary/solar-wind-mag-field.json", "mag.json", parse_mag),
        ("f107", f"{SWPC_BASE}/products/summary/10cm-flux.json", "f107.json", parse_f107),
        ("xray", f"{SWPC_BASE}/json/goes/primary/xrays-1-day.json", "xray.json", parse_xray),
    ]


def forecasts():
    """(key, url, filename, parser) for the forecast products behind /forecast. They
    feed that page and /api/forecast.json, not metrics; each parser returns
    ``{"issued": str | None, "days": {"YYYY-MM-DD": {field: value}}}`` by UTC day."""
    return [
        ("kp_forecast", f"{SWPC_BASE}/products/noaa-planetary-k-index-forecast.json",
         "kp_forecast.json", parse_kp_forecast),
        ("outlook_27d", f"{SWPC_BASE}/text/27-day-outlook.txt", "27-day-outlook.txt", parse_outlook_27d),
    ]


def _f(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _latest(raw: bytes):
    """Last element of a JSON list, or ``None``."""
    data = json.loads(raw.decode("utf-8", "replace"))
    return data[-1] if isinstance(data, list) and data else None


def parse_kp(raw: bytes) -> dict:
    row = _latest(raw)  # [{"time_tag":..., "Kp": 2.33, ...}, ...]
    if not isinstance(row, dict):
        return {}
    kp = _f(row.get("Kp"))
    return {"space_weather_planetary_k_index": kp} if kp is not None else {}


def parse_wind(raw: bytes) -> dict:
    row = _latest(raw)  # [{"proton_speed": 338, "time_tag": ...}]
    if not isinstance(row, dict):
        return {}
    speed = _f(row.get("proton_speed"))
    return {"space_weather_solar_wind_speed_km_per_second": speed} if speed is not None else {}


def parse_mag(raw: bytes) -> dict:
    row = _latest(raw)  # [{"bt": 4, "bz_gsm": 0, "time_tag": ...}]
    if not isinstance(row, dict):
        return {}
    out = {}
    bz = _f(row.get("bz_gsm"))
    bt = _f(row.get("bt"))
    if bz is not None:
        out["space_weather_imf_bz_nanotesla"] = bz
    if bt is not None:
        out["space_weather_imf_bt_nanotesla"] = bt
    return out


def parse_f107(raw: bytes) -> dict:
    row = _latest(raw)  # [{"flux": 105, "time_tag": ...}]
    if not isinstance(row, dict):
        return {}
    flux = _f(row.get("flux"))
    return {"space_weather_f107_solar_radio_flux": flux} if flux is not None else {}


def parse_xray(raw: bytes) -> dict:
    # list of {time_tag, satellite, flux, energy}; take latest long-band (0.1-0.8 nm)
    data = json.loads(raw.decode("utf-8", "replace"))
    if not isinstance(data, list):
        return {}
    longband = [d for d in data if d.get("energy") == "0.1-0.8nm"]
    if not longband:
        return {}
    flux = _f(longband[-1].get("flux"))
    return {"space_weather_goes_xray_flux_watts_per_m2": flux} if flux is not None else {}


def parse_kp_forecast(raw: bytes) -> dict:
    """3-hourly planetary Kp, observed then predicted ~3 days ahead:
    ``[{"time_tag": "2026-10-19T18:00:00", "kp": 1.67, "observed": "predicted"}, ...]``
    (older issues are a list of rows under a header row). Gives the largest Kp of each
    UTC day it covers: at least 6 of the day's 8 intervals, some of them not observed
    yet (today mixes observed with estimated ones; the last day is often a stub)."""
    data = json.loads(raw.decode("utf-8", "replace"))
    if not isinstance(data, list):
        return {"issued": None, "days": {}}
    if data and isinstance(data[0], list):  # header row + value rows
        data = [dict(zip(data[0], row)) for row in data[1:]]
    largest: dict[str, float] = {}
    intervals: dict[str, int] = {}
    ahead: set[str] = set()
    for row in data:
        if not isinstance(row, dict):
            continue
        kp, day = _f(row.get("kp")), str(row.get("time_tag") or "")[:10]
        if kp is None or len(day) != 10:
            continue
        largest[day] = max(largest.get(day, kp), kp)
        intervals[day] = intervals.get(day, 0) + 1
        if row.get("observed") != "observed":
            ahead.add(day)
    return {"issued": None, "days": {d: {"kp": round(largest[d], 2)}
                                     for d in sorted(ahead) if intervals[d] >= 6}}


_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def _outlook_date(year, month, day) -> str:
    return f"{int(year):04d}-{_MONTHS[month[:3].lower()]:02d}-{int(day):02d}"


def parse_outlook_27d(raw: bytes) -> dict:
    """NOAA's 27-day outlook (text, issued weekly): per UTC day the 10.7 cm radio flux,
    the planetary A index and the largest Kp, from rows like ``2026 Oct 12  120  16  4``
    under an ``:Issued: 2026 Oct 12 0345 UTC`` line."""
    issued, days = None, {}
    for line in raw.decode("utf-8", "replace").splitlines():
        parts = line.split()
        try:
            if line.startswith(":Issued:") and len(parts) >= 5:
                issued = _outlook_date(*parts[1:4])
            elif len(parts) == 6 and parts[0].isdigit() and parts[1][:3].lower() in _MONTHS:
                days[_outlook_date(*parts[:3])] = {
                    "f107": float(parts[3]), "ap": float(parts[4]), "kp": float(parts[5])}
        except (ValueError, KeyError):
            continue
    return {"issued": issued, "days": days}
