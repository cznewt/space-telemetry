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
from .collectors.solar_system_bodies.collector import BodyCollector
from .collectors.solar_system_bodies.sampler import BodySampler
from .collectors.celestial_bodies.collector import StarCollector
from .collectors.celestial_bodies.sampler import StarSampler
from .collectors.satellites.collector import SatelliteCollector
from .collectors.satellites.model import CatalogHolder
from .collectors.satellites.propagate import SatelliteProvider, footprint_radius_km
from .collectors.satellites.updater import SatelliteUpdater
from .collectors.space_weather.collector import SpaceWeatherCollector
from .collectors.space_weather.updater import SpaceWeatherUpdater


def load_timescale_ephemeris(settings: Settings, loader: "Loader | None" = None):
    loader = loader or Loader(str(settings.cache_dir))
    return loader.timescale(), loader(settings.ephemeris)


def _health_json(healths) -> list:
    return [{"source": h.source, "success": h.success,
             "age_seconds": round(h.age_s) if h.age_s is not None else None}
            for h in healths]


def _info_fn(settings, observers, sat_providers, sat_updater, sw_updater):
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

        space_weather = {"enabled": settings.space_weather_enabled}
        if settings.space_weather_enabled and sw_updater is not None:
            space_weather.update({
                "products": sw_updater.product_keys(),
                "sources": _health_json(sw_updater.health()),
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
                "solar_system_bodies": list(settings.bodies),
                "celestial_bodies": list(settings.stars),
                "satellites": satellites,
                "space_weather": space_weather,
            },
            "endpoints": ["/metrics", "/status", "/health", "/healthz", "/map", "/table",
                          "/api/satellites.json", "/api/tracks.json", "/api/passes.json",
                          "/api/bodies.json", "/api/stars.json"],
        }

    return info


# Multi-module space stations are catalogued as several NORAD objects sharing one
# ground point; on the map they collapse to a single marker labelled by station.
_STATIONS = {"iss": "ISS", "css": "CSS"}
# Craft docked to (or modules of) a station ride along at the same ground point but are
# catalogued in the generic "stations" group; hide any sitting within this many degrees
# of a station marker so they don't pile up on top of it.
_DOCKED_EPS_DEG = 0.5


def _lon_delta(a: float, b: float) -> float:
    """Smallest absolute longitude difference in degrees, across the antimeridian."""
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _visible_map_sats(p, offset_min=0.0):
    """Provider positions after collapsing ISS/CSS modules into one marker and hiding
    craft docked at a station. Returns position dicts (norad, name, group, lat, lon,
    alt_m, elevation, sunlit, footprint_km); shared by the /map position and track feeds.
    ``offset_min`` shifts the evaluation time (the /map time scrubber)."""
    raw = p.positions(offset_min)
    anchors = [(r["lat"], r["lon"]) for r in raw if r["group"] in _STATIONS]

    def at_station(lat, lon):
        return any(abs(lat - alat) < _DOCKED_EPS_DEG and _lon_delta(lon, alon) < _DOCKED_EPS_DEG
                   for alat, alon in anchors)

    out = []
    seen_station: set[str] = set()
    for r in raw:
        g = r["group"]
        if g in _STATIONS:  # keep one marker per station, not one per module
            if g in seen_station:
                continue
            seen_station.add(g)
            r = {**r, "name": _STATIONS[g]}
        elif g == "stations" and at_station(r["lat"], r["lon"]):
            continue  # docked craft / module co-located with ISS or CSS — hide it
        out.append(r)
    return out


def _positions_fn(settings, sat_providers, observers):
    """Current sub-satellite positions + observers, for the /map markers — small and
    polled frequently. Ground tracks are big and ride a separate endpoint."""
    obs = [{"name": o.name, "lat": round(o.latitude_deg, 4), "lon": round(o.longitude_deg, 4)}
           for o in observers]

    def data(offset_min=0.0) -> dict:
        if not (settings.sat_enabled and sat_providers):
            return {"satellites": [], "observers": obs}
        sats = [{
            "norad": r["norad"], "name": r["name"], "group": r["group"],
            "lat": round(r["lat"], 3), "lon": round(r["lon"], 3),
            "alt_km": round(r["alt_m"] / 1000.0, 1),
            "elevation": round(r["elevation"], 1),
            "sunlit": r["sunlit"],
            "footprint_km": round(r["footprint_km"]),
        } for r in _visible_map_sats(sat_providers[0], offset_min)]
        return {"satellites": sats, "observers": obs}
    return data


def _tracks_fn(settings, sat_providers):
    """Multi-orbit ground tracks for the /map, one entry per visible satellite. Big, so
    it rides its own endpoint that the page fetches far less often than the positions."""
    def data() -> dict:
        if not (settings.sat_enabled and sat_providers):
            return {"tracks": []}
        p = sat_providers[0]
        tracks = p.ground_tracks()
        return {"tracks": [
            {"name": r["name"], "group": r["group"], "alt": round(r["alt_m"] / 1000.0),
             "track": tracks.get(r["norad"], [])}
            for r in _visible_map_sats(p)
        ]}
    return data


def _passes_fn(settings, sat_providers):
    """Upcoming passes over the observer, for /api/passes.json and the /map passes panel:
    for each visible satellite that rises within the lookahead window, its next AOS/LOS,
    peak elevation, duration and reception-footprint radius. Sorted soonest-first."""
    def data() -> dict:
        if not (settings.sat_enabled and sat_providers):
            return {"passes": []}
        p = sat_providers[0]
        mask = settings.min_elevation_deg
        names = {r["norad"]: r["name"] for r in _visible_map_sats(p)}  # collapsed/filtered set
        passes = []
        for s in p.states():
            if s.norad_id not in names or s.next_aos_ts is None:
                continue
            dur = round(s.next_los_ts - s.next_aos_ts) if (s.next_los_ts and s.next_aos_ts) else None
            passes.append({
                "norad": s.norad_id, "name": names[s.norad_id], "group": s.group,
                "aos": s.next_aos_ts, "los": s.next_los_ts,
                "max_elev": round(s.next_max_elev_deg, 1) if s.next_max_elev_deg is not None else None,
                "duration_s": dur,
                "footprint_km": round(footprint_radius_km(s.altitude_m, mask)),
                "up_now": bool(s.above_horizon),
            })
        passes.sort(key=lambda x: x["aos"])
        return {"passes": passes}
    return data


def _bodies_fn(settings, body_samplers):
    """Solar-system body positions for /api/bodies.json and the /table view: altitude,
    azimuth, distance, next rise/set, plus Moon illumination and phase."""
    def data() -> dict:
        if not body_samplers:
            return {"bodies": []}
        snap = body_samplers[0].sample()
        return {"bodies": [{
            "name": s.body,
            "altitude": round(float(s.altitude_deg), 2),
            "azimuth": round(float(s.azimuth_deg), 1),
            "distance_km": round(float(s.distance_m) / 1000.0),
            "up": bool(s.above_horizon),
            "rise": float(s.next_rise_ts) if s.next_rise_ts is not None else None,
            "set": float(s.next_set_ts) if s.next_set_ts is not None else None,
            "illum": round(float(s.illuminated_fraction) * 100, 1) if s.illuminated_fraction is not None else None,
            "phase": round(float(s.phase_deg), 1) if s.phase_deg is not None else None,
        } for s in snap.bodies]}
    return data


def _stars_fn(settings, star_samplers):
    """Bright-star positions for /api/stars.json and the /table view: alt/az, magnitude,
    distance, spectral type, constellation and next rise/set, sorted brightest-first."""
    def data() -> dict:
        if not star_samplers:
            return {"stars": []}
        snap = star_samplers[0].sample()
        stars = [{
            "name": s.star, "mag": s.magnitude,
            "altitude": s.altitude_deg, "azimuth": s.azimuth_deg, "up": bool(s.above_horizon),
            "dist_ly": s.distance_ly, "spect": s.spectral, "con": s.constellation,
            "rise": s.next_rise_ts, "set": s.next_set_ts,
        } for s in snap.stars]
        stars.sort(key=lambda x: x["mag"])
        return {"stars": stars}
    return data


def run(settings: "Settings | None" = None) -> None:
    settings = settings or Settings()
    os.makedirs(settings.cache_dir, exist_ok=True)

    ts, eph = load_timescale_ephemeris(settings)
    observers = [Observer.from_config(c) for c in settings.observer_list()]

    body_samplers: list = []
    if settings.bodies:
        body_samplers = [BodySampler(eph=eph, observer=o, ts=ts, settings=settings) for o in observers]
        REGISTRY.register(BodyCollector(body_samplers))
    star_samplers: list = []
    if settings.stars or settings.star_max_magnitude > 0:
        star_samplers = [StarSampler(eph=eph, observer=o, ts=ts, settings=settings) for o in observers]
        REGISTRY.register(StarCollector(star_samplers))

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

    sw_updater = None
    if settings.space_weather_enabled:
        sw_updater = SpaceWeatherUpdater(settings, FileCache(settings.cache_dir, "space_weather"))
        REGISTRY.register(SpaceWeatherCollector(sw_updater))
        sw_updater.bootstrap()
        sw_updater.start()
        updaters.append(sw_updater)

    if settings.otlp_endpoint:
        attach_otel(body_samplers, settings, sat_providers)

    server = make_server(settings.host, settings.port,
                         _info_fn(settings, observers, sat_providers, sat_updater, sw_updater),
                         _positions_fn(settings, sat_providers, observers),
                         _tracks_fn(settings, sat_providers),
                         _passes_fn(settings, sat_providers),
                         _bodies_fn(settings, body_samplers),
                         _stars_fn(settings, star_samplers))
    print(
        f"[space-telemetry] serving on http://{settings.host}:{settings.port}/  (metrics at /metrics)  "
        f"observers={[o.name for o in observers]} | "
        f"solar_system_bodies={len(settings.bodies)} | celestial_bodies={len(settings.stars)} | "
        f"satellites={'on' if settings.sat_enabled else 'off'} | "
        f"space_weather={'on' if settings.space_weather_enabled else 'off'}",
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
