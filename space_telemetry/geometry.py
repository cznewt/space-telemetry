"""Shared topocentric geometry.

``altaz`` works for any ephemeris target (Sun/Moon/planets). The satellites
family will add a variant for ``EarthSatellite`` targets (which use
``(satellite - topos).at(t)`` rather than ``.observe()``).
"""

from __future__ import annotations


def altaz(site, t, target):
    """Return apparent ``(altitude_deg, azimuth_deg, distance_m)`` of *target*
    seen from *site* at time *t*.

    *site* must be a Skyfield vector sum ``ephemeris['earth'] + topos`` — i.e. a
    position on Earth's surface. Azimuth is measured clockwise from north.
    """
    alt, az, distance = site.at(t).observe(target).apparent().altaz()
    return alt.degrees, az.degrees, distance.m
