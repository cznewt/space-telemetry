"""Environment-first configuration for the whole exporter.

Every field maps to ``SPACE_TELEMETRY_<FIELD>`` (or a ``.env`` file). List fields
accept comma-separated strings, e.g. ``SPACE_TELEMETRY_STARS=vega,sirius``.
Multiple observers are given as a JSON list, e.g.
``SPACE_TELEMETRY_OBSERVERS=[{"name":"prague","latitude_deg":50.1,"longitude_deg":14.4}]``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Optional

from pydantic import BaseModel, field_validator
from pydantic_settings import (
    BaseSettings,
    NoDecode,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

_DEFAULT_BODIES = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn"]
_DEFAULT_STARS = ["sirius", "vega", "arcturus", "capella", "rigel",
                  "betelgeuse", "aldebaran", "polaris"]


class ObserverConfig(BaseModel):
    name: str = "observer"
    latitude_deg: float                       # +N
    longitude_deg: float                      # +E
    elevation_m: float = 0.0                  # metres above sea level


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SPACE_TELEMETRY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings,
                                   dotenv_settings, file_secret_settings):
        """Layer an optional YAML file under env vars.

        Precedence (highest first): constructor args, env vars, .env, YAML file,
        secrets. So env still overrides the file; the file overrides defaults. The
        path is ``$SPACE_TELEMETRY_CONFIG`` or ``space-telemetry.yaml`` in the CWD,
        and is skipped entirely when absent (pure env behaviour).
        """
        sources = [init_settings, env_settings, dotenv_settings]
        yaml_path = os.getenv("SPACE_TELEMETRY_CONFIG", "space-telemetry.yaml")
        if os.path.exists(yaml_path):
            sources.append(YamlConfigSettingsSource(settings_cls, yaml_file=yaml_path))
        sources.append(file_secret_settings)
        return tuple(sources)

    # --- Observer (single; defaults to Prague). For several sites use `observers`. ---
    observer_name: str = "observer"
    observer_lat: float = 50.0755            # degrees, +N
    observer_lon: float = 14.4378            # degrees, +E
    observer_elevation_m: float = 200.0      # metres above sea level (NOT an angle)
    observers: list[ObserverConfig] = []     # JSON list; overrides the observer_* fields when set

    # --- Sky: solar-system bodies ---
    bodies: Annotated[list[str], NoDecode] = _DEFAULT_BODIES
    min_elevation_deg: float = 0.0           # horizon mask (bodies, stars, satellite passes)

    # --- Sky: celestial bodies (stars) ---
    stars: Annotated[list[str], NoDecode] = _DEFAULT_STARS

    # --- Ephemeris / cache ---
    ephemeris: str = "de421.bsp"
    cache_dir: Path = Path("data")
    pass_cache_ttl_s: float = 300.0

    # --- Serving ---
    host: str = "0.0.0.0"
    port: int = 9110
    otlp_endpoint: Optional[str] = None

    # --- Satellites (CelesTrak orbits + SatNOGS transmitters) ---
    sat_enabled: bool = True
    sat_groups: Annotated[list[str], NoDecode] = ["stations"]
    sat_watchlist: Annotated[list[int], NoDecode] = []
    celestrak_format: str = "tle"            # "tle" or "json" (OMM)
    tle_refresh_hours: float = 8.0
    transmitter_refresh_hours: float = 168.0
    satnogs_satellites_refresh_hours: float = 168.0
    pass_lookahead_hours: float = 24.0
    sat_pass_cache_ttl_s: float = 60.0

    # --- SWPC (NOAA space weather) ---
    swpc_enabled: bool = True
    swpc_refresh_minutes: float = 5.0

    # --- Shared HTTP client (satellites + swpc updaters) ---
    http_timeout_s: float = 30.0
    user_agent: str = "space-telemetry/0.1 (+https://github.com/newt/space-telemetry)"

    def observer_list(self) -> list[ObserverConfig]:
        """The configured observers, or a single one from the observer_* fields."""
        if self.observers:
            return self.observers
        return [ObserverConfig(
            name=self.observer_name,
            latitude_deg=self.observer_lat,
            longitude_deg=self.observer_lon,
            elevation_m=self.observer_elevation_m,
        )]

    @field_validator("bodies", "stars", "sat_groups", mode="before")
    @classmethod
    def _split_str_list(cls, value):
        if isinstance(value, str):
            return [x.strip().lower() for x in value.split(",") if x.strip()]
        return value

    @field_validator("sat_watchlist", mode="before")
    @classmethod
    def _split_watchlist(cls, value):
        if isinstance(value, str):
            return [int(x) for x in value.replace(",", " ").split() if x.strip()]
        return value
