"""Solar-system body collector: positions from an offline JPL .bsp ephemeris.

No network and no updates — the ephemeris is downloaded once and is valid for
the kernel's whole span (de421: 1900-2050). Uses the shared geometry/passes
helpers; ``sampler`` produces a BodySnapshot per observer, ``collector`` emits it.
"""
