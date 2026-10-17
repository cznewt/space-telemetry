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

### Forecast products

Two more products feed the [`/forecast`](../web.md#forecast) page and
`/api/forecast.json`. They are not exposed as metrics.

| Key | Endpoint (under `services.swpc.noaa.gov`) | Gives |
|---|---|---|
| `kp_forecast` | `/products/noaa-planetary-k-index-forecast.json` | 3-hourly Kp, observed and predicted about 3 days ahead; `/forecast` uses each day's largest |
| `outlook_27d` | `/text/27-day-outlook.txt` | NOAA's weekly 27-day outlook: per day the largest Kp, the planetary A index and the 10.7 cm radio flux |

They refresh at most hourly, whatever `space_weather_refresh_minutes` says.

## Signals

Every metric this collector emits (rendered from `signals.yaml`). The `source`
label on the data-pipeline metrics is the product key (`kp`, `wind`, `mag`,
`f107`, `xray`, and the forecast products `kp_forecast`, `outlook_27d`).

<!-- signals:start -->
★ = on the observ-lib dashboard/alerts.

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
