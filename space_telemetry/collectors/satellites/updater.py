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
        """(key, url, filename, refresh_hours, check) for every configured source.
        ``check(raw)`` returns why a 200 reply is unusable, or None (None = no check)."""
        fmt = self.settings.celestrak_format
        check = lambda raw: celestrak.problem(raw, fmt)  # noqa: E731
        items = [
            (f"celestrak:{g}", celestrak.gp_url(g, fmt), celestrak.filename(g, fmt),
             self.settings.tle_refresh_hours, check)
            for g in self.settings.sat_groups
        ]
        # Watchlist/focus ids are fetched one by one too, so they are tracked even
        # when they sit outside every configured group (one tiny request each).
        for norad in sorted(set(self.settings.sat_watchlist) | set(self.settings.sat_focus)):
            items.append((f"celestrak:catnr:{norad}", celestrak.catnr_url(norad, fmt),
                          celestrak.catnr_filename(norad, fmt), self.settings.tle_refresh_hours, check))
        items.append(("satnogs:transmitters", satnogs.TRANSMITTERS_URL,
                      "satnogs_transmitters.json", self.settings.transmitter_refresh_hours, None))
        items.append(("satnogs:satellites", satnogs.SATELLITES_URL,
                      "satnogs_satellites.json", self.settings.satnogs_satellites_refresh_hours, None))
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
        meta = self.cache.meta_get(key)
        now = time()
        last = meta.get("last_success_ts")
        if last is not None and now - last < hours * 3600.0:
            return False
        # A source whose last reply was rejected (e.g. an unknown CelesTrak group)
        # is retried at most hourly, not every tick, so a bad group can't hammer it.
        rejected = meta.get("rejected_ts")
        return rejected is None or now - rejected >= min(hours, 1.0) * 3600.0

    def _refresh_due(self) -> None:
        # Rebuild after each source lands so orbits (small, fast) show up without
        # waiting for the large SatNOGS transmitter download on a cold cache.
        for key, url, filename, hours, check in self._sources():
            if self._due(key, hours) and self._fetch(key, url, filename, check):
                self._rebuild()

    def _fetch(self, key, url, filename, check=None) -> bool:
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
        # A 304 vouches for the cached copy, which may predate reply checks.
        payload = (self.cache.read(filename) or b"") if res.not_modified else res.data
        reason = check(payload) if check else None
        if reason:  # a reply that carries no data: keep the last-good cache, report failure
            self._errors[key] = reason
            # drop the validators so the retry is a full GET, not a 304 for the same reply
            self.cache.meta_set(key, {"last_status": res.status, "rejected_ts": time(),
                                      "fetch_duration_s": duration, "success": False,
                                      "etag": None, "last_modified": None})
            print(f"[sat-updater] {key} rejected reply: {reason}", flush=True)
            return False

        if res.not_modified:
            self.cache.meta_set(key, {"last_success_ts": time(), "last_status": 304,
                                      "fetch_duration_s": duration, "success": True})
            return False

        self.cache.write_atomic(filename, res.data)
        self.cache.meta_set(key, {"file": filename, "last_success_ts": time(),
                                  "last_status": res.status, "etag": res.etag,
                                  "last_modified": res.last_modified, "bytes": len(res.data),
                                  "fetch_duration_s": duration, "success": True,
                                  "rejected_ts": None})
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
        for key, _url, _file, _hours, _check in self._sources():
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
