# End-to-End Wiring Design

> Wire all TROPEK layers together: DB schema fixes, evaluation lifecycle (baseline pinning,
> status overrides), mock adapter, real Prometheus adapter, evaluation trigger/worker flow,
> and integration test pipeline.

## Context

The DB layer, SLO/SLI/asset CRUD, and UI are largely built but not wired together. Key gaps:

- UI expects endpoints that don't exist (trigger evaluation, pin baseline, override status, heatmap)
- Prometheus adapter has no `/query` implementation
- No way to run end-to-end evaluations without a real monitoring stack
- Bootstrap mock has incomplete seed data (empty groups, no eval trigger path)

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Implementation order | Bottom-up (schema → lifecycle → mock → trigger → integration) | Each phase testable in isolation, no circular deps |
| Baseline pinning | Sliding floor — `get_baselines()` can't look past the pinned eval | Matches "new release = new starting point" workflow |
| Pin history | Preserved — old pins get `unpinned_at`, new pin set atomically | Audit trail across releases |
| Status override | Store `original_result`, update `result` directly | Simple, queryable, reversible |
| Group trigger | Fan-out with rollup via `EvaluationBatch` | Individual asset evals useful standalone; rollup gives group view |
| Batch completion | Wait for all, with timeout via existing watchdog | Stuck evals marked partial, batch completes with available results |
| Mock adapter | Single container, namespace routing via `X-Datasource-Name` header | One mock simulates multiple datasource types (2x Prometheus + Splunk) |
| Mock data store | CSV files generated from scenario YAML definitions | Easy to maintain, deterministic, version-controllable |
| Prometheus adapter | Thin passthrough — no aggregation, PromQL must return single series | Adapter is dumb pipe; query authors responsible for correct PromQL |
| Adapter contract change | Add `X-Datasource-Name` header to all adapter calls | Backward-compatible; real adapters ignore it, mock uses it for routing |
| SLO schema | Already correct — `SLODefinitionRead` has `objectives[]` + `comparison` | No schema change needed; YAML export is a separate client-side concern |
| Single vs batch trigger | Two endpoints: `POST /evaluations` + `POST /evaluations/batch` | CI pipelines trigger per-asset; UI triggers per-group |

---

## Phase 1: Schema Fixes

### Migration 003 — Baseline Pin + Override Columns

New columns on `evaluations`:

```
baseline_pinned_at      TIMESTAMPTZ  nullable
baseline_unpinned_at    TIMESTAMPTZ  nullable
baseline_pin_reason     TEXT         nullable
baseline_pin_author     TEXT         nullable
original_result         TEXT         nullable  (same check constraint as result)
override_reason         TEXT         nullable
override_author         TEXT         nullable
```

New columns on `evaluation_batches` (for rollup results):

```
result              TEXT         nullable  (pass/warning/fail)
score               FLOAT        nullable
rollup_details      JSONB        nullable  (per-eval breakdown)
```

New partial unique index (DB-enforced single active pin per asset+SLO):

```sql
CREATE UNIQUE INDEX uq_evaluations_active_pin
ON evaluations (asset_id, slo_name)
WHERE baseline_pinned_at IS NOT NULL AND baseline_unpinned_at IS NULL;
```

Check constraint on `original_result`:

```sql
ALTER TABLE evaluations ADD CONSTRAINT ck_evaluations_original_result
CHECK (original_result IN ('pass', 'warning', 'fail', 'error') OR original_result IS NULL);
```

Active pin: `baseline_pinned_at IS NOT NULL AND baseline_unpinned_at IS NULL`.
Only one active pin per `(asset_id, slo_name)` — enforced at DB level by unique partial index.

### SLO Read Schema — Already Correct

`SLODefinitionRead` already has structured `objectives: list[SLOObjectiveRead]` and
`comparison: dict[str, Any]`. No schema change needed. YAML export for git-backed config
is handled by the Python client's manifest system (serializes structured data to YAML).

### Existing Endpoints — Already Implemented

The following endpoints already exist and need no changes:

- `POST /slo-definitions/validate` — accepts `SLOValidateRequest` with structured `objectives[]`
- `PATCH /asset-groups/{name}` — accepts `AssetGroupUpdate` with `display_name`, `description`
- `DELETE /asset-groups/{name}?deactivate_slos=bool` — cascading delete with SLO deactivation

**Note:** The SLO validate endpoint accepts structured input (not `slo_yaml`). If YAML-based
validation is needed in future, it would be a separate endpoint or request variant.

---

## Phase 2: Evaluation Lifecycle Endpoints

### Schema Changes

Add to `EvaluationSummary` (and thus `EvaluationDetail` which extends it):

```python
baseline_pinned_at: datetime | None = None
baseline_unpinned_at: datetime | None = None
baseline_pin_reason: str | None = None
baseline_pin_author: str | None = None
original_result: str | None = None
override_reason: str | None = None
override_author: str | None = None
```

New request schemas:

```python
class PinBaselineRequest(BaseModel):
    reason: str
    author: str

class OverrideStatusRequest(BaseModel):
    new_result: str  # pass, warning, fail
    reason: str
    author: str

class MetricHeatmapResponse(BaseModel):
    asset_name: str
    slots: list[datetime]
    metrics: list[dict[str, str]]
    cells: list[dict[str, Any]]
```

### Pin Baseline

**`PATCH /evaluations/{eval_id}/pin-baseline`**
- Body: `{reason: str, author: str}`
- Preconditions: eval is `completed` and not `invalidated`
- Steps:
  1. Find current active pin for same `(asset_id, slo_name)`
  2. If found: set `baseline_unpinned_at = now()` on old pin
  3. Set `baseline_pinned_at = now()`, `baseline_pin_reason`, `baseline_pin_author` on target eval
- Returns `EvaluationDetail`

**`PATCH /evaluations/{eval_id}/unpin-baseline`**
- No body
- Sets `baseline_unpinned_at = now()`
- No new pin set — baseline falls back to full history
- Returns `EvaluationDetail`

### Baseline Resolution Change

**Changes to `EvaluationRepository.get_baselines()`:**

The existing method signature is:
```python
async def get_baselines(self, *, name, scope_tags, asset_snapshot, include_result_with_score, limit, sli_name=None)
```

It queries by test `name` + JSONB tag matching. Two changes needed:

1. **Add `asset_id` and `slo_name` parameters** to the method signature (both optional,
   for backward compatibility with push/file evaluations that have no asset).

2. **Pin-aware filtering** — before the existing query logic, look up the active pin:

```python
if asset_id and slo_name:
    pin_query = select(Evaluation).where(
        Evaluation.asset_id == asset_id,
        Evaluation.slo_name == slo_name,
        Evaluation.baseline_pinned_at.is_not(None),
        Evaluation.baseline_unpinned_at.is_(None),
    )
    pin = (await self._session.execute(pin_query)).scalar_one_or_none()
    if pin is not None:
        q = q.where(Evaluation.period_start >= pin.period_start)
```

The caller (worker job) passes `asset_id` and `slo_name` from the evaluation record.
Existing callers that don't pass these params get unchanged behavior (full history).

### Override Status

**`PATCH /evaluations/{eval_id}/override-status`**
- Body: `{new_result: str, reason: str, author: str}` — `new_result` in (pass, warning, fail)
- Preconditions: eval is `completed`
- Steps:
  1. Store `result` → `original_result`
  2. Set `result = new_result`, `override_reason`, `override_author`
- Returns `EvaluationDetail`

**`PATCH /evaluations/{eval_id}/restore-override`**
- No body
- Restores `result = original_result`, clears `original_result`, `override_reason`, `override_author`
- Returns `EvaluationDetail`

### Metric Heatmap

**`GET /evaluations/metric-heatmap?asset_name=X&limit=20`**
- Resolves `asset_name` → `asset_id` via `AssetRepository.get_by_name()` (404 if not found)
- Fetches last N evaluations for the asset by `asset_id`
- Extracts `indicator_results` JSONB per eval
- Response:

```python
{
    "asset_name": str,
    "slots": [iso_timestamps],           # one per eval, ordered by period_start
    "metrics": [{"name": str, "display_name": str}],
    "cells": [{"slot": str, "metric": str, "result": str, "score": float, "eval_id": uuid}]
}
```

Read-only aggregation, no new tables.

---

## Phase 3: Mock Adapter

### Service Structure

```
adapters/mock/
├── app/
│   ├── main.py          — FastAPI: POST /query, GET /health
│   └── csv_store.py     — CSV reader with time-range lookup
├── data/                — generated CSVs (gitignored)
│   ├── prometheus-dc-a/
│   │   ├── response_time_p99.csv
│   │   └── error_rate.csv
│   ├── prometheus-dc-b/
│   │   └── cpu_usage.csv
│   └── splunk-prod/
│       └── query_latency_p99.csv
├── scenarios/
│   ├── stable.yaml
│   ├── regression.yaml
│   └── recovery.yaml
├── generate.py          — reads scenarios, writes CSVs
├── pyproject.toml
└── Dockerfile
```

### Adapter Contract

Same as all adapters:

```
POST /query
{
    "queries": {"metric_name": "query_string", ...},
    "start": "iso",
    "end": "iso"
}

Response:
{
    "values": {"metric_name": float, ...},
    "errors": {"metric_name": "error message", ...}
}

GET /health
{"status": "ok", "datasource": "mock"}
```

Routing: reads `X-Datasource-Name` header → picks `data/{namespace}/` directory.
Lookup: finds CSV rows where `start <= timestamp <= end`, returns last value per metric.
No data in range → metric goes to `errors`.

### CSV Format

```csv
timestamp,metric_name,value
2026-03-15T08:00:00Z,response_time_p99,445.2
2026-03-15T08:05:00Z,response_time_p99,451.8
```

One CSV per metric per namespace, or combined — the store matches by `metric_name` column.

### Scenario YAML Format

```yaml
name: regression
metrics:
  response_time_p99:
    baseline: 450
    phases:
      - duration_hours: 24
        pattern: stable
        jitter_pct: 5
      - duration_hours: 12
        pattern: ramp
        target: 800
        jitter_pct: 3
      - duration_hours: 24
        pattern: stable
        jitter_pct: 5
  error_rate:
    baseline: 0.001
    phases:
      - duration_hours: 60
        pattern: stable
        jitter_pct: 10
interval_minutes: 5
start: "2026-03-15T00:00:00Z"
```

Generator patterns: `stable` (baseline + jitter), `ramp` (linear to target), `spike` (jump then return).
Deterministic: scenario name used as random seed.

### Docker Compose

```yaml
adapter-mock:
  build: ./adapters/mock
  ports: ["8082:8082"]
  volumes: ["./adapters/mock/data:/app/data:ro"]
```

### API-Side Change

Worker adds header when calling any adapter:

```python
headers={"X-Datasource-Name": datasource.name}
```

Backward-compatible — real Prometheus adapter ignores the header.

---

## Phase 4: Evaluation Trigger + Worker

### Single Trigger

**`POST /evaluations`**
- Body:

```python
{
    "asset_name": str,
    "test_name": str,
    "slo_name": str,
    "period_start": datetime,
    "period_end": datetime,
    "metadata": dict = {}
}
```

- Steps:
  1. Resolve asset by name (404 if not found)
  2. Look up `AssetSLOLink` for asset + slo_name → get `sli_name`, `data_source_name`
  3. Resolve latest active versions: SLI definition, SLO definition, datasource
  4. Snapshot asset (name, labels) into `asset_snapshot`
  5. Create evaluation `status=pending`, enqueue Redis job
  6. Return `{id: uuid, status: "pending"}` — 202 Accepted

### Batch Trigger

**`POST /evaluations/batch`**
- Body:

```python
{
    "group_name": str,
    "test_name": str,
    "period_start": datetime,
    "period_end": datetime,
    "metadata": dict = {}
}
```

- Steps:
  1. Resolve group, get all member assets
  2. For each member: look up `AssetSLOLink`(s) + `AssetGroupSLOLink`(s)
  3. Create pending evaluation per asset per SLO link, enqueue jobs
  4. Create `EvaluationBatch` with `status=pending`, `evaluation_ids=[...]`
  5. Return `{batch_id: uuid, evaluation_ids: [...], status: "pending"}` — 202 Accepted

### Worker Job (arq task)

```
1. mark_running(eval_id, worker_id)
2. Load SLO definition + objectives → build_slo()
3. Build variables from asset labels + metadata + timestamps
4. Substitute variables into SLI queries
5. HTTP POST to adapter /query (with X-Datasource-Name header)
6. Resolve baselines (pin-aware):
   - Check for active pin on (asset_id, slo_name)
   - If pin: WHERE period_start >= pin.period_start
   - Fetch N previous completed, non-invalidated evals
   - Aggregate with SLO's aggregate function
7. evaluate(slo, metrics, baselines) — pure engine
8. mark_completed() with result, score, indicator_results
9. write_sli_values() for TimescaleDB
10. If batch member: check if all batch evals done → trigger rollup
```

### Batch Rollup

When last eval in batch completes (or watchdog marks stuck eval as partial):

- Collect all batch eval results
- Weighted score: `sum(eval.score * member.weight) / sum(weights)` for completed evals
- Overall result: worst-case of member results against SLO thresholds
- Update `EvaluationBatch.status = completed`, `result`, `score`, and `rollup_details` JSONB

### Timeout / Recovery

- Existing `find_stuck()` watchdog: evals in `running` > `stuck_job_threshold_seconds` → marked `partial`
- Batch treats `partial`/`failed` as done — rollup proceeds with available results
- Batch itself has no separate timeout — it resolves when all member evals reach terminal state

---

## Phase 5: Prometheus Adapter + Integration Test

### Prometheus Adapter (`adapters/prometheus/`)

Implement `POST /query`:

- For each metric in `queries` dict:
  1. Call Prometheus HTTP API `GET /api/v1/query_range` with the PromQL string, `start`, `end`, auto-calculated `step`
  2. Expect single time series in response — if multiple series returned, error for that metric
  3. Take the last data point value from the series
  4. Per-query timeout from config
- Return `{values: {...}, errors: {...}}`

The adapter is a thin passthrough. PromQL queries are pre-written to return single series
(e.g., `sum(rate(...))`, `avg(rate(...))`). The adapter does not aggregate or transform results.

`X-Datasource-Name` header received but ignored.

### Python Client Additions

```python
client.evaluations.trigger(asset_name, test_name, slo_name, period_start, period_end, metadata={})
client.evaluations.trigger_batch(group_name, test_name, period_start, period_end, metadata={})
client.evaluations.pin_baseline(eval_id, reason, author)
client.evaluations.unpin_baseline(eval_id)
client.evaluations.override_status(eval_id, new_result, reason, author)
client.evaluations.restore_override(eval_id)
```

### Bootstrap Manifest Updates

- Add group members: `core-services` ← checkout-api, product-catalog, user-service; `data-tier` ← orders-db
- Add second datasource: `mock-dc-b` with `adapter_url: http://adapter-mock:8082` (different namespace)
- SLI queries use `$asset_name` and `$instance` variables matching bootstrap assets

### Scenario Data

- `stable` scenario: 48h of flat metrics with 5% jitter — for checkout-api, product-catalog, user-service
- `regression` scenario: stable 24h → ramp up 12h → stable 24h — for orders-db

### Integration Test Flow

```
1. docker-compose up (mock adapter + API + worker + DB + Redis)
2. Generate scenario CSVs
3. Apply bootstrap manifests via client
4. Trigger single eval for checkout-api → poll until completed → assert pass
5. Trigger batch for core-services → poll until batch completed → verify rollup
6. Pin first eval as baseline
7. Trigger second eval (regression time window) → assert fail (degraded vs pinned baseline)
8. Override failed eval to pass → verify result changes
9. Tear down
```

---

## Files Changed / Created Summary

### New Files

| File | Phase |
|------|-------|
| `api/alembic/versions/003_baseline_pin_and_override.py` | 1 |
| `adapters/mock/app/main.py` | 3 |
| `adapters/mock/app/csv_store.py` | 3 |
| `adapters/mock/generate.py` | 3 |
| `adapters/mock/scenarios/*.yaml` | 3 |
| `adapters/mock/pyproject.toml` | 3 |
| `adapters/mock/Dockerfile` | 3 |

### Modified Files

| File | Phase | Change |
|------|-------|--------|
| `api/app/db/models.py` | 1 | Add 7 columns to Evaluation |
| `api/app/db/models.py` | 1 | Add 3 columns to EvaluationBatch (result, score, rollup_details) |
| `api/app/modules/quality_gate/schemas.py` | 2 | Add pin/override fields to EvaluationSummary/Detail, request schemas, heatmap response |
| `api/app/modules/quality_gate/router.py` | 2 | Add pin/unpin, override/restore, heatmap endpoints |
| `api/app/modules/quality_gate/repository.py` | 2 | Add pin/override methods, update get_baselines() |
| `docker-compose.yml` | 3 | Add adapter-mock service |
| `api/app/modules/quality_gate/router.py` | 4 | Add POST /evaluations, POST /evaluations/batch |
| `adapters/prometheus/app/main.py` | 5 | Implement POST /query |
| `clients/python/tropek_client/client.py` | 5 | Add trigger, pin, override methods to _Evaluations class |
| `bootstrap_mock/manifests/*.yaml` | 5 | Add group members, second datasource |
