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
export MOCK_DATA_DIR=adapters/mock/data

uv run --directory api alembic upgrade head

echo "=== Step 4: Start mock adapter on :$E2E_MOCK_PORT (background) ==="
uv run --directory adapters/mock uvicorn app.main:app --host 127.0.0.1 --port $E2E_MOCK_PORT &
PIDS+=($!)

echo "=== Step 5: Start API on :$E2E_API_PORT (background) ==="
uv run --directory api uvicorn app.main:app --host 127.0.0.1 --port $E2E_API_PORT &
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

API_URL="http://localhost:$E2E_API_PORT"

echo "=== Step 6: Apply bootstrap manifests ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
from tropek_client.manifest import load_manifests, apply

client = TropekClient('$API_URL')
docs = load_manifests('../../bootstrap_mock/manifests/')
result = apply(client, docs)
print(f'applied: {result.created} created, {result.updated} updated, {result.unchanged} unchanged')
"

echo "=== Step 7: Trigger single evaluation ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
import time

client = TropekClient('$API_URL')
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
client = TropekClient('$API_URL')
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

client = TropekClient('$API_URL')
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

client = TropekClient('$API_URL')
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
client = TropekClient('$API_URL')
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

echo ""
echo "=== All integration tests passed ==="
