#!/usr/bin/env just --justfile

set dotenv-load := true

# Image coordinates (override on the CLI, e.g. `just TAG=dev image`)
REGISTRY := "ghcr.io"
IMAGE := "cznewt/space-telemetry"
TAG := `cat VERSION`
OBSERV_LIB := "operations/space-telemetry-observ-lib"
OBSERV_LIB_IMAGE := "ghcr.io/cznewt/observ-lib:latest"

default:
  just --list

# --- Local dev ---

# Build + start the compose stack (exporter + Prometheus + Grafana)
up:
    docker compose up -d --build

# Stop the compose stack
down:
    docker compose down

# Run the exporter directly (env or ./space-telemetry.yaml)
run:
    python -m space_telemetry

# --- Docs ---

# Serve the docs locally with live reload (needs: pip install mkdocs-material)
docs-serve:
    mkdocs serve

# Build the docs site (strict; mirrors the Pages workflow)
docs-build:
    mkdocs build --strict

# --- Container registry (ghcr) ---

# Log in to ghcr. Set GHCR_USER + GHCR_TOKEN (a GitHub PAT with write:packages).
docker-login:
    echo "${GHCR_TOKEN:?set GHCR_TOKEN to a GitHub PAT with write:packages}" | docker login {{REGISTRY}} -u "${GHCR_USER:?set GHCR_USER to your GitHub username}" --password-stdin

# Build the image, tagged :<VERSION> and :latest
image:
    docker build -t {{REGISTRY}}/{{IMAGE}}:{{TAG}} -t {{REGISTRY}}/{{IMAGE}}:latest .

# Push both tags to ghcr (run `just docker-login` first)
push:
    docker push {{REGISTRY}}/{{IMAGE}}:{{TAG}}
    docker push {{REGISTRY}}/{{IMAGE}}:latest

# Build and push in one go
publish: image push
    @echo "published {{REGISTRY}}/{{IMAGE}}:{{TAG}} (+ :latest)"

# --- Observability library (observ-viz pack) ---
# Rendered through the observ-lib image (observ-viz on the jpath; no local jsonnet/jb).

# Render the observ-lib into dashboards/ alerts/ rules/ + inject signals into docs
observ-lib-build:
    docker run --rm --user "$(id -u):$(id -g)" -v "$PWD":/repo -w "/repo/{{OBSERV_LIB}}" --entrypoint python3 {{OBSERV_LIB_IMAGE}} render.py

# Push the rendered dashboard(s) to Grafana. Set GRAFANA_URL + GRAFANA_TOKEN in .env.
grafana-push:
    python3 {{OBSERV_LIB}}/push.py {{OBSERV_LIB}}/dashboards/*.json
