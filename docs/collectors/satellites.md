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
  ephemeris as the sky collector).
- **Passes** — `EarthSatellite.find_events` over `pass_lookahead_hours` yields the
  next AOS, LOS and peak elevation above `min_elevation_deg`. Cached per satellite
  for `sat_pass_cache_ttl_s`.
- **Doppler** — for each transmitter downlink `f`: `Δf = −(range_rate / c)·f`
  (positive when approaching).

## Metrics

Per tracked satellite — labels `norad,name,observer`:

`satellite_elevation_degrees`, `satellite_azimuth_degrees`,
`satellite_range_meters`, `satellite_range_rate_meters_per_second`,
`satellite_subpoint_latitude_degrees`, `satellite_subpoint_longitude_degrees`,
`satellite_altitude_meters`, `satellite_velocity_meters_per_second`,
`satellite_above_horizon`, `satellite_sunlit`,
`satellite_tle_epoch_timestamp_seconds`, `satellite_tle_age_seconds`,
`satellite_next_pass_aos_timestamp_seconds`,
`satellite_next_pass_los_timestamp_seconds`,
`satellite_next_pass_max_elevation_degrees`.

Per transmitter — labels `norad,uuid,mode,status` (observer-independent):
`satellite_transmitter_downlink_hertz`, `satellite_transmitter_uplink_hertz`,
`satellite_transmitter_baud`; and `satellite_doppler_hertz{norad,uuid,observer}`.

Catalog & pipeline health:
`satellite_catalog_size`, `satellite_catalog_with_transmitters`,
`satellite_tracked_count{observer}`, and per source
(`celestrak:<group>`, `satnogs:transmitters`, `satnogs:satellites`):
`satellite_data_update_success`, `satellite_data_update_timestamp_seconds`,
`satellite_data_age_seconds`, `satellite_data_fetch_duration_seconds`.

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
