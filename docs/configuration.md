# Configuration

Configuration comes from three layers, highest priority first:

1. **Environment variables** — `SPACE_TELEMETRY_<FIELD>` (uppercase field name)
2. **YAML file** — `space-telemetry.yaml` in the working directory, or the path in
   `$SPACE_TELEMETRY_CONFIG`. Skipped entirely if absent.
3. **Built-in defaults**

So an env var always overrides the YAML file, and the YAML file overrides the
defaults. A `.env` file (dotenv) is also read, sitting between env and YAML.

List fields (`bodies`, `stars`, `sat_groups`, `sat_watchlist`) accept either a
real YAML list or a comma-separated string in env vars
(e.g. `SPACE_TELEMETRY_STARS=vega,sirius`).

## Observers

Configure **one** observer with the `observer_*` fields, or **several** with the
`observers` list (which takes precedence when non-empty). Each sky and satellite
metric is labelled `observer=<name>`; SWPC metrics are global and carry no
observer label.

```yaml
# single
observer_name: prague
observer_lat: 50.0755
observer_lon: 14.4378
observer_elevation_m: 200

# multiple (overrides the single fields above)
observers:
  - {name: prague, latitude_deg: 50.0755, longitude_deg: 14.4378, elevation_m: 200}
  - {name: brno,   latitude_deg: 49.1951, longitude_deg: 16.6068, elevation_m: 237}
```

Via env, `observers` is a JSON string:

```bash
SPACE_TELEMETRY_OBSERVERS='[{"name":"prague","latitude_deg":50.07,"longitude_deg":14.44}]'
```

> `elevation_m` is the observer's altitude in **metres above sea level** — not to
> be confused with the `*_altitude_degrees` metrics, which are angles above the
> horizon.

## Field reference

### Observer
| Field | Default | Notes |
|---|---|---|
| `observer_name` | `observer` | label value |
| `observer_lat` / `observer_lon` | `50.0755` / `14.4378` | degrees, +N / +E |
| `observer_elevation_m` | `200` | metres above sea level |
| `observers` | `[]` | list of `{name, latitude_deg, longitude_deg, elevation_m}` |

### Sky
| Field | Default | Notes |
|---|---|---|
| `bodies` | sun,moon,mercury,venus,mars,jupiter,saturn | see [solar_system_bodies](collectors/solar_system_bodies.md) |
| `stars` | sirius,vega,arcturus,capella,rigel,betelgeuse,aldebaran,polaris | see [celestial_bodies](collectors/celestial_bodies.md) |
| `min_elevation_deg` | `0` | horizon mask for `above_horizon`, rise/set, satellite passes |
| `ephemeris` | `de421.bsp` | JPL kernel (downloaded once) |
| `cache_dir` | `data` | where kernels + satellite/swpc caches live |
| `pass_cache_ttl_s` | `300` | how long body/star rise-set results are reused |

### Satellites
| Field | Default | Notes |
|---|---|---|
| `sat_enabled` | `true` | turn the whole collector off with `false` |
| `sat_groups` | `[stations]` | CelesTrak GROUPs to track |
| `sat_watchlist` | `[]` | extra NORAD ids, always tracked |
| `celestrak_format` | `tle` | `tle` or `json` (OMM) |
| `tle_refresh_hours` | `8` | orbit refresh cadence |
| `transmitter_refresh_hours` | `168` | SatNOGS transmitter cadence |
| `satnogs_satellites_refresh_hours` | `168` | SatNOGS metadata cadence |
| `pass_lookahead_hours` | `24` | next-pass search window |
| `sat_pass_cache_ttl_s` | `60` | how long per-satellite pass results are reused |

### Space weather
| Field | Default | Notes |
|---|---|---|
| `space_weather_enabled` | `true` | turn space weather off with `false` |
| `space_weather_refresh_minutes` | `5` | product refresh cadence |

### Serving + HTTP client
| Field | Default | Notes |
|---|---|---|
| `host` / `port` | `0.0.0.0` / `9110` | metrics bind address |
| `otlp_endpoint` | _unset_ | if set, also push metrics via OTLP (needs the `otel` extra) |
| `http_timeout_s` | `30` | timeout for updater fetches |
| `user_agent` | `space-telemetry/0.1 …` | User-Agent for CelesTrak/SatNOGS/SWPC |

## Samples

Ready-to-run YAML in `examples/`: `single-observer.yaml`, `multi-observer.yaml`,
`all-sky-offline.yaml`, `weather-satellites.yaml`, `space-weather.yaml`.
