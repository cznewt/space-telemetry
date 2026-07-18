#!/usr/bin/env python3
"""Render signals.yaml into the docs "Signals" tables.

Injects a per-collector signals table (name, description, unit, range, labels; ★ =
on the observ-lib dashboard) between <!-- signals:start/end --> markers in each
docs/collectors/<collector>.md, and the full catalog into README.md.

Run from anywhere:  python3 scripts/render_signals.py   (needs pyyaml)
Or:  just signals-build
"""
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "signals.yaml")

COLLECTOR_ORDER = ["solar_system_bodies", "celestial_bodies", "satellites", "space_weather"]
COLLECTOR_TITLE = {
    "solar_system_bodies": "Solar-system bodies",
    "celestial_bodies": "Celestial bodies",
    "satellites": "Satellites",
    "space_weather": "Space weather",
}
COLLECTOR_PAGE = {
    "solar_system_bodies": "docs/collectors/solar_system_bodies.md",
    "celestial_bodies": "docs/collectors/celestial_bodies.md",
    "satellites": "docs/collectors/satellites.md",
    "space_weather": "docs/collectors/space_weather.md",
}
START, END = "<!-- signals:start -->", "<!-- signals:end -->"


def _row(s):
    star = " ★" if s.get("dashboard") else ""
    labels = ", ".join("`%s`" % lbl for lbl in (s.get("labels") or [])) or "—"
    return "| `%s`%s | %s | %s | %s | %s |" % (
        s["name"], star, s["description"], s.get("unit", ""), s.get("range", ""), labels)


def _table(rows):
    head = ["| Signal | Description | Unit | Range | Labels |", "|---|---|---|---|---|"]
    return "\n".join(head + [_row(s) for s in rows])


def inject(path, block):
    with open(path) as fh:
        txt = fh.read()
    if START not in txt or END not in txt:
        print("  skip (no markers):", os.path.relpath(path, ROOT))
        return
    head, _, rest = txt.partition(START)
    _, _, tail = rest.partition(END)
    with open(path, "w") as fh:
        fh.write(head + START + "\n" + block + "\n" + END + tail)
    print("  signals ->", os.path.relpath(path, ROOT))


def main():
    with open(CATALOG) as fh:
        catalog = yaml.safe_load(fh)["signals"]
    by_collector = {}
    for s in catalog:
        by_collector.setdefault(s["collector"], []).append(s)

    # Per-collector table into each collector doc page.
    for collector in COLLECTOR_ORDER:
        rows = by_collector.get(collector, [])
        if rows and collector in COLLECTOR_PAGE:
            block = "★ = on the observ-lib dashboard/alerts.\n\n" + _table(rows)
            inject(os.path.join(ROOT, COLLECTOR_PAGE[collector]), block)

    # Full catalog (grouped by collector) into the repo README.
    parts = ["★ = built into the [observ-lib](operations/space-telemetry-observ-lib/) dashboard/alerts."]
    for collector in COLLECTOR_ORDER:
        rows = by_collector.get(collector, [])
        if rows:
            parts.append("#### %s\n\n%s" % (COLLECTOR_TITLE[collector], _table(rows)))
    inject(os.path.join(ROOT, "README.md"), "\n\n".join(parts))


if __name__ == "__main__":
    main()
