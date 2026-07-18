"""Built-in bright-star catalog (ICRS/J2000). Offline, no ephemeris required."""

from __future__ import annotations

# name, right ascension (hours), declination (degrees), apparent visual magnitude
STAR_CATALOG = [
    ("sirius", 6.7525, -16.7161, -1.46),
    ("canopus", 6.3992, -52.6957, -0.74),
    ("arcturus", 14.2610, 19.1825, -0.05),
    ("vega", 18.6156, 38.7837, 0.03),
    ("capella", 5.2782, 45.9980, 0.08),
    ("rigel", 5.2423, -8.2016, 0.13),
    ("procyon", 7.6550, 5.2250, 0.34),
    ("betelgeuse", 5.9195, 7.4071, 0.50),
    ("achernar", 1.6286, -57.2367, 0.46),
    ("altair", 19.8464, 8.8683, 0.77),
    ("aldebaran", 4.5987, 16.5093, 0.85),
    ("antares", 16.4901, -26.4320, 1.09),
    ("spica", 13.4199, -11.1613, 1.04),
    ("pollux", 7.7553, 28.0262, 1.14),
    ("fomalhaut", 22.9608, -29.6222, 1.16),
    ("deneb", 20.6905, 45.2803, 1.25),
    ("regulus", 10.1395, 11.9672, 1.35),
    ("polaris", 2.5302, 89.2641, 1.98),
]

_MAGNITUDE = {name: mag for name, _ra, _dec, mag in STAR_CATALOG}


def star_targets(names: set[str] | None = None) -> dict:
    """Return ``{name: (Star, magnitude)}`` for the requested star names.

    Unknown names are ignored. ``names=None`` returns the whole catalog.
    """
    from skyfield.api import Star

    out: dict[str, tuple] = {}
    for name, ra_hours, dec_degrees, magnitude in STAR_CATALOG:
        if names is None or name in names:
            out[name] = (Star(ra_hours=ra_hours, dec_degrees=dec_degrees), magnitude)
    return out


def magnitude(name: str) -> float | None:
    return _MAGNITUDE.get(name)
