#!/usr/bin/env bash
# live-test-adapter.sh — Starts the adapter, runs e2e pytest suite, then stops.
#
# Prerequisites:
#   1. Observability stack: cd observability_stack/integration-test && just up
#   2. Redis on localhost:6379 (or set REDIS_URL)
#
# Usage:
#   ./scripts/live-test-adapter.sh
#   PROMETHEUS_URL=http://prom:9090 ./scripts/live-test-adapter.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ADAPTER_DIR="${REPO_ROOT}/adapters/prometheus"

PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
ADAPTER_PORT="${ADAPTER_PORT:-8081}"

ADAPTER_PID=""

cleanup() {
    if [[ -n "${ADAPTER_PID}" ]]; then
        echo "Stopping adapter (PID ${ADAPTER_PID})..."
        kill "${ADAPTER_PID}" 2>/dev/null || true
        wait "${ADAPTER_PID}" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Start adapter in background
echo "Starting adapter on :${ADAPTER_PORT}..."
PROMETHEUS_URL="${PROMETHEUS_URL}" \
REDIS_URL="${REDIS_URL}" \
PORT="${ADAPTER_PORT}" \
uv run --directory "${ADAPTER_DIR}" \
    uvicorn app.main:app --host 0.0.0.0 --port "${ADAPTER_PORT}" \
    --log-level warning &
ADAPTER_PID=$!

# Wait for health
echo -n "Waiting for health..."
for i in $(seq 1 30); do
    if uv run python -c "import httpx; httpx.get('http://localhost:${ADAPTER_PORT}/health/live').raise_for_status()" 2>/dev/null; then
        echo " ready (${i}s)"
        break
    fi
    if [[ $i -eq 30 ]]; then
        echo " timeout"
        exit 1
    fi
    sleep 1
done

# Run e2e tests
ADAPTER_URL="http://localhost:${ADAPTER_PORT}" \
uv run --directory "${ADAPTER_DIR}" \
    pytest tests/test_e2e.py -v -m e2e "$@"
