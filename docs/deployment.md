# Deployment

## Run directly

```bash
pip install -e .              # add .[otel] for the OTLP push path
python -m space_telemetry     # or the console script: space-telemetry
```

The first run downloads the ephemeris kernel (`de421.bsp`, ~17 MB) into
`cache_dir`. After that the sky collectors are fully offline; the satellites and
swpc updaters fetch in the background.

## Docker Compose

`docker compose up -d --build` starts three services:

| Service | Port | Notes |
|---|---|---|
| `exporter` | 9110 | this exporter; reads `space-telemetry.example.yaml`, caches into the `telemetry-data` named volume |
| `prometheus` | 9090 | scrapes `exporter:9110/metrics` every 15 s (`deploy/prometheus.yml`) |
| `grafana` | 3000 | anonymous admin; provisioned datasource + dashboard "Space Telemetry — Sky" |

The exporter runs from a **named volume** (`telemetry-data`) rather than a host
bind-mount, so the container manages its own cache and never changes ownership of
files in your working tree. Configuration is a read-only bind-mount of the YAML
file:

```yaml
volumes:
  - telemetry-data:/app/data
  - ./space-telemetry.example.yaml:/app/space-telemetry.yaml:ro
```

Edit the YAML and `docker compose restart exporter` to reconfigure.

## Prometheus

The exporter is a standard pull target at `/metrics` (default Prometheus path):

```yaml
scrape_configs:
  - job_name: space-telemetry-sky
    static_configs:
      - targets: ["exporter:9110"]
```

## Grafana

`deploy/grafana/provisioning/` auto-provisions a Prometheus datasource (uid
`prometheus`) and the dashboard in `deploy/grafana/dashboards/sky.json` (bodies,
Moon phase, satellite passes/altitude, SWPC Kp / solar wind / Bz / X-ray, star
altitude). The dashboards directory is mounted, so edits appear within ~30 s.

## OpenTelemetry (OTLP push)

Set `otlp_endpoint` (and install the `otel` extra). The same per-observer
snapshot feeds an OTLP push exporter alongside the Prometheus pull path:

```bash
pip install -e .[otel]
SPACE_TELEMETRY_OTLP_ENDPOINT=http://otel-collector:4317 python -m space_telemetry
```

If the OpenTelemetry packages are missing, the exporter logs and continues with
Prometheus only.

## Health

`/healthz` (and `/health`) return `200 {"status":"ok"}`. The container's
`HEALTHCHECK` polls `/healthz`.

## Cardinality

Series ≈ (bodies + stars + tracked satellites × transmitters) × observers. Keep
it sane by:

- tracking a **watchlist** (`sat_watchlist`) plus small `sat_groups` rather than
  large groups like `active` (~10 k satellites);
- trimming `stars` / `bodies` you don't need;
- remembering that each observer multiplies the sky + satellite series (SWPC does
  not multiply — it is global).
