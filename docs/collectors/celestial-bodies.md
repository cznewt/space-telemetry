# sky › celestial bodies (stars)

Positions of bright stars for each observer, from a small built-in catalog. A
star's ICRS/J2000 right ascension and declination are effectively fixed, so this
family needs **no ephemeris and no network** — positions are computed 100%
offline via Skyfield `Star` targets.

## Catalog

`stars:` selects by name from the built-in catalog (default is the first eight):

| Name | RA (h) | Dec (°) | mag | | Name | RA (h) | Dec (°) | mag |
|---|---|---|---|---|---|---|---|---|
| sirius | 6.75 | −16.72 | −1.46 | | altair | 19.85 | +8.87 | 0.77 |
| canopus | 6.40 | −52.70 | −0.74 | | aldebaran | 4.60 | +16.51 | 0.85 |
| arcturus | 14.26 | +19.18 | −0.05 | | antares | 16.49 | −26.43 | 1.09 |
| vega | 18.62 | +38.78 | 0.03 | | spica | 13.42 | −11.16 | 1.04 |
| capella | 5.28 | +46.00 | 0.08 | | pollux | 7.76 | +28.03 | 1.14 |
| rigel | 5.24 | −8.20 | 0.13 | | fomalhaut | 22.96 | −29.62 | 1.16 |
| procyon | 7.66 | +5.23 | 0.34 | | deneb | 20.69 | +45.28 | 1.25 |
| betelgeuse | 5.92 | +7.41 | 0.50 | | regulus | 10.14 | +11.97 | 1.35 |
| achernar | 1.63 | −57.24 | 0.46 | | polaris | 2.53 | +89.26 | 1.98 |

## Metrics

Labels `star,observer`.

| Metric | Meaning |
|---|---|
| `star_altitude_degrees` | apparent altitude above the horizon |
| `star_azimuth_degrees` | azimuth, degrees clockwise from north |
| `star_above_horizon` | 1 if above `min_elevation_deg` |
| `star_magnitude` | apparent visual magnitude (catalog constant) |
| `star_next_rise_timestamp_seconds` | next rise (UNIX seconds) |
| `star_next_set_timestamp_seconds` | next set (UNIX seconds) |

## Notes

- Positions use ICRS/J2000 without proper motion — negligible for altitude/azimuth
  and rise/set, which is all this collector reports.
- Circumpolar stars (e.g. Polaris at high northern latitudes) never set, so their
  rise/set metrics are absent.
- **Adding stars:** extend `STAR_CATALOG` in
  `space_telemetry/collectors/sky/celestial_bodies/stars.py` with
  `(name, ra_hours, dec_degrees, magnitude)`, then list the name in `stars:`.
