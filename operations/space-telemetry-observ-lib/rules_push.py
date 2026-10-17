#!/usr/bin/env python3
"""Load rendered rule groups (alerts/*.yaml, rules/*.yaml) into the Mimir ruler
through Grafana's data-source ruler API, with the same service-account token as
push.py (it needs alert.rules.external:write). Each group is upserted by name into
one ruler namespace; groups that are not in the given files are left alone.

Usage:  python3 rules_push.py alerts/*.yaml rules/*.yaml
Env:    GRAFANA_URL, GRAFANA_TOKEN
        RULER_DATASOURCE_UID  (default 'newt-mimir', the Mimir datasource in Grafana)
        RULER_NAMESPACE       (default 'space-telemetry')
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import yaml

URL = os.environ.get("GRAFANA_URL", "http://localhost:3000").rstrip("/")
TOKEN = os.environ.get("GRAFANA_TOKEN")
DS = os.environ.get("RULER_DATASOURCE_UID", "newt-mimir")
NS = os.environ.get("RULER_NAMESPACE", "space-telemetry")
API = f"{URL}/api/ruler/{DS}/api/v1/rules/{urllib.parse.quote(NS, safe='')}"


def push_group(group) -> int:
    r = urllib.request.Request(API, data=json.dumps(group).encode(), method="POST")
    if TOKEN:
        r.add_header("Authorization", "Bearer " + TOKEN)
    r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r) as resp:
            status, body = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read()
    if 200 <= status < 300:
        print(f"  OK   {NS}/{group['name']} ({len(group['rules'])} rules)")
        return 0
    print(f"  FAIL {NS}/{group['name']} (HTTP {status}): {body.decode()[:300]}")
    return 1


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    failed = 0
    for path in argv:
        with open(path) as fh:
            for group in (yaml.safe_load(fh) or {}).get("groups", []):
                failed += push_group(group)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
