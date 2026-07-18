# space-telemetry documentation

A Prometheus / OpenTelemetry exporter for space telemetry — the sky above your
ground station(s) and the space weather around Earth. It runs a set of sibling
**collectors** that all publish to one `/metrics` endpoint.

## Contents

- **[Configuration](configuration.md)** — env vars, YAML files, precedence, multiple observers
- **[Deployment](deployment.md)** — Docker Compose, Prometheus, Grafana, OTLP, cardinality
- **Collectors**
  - **[solar_system_bodies](collectors/solar_system_bodies.md)** — Sun, Moon, planets (ephemeris)
  - **[celestial_bodies](collectors/celestial_bodies.md)** — bright stars (offline catalog)
  - **[satellites](collectors/satellites.md)** — TLE/OMM → SGP4 tracking + transmitters
  - **[space_weather](collectors/space_weather.md)** — NOAA space weather
- **Config samples** — ready-to-run YAML in `examples/` (`SPACE_TELEMETRY_CONFIG=examples/…`)

## Collectors at a glance

| Collector | Metric prefix | Source | Network | Observer label |
|---|---|---|---|---|
| `solar_system_bodies` | `body_` / `moon_` | JPL `.bsp` ephemeris | once (kernel) | yes |
| `celestial_bodies` | `star_` | built-in star catalog | none | yes |
| `satellites` | `satellite_` | CelesTrak + SatNOGS | background updater | yes |
| `space_weather` | `space_weather_` | NOAA SWPC | background updater | no (global) |

## How it fits together

```
sources ─▶ cache (offline, last-good) ─▶ sampler / provider ─▶ collector ─┐
   ▲ updater (background, "due"-based)                                      ├─▶ registry ─▶ /metrics
   └───────────── ephemeris / star catalog (no network) ───────────────────┘
```

Every scrape reads local state only; background updaters refresh the cache and
keep the last-good copy on failure, so `/metrics` never blocks on the network.
Computation (positions, passes, Doppler) is separate from export, so the
Prometheus pull path and the optional OTLP push path read the same snapshot.

## HTTP endpoints

| Path | Purpose |
|---|---|
| `/` | human info page (append `?format=json` for JSON) |
| `/metrics` | Prometheus exposition |
| `/status` | JSON status: observers, collectors, source health |
| `/health`, `/healthz` | liveness (`{"status":"ok"}`) |

## Run

```bash
python -m space_telemetry                       # env vars or ./space-telemetry.yaml
SPACE_TELEMETRY_CONFIG=examples/multi-observer.yaml python -m space_telemetry
docker compose up -d --build                     # exporter + Prometheus + Grafana
```
