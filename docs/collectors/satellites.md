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

## Metrics

Per tracked satellite — labels `norad,name,observer`:

| Metric | Meaning |
|---|---|
| `satellite_elevation_degrees` | elevation above the horizon |
| `satellite_azimuth_degrees` | azimuth, clockwise from north |
| `satellite_range_meters` | slant range observer→satellite |
| `satellite_range_rate_meters_per_second` | range rate (+receding); drives Doppler |
| `satellite_subpoint_latitude_degrees` | sub-satellite point latitude |
| `satellite_subpoint_longitude_degrees` | sub-satellite point longitude |
| `satellite_altitude_meters` | height above the ellipsoid |
| `satellite_velocity_meters_per_second` | orbital speed |
| `satellite_above_horizon` | 1 if above the horizon mask |
| `satellite_sunlit` | 1 if in sunlight |
| `satellite_tle_epoch_timestamp_seconds` | element-set epoch (UNIX s) |
| `satellite_tle_age_seconds` | age of the element set |
| `satellite_next_pass_aos_timestamp_seconds` | next pass AOS (UNIX s) |
| `satellite_next_pass_los_timestamp_seconds` | next pass LOS (UNIX s) |
| `satellite_next_pass_max_elevation_degrees` | next pass peak elevation |

Per transmitter — labels `norad,uuid,mode,status` (frequencies are observer-independent):

| Metric | Meaning |
|---|---|
| `satellite_transmitter_downlink_hertz` | downlink frequency |
| `satellite_transmitter_uplink_hertz` | uplink frequency |
| `satellite_transmitter_baud` | symbol rate |
| `satellite_doppler_hertz` (labels `norad,uuid,observer`) | Doppler shift on the downlink |

Catalog & pipeline health:

| Metric | Labels | Meaning |
|---|---|---|
| `satellite_catalog_size` | — | satellites in the offline catalog |
| `satellite_catalog_with_transmitters` | — | catalog sats with ≥1 transmitter |
| `satellite_tracked_count` | `observer` | tracked satellites per observer |
| `satellite_data_update_success` | `source` | 1 if the last fetch succeeded |
| `satellite_data_update_timestamp_seconds` | `source` | last successful fetch (UNIX s) |
| `satellite_data_age_seconds` | `source` | seconds since last fetch |
| `satellite_data_fetch_duration_seconds` | `source` | last fetch duration |

where `source` is `celestrak:<group>`, `satnogs:transmitters`, or `satnogs:satellites`.

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

## TLE freshness

`satellite_tle_age_seconds` is `now − epoch`. SGP4 accuracy degrades over days, so
alert if it grows large (e.g. `> 3` days) — it means the updater hasn't refreshed.

## Configuration

`sat_enabled`, `sat_groups`, `sat_watchlist`, `celestrak_format`,
`tle_refresh_hours`, `transmitter_refresh_hours`,
`satnogs_satellites_refresh_hours`, `pass_lookahead_hours`,
`sat_pass_cache_ttl_s` — see [Configuration](../configuration.md). Example:
`examples/weather-satellites.yaml`.
