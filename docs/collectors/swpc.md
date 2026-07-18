# swpc collector

Space-weather metrics from **NOAA's Space Weather Prediction Center**. Unlike the
other collectors this observes the Sun and heliosphere, not the observer's local
sky, so its metrics carry **no observer label** — they are global.

## Products

Each product is fetched and the most recent observation exposed as a gauge.

| Key | Endpoint (under `services.swpc.noaa.gov`) | Metric | Unit |
|---|---|---|---|
| `kp` | `/products/noaa-planetary-k-index.json` | `swpc_planetary_k_index` | 0–9 |
| `wind` | `/products/summary/solar-wind-speed.json` | `swpc_solar_wind_speed_km_per_second` | km/s |
| `mag` | `/products/summary/solar-wind-mag-field.json` | `swpc_imf_bz_nanotesla`, `swpc_imf_bt_nanotesla` | nT |
| `f107` | `/products/summary/10cm-flux.json` | `swpc_f107_solar_radio_flux` | sfu |
| `xray` | `/json/goes/primary/xrays-1-day.json` | `swpc_goes_xray_flux_watts_per_m2` | W/m² |

## What the metrics mean

- **Planetary K-index (Kp)** — global geomagnetic activity, 0 (quiet) to 9
  (extreme storm). Kp ≥ 5 is a geomagnetic storm (aurora likely).
- **Solar wind speed** — bulk speed at L1; ~300–400 km/s ambient, 600–800+ km/s in
  high-speed streams / CMEs.
- **IMF Bz / Bt** — interplanetary magnetic field. **Bz** is the geoeffective
  component: strongly *southward* (negative) Bz couples energy into the
  magnetosphere and drives storms. **Bt** is the total field strength.
- **F10.7** — 10.7 cm solar radio flux (solar flux units), a proxy for solar
  activity and EUV heating of the upper atmosphere (affects satellite drag).
- **GOES X-ray flux** — long-band (0.1–0.8 nm) soft X-rays. Flare classes by flux:
  A < 10⁻⁷, B 10⁻⁷, C 10⁻⁶, **M 10⁻⁵**, **X 10⁻⁴** W/m².

## Health

Per product (`swpc:kp`, `swpc:wind`, `swpc:mag`, `swpc:f107`, `swpc:xray`):
`swpc_data_update_success`, `swpc_data_update_timestamp_seconds`,
`swpc_data_age_seconds`. Plus `swpc_scrape_duration_seconds`.

## Update mechanism

A daemon thread refreshes every product every `swpc_refresh_minutes` (default 5)
with conditional requests, caches the raw JSON under `<cache_dir>/swpc/`, and
parses the latest value into memory. Offline-first: on startup the last-cached
values are served immediately, and a failed refresh keeps the previous value.

Cadence note: Kp updates roughly every 3 h; solar wind and X-ray update about once
a minute at the source, so 5 minutes is a reasonable default — lower
`swpc_refresh_minutes` if you want fresher solar-wind data.

## Configuration

`swpc_enabled`, `swpc_refresh_minutes` — see [Configuration](../configuration.md).
Example: `examples/space-weather.yaml`.
