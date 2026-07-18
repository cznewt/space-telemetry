"""Observer (ground site) model."""

from __future__ import annotations

from dataclasses import dataclass

from skyfield.api import wgs84


@dataclass(frozen=True)
class Observer:
    name: str
    latitude_deg: float
    longitude_deg: float
    elevation_m: float = 0.0

    @classmethod
    def from_settings(cls, settings) -> "Observer":
        return cls(
            settings.observer_name,
            settings.observer_lat,
            settings.observer_lon,
            settings.observer_elevation_m,
        )

    @classmethod
    def from_config(cls, cfg) -> "Observer":
        return cls(cfg.name, cfg.latitude_deg, cfg.longitude_deg, cfg.elevation_m)

    def topos(self):
        """Skyfield WGS84 geographic position for this observer."""
        return wgs84.latlon(self.latitude_deg, self.longitude_deg, elevation_m=self.elevation_m)
