FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SPACE_TELEMETRY_CACHE_DIR=/app/data \
    SPACE_TELEMETRY_HOST=0.0.0.0 \
    SPACE_TELEMETRY_PORT=9110

# Ship the JPL ephemeris (~17 MB) so startup needs no network: without it every
# start downloaded de421.bsp and a DNS outage at boot crashed the exporter. A new
# named volume on /app/data is seeded from this copy. Checksum-pinned, and above
# the app layers so code changes don't re-download it.
ADD --checksum=sha256:a20a7139da04cbc462454634918e9a9ca69127044e2cc9d4f9c16e238d2deedc --chmod=644 \
    https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de421.bsp /app/data/de421.bsp

COPY pyproject.toml README.md ./
COPY space_telemetry ./space_telemetry
RUN pip install .

EXPOSE 9110

# /app/data holds the ephemeris + the satellite/space-weather cache. Mounting a
# volume there (optional) keeps the cache across restarts.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9110/healthz', timeout=5)"

CMD ["python", "-m", "space_telemetry"]
