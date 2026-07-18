# sky collector

The `sky` collector reports the **local sky above each observer** — where things
are right now relative to the ground station. It has two position families that
share one geometry/passes core:

- **[solar-system bodies](solar-system-bodies.md)** — Sun, Moon, planets, from a
  JPL `.bsp` ephemeris.
- **[celestial bodies](celestial-bodies.md)** — bright stars, from a built-in
  catalog.

Both are computed with Skyfield: for a target `T` seen from a site
(`ephemeris['earth'] + wgs84.latlon(...)`) at time `t`,

```
alt, az, distance = site.at(t).observe(T).apparent().altaz()
```

Rise/set times come from `skyfield.almanac.risings_and_settings` searched over the
next 24 h. One `SkySampler` is built per observer; the collector loops observers
and labels every series `observer=<name>`.

## Shared behaviour

- **Offline.** After the one-time ephemeris download the whole collector runs with
  no network. Stars need no download at all.
- **Horizon mask.** `min_elevation_deg` sets the boundary for `*_above_horizon`
  and the rise/set search (e.g. `10` to ignore the murky low sky).
- **Caching.** Fast-moving values (alt/az/distance) are recomputed every scrape;
  slow rise/set values are cached for `pass_cache_ttl_s` (default 300 s).

## Shared metrics

| Metric | Labels | Meaning |
|---|---|---|
| `sky_observer_info` | `observer,latitude_deg,longitude_deg,elevation_m` | observer location (value 1) |
| `sky_scrape_duration_seconds` | — | time to build the sky snapshot for a scrape |

See the two sub-pages for `body_*` / `moon_*` and `star_*` metrics.

## Configuration

`bodies`, `stars`, `min_elevation_deg`, `ephemeris`, `cache_dir`,
`pass_cache_ttl_s` — see [Configuration](../configuration.md).
