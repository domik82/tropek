# Refetch from Source — Design Spec

## Problem

TROPEK's re-evaluate feature re-scores historical evaluations against updated SLO thresholds, but
it always uses cached SLI values from the original evaluation. There is no way to re-fetch fresh
data from the adapter (e.g., Prometheus). This matters when the original evaluation returned nulls
or incorrect values due to transient adapter issues, data lag, or misconfigured queries.

## Solution

Add a `refetch_from_source` toggle (default off) to the re-evaluate endpoint. When enabled, instead
of re-scoring cached data inline, the system:

1. Marks each original evaluation as **superseded** (hidden from UI, excluded from baselines)
2. Creates new evaluations for the same time windows via `TriggerService`
3. New evaluations go through the standard worker pipeline (adapter query → evaluate → write)
4. Returns a simple `{ queued: N }` acknowledgment (async — results arrive via normal worker flow)

When `refetch_from_source=False`, the existing synchronous re-score behavior is unchanged.

## Data Model

### New column: `superseded`

Boolean column on `Evaluation`, default `False`. Mirrors the existing `invalidated` pattern.

Superseded evaluations are:
- Hidden from heatmaps and evaluation lists
- Excluded from baseline candidate queries
- Excluded from re-evaluation scope queries
- Not pinnable as baselines

If a superseded evaluation had a baseline pin, the pin is cleared.

### New column: `supersedes_id`

Nullable FK (`evaluations.id`) on `Evaluation`. Points from the replacement evaluation to the
original it replaced. Used for the UI indicator ("this replaced a previous evaluation").

### Migration

One Alembic migration adding both columns:
- `superseded: bool, default=False, not null`
- `supersedes_id: UUID, nullable, FK → evaluations.id`

## API Changes

### Request: `ReEvaluateRequest`

Add field:
```
refetch_from_source: bool = False
```

### Response: `ReEvaluateResponse`

Add optional field:
```
queued: int | None = None
```

Present only when `refetch_from_source=True`. The `results` list is empty in this case (results
arrive asynchronously). When `refetch_from_source=False`, behavior is unchanged — `queued` is
`None` and `results` contains the before/after diff.

### Endpoint behavior when `refetch_from_source=True`

1. Resolve scope (from_date / from_baseline / from_evaluation_id) — same as today
2. Load evaluations in scope
3. For each evaluation:
   - Mark original as `superseded`, clear any baseline pin
   - Call `TriggerService` with the original's metadata (asset, SLI, datasource, time window,
     variables) plus `supersedes_id=original.id` and `skip_dedup=True`. The SLO version used
     is the request's `slo_version` override if provided, otherwise the original eval's version.
     The SLI version is always the original eval's version (re-fetch uses the same queries).
4. Return `{ queued: N, slo_version_used: V, affected_evaluations: N, results: [] }`

## TriggerService Changes

Add two optional parameters to the trigger method:
- `supersedes_id: UUID | None = None` — set on the new evaluation row
- `skip_dedup: bool = False` — bypass duplicate detection for the time window

No other changes to trigger flow. The new evaluation is enqueued as a normal `run_evaluation_job`.

## Worker Changes

None. The existing `run_evaluation` handles everything — the new pending evaluations have all
required metadata. The worker queries the adapter, evaluates, writes indicator rows and SLI values
exactly as for fresh evaluations.

## Query Filtering

Every query that currently filters `invalidated == False` must also filter `superseded == False`:

| Location | Query purpose |
|---|---|
| `trend_repository.py` (2 places) | Heatmap and trend data |
| `baseline_repository.py:137` | Baseline candidate selection |
| `baseline_repository.py:192` | Re-evaluation scope loading |

## UI Changes

### ReEvaluateForm

- New checkbox: "Refetch data from source" (default: off)
- When checked, form description updates to indicate data will be re-fetched from the adapter
- On submit, payload includes `refetch_from_source: true`
- Response handling: show "N evaluations queued for re-evaluation" instead of the results table
- React Query invalidation triggers so the user sees new pending evaluations appearing

### TypeScript types

- `ReEvaluatePayload`: add `refetch_from_source?: boolean`
- `ReEvaluateResponse`: add `queued?: number`

### Superseded indicator

- Evaluations with `supersedes_id` set show a small icon (similar to existing invalidation styling)
- Tooltip: "Re-fetched from source — replaces earlier evaluation"
- No drill-into-history for now (phase 2: version chain display)

### Heatmap / list filtering

Superseded evaluations are excluded server-side. No UI filtering changes needed — the API already
won't return them in default queries.

## Phase 2 (out of scope)

- Job tracking: return a batch ID, poll for progress, show before/after diff when complete
- Supersede history chain: click indicator to see v1 → v2 → v3 progression
- Baseline pin indicator on UI (general feature, not specific to refetch)

## Testing

- **Unit tests**: Re-evaluator refetch path — calls TriggerService with correct params, marks
  originals as superseded, clears baseline pins, returns queued count
- **Integration tests**: Create evaluation with stored results, call re-evaluate with
  `refetch_from_source=True`, verify original is superseded, new eval is pending with correct
  metadata and `supersedes_id` FK
- **Filter tests**: Verify superseded evals excluded from trend queries, baseline queries, and
  re-evaluation scope queries (same pattern as existing invalidated filtering tests)
- **UI tests**: ReEvaluateForm toggle renders, payload includes `refetch_from_source` when checked
