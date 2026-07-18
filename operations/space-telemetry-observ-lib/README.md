# space-telemetry-observ-lib

An [observ-viz](https://github.com/cznewt/observ-viz) pack for space-telemetry: a
Grafana dashboard plus Prometheus alerts and recording rules for the exporter's
`body_*` / `star_*` / `satellite_*` / `space_weather_*` metrics.

## Rendered outputs (committed)

| Path | Contents |
| --- | --- |
| `dashboards/space-telemetry.json` | Grafana dashboard (schema v2): overview, solar-system bodies, stars, satellites, space weather, health |
| `alerts/space-telemetry.yaml` | `SpaceTelemetryExporterDown`, `SpaceTelemetrySourceFailing`, `SpaceTelemetryTLEStale`, `GeomagneticStorm`, `SolarFlareMClass` |
| `rules/space-telemetry.yaml` | `observer:body_above_horizon:sum`, `job:satellite_tracked_count:sum` |

## Rebuild

Rendered through the `ghcr.io/cznewt/observ-lib` image (observ-viz on the jpath,
no local `jsonnet`/`jb` needed):

```bash
just observ-lib-build      # from the repo root
```

Edit the sources — `config.libsonnet`, `signals/space_telemetry.libsonnet`,
`main.libsonnet` — then re-render. CI (`observ-lib.yml`) fails if the committed
outputs drift from the sources.

## Signals

The dashboard, alerts and rules are built from these signals. The queries below
are rendered from `signals/space_telemetry.libsonnet` by `render.py` (do not edit
between the markers by hand — re-render instead).

<!-- signals:start -->
#### Solar-system bodies

| Signal | Query | Unit |
|---|---|---|
| Body altitude | `body_altitude_degrees{job=~"$job", observer=~"$observer"}` | degree |
| Bodies above horizon | `sum by (observer) (body_above_horizon{job=~"$job", observer=~"$observer"})` | short |
| Moon illuminated | `moon_illuminated_fraction{job=~"$job", observer=~"$observer"}` | percentunit |
| Moon phase | `moon_phase_degrees{job=~"$job", observer=~"$observer"}` | degree |

#### Celestial bodies

| Signal | Query | Unit |
|---|---|---|
| Star altitude | `star_altitude_degrees{job=~"$job", observer=~"$observer"}` | degree |

#### Satellites

| Signal | Query | Unit |
|---|---|---|
| Satellites tracked | `satellite_tracked_count{job=~"$job", observer=~"$observer"}` | short |
| Satellite elevation | `satellite_elevation_degrees{job=~"$job", observer=~"$observer"}` | degree |
| Satellite altitude | `satellite_altitude_meters{job=~"$job", observer=~"$observer"}` | lengthm |
| TLE age | `max by (name) (satellite_tle_age_seconds{job=~"$job", observer=~"$observer"})` | s |
| Next pass max elevation | `satellite_next_pass_max_elevation_degrees{job=~"$job", observer=~"$observer"}` | degree |
| Satellite sources healthy | `sum(satellite_data_update_success{job=~"$job"})` | short |

#### Space weather

| Signal | Query | Unit |
|---|---|---|
| Planetary Kp | `space_weather_planetary_k_index{job=~"$job"}` | short |
| Solar wind speed | `space_weather_solar_wind_speed_km_per_second{job=~"$job"}` | short |
| IMF Bz | `space_weather_imf_bz_nanotesla{job=~"$job"}` | short |
| GOES X-ray flux | `space_weather_goes_xray_flux_watts_per_m2{job=~"$job"}` | short |
| F10.7 flux | `space_weather_f107_solar_radio_flux{job=~"$job"}` | short |

#### Health

| Signal | Query | Unit |
|---|---|---|
| Exporter up | `up{job=~"$job"}` | short |
| Scrape duration | `satellite_scrape_duration_seconds{job=~"$job"}` | s |
<!-- signals:end -->

## Use

- **Dashboard**: push it to Grafana with `just grafana-push` (set `GRAFANA_URL`
  + `GRAFANA_TOKEN` [+ `GRAFANA_NAMESPACE`] in `.env` — see `.env.example`), or
  import `dashboards/space-telemetry.json` manually. It expects `datasource`,
  `job`, and `observer` template variables.
- **Alerts / rules**: load the YAML into Prometheus/Mimir (or Grafana-managed
  rules). The alerts scope to `job="space-telemetry"` — adjust `exporterSelector`
  in `config.libsonnet` if your scrape job differs.
