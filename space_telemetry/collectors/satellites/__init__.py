"""Satellite (TLE/OMM -> SGP4) tracking collector.

  sources/celestrak.py  fetch + parse CelesTrak GP (TLE/OMM) by group
  sources/satnogs.py    fetch SatNOGS DB transmitters + satellite metadata
  catalog.py            merge orbits + transmitters on the NORAD catalog number
  model.py              Satellite / Transmitter / Catalog + thread-safe holder
  propagate.py          SGP4 provider: geometry, passes, Doppler (one per observer)
  updater.py            background refresh scheduler (the only networked part)
  collector.py          Prometheus SatelliteCollector

Shared root helpers (``..cache`` FileCache, ``..http_util`` conditional_get,
``..observer`` Observer) are reused by the updater/provider.
"""
