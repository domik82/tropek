#!/usr/bin/env bash
# Stop the test database container and remove its volume.
set -euo pipefail

echo "==> Stopping and removing test infrastructure (including volumes)..."
docker compose --profile test down -v

echo "==> Test infrastructure removed."
