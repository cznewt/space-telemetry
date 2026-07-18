#!/usr/bin/env python3
"""Render this observ-lib into dashboards/ alerts/ rules/.

Runs inside the observ-viz image (ghcr.io/cznewt/observ-lib), which has observ-viz
on the jpath, so no local jsonnet/jb is needed. Invoke from the repo root with:

    just observ-lib-build

Mirrors observ-viz's own render-lib, but for this lib's local main.libsonnet.
"""
import json
import os

import _jsonnet
import yaml

_SNIP = """
local lib = (import 'main.libsonnet').new({});
local dbs = if std.objectHas(lib.grafana, 'dashboards') then lib.grafana.dashboards
  else { [lib.config.uid + '.json']: lib.grafana.dashboard };
{
  dashboards: { [k]: dbs[k].toResource() for k in std.objectFields(dbs) },
  alerts: (if std.objectHas(lib, 'prometheus') then lib.prometheus.alerts else []),
  rules: (if std.objectHas(lib, 'prometheus') && std.objectHas(lib.prometheus, 'rules')
    then lib.prometheus.rules else []),
}
"""


def write_groups(groups, outdir):
    os.makedirs(outdir, exist_ok=True)
    for g in groups:
        with open(os.path.join(outdir, g["name"].replace("/", "_") + ".yaml"), "w") as fh:
            yaml.safe_dump({"groups": [g]}, fh, sort_keys=False, default_flow_style=False)


def main():
    m = json.loads(_jsonnet.evaluate_snippet("render", _SNIP, jpathdir=["/observ-viz", "."]))
    os.makedirs("dashboards", exist_ok=True)
    for name, d in m["dashboards"].items():
        fn = name if name.endswith(".json") else name + ".json"
        with open(os.path.join("dashboards", fn), "w") as fh:
            json.dump(d, fh, indent=2, sort_keys=True)
    write_groups(m["alerts"], "alerts")
    write_groups(m["rules"], "rules")
    print("dashboards:", list(m["dashboards"]))
    print("alerts:", [g["name"] for g in m["alerts"]])
    print("rules:", [g["name"] for g in m["rules"]])


if __name__ == "__main__":
    main()
