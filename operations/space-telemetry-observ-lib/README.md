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

## Use

- **Dashboard**: push it to Grafana with `just grafana-push` (set `GRAFANA_URL`
  + `GRAFANA_TOKEN` [+ `GRAFANA_NAMESPACE`] in `.env` — see `.env.example`), or
  import `dashboards/space-telemetry.json` manually. It expects `datasource`,
  `job`, and `observer` template variables.
- **Alerts / rules**: load the YAML into Prometheus/Mimir (or Grafana-managed
  rules). The alerts scope to `job="space-telemetry"` — adjust `exporterSelector`
  in `config.libsonnet` if your scrape job differs.
