"""Sky collector: solar-system bodies (ephemeris) + celestial bodies (stars).

  geometry.py             shared alt/az for any Skyfield target
  passes.py               shared rise/set search
  snapshot.py             SkySampler -> SkySnapshot (bodies + stars)
  collector.py            Prometheus SkyCollector (body_* / star_*)
  solar_system_bodies/    Sun, Moon, planets (offline .bsp ephemeris)
  celestial_bodies/       bright-star catalog (offline, fixed positions)
"""
