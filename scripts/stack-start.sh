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
  echo "=== Running dev-setup pipeline (bootstrap + seed) ==="
  uv run --directory clients/python python ../../dev_setup/run.py "http://localhost:8080" \
      --adapter-url http://adapter-mock:8082 \
      bootstrap seed-evaluations
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
