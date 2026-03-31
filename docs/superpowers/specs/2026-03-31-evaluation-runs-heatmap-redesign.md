# Evaluation Runs & Composite Heatmap Redesign

**Date:** 2026-03-31
**Status:** Draft
**Prerequisite:** `docs/superpowers/plans/2026-03-31-binding-model-hard-cut.md` must land first.

---

## Problem

The current evaluation model is flat: every SLO evaluation is a top-level entity with no parent. When an asset has 30 SLOs and a batch is triggered for 3 days, the heatmap receives 90 independent evaluations. Each gets its own column, producing 90 overlapping columns instead of 3. Grouping was attempted via `(period_start, evaluation_name)` inference — this is fragile, breaks with mixed cadences, and has no authoritative identity.

Root cause: there is no first-class concept of "evaluate this asset for this time window". That concept needs to exist in the data model.

---

## Goals

1. Introduce `evaluation_runs` as the authoritative parent — one run per (asset, eval_name, period). Heatmap columns are always runs.
2. Rename `evaluations` → `slo_evaluations` — they become children of a run, not top-level entities. Triggering is always asset-level; the user never targets a single SLO directly.
3. Drop `evaluation_batches` — replaced by the proper FK model.
4. Fix the heatmap API to return a grouped response (runs → SLO groups → indicators).
5. Fix the heatmap UI: one column per run, accordion SLO groups with expand/collapse.
6. Fix the SLI breakdown table: SLO section headers replacing the tab bar.
7. Fix trend charts: SLO-grouped sections.
8. Enforce `{table}_id` naming on all FK columns throughout.

---

## Breaking Changes

- `POST /evaluations/trigger` → `POST /evaluation-runs`
- `POST /evaluations/trigger-batch` → `POST /evaluation-runs/batch`
- `GET /evaluations/metric-heatmap` → `GET /evaluation-runs/metric-heatmap`
- `GET /evaluations/metric-heatmap` response shape changes completely (grouped schema).
- Python SDK client (`TropekClient`) must be updated to reflect the new endpoints.
- All existing `evaluation_batches` data is dropped (hard cut, no migration).
- All existing `evaluations` rows require backfill of `evaluation_run_id` — not feasible without original trigger context. Existing data is dropped and re-evaluated if needed.

---

## Out of Scope

- `slo_bindings` → two concrete FK tables (`asset_slo_bindings`, `asset_group_slo_bindings`). Follow-on after binding hard cut.
- `data_source_name` → `data_source_id FK` migration. Follow-on.
- SLO-level weights or importance flags for run scoring. Deferred — design not settled.

---

## Database Schema

### Naming convention (mandatory)

Every FK column must be named `{referenced_table_singular}_id`. No exceptions without documented justification.

### Documented text-ref exceptions

| Column | Table | Reason |
|---|---|---|
| `slo_name`, `slo_version` | `slo_evaluations` | Versioned snapshot — the exact SLO version at eval time is preserved. Hard FK to `slo_definitions.id` would prevent archiving old versions that have eval history. |
| `sli_name`, `sli_version` | `slo_evaluations` | Same as above. |
| `data_source_name` | `slo_evaluations` | Follow-on FK migration. |
| `slo_name` | `slo_bindings` | Resolved to latest active version at trigger time, not pinned to a specific version. |
| `target_id` | `slo_bindings`, `template_bindings` | Polymorphic target — follow-on split into concrete tables. |
| `asset_name`, `evaluation_name` | `sli_values` | Intentional denormalisation for Grafana queries (no joins in Grafana SQL). |

### New table: `evaluation_runs`

```sql
CREATE TABLE evaluation_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id        UUID NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
    eval_name       TEXT NOT NULL,
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','running','completed','failed')),
    result          TEXT CHECK (result IN ('pass','warning','fail','error') OR result IS NULL),
    achieved_points INTEGER,
    total_points    INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_evaluation_runs_asset      ON evaluation_runs (asset_id);
CREATE INDEX idx_evaluation_runs_status     ON evaluation_runs (status);
CREATE INDEX idx_evaluation_runs_period     ON evaluation_runs (asset_id, period_start DESC);
```

**`result`** — worst-case across all child `slo_evaluations` results.
**`achieved_points` / `total_points`** — raw sum of `score × weight` points across all child evaluations' indicator results. Informational only — not used as a pass/fail criterion at the run level. Displayed as a fraction or percentage in the UI.

### Renamed table: `slo_evaluations` (was `evaluations`)

Add column:
```sql
ALTER TABLE evaluations
    RENAME TO slo_evaluations;

ALTER TABLE slo_evaluations
    ADD COLUMN evaluation_run_id UUID NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    ADD COLUMN achieved_points INTEGER,
    ADD COLUMN total_points INTEGER;
```

Rename FK columns to comply with naming convention:
```sql
-- No column renames needed on slo_evaluations itself —
-- asset_id is already correct. Child tables need updating (see below).
```

### Renamed FK columns in child tables

```sql
-- indicator_results
ALTER TABLE indicator_results
    RENAME COLUMN evaluation_id TO slo_evaluation_id;

-- sli_values
ALTER TABLE sli_values
    RENAME COLUMN eval_id TO slo_evaluation_id;

-- evaluation_annotations
ALTER TABLE evaluation_annotations
    RENAME COLUMN evaluation_id TO slo_evaluation_id;
```

### Asset group tables — FK rename

```sql
ALTER TABLE asset_group_members
    RENAME COLUMN group_id TO asset_group_id;

ALTER TABLE asset_group_links
    RENAME COLUMN parent_group_id TO parent_asset_group_id,
    RENAME COLUMN child_group_id  TO child_asset_group_id;
```

### Dropped table: `evaluation_batches`

```sql
DROP TABLE evaluation_batches;
```

Replaced entirely by `evaluation_runs`. The JSONB `evaluation_ids[]` list is replaced by the `slo_evaluations.evaluation_run_id` FK.

---

## Trigger API

### Principle

Triggering is always **asset-level**. The user provides an asset + eval name + time window. The system discovers all SLOs bound to the asset (via `slo_bindings`) and evaluates all of them. There is no user-facing trigger that targets a single SLO.

### Endpoints

**Single trigger:**
```
POST /evaluation-runs
{
  "asset_name": "checkout-api",
  "eval_name": "daily-evaluation",
  "period_start": "2026-01-15T00:00:00Z",
  "period_end": "2026-01-15T23:59:59Z"
}
→ 201 { "evaluation_run_id": "uuid", "slo_evaluation_ids": ["uuid", ...] }
```

**Batch trigger** (multiple periods for one asset, or multiple asset+period entries):
```
POST /evaluation-runs/batch
{
  "asset_name": "checkout-api",
  "eval_name": "daily-evaluation",
  "periods": [
    { "start": "2026-01-15T00:00:00Z", "end": "2026-01-15T23:59:59Z" },
    { "start": "2026-01-16T00:00:00Z", "end": "2026-01-16T23:59:59Z" }
  ]
}
→ 201 { "evaluation_run_ids": ["uuid", "uuid"], "slo_evaluation_ids": ["uuid", ...] }
```

Or heterogeneous list:
```
POST /evaluation-runs/batch
{
  "evals": [
    { "asset_name": "...", "eval_name": "...", "period_start": "...", "period_end": "..." },
    ...
  ]
}
```

### Worker flow

1. Run is created with `status=pending`.
2. N worker jobs enqueued — one per SLO binding resolved for the asset.
3. Each worker: evaluates its SLO, writes `slo_evaluations` row with `achieved_points` + `total_points`, updates `status`.
4. On each child completion: check if all siblings for `evaluation_run_id` are done → if so, aggregate `result` (worst-case) and `achieved_points`/`total_points` (sum), set run `status=completed`.

---

## Heatmap API

### Response schema

```python
class HeatmapSummaryCell(BaseModel):
    """Per-slot aggregate for a SLO group or the composite row."""
    slot: datetime                 # period_start of the evaluation_run
    result: str                    # worst-case across indicators in this group/run
    score: float                   # achieved_points / total_points × 100
    evaluation_run_id: uuid.UUID   # for click navigation

class SloGroup(BaseModel):
    """One SLO's indicators within a run."""
    slo_name: str
    slo_display_name: str | None = None
    metrics: list[HeatmapMetric]           # indicator definitions
    cells: list[HeatmapCell]               # indicator × slot cells
    summary: list[HeatmapSummaryCell]      # per-slot aggregate (collapsed header row)

class EvaluationRunColumn(BaseModel):
    """Metadata for one heatmap column."""
    evaluation_run_id: uuid.UUID
    period_start: datetime         # column label
    period_end: datetime
    eval_name: str

class MetricHeatmapResponse(BaseModel):
    asset_name: str
    columns: list[EvaluationRunColumn]   # ordered oldest→newest
    groups: list[SloGroup]               # SLO groups in order
    composite: list[HeatmapSummaryCell]  # Overall row spanning all groups
```

`HeatmapCell` changes:
- `eval_id` → `slo_evaluation_id` (renamed per FK convention)
- `slot: datetime` → `evaluation_run_id: UUID` (column identity is the run, not the timestamp)
- Add `period_start: datetime` (display only — tooltip and x-axis label)

The frontend uses `evaluation_run_id` to map cells to columns and `period_start` for display. This removes the timestamp-as-column-key ambiguity that caused the original N-columns bug.

### Endpoint

```
GET /evaluation-runs/metric-heatmap?asset_name=X&eval_name=Y&from=T&to=T&limit=N
```

Column key = `evaluation_run_id` (UUID, guaranteed unique). `period_start` is the display label only.

---

## Frontend

### Config: default expand state

`config.yaml` gains:
```yaml
ui:
  heatmap_slo_groups_expanded_by_default: true
```

Loaded at startup, exposed via a `/config` API endpoint the UI reads on mount. No user-level preference yet — app-level only.

### Types (`ui/src/features/navigator/types.ts`)

```typescript
export interface EvaluationRunColumn {
  evaluation_run_id: string
  period_start: string
  period_end: string
  eval_name: string
}

export interface HeatmapSloGroup {
  slo_name: string
  slo_display_name?: string
  metrics: Array<{ name: string; display_name: string }>
  cells: MetricHeatmapCell[]
  summary: Array<{ slot: string; result: string; score: number; evaluation_run_id: string }>
}

export interface MetricHeatmapResponse {
  asset_name: string
  columns: EvaluationRunColumn[]
  groups: HeatmapSloGroup[]
  composite: Array<{ slot: string; result: string; score: number; evaluation_run_id: string }>
}
```

### Heatmap: accordion rows

`buildAssetHeatmapData()` in `utils.ts` is rewritten:

- Columns = `response.columns` (one per `evaluation_run_id`).
- Rows = flat array built from expand state: for each group, if expanded → emit SLO header row + indicator rows; if collapsed → emit SLO header row only.
- SLO header row uses `group.summary` cells for collapsed status display.
- Overall Score row is always visible at the top, built from `response.composite`.

Expand/collapse state lives in `AssetPanel` as `Map<slo_name, boolean>`, initialised from the config flag.

**Collapse/expand interactions:**
- Click SLO header row → toggle that group's expand state.
- Click indicator cell → expand that group if collapsed, scroll to SLI table section.
- Click Overall Score cell → expand all groups, scroll to SLI table.

`HeatmapChart` receives the already-flattened rows — no changes to the chart renderer itself.

### SLI breakdown table

`EvaluationTabs` component is removed. `SLIBreakdownTable` is replaced by `SLIBreakdownGrouped`:

- Renders a section header row per SLO group (SLO name + score badge + expand/collapse chevron).
- Under each header: the indicator rows for that SLO (same columns as today).
- Expand/collapse state shared with the heatmap accordion (same `Map` from `AssetPanel`).
- `mergedIndicators` in `AssetPanel` changes from `flatMap` to a structured `Array<{ slo_name, slo_display_name, indicators }>` built from `allSlotEvals`.

### Trend charts

`AssetPanelHeatmapView` renders trend charts grouped by SLO:

- One collapsible section per SLO group.
- Section header shows SLO name + indicator count.
- Chart grid inside each section (same `MetricTrendBlock` components as today).
- Expand/collapse state shared with the same `Map`.

---

## Testing

### Backend

- New integration tests: `test_evaluation_run_repository.py` — CRUD, status rollup, result aggregation.
- Update `test_trigger_service.py`: trigger creates run + N children.
- Update `test_heatmap_endpoints.py`: grouped response shape, correct column keys.
- Update `test_heatmap_query.py`: multi-SLO asset produces one column per run, not per SLO.
- Migration test: drop `evaluation_batches`, rename `evaluations`, add `evaluation_run_id NOT NULL`.

### Frontend

- Update `AssetHeatmap.test.tsx`: multi-SLO response renders correct column count.
- Update `utils.test.ts`: `buildAssetHeatmapData` with grouped response.
- New `SLIBreakdownGrouped.test.tsx`: section headers, expand/collapse.
- Mock handlers updated to return new grouped `MetricHeatmapResponse` shape.

---

## Phasing

This spec is large. Recommended implementation order:

1. **DB + migration** — create `evaluation_runs`, rename `evaluations` → `slo_evaluations`, rename FK columns, drop `evaluation_batches`.
2. **Trigger layer** — update `POST /evaluation-runs`, `POST /evaluation-runs/batch`, worker rollup logic.
3. **Heatmap API** — new grouped endpoint response.
4. **Frontend types + data layer** — update types, `buildAssetHeatmapData`, mock handlers.
5. **Heatmap accordion UI** — expand/collapse state, SLO header rows.
6. **SLI table** — `SLIBreakdownGrouped` replacing `EvaluationTabs` + flat table.
7. **Trend charts** — SLO-grouped sections.
8. **Config** — `heatmap_slo_groups_expanded_by_default` flag wired end-to-end.
