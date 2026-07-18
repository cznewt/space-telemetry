"""NOAA SWPC (Space Weather Prediction Center) collector.

Fetches a few key products — planetary K-index, solar-wind plasma & IMF, and GOES
X-ray flux — into the offline cache and exposes the latest values as metrics.
Unlike the sky/satellites collectors this observes the Sun/heliosphere rather than
the observer's local sky, so its metrics carry no observer labels.
"""
