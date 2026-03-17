#!/usr/bin/env bash
set -euo pipefail

# Start the full TROPEK stack with mock data for local development.
#
# Starts TimescaleDB, Redis, mock adapter, API, and arq worker on dedicated
# ports (never conflicts with the main dev environment), then applies bootstrap
# manifests so the app has data for visual inspection.
#
# API docs: http://localhost:9080/docs
# Press Ctrl+C to stop all services and tear down containers.
#
# Prerequisites: docker compose available, uv installed

DB_PORT=5434
REDIS_PORT=6380
API_PORT=9080
MOCK_PORT=9082

PIDS=()

cleanup() {
  echo ""
  echo "=== Stopping services ==="
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait "${PIDS[@]}" 2>/dev/null || true
  docker compose --profile e2e down -v 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Generating mock scenario data ==="
uv run --directory adapters/mock python generate.py

echo "=== Starting DB + Redis (ports $DB_PORT, $REDIS_PORT) ==="
docker compose --profile e2e up timescaledb-e2e redis-e2e -d --wait

echo "=== Applying migrations ==="
export QG_DB_USER=tropek_e2e
export QG_DB_PASSWORD=tropek_e2e
export QG_DB_HOST=localhost
export QG_DB_PORT=$DB_PORT
export QG_DB_NAME=tropek_e2e
export QG_REDIS_PASSWORD=e2e_redis
export QG_REDIS_HOST=localhost
export QG_REDIS_PORT=$REDIS_PORT
export QG_SECRET_KEY=e2e-test-key
export QG_CONFIG_PATH=config.yaml
export MOCK_DATA_DIR=data  # relative to adapters/mock/ (the adapter's --directory CWD)

uv run --directory api alembic upgrade head

echo "=== Starting mock adapter on :$MOCK_PORT (background) ==="
uv run --directory adapters/mock uvicorn app.main:app --host 127.0.0.1 --port $MOCK_PORT &
PIDS+=($!)

echo "=== Starting API on :$API_PORT (background) ==="
uv run --directory api uvicorn app.main:app --host 127.0.0.1 --port $API_PORT &
PIDS+=($!)

echo "=== Starting arq worker (background) ==="
# PYTHONPATH=. resolves to api/ (the uv --directory target), making app.queue importable
PYTHONPATH=. uv run --directory api arq app.queue.WorkerSettings &
PIDS+=($!)

echo "    waiting for API..."
for i in $(seq 1 15); do
  if curl -sf http://localhost:$API_PORT/health > /dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -sf http://localhost:$API_PORT/health > /dev/null 2>&1 || { echo "ERROR: API did not start"; exit 1; }

echo "=== Applying bootstrap manifests ==="
uv run --directory clients/python python ../../scripts/bootstrap.py "http://localhost:$API_PORT"

echo ""
echo "============================================"
echo "  Dev environment ready"
echo "  API:   http://localhost:$API_PORT"
echo "  Docs:  http://localhost:$API_PORT/docs"
echo ""
echo "  Press Ctrl+C to stop"
echo "============================================"
echo ""

wait "${PIDS[@]}"
