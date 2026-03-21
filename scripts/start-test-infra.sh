#!/usr/bin/env bash
# Start the test database container and apply migrations.
# Run this once before executing integration tests.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$REPO_ROOT/.env.test" ]]; then
    echo "ERROR: .env.test not found at repo root."
    exit 1
fi

echo "==> Starting timescaledb-test (port 5433)..."
docker compose --profile test up timescaledb-test -d --wait

echo "==> Applying migrations to test database..."
ENV_FILE="$REPO_ROOT/.env.test" uv run --directory "$REPO_ROOT/api" alembic upgrade head

echo "==> Test infrastructure ready. Run tests with:"
echo "    just test-int"
