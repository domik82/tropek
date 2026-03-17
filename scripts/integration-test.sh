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

API_URL="http://localhost:$E2E_API_PORT"

echo "=== Step 6: Apply bootstrap manifests ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
from tropek_client.manifest import load_manifests, apply

client = TropekClient('$API_URL')
docs = load_manifests('../../bootstrap_mock/manifests/')
result = apply(client, docs)
print(f'applied: {result.created} created, {result.updated} updated, {result.skipped} skipped')
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

echo "=== Step 12: Override failed eval result to pass ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
client = TropekClient('$API_URL')

# Get an eval that has a real result (completed)
evals = client.evaluations.list(asset_name='checkout-api')
completed = [e for e in evals.items if e.status == 'completed']
assert completed, 'expected at least one completed eval'
eval_id = str(completed[0].id)
original_result = completed[0].result

# Override to pass
result = client.evaluations.override_status(eval_id, 'pass', 'manual override to pass', 'test-runner')
assert result.result == 'pass', f'expected pass, got {result.result}'
assert result.original_result == original_result, f'expected original_result={original_result}, got {result.original_result}'
print(f'overridden: {original_result} -> pass')

# Restore
result = client.evaluations.restore_override(eval_id)
assert result.result == original_result, f'expected {original_result} after restore, got {result.result}'
assert result.original_result is None
print('PASS: override result to pass + restore')
"

echo "=== Step 13: Add and verify annotations on an evaluation ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
client = TropekClient('$API_URL')

evals = client.evaluations.list(asset_name='checkout-api')
assert evals.items, 'expected evaluations'
eval_id = str(evals.items[0].id)

# Create annotation
ann = client.annotations.create(eval_id, 'deployment looked fine, ignoring regression', author='test-runner', category='deployment')
assert ann.content == 'deployment looked fine, ignoring regression'
assert ann.author == 'test-runner'
ann_id = str(ann.id)
print(f'created annotation: {ann_id}')

# List — should contain the annotation
anns = client.annotations.list(eval_id)
found = [a for a in anns if str(a.id) == ann_id]
assert found, f'annotation {ann_id} not found in list'
print(f'listed {len(anns)} annotation(s)')

# Update content
updated = client.annotations.update(eval_id, ann_id, content='updated note')
assert updated.content == 'updated note'
print('updated annotation content')

# Delete
client.annotations.delete(eval_id, ann_id)
anns_after = client.annotations.list(eval_id)
remaining = [a for a in anns_after if str(a.id) == ann_id]
assert not remaining, 'annotation still present after delete'
print('PASS: create, list, update, delete annotation')
"

echo ""
echo "=== All integration tests passed ==="
