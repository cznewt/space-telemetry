# satellites collector

Tracks Earth-orbiting satellites for each observer: where they are in the sky,
their sub-point and velocity, upcoming passes, and — by joining a radio database —
their transmitters and the live Doppler shift on each downlink.

## Data sources

| Source | Endpoint | Gives |
|---|---|---|
| CelesTrak GP | `celestrak.org/NORAD/elements/gp.php?GROUP=<g>&FORMAT=<tle\|json>` | orbits (TLE or OMM) per group |
| SatNOGS DB | `db.satnogs.org/api/transmitters/?format=json` | downlink/uplink, mode, baud, status |
| SatNOGS DB | `db.satnogs.org/api/satellites/?format=json` | name + operational status |

The two datasets are merged on the **NORAD catalog number**. A satellite that
appears in several `sat_groups` accumulates all of them. Orbits are turned into
Skyfield `EarthSatellite` objects (SGP4/SDP4); OMM JSON is supported too
(`celestrak_format: json`).

## Tracked set & cardinality

Live geometry is computed only for the **tracked set** =
`sat_watchlist` ∪ (satellites in the configured `sat_groups`). The catalog itself
can be much larger; only tracked satellites emit `satellite_*` geometry series.

> Keep `sat_groups` small (e.g. `stations`, `weather`, `amateur`) and lean on the
> watchlist. Tracking a group like `active` (~10 000 satellites) × transmitters ×
> observers is a lot of series. See [Deployment → Cardinality](../deployment.md#cardinality).

Common CelesTrak groups: `stations`, `visual`, `active`, `weather`, `noaa`,
`goes`, `resource`, `sarsat`, `argos`, `amateur`, `cubesat`, `satnogs`,
`starlink`, `oneweb`, `galileo`, `beidou`, `gps-ops`, `glo-ops`, `science`,
`geodetic`, `engineering`, `education`, `military`.

## What is computed

For each tracked satellite from the observer, at scrape time:

- **Geometry** — `(satellite - topos).at(t).altaz()` gives elevation, azimuth,
  slant range. Range rate is the radial component of the topocentric velocity
  (`r·v / |r|`), which drives Doppler.
- **Sub-point** — latitude, longitude, altitude of the point directly below the
  satellite (`wgs84.subpoint`).
- **Sunlit** — whether the satellite is in sunlight (`is_sunlit`, using the same
  ephemeris as the solar-system-body collector).
- **Passes** — `EarthSatellite.find_events` over `pass_lookahead_hours` yields the
  next AOS, LOS and peak elevation above `min_elevation_deg`. Cached per satellite
  for `sat_pass_cache_ttl_s`.
- **Doppler** — for each transmitter downlink `f`: `Δf = −(range_rate / c)·f`
  (positive when approaching).

## Signals

Every metric this collector emits (rendered from `signals.yaml`). The `source`
label on the data-pipeline metrics is `celestrak:<group>`, `satnogs:transmitters`,
or `satnogs:satellites`.

<!-- signals:start -->
★ = on the observ-lib dashboard/alerts.

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
| `satellite_info` | Static per-satellite info (value always 1); the group label maps each satellite to its family (iss, css, weather, noaa, goes, stations). | info | 1 | `norad`, `name`, `group` |
| `satellite_catalog_size` | Number of satellites in the offline catalog. | count | >= 0 | — |
| `satellite_catalog_with_transmitters` | Catalog satellites that have at least one transmitter. | count | >= 0 | — |
| `satellite_tracked_count` ★ | Satellites tracked live for the observer (watchlist ∪ groups). | count | >= 0 | `observer` |
| `satellite_data_update_success` ★ | 1 if the source's last fetch attempt succeeded, else 0. | boolean | 0 or 1 | `source` |
| `satellite_data_update_timestamp_seconds` | Last successful fetch time, per source. | unix seconds | <= now | `source` |
| `satellite_data_age_seconds` | Seconds since the source's last successful fetch. | seconds | >= 0 | `source` |
| `satellite_data_fetch_duration_seconds` | Duration of the source's last fetch. | seconds | >= 0 | `source` |
| `satellite_scrape_duration_seconds` ★ | Time spent building the satellite snapshot for a scrape. | seconds | >= 0 | — |
<!-- signals:end -->

## Update mechanism

A daemon thread refreshes each source when it is **due**
(`tle_refresh_hours`, `transmitter_refresh_hours`,
`satnogs_satellites_refresh_hours`) using conditional requests
(`If-None-Match` / `If-Modified-Since` → `304` when unchanged), writes atomically
to `<cache_dir>/satellites/`, and rebuilds the catalog **as each source lands** —
so orbits (small) appear without waiting for the multi-MB transmitter download on
a cold cache. On failure the last-good cache is kept; scrapes never block on the
network, and on startup the exporter serves whatever is already cached.

Be a good citizen: CelesTrak asks clients to cache and refresh only a few times a
day (the defaults do). A real `user_agent` is sent.

## Configuration

`sat_enabled`, `sat_groups`, `sat_watchlist`, `celestrak_format`,
`tle_refresh_hours`, `transmitter_refresh_hours`,
`satnogs_satellites_refresh_hours`, `pass_lookahead_hours`,
`sat_pass_cache_ttl_s` — see [Configuration](../configuration.md). Example:
`examples/weather-satellites.yaml`.
