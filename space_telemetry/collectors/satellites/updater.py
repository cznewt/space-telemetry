"""Background refresh scheduler for satellite data (offline-first).

A daemon thread refreshes each source when it is *due* (TLE every few hours,
transmitters/metadata weekly), writes it to the offline cache with a conditional
request, and rebuilds the catalog. Failures keep the last-good cache. ``collect()``
never blocks on this thread — it only reads the current catalog + health.
"""

from __future__ import annotations

import threading
from time import time
from typing import Optional

from ...cache import FileCache
from ...http_util import conditional_get
from .catalog import build_catalog
from .model import CatalogHolder, SourceHealth
from .sources import celestrak, satnogs


class SatelliteUpdater:
    def __init__(self, settings, cache: FileCache, holder: CatalogHolder, ts, tick_s: float = 60.0):
        self.settings = settings
        self.cache = cache
        self.holder = holder
        self.ts = ts
        self._tick_s = tick_s
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._errors: dict[str, Optional[str]] = {}

    def _sources(self):
        """(key, url, filename, refresh_hours) for every configured source."""
        fmt = self.settings.celestrak_format
        items = [
            (f"celestrak:{g}", celestrak.gp_url(g, fmt), celestrak.filename(g, fmt),
             self.settings.tle_refresh_hours)
            for g in self.settings.sat_groups
        ]
        items.append(("satnogs:transmitters", satnogs.TRANSMITTERS_URL,
                      "satnogs_transmitters.json", self.settings.transmitter_refresh_hours))
        items.append(("satnogs:satellites", satnogs.SATELLITES_URL,
                      "satnogs_satellites.json", self.settings.satnogs_satellites_refresh_hours))
        return items

    # --- lifecycle ---
    def bootstrap(self) -> None:
        """Build the catalog from whatever is already cached (no network)."""
        self._rebuild()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="sat-updater", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while True:
            try:
                self._refresh_due()
            except Exception as exc:  # never let the updater thread die
                print(f"[sat-updater] cycle error: {exc}", flush=True)
            if self._stop.wait(self._tick_s):
                break

    # --- refresh ---
    def _due(self, key, hours) -> bool:
        last = self.cache.meta_get(key).get("last_success_ts")
        return last is None or (time() - last) >= hours * 3600.0

    def _refresh_due(self) -> None:
        # Rebuild after each source lands so orbits (small, fast) show up without
        # waiting for the large SatNOGS transmitter download on a cold cache.
        for key, url, filename, hours in self._sources():
            if self._due(key, hours) and self._fetch(key, url, filename):
                self._rebuild()

    def _fetch(self, key, url, filename) -> bool:
        meta = self.cache.meta_get(key)
        t0 = time()
        try:
            res = conditional_get(url, meta.get("etag"), meta.get("last_modified"),
                                  self.settings.user_agent, self.settings.http_timeout_s)
        except Exception as exc:
            self._errors[key] = str(exc)
            self.cache.meta_set(key, {"last_status": 0, "success": False})
            print(f"[sat-updater] {key} fetch failed: {exc}", flush=True)
            return False

        duration = time() - t0
        self._errors[key] = None
        if res.not_modified:
            self.cache.meta_set(key, {"last_success_ts": time(), "last_status": 304,
                                      "fetch_duration_s": duration, "success": True})
            return False

        self.cache.write_atomic(filename, res.data)
        self.cache.meta_set(key, {"file": filename, "last_success_ts": time(),
                                  "last_status": res.status, "etag": res.etag,
                                  "last_modified": res.last_modified, "bytes": len(res.data),
                                  "fetch_duration_s": duration, "success": True})
        print(f"[sat-updater] {key}: {len(res.data)} bytes", flush=True)
        return True

    def _rebuild(self) -> None:
        try:
            self.holder.set(build_catalog(self.cache, self.settings, self.ts))
        except Exception as exc:
            print(f"[sat-updater] catalog build failed: {exc}", flush=True)

    # --- health (read by the collector) ---
    def health(self) -> list[SourceHealth]:
        now = time()
        out = []
        for key, _url, _file, _hours in self._sources():
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
