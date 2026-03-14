#!/usr/bin/env bash
# Start the test database container and apply migrations.
# Run this once before executing integration tests.
# Requires: .env.test file (copy from .env.test.example and fill in values)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -f "$SCRIPT_DIR/.env.test" ]]; then
    echo "ERROR: .env.test not found. Copy .env.test.example to .env.test and fill in values."
    exit 1
fi

echo "==> Starting timescaledb-test (port 5433)..."
docker compose --profile test up timescaledb-test -d --wait

echo "==> Applying migrations to test database..."
ENV_FILE="$SCRIPT_DIR/.env.test" uv run --directory "$SCRIPT_DIR/api" alembic upgrade head

echo "==> Test infrastructure ready. Run tests with:"
echo "    uv run pytest api/tests/ -m integration -v"
