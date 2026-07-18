"""Offline file cache: atomic writes + per-key metadata, namespaced under cache_dir.

Used by every networked collector (satellites, swpc). ``meta.json`` records, per
source key, the last-success time, HTTP status, and the ETag/Last-Modified used
for conditional requests. A failed refresh never deletes the last-good payload,
so scrapes stay offline-first.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional


class FileCache:
    def __init__(self, base_dir, namespace: str = ""):
        self.dir = Path(base_dir) / namespace if namespace else Path(base_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._meta_path = self.dir / "meta.json"
        self._meta = self._load_meta()

    def _load_meta(self) -> dict:
        try:
            return json.loads(self._meta_path.read_text())
        except (FileNotFoundError, ValueError):
            return {}

    def read(self, filename: str) -> Optional[bytes]:
        try:
            return (self.dir / filename).read_bytes()
        except FileNotFoundError:
            return None

    def write_atomic(self, filename: str, data: bytes) -> None:
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, self.dir / filename)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def meta_get(self, key: str) -> dict:
        return dict(self._meta.get(key, {}))

    def meta_set(self, key: str, patch: dict) -> None:
        self._meta.setdefault(key, {}).update(patch)
        self.write_atomic("meta.json", json.dumps(self._meta, indent=2).encode())
