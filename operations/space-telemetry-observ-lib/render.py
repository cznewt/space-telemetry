#!/usr/bin/env python3
"""Render this observ-lib into dashboards/ alerts/ rules/, and inject the signals
table into README.md + the collector doc pages (between <!-- signals:start/end -->).

Runs inside the observ-viz image (ghcr.io/cznewt/observ-lib), which has observ-viz
on the jpath, so no local jsonnet/jb is needed. Invoke from the repo root with:

    just observ-lib-build

Mounts the repo root so it can update ../../docs/collectors/*.md as well.
"""
import json
import os

import _jsonnet
import yaml

_SNIP = """
local lib = (import 'main.libsonnet').new({});
local sigs = lib.config.signals.space_telemetry;
local dbs = if std.objectHas(lib.grafana, 'dashboards') then lib.grafana.dashboards
  else { [lib.config.uid + '.json']: lib.grafana.dashboard };
{
  dashboards: { [k]: dbs[k].toResource() for k in std.objectFields(dbs) },
  alerts: (if std.objectHas(lib, 'prometheus') then lib.prometheus.alerts else []),
  rules: (if std.objectHas(lib, 'prometheus') && std.objectHas(lib.prometheus, 'rules')
    then lib.prometheus.rules else []),
  // The rendered PromQL query behind each signal.
  signals: { [k]: sigs[k].asTarget().spec.query.spec.expr for k in std.objectFields(sigs) },
}
"""

# signal key -> (display name, unit, group). The query comes from the jsonnet.
SIGNAL_META = {
    'up': ('Exporter up', 'short', 'Health'),
    'scrapeDuration': ('Scrape duration', 's', 'Health'),
    'bodyAltitude': ('Body altitude', 'degree', 'Solar-system bodies'),
    'bodiesUp': ('Bodies above horizon', 'short', 'Solar-system bodies'),
    'moonIllum': ('Moon illuminated', 'percentunit', 'Solar-system bodies'),
    'moonPhase': ('Moon phase', 'degree', 'Solar-system bodies'),
    'starAltitude': ('Star altitude', 'degree', 'Celestial bodies'),
    'trackedCount': ('Satellites tracked', 'short', 'Satellites'),
    'satElevation': ('Satellite elevation', 'degree', 'Satellites'),
    'satAltitude': ('Satellite altitude', 'lengthm', 'Satellites'),
    'tleAge': ('TLE age', 's', 'Satellites'),
    'nextPassMaxEl': ('Next pass max elevation', 'degree', 'Satellites'),
    'satSourcesOk': ('Satellite sources healthy', 'short', 'Satellites'),
    'kp': ('Planetary Kp', 'short', 'Space weather'),
    'solarWind': ('Solar wind speed', 'short', 'Space weather'),
    'imfBz': ('IMF Bz', 'short', 'Space weather'),
    'xray': ('GOES X-ray flux', 'short', 'Space weather'),
    'f107': ('F10.7 flux', 'short', 'Space weather'),
}
GROUP_ORDER = ['Solar-system bodies', 'Celestial bodies', 'Satellites', 'Space weather', 'Health']
# group -> collector doc page (relative to repo root); groups not listed go to the README only.
GROUP_PAGE = {
    'Solar-system bodies': 'docs/collectors/solar_system_bodies.md',
    'Celestial bodies': 'docs/collectors/celestial_bodies.md',
    'Satellites': 'docs/collectors/satellites.md',
    'Space weather': 'docs/collectors/space_weather.md',
}
START, END = '<!-- signals:start -->', '<!-- signals:end -->'


def _table(keys, exprs):
    out = ['| Signal | Query | Unit |', '|---|---|---|']
    for k in keys:
        name, unit, _g = SIGNAL_META[k]
        out.append('| %s | `%s` | %s |' % (name, exprs[k], unit))
    return '\n'.join(out)


def _group_keys(group, exprs):
    return [k for k in SIGNAL_META
            if SIGNAL_META[k][2] == group and k in exprs]


def inject(path, block):
    try:
        with open(path) as fh:
            txt = fh.read()
    except FileNotFoundError:
        print('  skip (missing):', path)
        return
    if START not in txt or END not in txt:
        print('  skip (no markers):', path)
        return
    head, _, rest = txt.partition(START)
    _, _, tail = rest.partition(END)
    with open(path, 'w') as fh:
        fh.write(head + START + '\n' + block + '\n' + END + tail)
    print('  signals ->', path)


def main():
    m = json.loads(_jsonnet.evaluate_snippet('render', _SNIP, jpathdir=['/observ-viz', '.']))

    os.makedirs('dashboards', exist_ok=True)
    for name, d in m['dashboards'].items():
        fn = name if name.endswith('.json') else name + '.json'
        with open(os.path.join('dashboards', fn), 'w') as fh:
            json.dump(d, fh, indent=2, sort_keys=True)
    write_groups(m['alerts'], 'alerts')
    write_groups(m['rules'], 'rules')
    print('dashboards:', list(m['dashboards']))
    print('alerts:', [g['name'] for g in m['alerts']])
    print('rules:', [g['name'] for g in m['rules']])

    exprs = m['signals']
    repo = os.path.abspath(os.path.join(os.getcwd(), '..', '..'))

    # Full table (all groups) into the observ-lib README and the repo README.
    full = '\n\n'.join(
        '#### %s\n\n%s' % (g, _table(_group_keys(g, exprs), exprs))
        for g in GROUP_ORDER if _group_keys(g, exprs)
    )
    inject('README.md', full)
    inject(os.path.join(repo, 'README.md'), full)

    # Per-collector table into each collector doc page.
    for group, page in GROUP_PAGE.items():
        keys = _group_keys(group, exprs)
        if keys:
            inject(os.path.join(repo, page), _table(keys, exprs))


def write_groups(groups, outdir):
    os.makedirs(outdir, exist_ok=True)
    for g in groups:
        with open(os.path.join(outdir, g['name'].replace('/', '_') + '.yaml'), 'w') as fh:
            yaml.safe_dump({'groups': [g]}, fh, sort_keys=False, default_flow_style=False)


if __name__ == '__main__':
    main()
