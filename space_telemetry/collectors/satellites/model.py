"""Data model for the satellites family."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Optional


@dataclass
class Transmitter:
    uuid: str
    description: str
    mode: Optional[str]
    status: Optional[str]
    downlink_hz: Optional[float]
    uplink_hz: Optional[float]
    baud: Optional[float]


@dataclass
class Satellite:
    norad_id: int
    name: str
    earthsat: object                       # skyfield EarthSatellite (built once at catalog time)
    groups: set[str] = field(default_factory=set)
    status: Optional[str] = None
    transmitters: list[Transmitter] = field(default_factory=list)

    @property
    def epoch_ts(self) -> float:
        return self.earthsat.epoch.utc_datetime().timestamp()


@dataclass
class Catalog:
    satellites: dict[int, Satellite] = field(default_factory=dict)
    built_at: float = 0.0

    def stats(self) -> tuple[int, int]:
        total = len(self.satellites)
        with_tx = sum(1 for s in self.satellites.values() if s.transmitters)
        return total, with_tx


EMPTY_CATALOG = Catalog()


class CatalogHolder:
    """Thread-safe handoff: the updater swaps in a fresh catalog, scrapes read it."""

    def __init__(self):
        self._lock = Lock()
        self._catalog = EMPTY_CATALOG

    def get(self) -> Catalog:
        with self._lock:
            return self._catalog

    def set(self, catalog: Catalog) -> None:
        with self._lock:
            self._catalog = catalog


@dataclass
class SatelliteState:
    norad_id: int
    name: str
    elevation_deg: float
    azimuth_deg: float
    range_m: float
    range_rate_m_s: float
    subpoint_lat_deg: float
    subpoint_lon_deg: float
    altitude_m: float
    velocity_m_s: float
    above_horizon: bool
    sunlit: Optional[bool]
    tle_epoch_ts: float
    next_aos_ts: Optional[float]
    next_los_ts: Optional[float]
    next_max_elev_deg: Optional[float]
    group: str = ""
    transmitters: list[Transmitter] = field(default_factory=list)


@dataclass
class SourceHealth:
    source: str
    success: bool
    last_success_ts: Optional[float]
    last_status: Optional[int]
    age_s: Optional[float]
    fetch_duration_s: Optional[float]
    error: Optional[str]
