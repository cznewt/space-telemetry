"""NOAA SWPC products: URLs + parsers that extract the latest value(s).

Each parser takes the raw JSON bytes and returns ``{metric_name: float}`` for the
most recent observation, skipping any null fields. All these products are a JSON
list; the latest observation is the last element.
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
