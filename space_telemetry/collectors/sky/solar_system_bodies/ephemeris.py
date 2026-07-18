"""Resolve body names to Skyfield ephemeris targets."""

from __future__ import annotations

# Bodies whose only segment in common kernels (e.g. de421) is the barycentre.
_BARYCENTER_ONLY = {"jupiter", "saturn", "uranus", "neptune", "pluto"}


def target_for(eph, name: str):
    """Resolve a body name (``'mars'``, ``'jupiter'``, ``'moon'``, ...) to a target.

    Tries the direct segment first, then ``'<name> barycenter'``, so the same
    friendly names work across de421 / de440 / de440s. Raises ``KeyError`` if the
    body is not present in the loaded kernel.
    """
    key = name.lower().strip()
    candidates = [key, f"{key} barycenter"]
    if key in _BARYCENTER_ONLY:
        candidates.reverse()
    for candidate in candidates:
        try:
            return eph[candidate]
        except (KeyError, ValueError):
            continue
    raise KeyError(f"body {name!r} not found in ephemeris")
