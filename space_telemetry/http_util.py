"""Minimal conditional HTTP GET using the standard library (no extra deps).

Sends If-None-Match / If-Modified-Since so unchanged sources come back as 304 and
we keep serving the cached copy — polite to CelesTrak/SatNOGS and offline-first.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional


@dataclass
class FetchResult:
    status: int
    data: Optional[bytes]
    etag: Optional[str]
    last_modified: Optional[str]
    not_modified: bool


def conditional_get(url, etag=None, last_modified=None,
                    user_agent="space-telemetry", timeout=30.0) -> FetchResult:
    headers = {"User-Agent": user_agent, "Accept-Encoding": "identity"}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            return FetchResult(getattr(resp, "status", 200), data,
                               resp.headers.get("ETag"), resp.headers.get("Last-Modified"), False)
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return FetchResult(304, None, etag, last_modified, True)
        raise
