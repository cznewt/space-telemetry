"""Space-weather collector (NOAA SWPC — Space Weather Prediction Center).

Fetches a few key products — planetary K-index, solar-wind speed & IMF, F10.7,
and GOES X-ray flux — into the offline cache and exposes the latest values as
``space_weather_*`` metrics. This observes the Sun/heliosphere rather than the
observer's local sky, so its metrics carry no observer label.
"""
