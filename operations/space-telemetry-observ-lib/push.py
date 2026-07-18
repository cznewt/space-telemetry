#!/usr/bin/env python3
"""Push rendered observ-viz v2 Dashboard resources (dashboards/*.json) to Grafana
via the app-platform (kubernetes-style) API. Mirrors observ-viz scripts/load.py
but takes the already-rendered JSON, so it needs only the stdlib.

Usage:  python3 push.py dashboards/*.json
Env:    GRAFANA_URL        (e.g. http://10.13.13.9:3000)
        GRAFANA_TOKEN      (Grafana service-account token, glsa_...)
        GRAFANA_NAMESPACE  (default 'default'; the org/stack namespace)
"""
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("GRAFANA_URL", "http://localhost:3000").rstrip("/")
TOKEN = os.environ.get("GRAFANA_TOKEN")
NS = os.environ.get("GRAFANA_NAMESPACE", "default")
API = f"{URL}/apis/dashboard.grafana.app/v2beta1/namespaces/{NS}/dashboards"


def req(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if TOKEN:
        r.add_header("Authorization", "Bearer " + TOKEN)
    r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


_folders_done = set()


def ensure_folder(uid, title=None, parent_uid=None):
    """Create/update a Grafana folder (idempotent); nest under parent_uid if given."""
    if not uid or uid in _folders_done:
        return
    t = title or uid.replace("-", " ").title()
    body = {"uid": uid, "title": t}
    if parent_uid:
        body["parentUid"] = parent_uid
    status, _ = req("POST", f"{URL}/api/folders", body)
    if status >= 400:  # already exists -> update title
        req("PUT", f"{URL}/api/folders/{uid}", {"title": t, "overwrite": True})
    if parent_uid:  # ensure nesting (idempotent)
        req("POST", f"{URL}/api/folders/{uid}/move", {"parentUid": parent_uid})
    _folders_done.add(uid)


def push(path):
    doc = json.load(open(path))
    doc.setdefault("metadata", {})["namespace"] = NS
    name = doc["metadata"]["name"]
    anns = doc["metadata"].get("annotations", {})
    folder = anns.get("grafana.app/folder")
    # observ-viz.dev/* are placement hints, not real Grafana annotations -> strip.
    title = anns.pop("observ-viz.dev/folder-title", None)
    parent_uid = anns.pop("observ-viz.dev/folder-parent-uid", None)
    parent_title = anns.pop("observ-viz.dev/folder-parent-title", None)
    if parent_uid:
        ensure_folder(parent_uid, parent_title)
    if folder:
        ensure_folder(folder, title, parent_uid)
    status, body = req("POST", API, doc)
    if status == 409:  # exists -> replace
        req("DELETE", f"{API}/{name}", None)
        status, body = req("POST", API, doc)
    if 200 <= status < 300:
        print(f"  OK   {name} -> {URL}/d/{name}")
        return 0
    print(f"  FAIL {name} (HTTP {status}): {body.decode()[:300]}")
    return 1


def main(argv):
    if not TOKEN:
        print("GRAFANA_TOKEN is not set (put it in .env or the environment).", file=sys.stderr)
        return 2
    print(f"Pushing {len(argv)} dashboard(s) to {API}")
    return max((push(p) for p in argv), default=0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
