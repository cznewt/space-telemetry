"""SatNOGS DB source: URLs + parsing of transmitters and satellite metadata.

Endpoints:
    https://db.satnogs.org/api/transmitters/?format=json
    https://db.satnogs.org/api/satellites/?format=json

Transmitters carry downlink/uplink frequency, mode, baud and status; they join to
CelesTrak orbits on the NORAD catalog number (``norad_cat_id``).
"""

from __future__ import annotations

import json
from typing import Optional

from ..model import Transmitter

SATNOGS_DB_URL = "https://db.satnogs.org/api"
TRANSMITTERS_URL = f"{SATNOGS_DB_URL}/transmitters/?format=json"
SATELLITES_URL = f"{SATNOGS_DB_URL}/satellites/?format=json"


def _items(text: str):
    data = json.loads(text)
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


def _to_float(value) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_transmitters(raw: bytes) -> dict[int, list[Transmitter]]:
    out: dict[int, list[Transmitter]] = {}
    for t in _items(raw.decode("utf-8", "replace")):
        norad = t.get("norad_cat_id")
        if norad is None:
            continue
        status = t.get("status") or ("active" if t.get("alive") else "inactive")
        out.setdefault(int(norad), []).append(Transmitter(
            uuid=t.get("uuid", ""),
            description=t.get("description", ""),
            mode=t.get("mode"),
            status=status,
            downlink_hz=_to_float(t.get("downlink_low")),
            uplink_hz=_to_float(t.get("uplink_low")),
            baud=_to_float(t.get("baud")),
        ))
    return out


def parse_satellites(raw: bytes) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for s in _items(raw.decode("utf-8", "replace")):
        norad = s.get("norad_cat_id")
        if norad is None:
            continue
        out[int(norad)] = {"name": s.get("name"), "status": s.get("status")}
    return out
