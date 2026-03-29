#!/usr/bin/env bash
set -euo pipefail

# Start the full TROPEK stack for local development.
#
# Starts TimescaleDB, Redis, mock adapter, Prometheus adapter, API, arq worker,
# and UI on dedicated ports. Applies bootstrap manifests (mock + Prometheus) and
# seeds historical evaluations for visual inspection.
#
# If the observability stack is running (cd observability_stack/integration-test && just up),
# the Prometheus adapter will query real metrics and evaluations will produce real results.
# If not, those evaluations will fail with timeouts — the mock data still works independently.
#
# API docs: http://localhost:9080/docs
# Press Ctrl+C to stop all services and tear down containers.
#
# Prerequisites: docker compose, uv, pnpm
# Optional: observability stack + Redis on :6379 (for Prometheus adapter)

cd "$(dirname "$0")/.."

DB_PORT=5434
REDIS_PORT=6380
API_PORT=9080
MOCK_PORT=9082
ADAPTER_PORT=8081
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
ADAPTER_REDIS_URL="${ADAPTER_REDIS_URL:-redis://localhost:6379/0}"

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

echo "=== Starting Prometheus adapter on :$ADAPTER_PORT (background) ==="
PROMETHEUS_URL="$PROMETHEUS_URL" \
REDIS_URL="$ADAPTER_REDIS_URL" \
PORT="$ADAPTER_PORT" \
uv run --directory adapters/prometheus \
    uvicorn app.main:app --host 127.0.0.1 --port $ADAPTER_PORT --log-level warning &
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

echo "=== Seeding historical evaluations (mock) ==="
uv run --directory clients/python python ../../scripts/seed_evaluations.py "http://localhost:$API_PORT"

echo "=== Running e2e tests ==="
uv run --directory clients/python python ../../scripts/e2e_tests.py "http://localhost:$API_PORT"

echo "=== Applying Prometheus bootstrap manifests ==="
BOOTSTRAP_PROMETHEUS_DIR="$(pwd)/bootstrap_prometheus/manifests"
uv run --directory clients/python python -c "
import sys; sys.path.insert(0, '.')
from tropek_client import TropekClient
from tropek_client.manifest import apply, load_manifests
client = TropekClient('http://localhost:$API_PORT')
result = apply(client, load_manifests('$BOOTSTRAP_PROMETHEUS_DIR'))
print(f'prometheus bootstrap: {result.created} created, {result.updated} updated, {result.skipped} skipped')
if result.failed: print(f'  errors: {result.errors}')
"

echo "=== Seeding Prometheus evaluations (7 days x 3 assets) ==="
uv run --directory clients/python python ../../scripts/seed_e2e_prometheus.py "http://localhost:$API_PORT"

echo "=== Installing UI dependencies ==="
pnpm --dir ui install

echo "=== Starting UI (background) ==="
VITE_USE_MOCKS=false pnpm --dir ui run dev &
PIDS+=($!)

echo ""
echo "============================================"
echo "  Dev environment ready"
echo "  UI:      http://localhost:5173"
echo "  API:     http://localhost:$API_PORT"
echo "  Adapter: http://localhost:$ADAPTER_PORT"
echo "  Docs:    http://localhost:$API_PORT/docs"
echo ""
echo "  Press Ctrl+C to stop"
echo "============================================"
echo ""

wait "${PIDS[@]}"
