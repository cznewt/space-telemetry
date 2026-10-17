# space-telemetry-observ-lib

An [observ-viz](https://github.com/cznewt/observ-viz) pack for space-telemetry: a
Grafana dashboard plus Prometheus alerts and recording rules for the exporter's
`body_*` / `star_*` / `satellite_*` / `space_weather_*` metrics.

## Rendered outputs (committed)

| Path | Contents |
| --- | --- |
| `dashboards/space-telemetry-{weather,satellites,bodies}.json` | Grafana dashboards (schema v2), filed under *Workloads / Sky monitoring* |
| `alerts/space-telemetry.yaml` | `SpaceTelemetryExporterDown`, `SpaceTelemetryExporterAbsent`, `SpaceTelemetrySourceFailing`, `SpaceTelemetryTLEStale`, `GeomagneticStorm`, `SolarFlareMClass` |
| `rules/space-telemetry-recording.yaml` | `observer:body_above_horizon:sum`, `job:satellite_tracked_count:sum` |

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
| Body altitude | `body_altitude_degrees{job=~"$job", observer=~"$observer", body=~"$body"}` | degree |
| Bodies above horizon | `sum by (observer) (body_above_horizon{job=~"$job", observer=~"$observer"})` | short |
| Moon illuminated | `avg without (instance, pod) (moon_illuminated_fraction{job=~"$job", observer=~"$observer"})` | percentunit |
| Moon phase | `avg without (instance, pod) (moon_phase_degrees{job=~"$job", observer=~"$observer"})` | degree |

#### Celestial bodies

| Signal | Query | Unit |
|---|---|---|
| Star altitude | `star_altitude_degrees{job=~"$job", observer=~"$observer"}` | degree |

#### Satellites

| Signal | Query | Unit |
|---|---|---|
| Satellites tracked | `satellite_tracked_count{job=~"$job", observer=~"$observer"}` | short |
| Satellite elevation | `satellite_elevation_degrees{job=~"$job", observer=~"$observer", group=~"$group"}` | degree |
| Satellite altitude | `satellite_altitude_meters{job=~"$job", observer=~"$observer", group=~"$group"}` | lengthm |
| TLE age | `max by (name) (satellite_tle_age_seconds{job=~"$job", observer=~"$observer", group=~"$group"})` | s |
| Next pass max elevation | `max by (name) (satellite_next_pass_max_elevation_degrees{job=~"$job", observer=~"$observer", group=~"$group"})` | degree |
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
  import the `dashboards/*.json` manually. They expect `datasource`, `job`, and
  `observer` template variables.
- **Alerts / rules**: `just rules-push` loads both groups into the Mimir ruler
  through Grafana's data-source ruler API (ruler namespace `space-telemetry`; set
  `RULER_DATASOURCE_UID` if your Mimir datasource uid is not `newt-mimir`; the
  token needs `alert.rules.external:write`). Or load the YAML into Prometheus
  yourself. The alerts scope to `job="space-telemetry"` — adjust
  `exporterSelector` in `config.libsonnet` if your scrape job differs.
  `SpaceTelemetryExporterAbsent` covers the case `ExporterDown` can't see: no
  `up` series at all because the pod never started.
