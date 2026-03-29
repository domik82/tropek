#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Stopping stack and removing volumes..."
docker compose -f "$DIR/docker-compose.yml" down -v

echo "==> Done."
