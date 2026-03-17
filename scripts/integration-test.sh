#!/usr/bin/env bash
set -euo pipefail

# End-to-end integration test using mock adapter + bootstrap manifests
#
# Uses dedicated E2E infrastructure (DB on 5434, Redis on 6380, API on 9080,
# mock adapter on 9082) so it never conflicts with the dev environment.
#
# Prerequisites: docker compose available, uv installed

# --- E2E-dedicated ports (never conflict with dev) ---
E2E_DB_PORT=5434
E2E_REDIS_PORT=6380
E2E_API_PORT=9080
E2E_MOCK_PORT=9082

PIDS=()

cleanup() {
  echo ""
  echo "=== Cleaning up ==="
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait "${PIDS[@]}" 2>/dev/null || true
  docker compose --profile e2e down -v 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Step 1: Generate mock scenario data ==="
uv run --directory adapters/mock python generate.py

echo "=== Step 2: Start E2E DB + Redis (ports $E2E_DB_PORT, $E2E_REDIS_PORT) ==="
docker compose --profile e2e up timescaledb-e2e redis-e2e -d --wait

echo "=== Step 3: Apply migrations ==="
export QG_DB_USER=tropek_e2e
export QG_DB_PASSWORD=tropek_e2e
export QG_DB_HOST=localhost
export QG_DB_PORT=$E2E_DB_PORT
export QG_DB_NAME=tropek_e2e
export QG_REDIS_PASSWORD=e2e_redis
export QG_REDIS_HOST=localhost
export QG_REDIS_PORT=$E2E_REDIS_PORT
export QG_SECRET_KEY=e2e-test-key
export QG_CONFIG_PATH=config.yaml
export MOCK_DATA_DIR=data  # relative to adapters/mock/ (the adapter's --directory CWD)

uv run --directory api alembic upgrade head

echo "=== Step 4: Start mock adapter on :$E2E_MOCK_PORT (background) ==="
uv run --directory adapters/mock uvicorn app.main:app --host 127.0.0.1 --port $E2E_MOCK_PORT &
PIDS+=($!)

echo "=== Step 5: Start API on :$E2E_API_PORT (background) ==="
uv run --directory api uvicorn app.main:app --host 127.0.0.1 --port $E2E_API_PORT &
PIDS+=($!)

echo "=== Step 5b: Start arq worker (background) ==="
# PYTHONPATH=. resolves to api/ (the uv --directory target), making app.queue importable
PYTHONPATH=. uv run --directory api arq app.queue.WorkerSettings &
PIDS+=($!)

# Wait for services to be ready
echo "    waiting for services..."
for i in $(seq 1 15); do
  if curl -sf http://localhost:$E2E_API_PORT/health > /dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -sf http://localhost:$E2E_API_PORT/health > /dev/null 2>&1 || { echo "ERROR: API did not start"; exit 1; }
echo "    services ready"

echo "=== Steps 6-13: Run integration tests ==="
uv run --directory clients/python python ../../scripts/e2e_tests.py "http://localhost:$E2E_API_PORT"
