# space_weather collector

Space-weather metrics from **NOAA's Space Weather Prediction Center (SWPC)**.
Unlike the other collectors this observes the Sun and heliosphere, not the
observer's local sky, so its metrics carry **no observer label** — they are global.

## Products

Each product is fetched and its most recent observation exposed as a gauge.

| Key | Endpoint (under `services.swpc.noaa.gov`) | Metric | Unit |
|---|---|---|---|
| `kp` | `/products/noaa-planetary-k-index.json` | `space_weather_planetary_k_index` | 0–9 |
| `wind` | `/products/summary/solar-wind-speed.json` | `space_weather_solar_wind_speed_km_per_second` | km/s |
| `mag` | `/products/summary/solar-wind-mag-field.json` | `space_weather_imf_bz_nanotesla`, `space_weather_imf_bt_nanotesla` | nT |
| `f107` | `/products/summary/10cm-flux.json` | `space_weather_f107_solar_radio_flux` | sfu |
| `xray` | `/json/goes/primary/xrays-1-day.json` | `space_weather_goes_xray_flux_watts_per_m2` | W/m² |

## Metrics

| Metric | Meaning |
|---|---|
| `space_weather_planetary_k_index` | Planetary K-index, 0 (quiet) – 9 (extreme storm); Kp ≥ 5 is a geomagnetic storm |
| `space_weather_solar_wind_speed_km_per_second` | Solar-wind bulk speed at L1 (~300–400 ambient, 600–800+ in high-speed streams) |
| `space_weather_imf_bz_nanotesla` | IMF Bz (GSM); strongly **southward/negative** Bz drives storms |
| `space_weather_imf_bt_nanotesla` | IMF total field strength Bt |
| `space_weather_f107_solar_radio_flux` | 10.7 cm solar radio flux (sfu); proxy for solar activity / upper-atmosphere heating |
| `space_weather_goes_xray_flux_watts_per_m2` | GOES long-band (0.1–0.8 nm) X-ray flux; flare classes A<10⁻⁷, B, C, **M 10⁻⁵**, **X 10⁻⁴** |

Health, per product (`source` ∈ `kp`, `wind`, `mag`, `f107`, `xray`):

| Metric | Labels | Meaning |
|---|---|---|
| `space_weather_data_update_success` | `source` | 1 if the last fetch succeeded |
| `space_weather_data_update_timestamp_seconds` | `source` | last successful fetch (UNIX s) |
| `space_weather_data_age_seconds` | `source` | seconds since last fetch |
| `space_weather_scrape_duration_seconds` | — | snapshot build time per scrape |

## Update mechanism

A daemon thread refreshes every product every `space_weather_refresh_minutes`
(default 5) with conditional requests, caches the raw JSON under
`<cache_dir>/space_weather/`, and parses the latest value into memory.
Offline-first: on startup the last-cached values are served immediately, and a
failed refresh keeps the previous value.

Cadence note: Kp updates roughly every 3 h; solar wind and X-ray update about once
a minute at the source, so 5 minutes is a reasonable default — lower
`space_weather_refresh_minutes` for fresher solar-wind data.

## Configuration

`space_weather_enabled`, `space_weather_refresh_minutes` — see
[Configuration](../configuration.md). Example: `examples/space-weather.yaml`.

## Dashboard signals

The [observ-lib](https://github.com/cznewt/space-telemetry/tree/main/operations/space-telemetry-observ-lib)
dashboard and alerts use these signals for this collector (queries rendered from
the mixin sources):

<!-- signals:start -->
| Signal | Query | Unit |
|---|---|---|
| Planetary Kp | `space_weather_planetary_k_index{job=~"$job"}` | short |
| Solar wind speed | `space_weather_solar_wind_speed_km_per_second{job=~"$job"}` | short |
| IMF Bz | `space_weather_imf_bz_nanotesla{job=~"$job"}` | short |
| GOES X-ray flux | `space_weather_goes_xray_flux_watts_per_m2{job=~"$job"}` | short |
| F10.7 flux | `space_weather_f107_solar_radio_flux{job=~"$job"}` | short |
<!-- signals:end -->
