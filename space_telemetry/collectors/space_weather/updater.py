"""Background refresh for NOAA space-weather products (offline-first).

A daemon thread refreshes each product when it is *due* (every
``space_weather_refresh_minutes``) via a conditional request, caches the raw JSON,
and parses the latest value(s) into an in-memory snapshot that the collector reads.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from time import time
from typing import Optional

from ...cache import FileCache
from ...http_util import conditional_get
from . import source


@dataclass
class SourceHealth:
    source: str
    success: bool
    last_success_ts: Optional[float]
    last_status: Optional[int]
    age_s: Optional[float]
    fetch_duration_s: Optional[float]
    error: Optional[str]


class SpaceWeatherUpdater:
    def __init__(self, settings, cache: FileCache, tick_s: float = 60.0):
        self.settings = settings
        self.cache = cache
        self._tick_s = tick_s
        self._products = source.products()
        self._latest: dict[str, float] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._errors: dict[str, Optional[str]] = {}

    def product_keys(self) -> list:
        return [key for key, _url, _file, _parser in self._products]

    # --- lifecycle ---
    def bootstrap(self) -> None:
        """Parse whatever is already cached into the latest snapshot (no network)."""
        for key, _url, filename, parser in self._products:
            self._parse_into_latest(key, filename, parser)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="space-weather-updater", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while True:
            try:
                self._refresh_due()
            except Exception as exc:
                print(f"[space-weather-updater] cycle error: {exc}", flush=True)
            if self._stop.wait(self._tick_s):
                break

    # --- refresh ---
    def _due(self, key) -> bool:
        last = self.cache.meta_get(key).get("last_success_ts")
        return last is None or (time() - last) >= self.settings.space_weather_refresh_minutes * 60.0

    def _refresh_due(self) -> None:
        for key, url, filename, parser in self._products:
            if self._due(key):
                self._fetch(key, url, filename, parser)

    def _fetch(self, key, url, filename, parser) -> None:
        meta = self.cache.meta_get(key)
        t0 = time()
        try:
            res = conditional_get(url, meta.get("etag"), meta.get("last_modified"),
                                  self.settings.user_agent, self.settings.http_timeout_s)
        except Exception as exc:
            self._errors[key] = str(exc)
            self.cache.meta_set(key, {"last_status": 0, "success": False})
            print(f"[space-weather-updater] {key} fetch failed: {exc}", flush=True)
            return

        duration = time() - t0
        self._errors[key] = None
        if res.not_modified:
            self.cache.meta_set(key, {"last_success_ts": time(), "last_status": 304,
                                      "fetch_duration_s": duration, "success": True})
            return

        self.cache.write_atomic(filename, res.data)
        self.cache.meta_set(key, {"file": filename, "last_success_ts": time(),
                                  "last_status": res.status, "etag": res.etag,
                                  "last_modified": res.last_modified, "bytes": len(res.data),
                                  "fetch_duration_s": duration, "success": True})
        self._parse_into_latest(key, filename, parser)
        print(f"[space-weather-updater] {key}: {len(res.data)} bytes", flush=True)

    def _parse_into_latest(self, key, filename, parser) -> None:
        raw = self.cache.read(filename)
        if not raw:
            return
        try:
            values = parser(raw)
        except Exception as exc:
            print(f"[space-weather-updater] {key} parse failed: {exc}", flush=True)
            return
        with self._lock:
            self._latest.update(values)

    # --- read by the collector ---
    def latest(self) -> dict:
        with self._lock:
            return dict(self._latest)

    def health(self) -> list:
        now = time()
        out = []
        for key, _url, _file, _parser in self._products:
            m = self.cache.meta_get(key)
            last = m.get("last_success_ts")
            out.append(SourceHealth(
                source=key,
                success=bool(m.get("success")),
                last_success_ts=last,
                last_status=m.get("last_status"),
                age_s=(now - last) if last else None,
                fetch_duration_s=m.get("fetch_duration_s"),
                error=self._errors.get(key),
            ))
        return out
