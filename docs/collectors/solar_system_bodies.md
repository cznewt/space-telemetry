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

## Signals

Every metric this collector emits (rendered from `signals.yaml`):

<!-- signals:start -->
★ = on the observ-lib dashboard/alerts.

| Signal | Description | Unit | Range | Labels |
|---|---|---|---|---|
| `body_altitude_degrees` ★ | Apparent altitude of the body above the horizon. | degrees | -90 … 90 | `body`, `observer` |
| `body_azimuth_degrees` | Apparent azimuth, clockwise from north. | degrees | 0 … 360 | `body`, `observer` |
| `body_distance_meters` | Distance from the observer to the body. | metres | ~3.6e8 (Moon) … ~6e12 (Neptune) | `body`, `observer` |
| `body_above_horizon` ★ | 1 if the body is above the horizon mask, else 0. | boolean | 0 or 1 | `body`, `observer` |
| `body_next_rise_timestamp_seconds` | Next rise time (absent if none within the search window). | unix seconds | >= now | `body`, `observer` |
| `body_next_set_timestamp_seconds` | Next set time (absent if none within the search window). | unix seconds | >= now | `body`, `observer` |
| `moon_illuminated_fraction` ★ | Fraction of the lunar disc that is lit. | fraction | 0 … 1 | `observer` |
| `moon_phase_degrees` ★ | Moon phase angle (0=new, 90=first quarter, 180=full, 270=last). | degrees | 0 … 360 | `observer` |
| `observer_info` | Observer location (value is always 1; detail is in the labels). | info | 1 | `observer`, `latitude_deg`, `longitude_deg`, `elevation_m` |
| `body_scrape_duration_seconds` | Time spent building the solar-system-body snapshot for a scrape. | seconds | >= 0 (typ. < 0.05) | — |
<!-- signals:end -->

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
