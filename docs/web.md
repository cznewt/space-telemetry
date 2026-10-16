# Web UI

Next to `/metrics` the exporter serves two pages: `/map`, a live satellite map,
and `/table`, the focus pass plan plus tables of satellites, passes, bodies and
stars. Both are plain HTML fed by the JSON feeds under `/api/` (see below).

## /map

- **Markers** at the sub-satellite points (refreshed every 15 s), **ground
  tracks** ~10 orbits ahead and **reception footprints**, filled while the
  satellite is above your horizon. The observer is the gold dot. Click a
  satellite for its altitude, elevation, sunlight and footprint.
- **Top bar**: search (filters by name and flies to the first match), labels,
  footprints, globe projection.
- **Time scrubber** (bottom): shifts the map ±1 day; positions are recomputed
  for that time.
- **Passes panel** (bottom right): the next passes over the observer, focus
  satellites first; click one to fly to it.
- **Focus satellites** (`sat_focus`) get a gold ring, a gold label and a bold
  track.

## /table

From the top: the focus **pass plan** (every pass in the lookahead window, see
[focus satellites](collectors/satellites.md#focus-satellites)), solar-system
bodies, the satellite filters, **satellites over the observer**, **upcoming
passes** and bright stars.

## Satellite filters

Both pages share one filter panel: top left on `/map`, above the satellite
tables on `/table`. The filters narrow down one set of satellites. On `/map`
that set drives the markers, labels, tracks, footprints and the passes panel;
on `/table` it drives the satellite and pass tables. Bodies, stars and the focus
pass plan are never filtered.

| Filter | What it does |
|---|---|
| **Groups** | Click a group to hide it; alt-click it (or hover → **only**) to show just that group. **▸** opens its satellite list. |
| **Satellites** | In an open group, tick or untick single satellites. **only** shows just that one; tick more to add them back. Names in grey italics are ticked but hidden by another filter. |
| **Orbit** | LEO (apogee under 2,000 km), MEO (up to GEO), GEO (about 1 rev/day, near-circular) or HEO (highly elliptical, e.g. Molniya/Tundra, or beyond GEO), from the element set. |
| **Altitude** | Current altitude from–to, log scale 200 km – 40,000 km. |
| **Radio band** | At least one active SatNOGS downlink in the band (see the table below). |
| **Mode** | At least one active downlink in that mode: the first word of the SatNOGS mode, so `BPSK PMT-A3` counts as `BPSK`. With a band picked too, one downlink must match both, e.g. 137 MHz + LRPT. |
| **Above horizon / sunlit** | Above the observer's horizon (on `/map`: at the scrubber time); in sunlight, so visible by eye from a dark sky. |
| **Pass within / peak ≥** | The next pass starts within N hours (or the satellite is up now); the next pass peaks at least X°. A geostationary satellite uses its current elevation. |
| **★ always show focus satellites** | On by default: focus satellites skip the group, orbit, altitude, band, mode and visibility filters. The search and your per-satellite ticks still apply. |

Each chip shows how many tracked satellites have that property. Picks within one
filter are OR-ed (137 MHz *or* 2 m); different filters are AND-ed.

### Radio bands

Wavelength ≈ 300 ÷ frequency in MHz, in metres. The three amateur and weather
sub-bands are matched before the wide bands.

| Chip | Frequency | Wavelength | Typical use |
|---|---|---|---|
| 137 MHz | 137–138 MHz | ≈ 2.2 m | weather pictures (Meteor LRPT) |
| 2 m | 144–148 MHz | ≈ 2 m | amateur: ISS voice, APRS, SSTV |
| 70 cm | 430–440 MHz | ≈ 69 cm | amateur: cubesats, ISS |
| HF | below 30 MHz | over 10 m | rare: the ionosphere reflects it |
| VHF | other 30–300 MHz | 1–10 m | |
| UHF | other 300–1000 MHz | 30 cm – 1 m | data collection, e.g. 401 / 466 MHz |
| L | 1–2 GHz | 15–30 cm | HRPT / AHRPT, GOES HRIT and GRB |
| S | 2–4 GHz | 7.5–15 cm | telemetry and control |
| C | 4–7 GHz | 4.3–7.5 cm | |
| X | 7–12 GHz | 2.5–4.3 cm | bulk image and science downloads |
| Ku | 12–18 GHz | 1.7–2.5 cm | |
| Ka | above 18 GHz | under 1.7 cm | very high-rate downloads |

SatNOGS uses the mode `FM` loosely for many L-, S- and X-band entries; most of
those are really digital PSK links.

### URL parameters

The filter state lives in the page URL, so a filtered view can be bookmarked or
shared, and the map ↔ table links carry it over. A page opened without
parameters restores the last filters used in that browser; **reset** clears
them.

| Parameter | Example | Meaning |
|---|---|---|
| `hg` | `hg=stations,css` | hidden groups |
| `hs` | `hs=66906` | hidden satellites (NORAD ids) |
| `only` | `only=57166,59051` | show only these NORAD ids |
| `orb` | `orb=LEO,HEO` | orbit classes |
| `amin`, `amax` | `amin=300&amax=1000` | altitude range in km |
| `band` | `band=137,l` | bands: `137`, `2m`, `70cm`, `hf`, `vhf`, `uhf`, `l`, `s`, `c`, `x`, `ku`, `ka` |
| `mode` | `mode=LRPT` | modes |
| `up`, `sun` | `up=1` | above the horizon; sunlit |
| `win` | `win=6` | next pass within 1, 3, 6, 12 or 24 hours |
| `peak` | `peak=30` | next pass peaks at least 10–75° |
| `pin` | `pin=0` | stop exempting focus satellites |
| `q` | `q=meteor` | name search |

For example:

- `/map?band=137&mode=LRPT`: only the Meteor LRPT picture feeds.
- `/table?only=57166,59051`: just METEOR-M2 3 and METEOR-M2 4.
- `/map?orb=GEO&up=1&pin=0`: the geostationary satellites above your horizon.

## JSON feeds

| Path | Payload |
|---|---|
| `/api/satellites.json` | `{satellites: [{norad, name, group, lat, lon, alt_km, elevation, sunlit, footprint_km, orbit, tx?, focus?}], observers}`. `orbit` is LEO/MEO/GEO/HEO and `tx` the distinct active downlinks as `[[mhz, mode], …]`; a station marker (ISS, CSS) carries all of its modules' downlinks. `?t=<minutes>` shifts the time by up to ±1440. |
| `/api/tracks.json` | `{tracks: [{norad, name, group, alt, track: [[lat, lon], …], focus?}]}` |
| `/api/passes.json` | `{passes: [{norad, name, group, aos, los, max_elev, duration_s, footprint_km, up_now, focus}]}`, the next pass of each satellite |
| `/api/focus.json` | the focus pass plan (see [focus satellites](collectors/satellites.md#focus-satellites)) |
| `/api/bodies.json`, `/api/stars.json` | the bodies and bright-star tables |
