"""Solar-system body family: positions from an offline JPL .bsp ephemeris.

No network and no updates — the ephemeris is downloaded once and is valid for
the kernel's whole span (de421: 1900-2050). This is the position provider that
plugs into the shared geometry/passes/snapshot core.
"""
