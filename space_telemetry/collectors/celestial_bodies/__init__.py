"""Celestial-body collector: a small bright-star catalog.

A star's ICRS right ascension / declination is effectively fixed, so positions
are computed offline from the built-in catalog (no network, no updates). Uses the
shared geometry/passes helpers; ``sampler`` produces a StarSnapshot per observer,
``collector`` emits it.
"""
