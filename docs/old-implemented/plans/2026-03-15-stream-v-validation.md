# Stream V: Cross-Stream Validation

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Read first:** `docs/superpowers/plans/2026-03-15-api-ui-alignment-overview.md`
>
> **Prerequisite:** ALL streams (A, B, C, D, E) must be merged to main before running this.

**Goal:** Verify that all streams integrate correctly after merge — no regressions, no
interface mismatches, all contracts honored.

**Architecture:** Sequential validation checks covering API, UI, SDK, and cross-cutting concerns.

---

## Pre-check: Verify All Streams Merged

- [ ] **Step 1: Confirm branch is clean and up to date**

```bash
git status
git log --oneline -10
```

Verify commits from all 5 streams are present.

---

### Task 1: API — Full Test Suite

- [ ] **Step 1: Run all unit tests**

```bash
uv run pytest api/tests/ -m "not integration" -v
```

Expected: All pass. Zero failures.

- [ ] **Step 2: Lint and type check entire API**

```bash
uv run ruff check api/
uv run mypy api/app
```

Expected: Clean — no errors.

- [ ] **Step 3: Verify new endpoints exist in OpenAPI schema**

```bash
uv run python -c "
from app.main import app
routes = [r.path for r in app.routes]
assert '/trend' in routes, 'missing /trend'
assert '/evaluations' in routes, 'missing /evaluations'
assert '/slo-definitions/validate' in routes, 'missing /slo-definitions/validate'
assert '/slo-definitions/test' in routes, 'missing /slo-definitions/test'
assert '/sli-definitions' in routes, 'missing /sli-definitions'
print('All expected routes present')
"
```

---

### Task 2: API — Endpoint Contract Verification

- [ ] **Step 1: Trend endpoint — both entry points work**

Verify the trend endpoint accepts both `eval_id` and `asset_name+slo_name` patterns.
Test via TestClient:

```python
# Run inline or as a test file
from fastapi.testclient import TestClient
from app.main import app
import uuid

client = TestClient(app)

# eval_id path — should get 404 (no DB) but NOT 422
r = client.get("/trend", params={"eval_id": str(uuid.uuid4()), "metric": "cpu"})
assert r.status_code in (404, 500), f"Expected 404, got {r.status_code}"

# asset_name+slo_name path — should get 404 (no DB) but NOT 422
r = client.get("/trend", params={"asset_name": "vm", "slo_name": "slo", "metric": "cpu"})
assert r.status_code in (404, 500), f"Expected 404, got {r.status_code}"

# Both provided — should get 422
r = client.get("/trend", params={
    "eval_id": str(uuid.uuid4()), "asset_name": "vm", "slo_name": "slo", "metric": "cpu"
})
assert r.status_code == 422

# Neither provided — should get 422
r = client.get("/trend", params={"metric": "cpu"})
assert r.status_code == 422

print("Trend endpoint validation: OK")
```

- [ ] **Step 2: Evaluation list — from/to filters accepted**

```python
r = client.get("/evaluations", params={"from": "2026-03-01T00:00:00Z", "to": "2026-03-01T23:59:59Z"})
assert r.status_code == 200

# date + from = 422
r = client.get("/evaluations", params={"date": "2026-03-01", "from": "2026-03-01T00:00:00Z"})
assert r.status_code == 422

print("Evaluation time-range filters: OK")
```

- [ ] **Step 3: SLO validate endpoint works**

```python
r = client.post("/slo-definitions/validate", json={"slo_yaml": ""})
assert r.status_code == 200
assert r.json()["valid"] is False

print("SLO validate endpoint: OK")
```

- [ ] **Step 4: SLO test endpoint exists and validates**

```python
r = client.post("/slo-definitions/test", json={
    "slo_yaml": "spec_version: '1.0'\nindicators:\n  cpu: q\nobjectives:\n  - sli: cpu\n    pass:\n      - criteria: ['<100']\ntotal_score:\n  pass: '90%'\n  warning: '75%'",
    "sli_name": "missing",
    "data_source_name": "missing",
    "asset_name": "missing",
    "period_start": "2026-03-01T00:00:00Z",
    "period_end": "2026-03-01T01:00:00Z",
})
# Should be 404 (entities not found) not 422 (bad request)
assert r.status_code == 404

print("SLO test endpoint: OK")
```

---

### Task 3: UI — Build Verification

- [ ] **Step 1: Clean install and build**

```bash
cd ui && rm -rf node_modules && npm install && npm run build
```

Expected: Build completes with zero TypeScript errors.

- [ ] **Step 2: Type check**

```bash
cd ui && npx tsc --noEmit
```

Expected: No type errors.

- [ ] **Step 3: Run UI tests**

```bash
cd ui && npm test -- --run
```

Expected: All pass.

---

### Task 4: UI — Contract Alignment Verification

- [ ] **Step 1: Verify no old paths remain**

Search for old mock paths that should have been replaced:

```bash
# These should return zero results:
grep -r "'/api/slos'" ui/src/ --include="*.ts" --include="*.tsx" || echo "CLEAN"
grep -r '"/api/slos"' ui/src/ --include="*.ts" --include="*.tsx" || echo "CLEAN"
grep -r "asset-groups'" ui/src/features/ --include="*.ts" | grep -v "asset-groups/tree" | grep -v "asset-groups/" || echo "CLEAN"
```

Expected: No matches (all paths updated to `/api/slo-definitions`, `/api/asset-groups/tree`).

- [ ] **Step 2: Verify no old field names remain**

```bash
# These patterns in evaluation types/api should be gone:
grep -n "\.start\b" ui/src/features/evaluations/ --include="*.ts" | grep -v "period_start" || echo "CLEAN"
grep -n "\.end\b" ui/src/features/evaluations/ --include="*.ts" | grep -v "period_end" || echo "CLEAN"
grep -n "\.lab\b" ui/src/features/evaluations/ --include="*.ts" | grep -v "group_name" || echo "CLEAN"
grep -n "\.slot\b" ui/src/features/evaluations/ --include="*.ts" || echo "CLEAN"
grep -n "asset_group:" ui/src/features/evaluations/ --include="*.ts" || echo "CLEAN"
```

- [ ] **Step 3: Verify SLI module exists**

```bash
ls ui/src/features/slis/api.ts ui/src/features/slis/types.ts ui/src/features/slis/hooks.ts
ls ui/src/mocks/handlers/slis.ts ui/src/mocks/data/sli-definitions.json
```

Expected: All files exist.

---

### Task 5: SDK — Test Suite

- [ ] **Step 1: Run SDK tests**

```bash
uv run pytest clients/python/tests/ -v
```

Expected: All pass.

- [ ] **Step 2: SDK lint + type check**

```bash
uv run ruff check clients/python/
uv run mypy clients/python/tropek_client/
```

Expected: Clean.

- [ ] **Step 3: Verify CLI works**

```bash
# Create a test manifest
cat > /tmp/tropek-test.yaml << 'EOF'
api_version: tropek/v1
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
EOF

uv run tropek validate -f /tmp/tropek-test.yaml
```

Expected: `Valid: 1 document(s)`

- [ ] **Step 4: Verify CLI rejects invalid manifests**

```bash
cat > /tmp/tropek-bad.yaml << 'EOF'
kind: AssetType
metadata:
  name: vm
EOF

uv run tropek validate -f /tmp/tropek-bad.yaml
```

Expected: Exit code 1 with `api_version` error.

---

### Task 6: Cross-Module Consistency

- [ ] **Step 1: Verify SDK models match API schemas**

Compare the field names in SDK models vs API schemas to catch drift:

```python
# Quick check: SDK EvaluationSummary fields match API schema fields
from tropek_client.models import EvaluationSummary as SDKEval
from app.modules.quality_gate.schemas import EvaluationSummary as APIEval

sdk_fields = set(SDKEval.model_fields.keys())
api_fields = set(APIEval.model_fields.keys())

missing_in_sdk = api_fields - sdk_fields
extra_in_sdk = sdk_fields - api_fields

if missing_in_sdk:
    print(f"WARNING: SDK missing fields: {missing_in_sdk}")
if extra_in_sdk:
    print(f"WARNING: SDK has extra fields: {extra_in_sdk}")
if not missing_in_sdk and not extra_in_sdk:
    print("EvaluationSummary models match")
```

Repeat for other key models: `SLODefinition`, `SLIDefinition`, `Asset`, `DataSource`.

- [ ] **Step 2: Verify MSW handler paths match real router paths**

```bash
# Extract all paths from MSW handlers
grep -h "http\.\(get\|post\|patch\|delete\)" ui/src/mocks/handlers/*.ts | \
  grep -oP "'/api/[^']*'" | sort -u > /tmp/msw-paths.txt

# Extract all paths from FastAPI routers
grep -h "@router\.\(get\|post\|patch\|delete\)" api/app/modules/*/router.py | \
  grep -oP '"/[^"]*"' | sort -u > /tmp/api-paths.txt

echo "=== MSW paths ===" && cat /tmp/msw-paths.txt
echo "=== API paths ===" && cat /tmp/api-paths.txt
```

Manually verify that every MSW path has a corresponding API path (allowing for `/api/` prefix
in MSW vs no prefix in API routers).

---

### Task 7: Final Full Suite

- [ ] **Step 1: Run everything**

```bash
uv run pytest api/tests/ clients/python/tests/ -m "not integration" -v
uv run ruff check api/ clients/python/ adapters/
uv run mypy api/app clients/python/tropek_client adapters/prometheus/app
cd ui && npm run build && npm test -- --run
```

Expected: All green.

- [ ] **Step 2: Commit any fixes found during validation**

If any issues were found and fixed during validation:

```bash
git add -A
git commit -m "fix: address issues found during cross-stream validation"
```
