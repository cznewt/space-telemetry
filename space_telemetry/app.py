"""Top-level orchestrator: load settings, register every enabled collector on one
registry, start background updaters, and serve HTTP. Supports multiple observers."""

from __future__ import annotations

import os

from prometheus_client import REGISTRY
from skyfield.api import Loader

from . import __version__
from .cache import FileCache
from .observer import Observer
from .otel import attach_otel
from .server import make_server
from .settings import Settings
from .collectors.sky.collector import SkyCollector
from .collectors.sky.snapshot import SkySampler
from .collectors.satellites.collector import SatelliteCollector
from .collectors.satellites.model import CatalogHolder
from .collectors.satellites.propagate import SatelliteProvider
from .collectors.satellites.updater import SatelliteUpdater
from .collectors.swpc.collector import SWPCCollector
from .collectors.swpc.updater import SWPCUpdater


def load_timescale_ephemeris(settings: Settings, loader: "Loader | None" = None):
    loader = loader or Loader(str(settings.cache_dir))
    return loader.timescale(), loader(settings.ephemeris)


def _health_json(healths) -> list:
    return [{"source": h.source, "success": h.success,
             "age_seconds": round(h.age_s) if h.age_s is not None else None}
            for h in healths]


def _info_fn(settings, observers, sat_providers, sat_updater, swpc_updater):
    def info() -> dict:
        satellites = {"enabled": settings.sat_enabled}
        if settings.sat_enabled and sat_providers and sat_updater is not None:
            total, with_tx = sat_providers[0].catalog().stats()
            satellites.update({
                "groups": list(settings.sat_groups),
                "watchlist": list(settings.sat_watchlist),
                "catalog_size": total,
                "with_transmitters": with_tx,
                "sources": _health_json(sat_updater.health()),
            })

        swpc = {"enabled": settings.swpc_enabled}
        if settings.swpc_enabled and swpc_updater is not None:
            swpc.update({
                "products": swpc_updater.product_keys(),
                "sources": _health_json(swpc_updater.health()),
            })

        return {
            "service": "space-telemetry",
            "version": __version__,
            "observers": [
                {"name": o.name, "latitude_deg": o.latitude_deg,
                 "longitude_deg": o.longitude_deg, "elevation_m": o.elevation_m}
                for o in observers
            ],
            "collectors": {
                "sky": {
                    "solar_system_bodies": list(settings.bodies),
                    "celestial_bodies": list(settings.stars),
                },
                "satellites": satellites,
                "swpc": swpc,
            },
            "endpoints": ["/metrics", "/status", "/health", "/healthz"],
        }

    return info


def run(settings: "Settings | None" = None) -> None:
    settings = settings or Settings()
    os.makedirs(settings.cache_dir, exist_ok=True)

    ts, eph = load_timescale_ephemeris(settings)
    observers = [Observer.from_config(c) for c in settings.observer_list()]

    # sky: solar-system bodies + celestial bodies, one sampler per observer
    sky_samplers = [SkySampler(eph=eph, observer=o, ts=ts, settings=settings) for o in observers]
    REGISTRY.register(SkyCollector(sky_samplers))

    updaters = []

    sat_providers: list = []
    sat_updater = None
    if settings.sat_enabled:
        holder = CatalogHolder()
        sat_updater = SatelliteUpdater(settings, FileCache(settings.cache_dir, "satellites"), holder, ts)
        sat_providers = [SatelliteProvider(holder, o, eph, ts, settings) for o in observers]
        REGISTRY.register(SatelliteCollector(sat_providers, sat_updater))
        sat_updater.bootstrap()
        sat_updater.start()
        updaters.append(sat_updater)

    swpc_updater = None
    if settings.swpc_enabled:
        swpc_updater = SWPCUpdater(settings, FileCache(settings.cache_dir, "swpc"))
        REGISTRY.register(SWPCCollector(swpc_updater))
        swpc_updater.bootstrap()
        swpc_updater.start()
        updaters.append(swpc_updater)

    if settings.otlp_endpoint:
        attach_otel(sky_samplers, settings, sat_providers)

    server = make_server(settings.host, settings.port,
                         _info_fn(settings, observers, sat_providers, sat_updater, swpc_updater))
    print(
        f"[space-telemetry] serving on http://{settings.host}:{settings.port}/  (metrics at /metrics)  "
        f"observers={[o.name for o in observers]} | "
        f"sky: {len(settings.bodies)} bodies + {len(settings.stars)} stars | "
        f"satellites: {'on' if settings.sat_enabled else 'off'} | "
        f"swpc: {'on' if settings.swpc_enabled else 'off'}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for u in updaters:
            u.stop()
        server.shutdown()


def main() -> None:  # console-script entrypoint
    run()
