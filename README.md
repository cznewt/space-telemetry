# space-telemetry

A Prometheus / OpenTelemetry exporter for space telemetry — the sky above your
ground station(s) and the space weather around Earth. Organised as sibling
**collector** modules under `space_telemetry.collectors`:

| Collector | What it exposes | Source | Network |
|---|---|---|---|
| `solar_system_bodies` | Sun, Moon, planets: alt/az, distance, rise/set, Moon phase | JPL `.bsp` ephemeris | once (kernel) |
| `celestial_bodies` | bright stars: alt/az, rise/set, magnitude | built-in catalog | none |
| `satellites` | TLE/OMM → SGP4: alt/az, range, Doppler, passes, transmitters | CelesTrak + SatNOGS | background updater |
| `space_weather` | Kp, solar wind, IMF Bz/Bt, F10.7, GOES X-ray | NOAA SWPC | background updater |

Offline-first: every scrape is served from local state; background updaters
refresh it and keep the last-good copy on failure. Solar-system + celestial
bodies need no network at all after the one-time ephemeris download.

📖 **Docs:** [`docs/`](docs/index.md) — [configuration](docs/configuration.md),
[deployment](docs/deployment.md), and a page per collector
([solar_system_bodies](docs/collectors/solar_system_bodies.md) ·
[celestial_bodies](docs/collectors/celestial_bodies.md) ·
[satellites](docs/collectors/satellites.md) ·
[space_weather](docs/collectors/space_weather.md)).
Ready-made configs in [`examples/`](examples/).

## Quickstart

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .              # add [otel] for OTLP push

python -m space_telemetry     # first run downloads de421.bsp (~17 MB) into ./data
curl -s localhost:9110/metrics | grep -E '^(body_|star_|satellite_|space_weather_)'
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
| space weather | `SPACE_WEATHER_ENABLED`, `SPACE_WEATHER_REFRESH_MINUTES` | on · 5 |
| serving | `HOST`, `PORT`, `CACHE_DIR`, `OTLP_ENDPOINT` | 0.0.0.0 · 9110 · data · — |

Multiple observers via YAML — every body/star/satellite series is labelled `observer=…`:

```yaml
observers:
  - {name: prague, latitude_deg: 50.0755, longitude_deg: 14.4378, elevation_m: 200}
  - {name: brno,   latitude_deg: 49.1951, longitude_deg: 16.6068, elevation_m: 237}
```

> Note: observer `elevation_m` (your altitude in metres) is distinct from the
> `*_altitude_degrees` metrics (angle above the horizon).

## Metrics

Every metric the exporter emits, with description, unit, expected range and
labels. Per-collector detail is in [docs/](docs/index.md).

### Signals

<!-- signals:start -->
★ = built into the [observ-lib](operations/space-telemetry-observ-lib/) dashboard/alerts.

#### Solar-system bodies

| Signal | Description | Unit | Range | Labels |
|---|---|---|---|---|
| `body_altitude_degrees` ★ | Apparent altitude of the body above the horizon. | degrees | -90 … 90 | `body`, `observer` |
| `body_azimuth_degrees` | Apparent azimuth, clockwise from north. | degrees | 0 … 360 | `body`, `observer` |
| `body_distance_meters` | Distance from the observer to the body. | metres | ~3.6e8 (Moon) … ~6e12 (Neptune) | `body`, `observer` |
| `body_above_horizon` ★ | 1 if the body is above the horizon mask, else 0. | boolean | 0 or 1 | `body`, `observer` |
| `body_next_rise_timestamp_seconds` | Next rise time (absent if none within the search window). | unix seconds | >= now | `body`, `observer` |
| `body_next_set_timestamp_seconds` | Next set time (absent if none within the search window). | unix seconds | >= now | `body`, `observer` |
| `moon_illuminated_fraction` ★ | Fraction of the lunar disc that is lit. | fraction | 0 … 1 | `observer` |
| `moon_phase_degrees` ★ | Moon phase angle (0=new, 90=first quarter, 180=full, 270=last). | degrees | 0 … 360 | `observer` |
| `observer_info` | Observer location (value is always 1; detail is in the labels). | info | 1 | `observer`, `latitude_deg`, `longitude_deg`, `elevation_m` |
| `body_scrape_duration_seconds` | Time spent building the solar-system-body snapshot for a scrape. | seconds | >= 0 (typ. < 0.05) | — |

#### Celestial bodies

| Signal | Description | Unit | Range | Labels |
|---|---|---|---|---|
| `star_altitude_degrees` ★ | Apparent altitude of the star above the horizon. | degrees | -90 … 90 | `star`, `observer` |
| `star_azimuth_degrees` | Apparent azimuth, clockwise from north. | degrees | 0 … 360 | `star`, `observer` |
| `star_above_horizon` | 1 if the star is above the horizon mask, else 0. | boolean | 0 or 1 | `star`, `observer` |
| `star_magnitude` | Apparent visual magnitude (catalog constant; lower is brighter). | magnitude | -1.5 … 2 (catalog) | `star`, `observer` |
| `star_next_rise_timestamp_seconds` | Next rise time (absent for circumpolar stars). | unix seconds | >= now | `star`, `observer` |
| `star_next_set_timestamp_seconds` | Next set time (absent for circumpolar stars). | unix seconds | >= now | `star`, `observer` |
| `star_scrape_duration_seconds` | Time spent building the celestial-body snapshot for a scrape. | seconds | >= 0 (typ. < 0.05) | — |

#### Satellites

| Signal | Description | Unit | Range | Labels |
|---|---|---|---|---|
| `satellite_elevation_degrees` ★ | Elevation above the horizon. | degrees | -90 … 90 | `norad`, `name`, `observer` |
| `satellite_azimuth_degrees` | Azimuth, clockwise from north. | degrees | 0 … 360 | `norad`, `name`, `observer` |
| `satellite_range_meters` | Slant range from the observer to the satellite. | metres | ~2e5 … ~4.5e7 | `norad`, `name`, `observer` |
| `satellite_range_rate_meters_per_second` | Radial velocity (positive = receding); drives Doppler. | metres/second | ~-8000 … 8000 | `norad`, `name`, `observer` |
| `satellite_subpoint_latitude_degrees` | Latitude of the sub-satellite point. | degrees | -90 … 90 | `norad`, `name`, `observer` |
| `satellite_subpoint_longitude_degrees` | Longitude of the sub-satellite point. | degrees | -180 … 180 | `norad`, `name`, `observer` |
| `satellite_track_latitude_degrees` | Sub-satellite latitude at a time offset (the ground track shown on the map). | degrees | -90 … 90 | `norad`, `name`, `offset` |
| `satellite_track_longitude_degrees` | Sub-satellite longitude at a time offset (the ground track shown on the map). | degrees | -180 … 180 | `norad`, `name`, `offset` |
| `satellite_altitude_meters` ★ | Satellite height above the WGS84 ellipsoid. | metres | ~2e5 (LEO) … ~3.6e7 (GEO) | `norad`, `name`, `observer` |
| `satellite_velocity_meters_per_second` | Orbital speed (geocentric). | metres/second | ~3000 (GEO) … ~7800 (LEO) | `norad`, `name`, `observer` |
| `satellite_above_horizon` | 1 if above the horizon mask, else 0. | boolean | 0 or 1 | `norad`, `name`, `observer` |
| `satellite_sunlit` | 1 if the satellite is in sunlight, else 0. | boolean | 0 or 1 | `norad`, `name`, `observer` |
| `satellite_tle_epoch_timestamp_seconds` | Epoch of the current element set. | unix seconds | <= now | `norad`, `name`, `observer` |
| `satellite_tle_age_seconds` ★ | Age of the current element set (now - epoch). SGP4 accuracy decays with age. | seconds | >= 0 (alert if > 3 days) | `norad`, `name`, `observer` |
| `satellite_next_pass_aos_timestamp_seconds` | Next pass acquisition-of-signal time. | unix seconds | >= now | `norad`, `name`, `observer` |
| `satellite_next_pass_los_timestamp_seconds` | Next pass loss-of-signal time. | unix seconds | >= now | `norad`, `name`, `observer` |
| `satellite_next_pass_max_elevation_degrees` ★ | Peak elevation of the next pass. | degrees | 0 … 90 | `norad`, `name`, `observer` |
| `satellite_transmitter_downlink_hertz` | Transmitter downlink frequency (from SatNOGS). | hertz | ~3e7 … ~3e10 | `norad`, `uuid`, `mode`, `status` |
| `satellite_transmitter_uplink_hertz` | Transmitter uplink frequency (from SatNOGS). | hertz | ~3e7 … ~3e10 | `norad`, `uuid`, `mode`, `status` |
| `satellite_transmitter_baud` | Transmitter symbol rate. | baud | ~50 … ~1e6 | `norad`, `uuid`, `mode`, `status` |
| `satellite_doppler_hertz` | Doppler shift on the downlink at the current range rate. | hertz | ~-1e5 … 1e5 | `norad`, `uuid`, `observer` |
| `satellite_catalog_size` | Number of satellites in the offline catalog. | count | >= 0 | — |
| `satellite_catalog_with_transmitters` | Catalog satellites that have at least one transmitter. | count | >= 0 | — |
| `satellite_tracked_count` ★ | Satellites tracked live for the observer (watchlist ∪ groups). | count | >= 0 | `observer` |
| `satellite_data_update_success` ★ | 1 if the source's last fetch attempt succeeded, else 0. | boolean | 0 or 1 | `source` |
| `satellite_data_update_timestamp_seconds` | Last successful fetch time, per source. | unix seconds | <= now | `source` |
| `satellite_data_age_seconds` | Seconds since the source's last successful fetch. | seconds | >= 0 | `source` |
| `satellite_data_fetch_duration_seconds` | Duration of the source's last fetch. | seconds | >= 0 | `source` |
| `satellite_scrape_duration_seconds` ★ | Time spent building the satellite snapshot for a scrape. | seconds | >= 0 | — |

#### Space weather

| Signal | Description | Unit | Range | Labels |
|---|---|---|---|---|
| `space_weather_planetary_k_index` ★ | Planetary K-index (geomagnetic activity); >= 5 is a geomagnetic storm. | index | 0 … 9 | — |
| `space_weather_solar_wind_speed_km_per_second` ★ | Solar-wind bulk speed at L1. | km/second | ~250 … ~900 | — |
| `space_weather_imf_bz_nanotesla` ★ | Interplanetary magnetic field Bz (GSM); strongly negative drives storms. | nanotesla | ~-50 … 50 | — |
| `space_weather_imf_bt_nanotesla` | Interplanetary magnetic field total strength Bt. | nanotesla | 0 … ~50 | — |
| `space_weather_f107_solar_radio_flux` ★ | 10.7 cm solar radio flux (F10.7); proxy for solar activity. | sfu | ~60 … ~300 | — |
| `space_weather_goes_xray_flux_watts_per_m2` ★ | GOES long-band (0.1-0.8 nm) X-ray flux; M >= 1e-5, X >= 1e-4. | W/m^2 | ~1e-9 … ~1e-3 | — |
| `space_weather_data_update_success` | 1 if the product's last fetch attempt succeeded, else 0. | boolean | 0 or 1 | `source` |
| `space_weather_data_update_timestamp_seconds` | Last successful fetch time, per product. | unix seconds | <= now | `source` |
| `space_weather_data_age_seconds` | Seconds since the product's last successful fetch. | seconds | >= 0 | `source` |
| `space_weather_scrape_duration_seconds` | Time spent building the space-weather snapshot for a scrape. | seconds | >= 0 | — |
<!-- signals:end -->

### Offline-first updaters

Satellites and space weather each run a daemon thread that refreshes each source
when **due** (TLE ~`TLE_REFRESH_HOURS`, SatNOGS weekly, space weather
~`SPACE_WEATHER_REFRESH_MINUTES`) via conditional requests
(`If-None-Match`/`If-Modified-Since` → `304`), writes atomically to the cache, and
rebuilds. Failures keep the last-good copy, and the catalog is rebuilt as each
source lands, so scrapes never block on the network.

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
