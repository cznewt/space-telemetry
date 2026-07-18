# space-telemetry

A Prometheus / OpenTelemetry exporter for space telemetry — the sky above your
ground station(s) and the space weather around Earth. Organised as sibling
**collector** modules under `space_telemetry.collectors`:

| Collector | What it exposes | Source | Network |
|---|---|---|---|
| `sky` › solar-system bodies | Sun, Moon, planets: alt/az, distance, rise/set, Moon phase | JPL `.bsp` ephemeris | once (kernel) |
| `sky` › celestial bodies | bright stars: alt/az, rise/set, magnitude | built-in catalog | none |
| `satellites` | TLE/OMM → SGP4: alt/az, range, Doppler, passes, transmitters | CelesTrak + SatNOGS | background updater |
| `swpc` | space weather: Kp, solar wind, IMF Bz/Bt, F10.7, GOES X-ray | NOAA SWPC | background updater |

Offline-first: every scrape is served from local state; background updaters
refresh it and keep the last-good copy on failure. Solar-system + celestial
bodies need no network at all after the one-time ephemeris download.

📖 **Docs:** [`docs/`](docs/index.md) — [configuration](docs/configuration.md),
[deployment](docs/deployment.md), and a page per collector
([sky](docs/collectors/sky.md) ·
[satellites](docs/collectors/satellites.md) ·
[swpc](docs/collectors/swpc.md)). Ready-made configs in [`examples/`](examples/).

## Quickstart

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .              # add [otel] for OTLP push

python -m space_telemetry     # first run downloads de421.bsp (~17 MB) into ./data
curl -s localhost:9110/metrics | grep -E '^(body_|star_|satellite_|swpc_)'
```

Open `http://localhost:9110/` for a status page. Endpoints: `/` (info,
`?format=json` for JSON), `/metrics` (Prometheus), `/status` (JSON), `/health`
+ `/healthz`.

## Configuration

Env-first (`SPACE_TELEMETRY_<FIELD>`) **or** a YAML file (`space-telemetry.yaml`,
or point `$SPACE_TELEMETRY_CONFIG` at one). Precedence: **env > YAML > defaults**.
Copy `space-telemetry.example.yaml` to start.

| Setting | Env var(s) | Default |
|---|---|---|
| observer | `OBSERVER_LAT` / `_LON` / `_ELEVATION_M` / `_NAME` | Prague |
| multiple observers | `OBSERVERS` (JSON) or `observers:` (YAML list) | — |
| solar-system bodies | `BODIES` | sun,moon,mercury,venus,mars,jupiter,saturn |
| stars | `STARS` | sirius,vega,arcturus,capella,rigel,betelgeuse,aldebaran,polaris |
| horizon mask | `MIN_ELEVATION_DEG` | 0 |
| satellites | `SAT_ENABLED`, `SAT_GROUPS`, `SAT_WATCHLIST`, `TLE_REFRESH_HOURS` | on · [stations] · [] · 8 |
| space weather | `SWPC_ENABLED`, `SWPC_REFRESH_MINUTES` | on · 5 |
| serving | `HOST`, `PORT`, `CACHE_DIR`, `OTLP_ENDPOINT` | 0.0.0.0 · 9110 · data · — |

Multiple observers via YAML — every sky/satellite series is labelled `observer=…`:

```yaml
observers:
  - {name: prague, latitude_deg: 50.0755, longitude_deg: 14.4378, elevation_m: 200}
  - {name: brno,   latitude_deg: 49.1951, longitude_deg: 16.6068, elevation_m: 237}
```

> Note: observer `elevation_m` (your altitude in metres) is distinct from the
> `*_altitude_degrees` metrics (angle above the horizon).

## Metrics

**sky › solar-system bodies** (labels `body,observer`): `body_altitude_degrees`,
`body_azimuth_degrees`, `body_distance_meters`, `body_above_horizon`,
`body_next_rise_timestamp_seconds`, `body_next_set_timestamp_seconds`; plus
`moon_illuminated_fraction`, `moon_phase_degrees` (labels `observer`).

**sky › celestial bodies** (labels `star,observer`): `star_altitude_degrees`,
`star_azimuth_degrees`, `star_above_horizon`, `star_magnitude`,
`star_next_rise_timestamp_seconds`, `star_next_set_timestamp_seconds`.

**satellites** (labels `norad,name,observer`): `satellite_elevation_degrees`,
`…_azimuth_degrees`, `…_range_meters`, `…_range_rate_meters_per_second`,
`…_subpoint_{latitude,longitude}_degrees`, `…_altitude_meters`,
`…_velocity_meters_per_second`, `…_above_horizon`, `…_sunlit`,
`…_tle_epoch_timestamp_seconds`, `…_tle_age_seconds`,
`…_next_pass_{aos,los}_timestamp_seconds`, `…_next_pass_max_elevation_degrees`.
Transmitters (labels `norad,uuid,mode,status`):
`satellite_transmitter_{downlink,uplink}_hertz`, `…_baud`;
`satellite_doppler_hertz{norad,uuid,observer}`. Catalog/health:
`satellite_catalog_size`, `…_with_transmitters`, `satellite_tracked_count{observer}`,
`satellite_data_{update_success,update_timestamp_seconds,age_seconds,fetch_duration_seconds}{source}`.

**swpc** (no observer label): `swpc_planetary_k_index`,
`swpc_solar_wind_speed_km_per_second`, `swpc_imf_bz_nanotesla`,
`swpc_imf_bt_nanotesla`, `swpc_f107_solar_radio_flux`,
`swpc_goes_xray_flux_watts_per_m2`; health
`swpc_data_{update_success,update_timestamp_seconds,age_seconds}{source}`.

### Offline-first updaters

Satellites and SWPC each run a daemon thread that refreshes each source when
**due** (TLE ~`TLE_REFRESH_HOURS`, SatNOGS weekly, SWPC ~`SWPC_REFRESH_MINUTES`)
via conditional requests (`If-None-Match`/`If-Modified-Since` → `304`), writes
atomically to the cache, and rebuilds. Failures keep the last-good copy, and the
catalog is rebuilt as each source lands, so scrapes never block on the network.

## Docker Compose

Exporter + Prometheus (scraping it) + Grafana (provisioned dashboard). The
exporter reads `space-telemetry.example.yaml` (two observers) and caches into a
container-owned named volume.

```bash
docker compose up -d --build
# exporter   http://localhost:9110/
# prometheus http://localhost:9090
# grafana    http://localhost:3000   (anonymous admin; dashboard "Space Telemetry — Sky")
```

Edit `space-telemetry.example.yaml`, then `docker compose restart exporter`.
