"""Lunar phase / illumination helpers."""

from __future__ import annotations

from skyfield import almanac


def illuminated_fraction(eph, t) -> float:
    """Fraction of the Moon's disc that is lit (0..1)."""
    return float(almanac.fraction_illuminated(eph, "moon", t))


def phase_degrees(eph, t) -> float:
    """Moon phase angle in degrees (0=new, 90=first quarter, 180=full, 270=last)."""
    return float(almanac.moon_phase(eph, t).degrees)
