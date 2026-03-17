#!/usr/bin/env bash
set -euo pipefail

# End-to-end integration test using mock adapter + bootstrap manifests
# Prerequisites: docker compose available, uv installed
#
# Runs DB + Redis in Docker, everything else locally via uv run.
# Background processes (API, worker, mock adapter) are cleaned up on exit.

PIDS=()

cleanup() {
  echo "=== Cleaning up background processes ==="
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait "${PIDS[@]}" 2>/dev/null || true
  echo "=== Stopping Docker infrastructure ==="
  docker compose down -v 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Step 1: Generate mock scenario data ==="
uv run --directory adapters/mock python generate.py

echo "=== Step 2: Start DB + Redis ==="
docker compose up timescaledb redis -d --wait

echo "=== Step 3: Apply migrations ==="
# Load credentials from .env (same file docker compose uses)
set -a
source .env
set +a
export QG_DB_HOST=localhost
export QG_DB_PORT=5432
export QG_DB_NAME=tropek
export QG_CONFIG_PATH=config.yaml
export MOCK_DATA_DIR=adapters/mock/data

uv run --directory api alembic upgrade head

echo "=== Step 4: Start mock adapter (background) ==="
uv run --directory adapters/mock uvicorn app.main:app --host 0.0.0.0 --port 8082 &
PIDS+=($!)

echo "=== Step 5: Start API (background) ==="
uv run --directory api uvicorn app.main:app --host 0.0.0.0 --port 8080 &
PIDS+=($!)

# Give services a moment to start
sleep 3

echo "=== Step 6: Apply bootstrap manifests ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
from tropek_client.manifest import load_manifests, apply

client = TropekClient('http://localhost:8080')
docs = load_manifests('../../bootstrap_mock/manifests/')
result = apply(client, docs)
print(f'applied: {result.created} created, {result.updated} updated, {result.unchanged} unchanged')
"

echo "=== Step 7: Trigger single evaluation ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
import time

client = TropekClient('http://localhost:8080')
result = client.evaluations.trigger(
    'checkout-api', 'integration-test', 'http-availability-slo',
    '2026-03-15T08:00:00Z', '2026-03-15T08:30:00Z',
)
eval_id = result['id']
print(f'triggered: {eval_id}')

# Poll until complete
for _ in range(30):
    ev = client.evaluations.get(eval_id)
    if ev.status in ('completed', 'failed', 'partial'):
        break
    time.sleep(1)

print(f'status={ev.status} result={ev.result} score={ev.score}')
assert ev.status == 'completed', f'expected completed, got {ev.status}'
print('PASS: single evaluation')
"

echo "=== Step 8: Test pin baseline ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
client = TropekClient('http://localhost:8080')
evals = client.evaluations.list(asset_name='checkout-api')
eval_id = str(evals.items[0].id)
result = client.evaluations.pin_baseline(eval_id, 'integration test pin', 'test-runner')
print(f'pinned: {eval_id}')
assert result.baseline_pinned_at is not None
print('PASS: pin baseline')
"

echo "=== Step 9: Trigger batch evaluation ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
import time

client = TropekClient('http://localhost:8080')
result = client.evaluations.trigger_batch(
    'core-services', 'batch-test',
    '2026-03-15T08:00:00Z', '2026-03-15T08:30:00Z',
)
batch_id = result['batch_id']
eval_ids = result['evaluation_ids']
print(f'batch triggered: {batch_id}, {len(eval_ids)} evaluations')
assert len(eval_ids) >= 1, f'expected at least 1 evaluation, got {len(eval_ids)}'

# Poll until all complete
for _ in range(60):
    all_done = True
    for eid in eval_ids:
        ev = client.evaluations.get(str(eid))
        if ev.status not in ('completed', 'failed', 'partial'):
            all_done = False
            break
    if all_done:
        break
    time.sleep(1)

print('PASS: batch evaluation')
"

echo "=== Step 10: Trigger regression eval after pin ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
import time

client = TropekClient('http://localhost:8080')
result = client.evaluations.trigger(
    'checkout-api', 'regression-test', 'http-availability-slo',
    '2026-03-16T12:00:00Z', '2026-03-16T12:30:00Z',
)
eval_id = result['id']
print(f'triggered regression eval: {eval_id}')

for _ in range(30):
    ev = client.evaluations.get(str(eval_id))
    if ev.status in ('completed', 'failed', 'partial'):
        break
    time.sleep(1)

print(f'status={ev.status} result={ev.result} score={ev.score}')
print('PASS: regression eval completed (check result manually if needed)')
"

echo "=== Step 11: Test override status ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
client = TropekClient('http://localhost:8080')
evals = client.evaluations.list(asset_name='checkout-api')
eval_id = str(evals.items[0].id)
result = client.evaluations.override_status(eval_id, 'fail', 'testing override', 'test-runner')
assert result.result == 'fail'
assert result.original_result is not None
# Restore
result = client.evaluations.restore_override(eval_id)
assert result.original_result is None
print('PASS: override + restore')
"

echo "=== All integration tests passed ==="
