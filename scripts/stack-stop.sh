#!/usr/bin/env bash
set -euo pipefail

# Stop the TROPEK Docker Compose stack.
#
# Usage:
#   ./scripts/stack-stop.sh             # stop containers, keep data volumes
#   ./scripts/stack-stop.sh --clean     # stop containers AND delete all volumes

cd "$(dirname "$0")/.."

if [ "${1:-}" = "--clean" ]; then
  echo "=== Stopping stack and removing volumes ==="
  docker compose down -v
  echo "  Done — all containers and data removed"
else
  echo "=== Stopping stack ==="
  docker compose down
  echo "  Done — containers stopped, volumes preserved"
  echo "  Use --clean to also remove data volumes"
fi
