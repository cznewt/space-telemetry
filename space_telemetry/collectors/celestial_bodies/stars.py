"""Bright-star catalog backed by the HYG database (vendored subset, magnitude ≤ 6.5).

Source: HYG v4.4 — https://codeberg.org/astronexus/hyg (CC BY-SA 4.0). The vendored CSV
keeps a stable id, a display name (proper name, else Bayer/Flamsteed + constellation,
else a catalog designation), the ICRS/J2000 position (RA hours, Dec degrees), apparent
visual magnitude, distance in light-years, spectral type and 3-letter constellation.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

_CSV = Path(__file__).with_name("data") / "hyg_bright.csv"


@lru_cache(maxsize=1)
def load_catalog() -> list:
    """``[(id, name, ra_hours, dec_deg, mag, dist_ly, spect, con)]`` — brightest first,
    deduplicated by display name (the name is a metric label, so it must be unique; the
    CSV is magnitude-sorted, so the first/brightest of a shared name wins)."""
    out: list = []
    seen: set = set()
    with open(_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["name"] in seen:
                continue
            seen.add(r["name"])
            out.append((
                r["id"], r["name"], float(r["ra"]), float(r["dec"]), float(r["mag"]),
                float(r["dist_ly"]) if r["dist_ly"] else None,
                r["spect"], r["con"],
            ))
    return out


def tracked_stars(max_magnitude: float, names=None) -> list:
    """Catalog entries with magnitude ≤ ``max_magnitude``, plus any whose display name is
    in ``names`` (case-insensitive) so explicitly-named fainter stars are kept as well."""
    want = {n.lower() for n in (names or [])}
    return [s for s in load_catalog() if s[4] <= max_magnitude or s[1].lower() in want]


def magnitude(name: str) -> "float | None":
    lo = name.lower()
    for s in load_catalog():
        if s[1].lower() == lo:
            return s[4]
    return None
