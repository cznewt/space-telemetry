"""CelesTrak GP source: URL building + parsing of TLE and OMM/JSON element sets.

Endpoint:
    https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT={tle|json}

Etiquette (enforced by the updater): conditional requests, a real User-Agent, and
refreshing only a few times per day. Scrapes are served from the on-disk cache.
"""

from __future__ import annotations

import json
from typing import Iterator

CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"


def gp_url(group: str, fmt: str = "tle") -> str:
    return f"{CELESTRAK_GP_URL}?GROUP={group}&FORMAT={fmt}"


def filename(group: str, fmt: str) -> str:
    return f"celestrak_{group}.{'json' if fmt == 'json' else 'tle'}"


def parse(raw: bytes, fmt: str, ts) -> Iterator[tuple[int, str, object]]:
    """Yield ``(norad_id, name, EarthSatellite)`` for each element set."""
    text = raw.decode("utf-8", "replace")
    if fmt == "json":
        yield from _parse_omm_json(text, ts)
    else:
        yield from _parse_tle(text, ts)


def _parse_tle(text, ts):
    from skyfield.api import EarthSatellite

    lines = [ln.rstrip("\r\n") for ln in text.splitlines() if ln.strip()]
    n = len(lines)
    i = 0
    while i + 1 < n:
        if lines[i].startswith("1 ") and lines[i + 1].startswith("2 "):
            name = f"CATNR-{lines[i][2:7].strip()}"
            l1, l2 = lines[i], lines[i + 1]
            i += 2
        elif i + 2 < n and lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 "):
            name, l1, l2 = lines[i].strip(), lines[i + 1], lines[i + 2]
            i += 3
        else:
            i += 1
            continue
        try:
            norad = int(l2[2:7])
            yield norad, name, EarthSatellite(l1, l2, name, ts)
        except Exception:
            continue


def _parse_omm_json(text, ts):
    from sgp4 import omm
    from sgp4.api import Satrec
    from skyfield.api import EarthSatellite

    for fields in json.loads(text):
        try:
            satrec = Satrec()
            omm.initialize(satrec, fields)
            es = EarthSatellite.from_satrec(satrec, ts)
            name = fields.get("OBJECT_NAME") or f"CATNR-{fields.get('NORAD_CAT_ID')}"
            es.name = name
            yield int(fields["NORAD_CAT_ID"]), name, es
        except Exception:
            continue
