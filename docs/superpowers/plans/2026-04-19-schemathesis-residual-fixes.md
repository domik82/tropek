# Schemathesis Residual Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take schemathesis from 14 failures to 0 (or documented residuals) by fixing 6 root causes on branch `feat/contract-testing-phase-3-schemathesis`.

**Architecture:** Seven sequential commits — six cheap/contained fixes, one cross-stack URL refactor. Each commit keeps `just test-int` green. Schemathesis itself is the acceptance test for each group.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy async, React + React Query, MSW, Python SDK. Schemathesis 4.15.x as contract-test oracle.

**Spec:** `docs/superpowers/specs/2026-04-19-schemathesis-residual-fixes-design.md`

---

## Verification commands (used by every task)

- Targeted schemathesis for one failure:
  `uv run --directory api pytest tests/schemathesis/test_schema.py -v -k '<op-substring>'`
- Full schemathesis: `uv run --directory api pytest tests/schemathesis/test_schema.py -v`
- Integration: `./scripts/api-test.sh --tail 5 -m integration -v` — must show `265 passed`
- UI (after commit 5 only): `./scripts/ui-test.sh --tail 10`
- SDK (after commit 5 only): `uv run --directory clients/python pytest --tail 5`

---

## Task 1: StrictBool / StrictInt / StrictFloat sweep (Group B)

**Files:**
- Modify: `api/tropek/modules/slo_definitions/schemas.py` — `comparable_from_version`, `total_score_pass_threshold`, `total_score_warning_threshold`
- Modify: `api/tropek/modules/assets/router.py` — `deactivate_slos` query parameter on `DELETE /asset-groups/{name}` (find exact file via `Grep`)
- Modify: matching `SloTestRequest`/validate schema if threshold fields live there too

- [ ] **Step 1.1: Find exact locations**

Run: `grep -rn "deactivate_slos" api/tropek/modules/` and `grep -rn "comparable_from_version" api/tropek/modules/` and `grep -rn "total_score_warning_threshold" api/tropek/modules/`. Note file + line for each hit.

- [ ] **Step 1.2: Change types**

In each schema file, replace:
```python
comparable_from_version: int | None = None
total_score_pass_threshold: float = 90.0
total_score_warning_threshold: float = 75.0
```
with:
```python
from pydantic import StrictInt, StrictFloat
comparable_from_version: StrictInt | None = None
total_score_pass_threshold: StrictFloat = 90.0
total_score_warning_threshold: StrictFloat = 75.0
```

For the query parameter in the router handler, change:
```python
async def delete_asset_group(..., deactivate_slos: bool = Query(False)):
```
to:
```python
from pydantic import StrictBool
async def delete_asset_group(..., deactivate_slos: StrictBool = Query(False)):
```

- [ ] **Step 1.3: Run integration tests**

Run: `./scripts/api-test.sh --tail 5 -m integration -v`
Expected: `265 passed`. If any test now sends `0`/`1` or `false` where an int was expected, fix the test to send the correct type.

- [ ] **Step 1.4: Run targeted schemathesis**

Run: `uv run --directory api pytest tests/schemathesis/test_schema.py -v -k 'POST /slo-definitions or DELETE /asset-groups'`
Expected: the 3 Group-B failures are gone.

- [ ] **Step 1.5: Commit**

```bash
git -C /home/domik/projects/tropek/.worktrees/contract-testing-phase-3-schemathesis add -A
git -C /home/domik/projects/tropek/.worktrees/contract-testing-phase-3-schemathesis commit -m "fix(api): Strict types on bool/int/float fields (schemathesis group B)

StrictBool on deactivate_slos query param, StrictInt on comparable_from_version,
StrictFloat on total_score thresholds. Prevents Pydantic from coercing bool<->int
on schemathesis-generated inputs."
```

---

## Task 2: sort_order int32 bound (Group C)

**Files:**
- Modify: `api/tropek/modules/display_groups/schemas.py` — `DisplayGroupCreate`, `DisplayGroupUpdate`

- [ ] **Step 2.1: Apply Field bound**

Read the schema file. Change `sort_order: int | None = None` (or similar) to:
```python
from typing import Annotated
from pydantic import Field

sort_order: Annotated[int, Field(ge=-(2**31), le=2**31 - 1)] | None = None
```
Apply to both Create and Update models (and any `DisplayGroupRead` does NOT need it).

- [ ] **Step 2.2: Integration tests**

Run: `./scripts/api-test.sh --tail 5 -m integration -v`
Expected: `265 passed`.

- [ ] **Step 2.3: Targeted schemathesis**

Run: `uv run --directory api pytest tests/schemathesis/test_schema.py -v -k 'POST /slo-display-groups'`
Expected: Group-C failure gone.

- [ ] **Step 2.4: Commit**

```bash
git -C ... add -A
git -C ... commit -m "fix(api): bound sort_order to int32 range (schemathesis group C)

Prevents schemathesis-generated int64 values from overflowing the underlying
INTEGER column at the asyncpg layer."
```

---

## Task 3: JSONB null-byte validator (Group A)

**Files:**
- Modify: `api/tropek/modules/common/schemas.py` — add `SafeJsonDict`
- Modify: `api/tropek/modules/assets/schemas.py` — apply to `tags` and `variables`
- Modify: `api/tropek/modules/quality_gate/schemas/annotations.py` — apply to `tags`
- Grep for other `tags: dict` / `variables: dict` on request bodies; apply `SafeJsonDict`

- [ ] **Step 3.1: Add validator**

Append to `api/tropek/modules/common/schemas.py`:

```python
def reject_null_bytes_in_json_dict(value: dict[str, object]) -> dict[str, object]:
    """Reject null bytes in keys or string values of a JSON dict."""
    for key, val in value.items():
        if '\x00' in key:
            raise ValueError('null bytes are not allowed in keys')
        if isinstance(val, str) and '\x00' in val:
            raise ValueError('null bytes are not allowed in values')
    return value


SafeJsonDict = Annotated[
    dict[str, object],
    AfterValidator(reject_null_bytes_in_json_dict),
]
```

- [ ] **Step 3.2: Find all call sites**

Run: `grep -rn "tags: dict" api/tropek/modules/` and `grep -rn "variables: dict" api/tropek/modules/`. For every request-body (Create/Update) schema hit, switch the type annotation to `SafeJsonDict`.

- [ ] **Step 3.3: Integration tests**

Run: `./scripts/api-test.sh --tail 5 -m integration -v`
Expected: `265 passed`. If a fixture sends `{'\x00': ...}` it should now 422 — adapt the fixture.

- [ ] **Step 3.4: Targeted schemathesis**

Run: `uv run --directory api pytest tests/schemathesis/test_schema.py -v -k 'POST /assets or PATCH /assets/ or PATCH /evaluation/'`
Expected: 3 Group-A failures gone.

- [ ] **Step 3.5: Commit**

```bash
git -C ... add -A
git -C ... commit -m "fix(api): reject null bytes in JSONB dict fields (schemathesis group A)

SafeJsonDict validator walks keys and string values rejecting \\x00. Applied to
all tags / variables request-body fields. Prevents asyncpg 500s from
schemathesis-generated JSON containing null bytes."
```

---

## Task 4: Cross-field schema constraints (Group D — schema parts)

**Files:**
- Modify: `api/tropek/modules/quality_gate/schemas/trigger.py` (or wherever `SloTestRequest` lives) — `objectives: Annotated[list[Objective], MinLen(1)]`
- Modify: `api/tropek/modules/asset_meta/schemas.py` — split `MetaSnapshotCreate` into `SnapshotValues | SnapshotClosed` discriminated union
- Modify: matching router handler for meta snapshots
- Modify: integration tests that POST `/meta/snapshots` if shape changes

- [ ] **Step 4.1: Find schema locations**

Run: `grep -rn "class MetaSnapshotCreate" api/tropek/modules/` and `grep -rn "objectives list is empty" api/tropek/modules/`. Read the files.

- [ ] **Step 4.2: MinLen on objectives**

Wrap the `objectives: list[...]` field in the validate/test request schema:
```python
from annotated_types import MinLen
from typing import Annotated

objectives: Annotated[list[Objective], MinLen(1)]
```
Remove the corresponding handler-level "objectives list is empty" ValueError (the schema now enforces it).

- [ ] **Step 4.3: Discriminated union for snapshots**

Replace single `MetaSnapshotCreate` with:

```python
from typing import Annotated, Literal
from pydantic import BaseModel, Field

class MetaSnapshotValues(StrictInput):
    kind: Literal['values']
    values: dict[str, object]
    observed_at: datetime
    source: str

class MetaSnapshotClosed(StrictInput):
    kind: Literal['closed']
    closed: Annotated[list[str], Field(min_length=1)]
    observed_at: datetime
    source: str

MetaSnapshotCreate = Annotated[
    MetaSnapshotValues | MetaSnapshotClosed,
    Field(discriminator='kind'),
]
```

Update the router handler signature. Update any repository call to branch on `kind` or handle both shapes. Delete the "must contain values or closed" handler-level ValueError.

- [ ] **Step 4.4: Migrate integration tests**

Any test calling `POST /assets/.../meta/snapshots` now needs `"kind": "values"` or `"kind": "closed"` in the body. Update fixtures.

- [ ] **Step 4.5: Integration tests pass**

Run: `./scripts/api-test.sh --tail 5 -m integration -v`
Expected: `265 passed`.

- [ ] **Step 4.6: Targeted schemathesis**

Run: `uv run --directory api pytest tests/schemathesis/test_schema.py -v -k 'meta/snapshots or slo-definitions/test'`
Expected: both failures gone.

- [ ] **Step 4.7: Regen openapi**

Run: `uv run --directory api python scripts/export-schema.py` (or equivalent — check `justfile`). Stage `api/openapi.json`.

- [ ] **Step 4.8: Commit**

```bash
git -C ... add -A
git -C ... commit -m "fix(api): schema-level cross-field constraints for meta snapshots and slo test (schemathesis group D schema parts)

MinLen(1) on SloTestRequest.objectives. MetaSnapshotCreate split into
discriminated union (kind='values' | kind='closed'), removing the handler-level
XOR validator. Both now representable in OpenAPI."
```

---

## Task 5: SLO-assignment URL refactor (Group D URL parts) — cross-stack

**Files:** (cross-stack migration — touch each in order)
- Modify: `api/tropek/modules/assignments/router.py` — replace POST+DELETE pair for each assignment kind with PUT+DELETE keyed by the target reference in URL
- Modify: `api/tropek/modules/assignments/schemas.py` — slim body to `{data_source_name: str | None}`
- Modify: `api/tropek/modules/assignments/repository.py` — functions take (source_name, target_name, data_source_name) instead of body.slo_definition_id etc.
- Modify: `api/tests/quality_gate/` tests + `api/tests/assignments/` (find via `grep -rn 'slo-assignments' api/tests/`)
- Modify: `clients/python/tropek_client/client.py` — assignment methods
- Modify: `clients/python/tests/test_client.py`
- Modify: `ui/src/features/registry/api.ts` + `ui/src/features/assets/api.ts` (grep for `slo-assignments` and `slo-group-assignments`)
- Modify: `ui/src/mocks/handlers/` — MSW assignment handlers
- Regen: `api/openapi.json`, `ui/src/generated/api.ts`

### URL surface (target)

```
PUT    /asset-groups/{group_name}/slo-definitions/{slo_definition_id}
DELETE /asset-groups/{group_name}/slo-definitions/{slo_definition_id}
PUT    /assets/{asset_name}/slo-definitions/{slo_definition_id}
DELETE /assets/{asset_name}/slo-definitions/{slo_definition_id}

PUT    /assets/{asset_name}/slo-groups/{slo_group_name}
DELETE /assets/{asset_name}/slo-groups/{slo_group_name}
PUT    /asset-groups/{group_name}/slo-groups/{slo_group_name}
DELETE /asset-groups/{group_name}/slo-groups/{slo_group_name}
```

Keep `GET /asset-groups/{name}/slo-assignments` and `GET /assets/{name}/slo-assignments` (list endpoints) unchanged.
Keep the `PATCH /assets/{name}/slo-assignments/{assignment_id}` upgrade endpoint unchanged (internally keyed by assignment id, legitimate resource).

Request body on PUT:
```json
{"data_source_name": "prometheus"}
```
or empty `{}` if `data_source_name` can be optional/defaulted.

Response: 200 OK with `SLOAssignmentRead` (upsert semantics — create or reactivate).
Response: 204 No Content on DELETE.

### Steps

- [ ] **Step 5.1: API — rewrite router handlers**

Read `api/tropek/modules/assignments/router.py` fully. Replace the 4 `POST`-pattern handlers with `PUT` handlers keyed by URL path. Each handler:
1. Look up parent (asset or group) by `{name}` → 404 if missing.
2. Look up target (slo-definition or slo-group) by URL-segment identifier → 404 if missing.
3. Upsert the assignment row.
4. Return 200 with the assignment body.

Replace the 4 `DELETE /{assignment_id}` handlers with `DELETE` keyed by target identifier. Handler:
1. Look up parent → 404.
2. Look up target → 404.
3. Deactivate/delete the matching assignment row (idempotent — 204 even if already absent).

- [ ] **Step 5.2: API — update schemas**

In `api/tropek/modules/assignments/schemas.py`, remove `slo_definition_id` / `slo_group_name` from request bodies. The body is either `class AssignmentBody(StrictInput): data_source_name: str | None = None` or removed entirely.

- [ ] **Step 5.3: API — update repository**

Repository functions now take `(parent_name, target_name_or_id, data_source_name)` directly. No more extracting from a body dataclass.

- [ ] **Step 5.4: Run integration tests**

Run: `./scripts/api-test.sh --tail 5 -m integration -v`
Expected: FAIL — tests still use old URLs. Confirm the failures are just URL-shape, not logic regressions.

- [ ] **Step 5.5: Migrate integration tests**

Rewrite every `client.post('/asset-groups/X/slo-assignments', json={...})` call to `client.put(f'/asset-groups/X/slo-definitions/{slo_id}', json={'data_source_name': ...})`. Same for the 3 other assignment kinds. Delete any "reject missing slo_definition_id" tests (replaced by natural 404).

Run: `./scripts/api-test.sh --tail 5 -m integration -v`
Expected: `265 passed`.

- [ ] **Step 5.6: SDK migration**

In `clients/python/tropek_client/client.py`, update the assignment-related methods (search for `slo-assignments`, `slo-group-assignments`). Each `assign_*` method now PUTs to the target URL.

Update `clients/python/tests/test_client.py` URL expectations.

Run: `uv run --directory clients/python pytest --tail 5`
Expected: `23 passed`.

- [ ] **Step 5.7: UI migration**

Search UI for the old URLs: `rg -n "slo-assignments|slo-group-assignments" ui/src/`. Update fetch builders to the new URL shape. Update MSW handlers to the new URL shape.

Run: `./scripts/ui-test.sh --tail 10`
Expected: all green.

- [ ] **Step 5.8: Regen openapi + api.ts**

Run: `uv run --directory api python scripts/export-schema.py`
Run: `just codegen` (or whatever regenerates `ui/src/generated/api.ts`).

Stage `api/openapi.json` and `ui/src/generated/api.ts`.

- [ ] **Step 5.9: Targeted schemathesis**

Run: `uv run --directory api pytest tests/schemathesis/test_schema.py -v -k 'assignments or slo-definitions/{slo_definition_id} or slo-groups/{slo_group_name}'`
Expected: Group D URL failures gone.

- [ ] **Step 5.10: Commit**

```bash
git -C ... add -A
git -C ... commit -m "refactor(api+ui+sdk): move slo-assignment target into URL (schemathesis group D URLs)

Replaces POST /assets/{name}/slo-assignments + {slo_definition_id in body}
with PUT /assets/{name}/slo-definitions/{slo_definition_id}. Same pattern for
the other 3 assignment variants. Body shrinks to {data_source_name?}.
Missing-target becomes natural 404 instead of 422 domain validation.

Atomic cross-stack migration: router + schemas + repository + integration
tests + Python SDK + UI + MSW + regenerated openapi.json + api.ts."
```

---

## Task 6: `GET /evaluations` `to` query nullability (Group E)

**Files:**
- Modify: router file handling `GET /evaluations` (grep: `grep -rn '"/evaluations"' api/tropek/modules/quality_gate/router.py`)

- [ ] **Step 6.1: Read current signature**

Read the handler. Current signature is likely `to_ts: datetime | None = Query(default=None, alias='to')`.

- [ ] **Step 6.2: Remove `| None` from query parameter**

Change to:
```python
to_ts: datetime | None = Query(default=None, alias='to', json_schema_extra={'nullable': False})
```
or simpler: keep `datetime | None` but ensure the generated OpenAPI parameter object has no `nullable: true`. If unclear, write a tiny test that parses the generated OpenAPI for the `to` parameter and asserts it is not marked nullable; adjust the signature until the assertion holds.

Alternative (cleaner): only accept `to` as an optional ISO datetime string; if client wants "no upper bound", omit the param entirely. This matches the domain: `to=null` has no meaningful semantics.

- [ ] **Step 6.3: Integration + schemathesis**

Run: `./scripts/api-test.sh --tail 5 -m integration -v` → 265 passed.
Run: `uv run --directory api pytest tests/schemathesis/test_schema.py -v -k 'GET /evaluations'` → failure gone.

- [ ] **Step 6.4: Commit**

```bash
git -C ... add -A
git -C ... commit -m "fix(api): GET /evaluations 'to' query param not nullable (schemathesis group E)

Schemathesis was generating the literal string 'null' because OpenAPI marked
the param as nullable. The contract never intended 'to=null' to be sent — omit
the param for 'no upper bound'."
```

---

## Task 7: MethodNotAllowedMiddleware routing fix (Group F)

**Files:**
- Modify: `api/tropek/modules/common/method_not_allowed.py`

- [ ] **Step 7.1: Read middleware**

Read the full file. Understand how it decides "path exists with other methods" vs "path does not exist at all."

- [ ] **Step 7.2: Reproduce locally**

```bash
uv run --directory api python -c "
from fastapi.testclient import TestClient
from tropek.main import app
c = TestClient(app)
r = c.delete('/slo-definitions/foo/versions')
print(r.status_code, r.text)
"
```
Expected status: `404`. Target: `405`.

- [ ] **Step 7.3: Fix middleware**

Likely cause: middleware checks for exact route match, missing the fact that `{name:path}` catches `foo/versions` on the GET route. Options:
- iterate all registered routes, match path pattern against request path; if any matches under a different method, return 405.
- or inspect `app.router.routes` via `route.matches(request.scope)`.

Implement, confirming with the reproduction above that it now returns 405.

- [ ] **Step 7.4: Integration tests + targeted schemathesis**

Run: `./scripts/api-test.sh --tail 5 -m integration -v` → 265 passed.
Run: `uv run --directory api pytest tests/schemathesis/test_schema.py -v -k 'slo-definitions/{name}/versions'` → failure gone.

- [ ] **Step 7.5: Commit**

```bash
git -C ... add -A
git -C ... commit -m "fix(api): 405 for unsupported methods on path-param subroutes (schemathesis group F)

MethodNotAllowedMiddleware now matches registered route patterns against the
request path instead of exact string equality, so DELETE /slo-definitions/foo/versions
returns 405 Method Not Allowed instead of 404 Not Found."
```

---

## Task 8: Full verification + report update

**Files:**
- Modify: `reports/schemathesis-phase3-final.md` — add final trajectory row and close-out notes

- [ ] **Step 8.1: Full schemathesis run**

Run: `uv run --directory api pytest tests/schemathesis/test_schema.py -v > /tmp/schemathesis-final.txt 2>&1`
Read the tail. Confirm `0 failed` (or identify any residuals).

- [ ] **Step 8.2: Full integration**

Run: `./scripts/api-test.sh --tail 10 -m integration -v` → 265 passed (or updated count if task 4 added/removed tests — note the number).

- [ ] **Step 8.3: UI + SDK sanity**

Run: `./scripts/ui-test.sh --tail 10` → green.
Run: `uv run --directory clients/python pytest --tail 5` → green.

- [ ] **Step 8.4: Update report**

Append to `reports/schemathesis-phase3-final.md`:

```markdown
## Final trajectory (2026-04-19, residual fixes)

| Checkpoint | Passed | Failed | Notes |
|---|---|---|---|
| ... previous rows ... |
| After Task 1 (Strict types) | 93 | 11 | |
| After Task 2 (int32 bound) | 94 | 10 | |
| After Task 3 (SafeJsonDict) | 97 | 7 | |
| After Task 4 (cross-field schema) | 99 | 5 | |
| After Task 5 (URL refactor) | 102 | 2 | |
| After Task 6 (to nullability) | 103 | 1 | |
| After Task 7 (405 middleware) | 104 | 0 | |
```

(Numbers are placeholders — fill with actual observed counts.)

- [ ] **Step 8.5: Commit report + close out**

```bash
git -C ... add reports/schemathesis-phase3-final.md
git -C ... commit -m "docs: schemathesis residual-fix trajectory (0 failures)"
```

---

## Rollback

If any commit breaks `test-int`, revert that single commit (`git revert <sha>`) and debug in isolation — do not proceed to the next task with integration tests red.
