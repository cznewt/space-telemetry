FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SPACE_TELEMETRY_CACHE_DIR=/app/data \
    SPACE_TELEMETRY_HOST=0.0.0.0 \
    SPACE_TELEMETRY_PORT=9110

COPY pyproject.toml README.md ./
COPY space_telemetry ./space_telemetry
RUN pip install .

EXPOSE 9110

# Offline-first: /app/data (ephemeris + satellite cache) is mounted at runtime.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9110/healthz', timeout=5)"

CMD ["python", "-m", "space_telemetry"]
