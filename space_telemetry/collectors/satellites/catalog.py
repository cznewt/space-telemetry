"""Merge cached CelesTrak orbits + SatNOGS data into a Catalog.

Join key is the NORAD catalog number. A satellite that appears in several
CelesTrak groups accumulates all of them (used for tracked-set selection).
"""

from __future__ import annotations

from time import time

from .model import Catalog, Satellite
from .sources import celestrak, satnogs


def build_catalog(cache, settings, ts) -> Catalog:
    sats: dict[int, Satellite] = {}
    fmt = settings.celestrak_format

    for group in settings.sat_groups:
        raw = cache.read(celestrak.filename(group, fmt))
        if not raw:
            continue
        for norad, name, earthsat in celestrak.parse(raw, fmt, ts):
            sat = sats.get(norad)
            if sat is None:
                sat = Satellite(norad_id=norad, name=name, earthsat=earthsat)
                sats[norad] = sat
            sat.groups.add(group)

    meta_raw = cache.read("satnogs_satellites.json")
    metadata = satnogs.parse_satellites(meta_raw) if meta_raw else {}
    tx_raw = cache.read("satnogs_transmitters.json")
    transmitters = satnogs.parse_transmitters(tx_raw) if tx_raw else {}

    for norad, sat in sats.items():
        info = metadata.get(norad)
        if info:
            sat.status = info.get("status")
            if info.get("name") and sat.name.startswith("CATNR-"):
                sat.name = info["name"]
        sat.transmitters = transmitters.get(norad, [])

    return Catalog(satellites=sats, built_at=time())
