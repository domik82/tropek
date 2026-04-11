#!/usr/bin/env bash
set -euo pipefail

# Start the full TROPEK stack via Docker Compose.
#
# Builds images, starts all services, applies migrations, bootstraps mock data,
# and seeds historical evaluations. Exits 0 on success.
#
# Usage:
#   ./scripts/stack-start.sh               # full stack with seeded data
#   ./scripts/stack-start.sh --no-seed     # stack only, no bootstrap/seed
#   ./scripts/stack-start.sh --build-only  # build images, don't start
#
# Prerequisites: docker compose, uv (for bootstrap/seed scripts)
# Stop with: ./scripts/stack-stop.sh

cd "$(dirname "$0")/.."

SEED=true
BUILD_ONLY=false
for arg in "$@"; do
  case $arg in
    --no-seed) SEED=false ;;
    --build-only) BUILD_ONLY=true ;;
    *) echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

# --- Ensure .env exists ---
if [ ! -f .env ]; then
  echo "=== No .env found — creating from .env.example ==="
  cp .env.example .env
  echo "  Edit .env to set real passwords for production use"
fi

# --- Generate mock scenario CSVs (bind-mounted into adapter-mock) ---
echo "=== Generating mock scenario data ==="
uv run --directory adapters/mock python generate.py

# --- Build ---
echo "=== Building images ==="
docker compose build

if [ "$BUILD_ONLY" = true ]; then
  echo "=== Build complete (--build-only) ==="
  exit 0
fi

# --- Start infra + app ---
echo "=== Starting services ==="
docker compose up -d --wait

echo "=== Verifying API health ==="
curl -sf http://localhost:8080/health > /dev/null
echo "  API healthy"

if [ "$SEED" = true ]; then
  # --- Bootstrap: create a temp manifests dir with docker adapter URLs ---
  DOCKER_MANIFESTS=$(mktemp -d)
  cp bootstrap_mock/manifests/*.yaml "$DOCKER_MANIFESTS/"
  # Rewrite adapter URLs from localhost to docker-network names
  sed -i 's|http://127.0.0.1:9082|http://adapter-mock:8082|g' "$DOCKER_MANIFESTS/datasources.yaml"

  echo "=== Applying bootstrap manifests ==="
  TROPEK_MANIFESTS_DIR="$DOCKER_MANIFESTS" \
    uv run --directory clients/python python -c "
import os, sys
sys.path.insert(0, '.')
from tropek_client import TropekClient
from tropek_client.manifest import apply, load_manifests
client = TropekClient('http://localhost:8080')
docs = load_manifests(os.environ['TROPEK_MANIFESTS_DIR'])
result = apply(client, docs)
print(f'bootstrap: {result.created} created, {result.updated} updated, {result.skipped} skipped')
if result.failed: raise RuntimeError(f'bootstrap failed: {result.errors}')
"

  rm -rf "$DOCKER_MANIFESTS"

  echo "=== Seeding historical evaluations ==="
  uv run --directory clients/python python ../../scripts/seed_evaluations.py "http://localhost:8080"
fi

echo ""
echo "============================================"
echo "  TROPEK stack is running"
echo ""
echo "  UI:      http://localhost:3000"
echo "  API:     http://localhost:8080"
echo "  Docs:    http://localhost:8080/docs"
echo "  Mock:    http://localhost:8082"
echo ""
echo "  Logs:    docker compose logs -f"
echo "  Stop:    ./scripts/stack-stop.sh"
echo "============================================"
