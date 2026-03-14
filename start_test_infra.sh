#!/usr/bin/env bash
# Start the test database container and apply migrations.
# Run this once before executing integration tests.
# Requires: .env.test file (copy from .env.test.example and fill in values)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_TEST="$SCRIPT_DIR/.env.test"

if [[ ! -f "$ENV_TEST" ]]; then
    echo "ERROR: $ENV_TEST not found. Copy .env.test.example to .env.test and fill in values."
    exit 1
fi

echo "==> Starting timescaledb-test (port 5433)..."
docker compose --profile test up timescaledb-test -d --wait

echo "==> Applying migrations to test database..."
# Load .env.test so pydantic-settings / alembic env.py picks up QG_DB_* vars
set -a
# shellcheck source=.env.test
source "$ENV_TEST"
set +a

uv run --directory "$SCRIPT_DIR/api" alembic upgrade head

echo "==> Test infrastructure ready. Run tests with:"
echo "    uv run pytest api/tests/ -m integration -v"
