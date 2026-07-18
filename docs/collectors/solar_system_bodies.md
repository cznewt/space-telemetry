# solar_system_bodies collector

Positions of the Sun, Moon and planets for each observer, from a JPL Development
Ephemeris (SPICE `.bsp` kernel). These bodies can't be tracked with TLEs — their
motion is a high-precision analytical/ numerical model that is valid for the
kernel's whole span with **no updates ever**; the kernel is downloaded once into
`cache_dir` and then used entirely offline.

## Ephemeris kernels

| Kernel | Span | Size | Notes |
|---|---|---|---|
| `de421.bsp` | 1900–2050 | ~17 MB | default; plenty for live telemetry |
| `de440s.bsp` | 1849–2150 | ~32 MB | "small" modern kernel, wider span |
| `de440.bsp` | 1550–2650 | ~114 MB | full modern kernel |

Set with `ephemeris:`. Outer planets are resolved via their barycenter segment
automatically, so `jupiter`, `saturn`, `uranus`, `neptune`, `pluto` all work with
the compact kernels.

## Bodies

`bodies:` accepts any name present in the kernel:
`sun`, `moon`, `mercury`, `venus`, `mars`, `jupiter`, `saturn`, `uranus`,
`neptune`, `pluto`. Default is the seven classically visible bodies.

## Metrics

Labels `body,observer` unless noted.

| Metric | Meaning |
|---|---|
| `body_altitude_degrees` | apparent altitude above the horizon |
| `body_azimuth_degrees` | azimuth, degrees clockwise from north |
| `body_distance_meters` | observer → body distance |
| `body_above_horizon` | 1 if above `min_elevation_deg` |
| `body_next_rise_timestamp_seconds` | next rise (UNIX seconds) |
| `body_next_set_timestamp_seconds` | next set (UNIX seconds) |
| `moon_illuminated_fraction` | (labels `observer`) lit fraction of the lunar disc, 0..1 |
| `moon_phase_degrees` | (labels `observer`) 0 = new, 90 = first quarter, 180 = full, 270 = last |
| `observer_info` | (labels `observer,latitude_deg,longitude_deg,elevation_m`) observer location, value 1 |
| `body_scrape_duration_seconds` | (no labels) snapshot build time per scrape |

## Handy derivations

- **Day / night / twilight** — from the Sun's altitude:
  `body_altitude_degrees{body="sun"}` > 0 is day, < −6 / −12 / −18 are civil /
  nautical / astronomical twilight boundaries.
- **Planet visibility** — `body_above_horizon{body="jupiter"} == 1` and the Sun
  below the horizon.

## Notes

- Values are physically exact: e.g. the Moon reports ~384 000 km, Saturn ~1.4×10⁹
  km, the Sun ~1.0 AU (≈1.5×10¹¹ m).
- Rise/set can be `None` (metric absent) for circumpolar bodies or when an event
  doesn't occur in the next 24 h.
