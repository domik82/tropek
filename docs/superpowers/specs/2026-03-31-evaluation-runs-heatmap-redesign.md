# Evaluations & Composite Heatmap Redesign

**Date:** 2026-03-31
**Status:** Draft
**Prerequisite:** `docs/superpowers/plans/2026-03-31-binding-model-hard-cut.md` must land first.

---

## Problem

The current evaluation model is flat: every SLO evaluation is a top-level entity with no parent. When an asset has 30 SLOs and a batch is triggered for 3 days, the heatmap receives 90 independent evaluations. Each gets its own column, producing 90 overlapping columns instead of 3. Grouping was attempted via `(period_start, evaluation_name)` inference — this is fragile, breaks with mixed cadences, and has no authoritative identity.

Root cause: there is no first-class concept of "evaluate this asset for this time window". That concept needs to exist in the data model.

---

## Goals

1. Introduce `evaluations` as the authoritative parent — one evaluation per (asset, eval_name, period). Heatmap columns are always parent evaluations.
2. Rename old `evaluations` → `slo_evaluations` — they become children, not top-level entities. Triggering is always asset-level; the user never targets a single SLO directly.
3. Drop `evaluation_batches` — replaced by the proper FK model.
4. Fix the heatmap API to return a grouped response (evaluations → SLO groups → indicators).
5. Fix the heatmap UI: one column per evaluation, accordion SLO groups with expand/collapse.
6. Fix the SLI breakdown table: SLO section headers replacing the tab bar.
7. Fix trend charts: SLO-grouped sections.
8. Enforce `{table}_id` naming on all FK columns throughout.

---

## Breaking Changes

- `POST /evaluations/trigger` → `POST /evaluate`
- `POST /evaluations/trigger-batch` → `POST /evaluate/batch`
- `GET /evaluations/metric-heatmap` → `GET /evaluate/metric-heatmap`
- `GET /evaluate/metric-heatmap` response shape changes completely (grouped schema).
- Python SDK client (`TropekClient`) must be updated to reflect the new endpoints.
- All existing `evaluation_batches` data is dropped (hard cut, no migration).
- All existing `evaluations` (old flat table) rows are dropped — backfill not feasible without original trigger context. Re-evaluate from source if historical data is needed.

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

### New table: `evaluations` (parent)

```sql
CREATE TABLE evaluations (
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

CREATE INDEX idx_evaluations_asset   ON evaluations (asset_id);
CREATE INDEX idx_evaluations_status  ON evaluations (status);
CREATE INDEX idx_evaluations_period  ON evaluations (asset_id, period_start DESC);
```

**`result`** — worst-case across all child `slo_evaluations` results.
**`achieved_points` / `total_points`** — raw sum of indicator score points across all children. Informational only — not a pass/fail criterion at the evaluation level. Displayed as a fraction or percentage in the UI.

### Renamed table: `slo_evaluations` (was `evaluations`)

```sql
-- Step 1: rename old flat table
ALTER TABLE evaluations RENAME TO slo_evaluations;

-- Step 2: add FK to new parent + point columns
ALTER TABLE slo_evaluations
    ADD COLUMN evaluation_id   UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    ADD COLUMN achieved_points INTEGER,
    ADD COLUMN total_points    INTEGER;

CREATE INDEX idx_slo_evaluations_evaluation ON slo_evaluations (evaluation_id);
```

### Renamed FK columns in child tables

```sql
-- indicator_results: evaluation_id → slo_evaluation_id
ALTER TABLE indicator_results
    RENAME COLUMN evaluation_id TO slo_evaluation_id;

-- sli_values: eval_id → slo_evaluation_id
ALTER TABLE sli_values
    RENAME COLUMN eval_id TO slo_evaluation_id;

-- evaluation_annotations: evaluation_id → slo_evaluation_id
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

Replaced by `evaluations` (parent) + the `slo_evaluations.evaluation_id` FK. The old JSONB `evaluation_ids[]` list is gone.

### Table relationship overview

```
evaluations  (parent — one per asset × period × eval_name)
  id PK
  asset_id FK → assets.id
  eval_name, period_start, period_end
  status, result, achieved_points, total_points
      │
      │ 1:N  evaluation_id FK
      ▼
slo_evaluations  (one per SLO bound to the asset)
  id PK
  evaluation_id FK → evaluations.id
  asset_id FK → assets.id
  slo_name (text snapshot), slo_version
  result, score, achieved_points, total_points
  status, invalidated, baseline_pin_*, override_*
      │                    │                   │
      │ 1:N                │ 1:N               │ 1:N
      ▼                    ▼                   ▼
indicator_results      sli_values         evaluation_annotations
  slo_evaluation_id FK   slo_evaluation_id FK   slo_evaluation_id FK
  slo_objective_id FK    metric_name, value     content, author
  value, status, score   (TimescaleDB hyper)
      │
      ▼
slo_objectives FK → slo_definitions
```

---

## Trigger API

### Principle

Triggering is always **asset-level**. The user provides an asset + eval name + time window. The system resolves all SLOs bound to that asset via `slo_bindings` and evaluates all of them. There is no user-facing trigger that targets a single SLO.

### Endpoints

**Single evaluation:**
```
POST /evaluate
{
  "asset_name": "checkout-api",
  "eval_name":  "daily-evaluation",
  "period_start": "2026-01-15T00:00:00Z",
  "period_end":   "2026-01-15T23:59:59Z"
}
→ 201 {
    "evaluation_id":     "uuid",
    "slo_evaluation_ids": ["uuid", ...]
  }
```

**Batch evaluation** — two modes, one endpoint:

`by_date` — same asset, multiple time windows:
```
POST /evaluate/batch
{
  "mode":      "by_date",
  "asset_name": "checkout-api",
  "eval_name":  "daily-evaluation",
  "periods": [
    { "period_start": "2026-01-15T00:00:00Z", "period_end": "2026-01-15T23:59:59Z" },
    { "period_start": "2026-01-16T00:00:00Z", "period_end": "2026-01-16T23:59:59Z" },
    { "period_start": "2026-01-17T00:00:00Z", "period_end": "2026-01-17T23:59:59Z" }
  ]
}
→ 201 {
    "evaluation_ids":     ["uuid", "uuid", "uuid"],
    "slo_evaluation_ids": ["uuid", ...]
  }
```

`by_asset` — same time window, multiple assets (e.g. a deployment rollout across a fleet):
```
POST /evaluate/batch
{
  "mode":       "by_asset",
  "asset_names": ["vm-01", "vm-02", "vm-03"],
  "eval_name":   "post-deploy-check",
  "period_start": "2026-01-15T14:00:00Z",
  "period_end":   "2026-01-15T15:00:00Z"
}
→ 201 {
    "evaluation_ids":     ["uuid", "uuid", "uuid"],
    "slo_evaluation_ids": ["uuid", ...]
  }
```

Both modes create one `evaluations` row per (asset, period) pair.

### Worker flow

1. Parent `evaluations` row created with `status=pending`.
2. N worker jobs enqueued — one per SLO binding resolved for the asset.
3. Each worker: evaluates its SLO, writes `slo_evaluations` row with `achieved_points` + `total_points`, marks its status.
4. On each child completion: check if all siblings with the same `evaluation_id` are done. If so:
   - `result` = worst-case of child results
   - `achieved_points` = sum of child `achieved_points`
   - `total_points` = sum of child `total_points`
   - `status` = `completed` (or `failed` if any child failed without result)

---

## Heatmap API

### Response schema

```python
class HeatmapSummaryCell(BaseModel):
    """Per-column aggregate for a SLO group or the composite Overall row."""
    evaluation_id: uuid.UUID   # column identity — maps to evaluations.id
    period_start:  datetime    # display label for x-axis
    result:        str         # worst-case across indicators in this group
    score:         float       # achieved_points / total_points × 100

class SloGroup(BaseModel):
    """One SLO's contribution to the heatmap."""
    slo_name:         str
    slo_display_name: str | None = None
    metrics:  list[HeatmapMetric]       # indicator definitions (name, display_name)
    cells:    list[HeatmapCell]         # individual indicator × column cells
    summary:  list[HeatmapSummaryCell]  # per-column aggregate (for collapsed header row)

class EvaluationColumn(BaseModel):
    """One heatmap column = one parent evaluation."""
    evaluation_id: uuid.UUID
    period_start:  datetime
    period_end:    datetime
    eval_name:     str

class MetricHeatmapResponse(BaseModel):
    asset_name: str
    columns:    list[EvaluationColumn]      # ordered oldest → newest
    groups:     list[SloGroup]             # SLO groups in SLO-name order
    composite:  list[HeatmapSummaryCell]   # Overall row spanning all groups
```

`HeatmapCell` updated fields:
- `eval_id` → `slo_evaluation_id` (FK naming convention)
- `slot: datetime` → `evaluation_id: UUID` (column identity)
- Add `period_start: datetime` (display only — tooltip and axis label)

### Endpoint

```
GET /evaluate/metric-heatmap?asset_name=X&eval_name=Y&from=T&to=T&limit=N
```

Column key = `evaluation_id` (UUID, guaranteed unique). `period_start` is the axis label only — two evaluations with the same `period_start` get separate columns because they have different `evaluation_id` values.

---

## Frontend

### Config: default expand state

`config.yaml` gains:
```yaml
ui:
  heatmap_slo_groups_expanded_by_default: true
```

Exposed via `GET /config` endpoint the UI reads on mount. App-level only — no per-user preference yet.

### Types (`ui/src/features/navigator/types.ts`)

```typescript
export interface EvaluationColumn {
  evaluation_id: string
  period_start:  string
  period_end:    string
  eval_name:     string
}

export interface HeatmapSloGroup {
  slo_name:         string
  slo_display_name?: string
  metrics:  Array<{ name: string; display_name: string }>
  cells:    MetricHeatmapCell[]
  summary:  Array<{ evaluation_id: string; period_start: string; result: string; score: number }>
}

export interface MetricHeatmapResponse {
  asset_name: string
  columns:    EvaluationColumn[]
  groups:     HeatmapSloGroup[]
  composite:  Array<{ evaluation_id: string; period_start: string; result: string; score: number }>
}
```

### Heatmap accordion — wireframe

The heatmap Y-axis is a flat list of rows built dynamically from expand state. The chart renderer (`HeatmapChart`) receives the flattened rows unchanged — no changes to ECharts logic.

```
X-axis:  Jan 15   Jan 16   Jan 17       ← one column per evaluation_id
         (10:00)  (10:00)  (10:00)         period_start shown as label

─────────────────────────────────────────────────────────────────
 Overall Score  [pass]   [warn]   [pass]   ← always visible, composite row
                                              click → expand all + scroll to table
─────────────────────────────────────────────────────────────────
 ▾ nginx        [pass]   [fail]   [warn]   ← SLO header row, expanded
                                              cells = group.summary (worst-case per col)
                                              click header → toggle collapse
   request_rate [pass]   [pass]   [warn]   ← indicator rows, visible when expanded
   error_rate   [pass]   [pass]   [pass]     click cell → scroll to this row in table
   p99_latency  [pass]   [fail]   [pass]
─────────────────────────────────────────────────────────────────
 ▸ redis        [pass]   [pass]   [pass]   ← SLO header row, collapsed
                                              shows aggregate status per column
                                              click → expand, reveals 3 indicator rows
─────────────────────────────────────────────────────────────────
 ▸ postgres     [pass]   [warn]   [pass]   ← collapsed, postgres had a warn Jan 16
─────────────────────────────────────────────────────────────────
```

**Visual conventions:**
- SLO header rows: blue label (`#58a6ff`), slightly darker background (`bg-surface-sunken`), expand chevron left of name
- Collapsed header: shows status cells (worst-case colour fill) per column — same colour scale as indicator cells
- Expanded header: shows chevron-down, no status cells in the header row itself (indicators below carry that)
- Overall Score: always pinned at top, full-width, slightly bolder text
- Row height: same as existing indicator rows (28px)
- Expand/collapse state: `Map<slo_name, boolean>` in `AssetPanel`, initialised from config flag

### SLI breakdown table — wireframe

`EvaluationTabs` removed. `SLIBreakdownTable` replaced by `SLIBreakdownGrouped`.

```
┌─────────────────────────────────────────────────────────────┐
│ SLI BREAKDOWN                                               │
├─────────────────────────────────────────────────────────────┤
│ ▾  nginx  ──────────────────────────────── 98pts  [PASS]   │  ← SLO section header
├──────────┬──────────┬──────────┬───────┬────────────────────┤
│ Indicator│ Value    │ Baseline │ Δ     │ Status             │
├──────────┼──────────┼──────────┼───────┼────────────────────┤
│ request_ │ 1250     │ 1200     │ +4.2% │ PASS               │
│ error_r  │ 0.02     │ 0.03     │ -33%  │ PASS               │
│ p99_lat  │ 450ms    │ 420ms    │ +7.1% │ WARN               │
├─────────────────────────────────────────────────────────────┤
│ ▸  redis  ──────────────────────────────── 100pts  [PASS]  │  ← collapsed, click to expand
├─────────────────────────────────────────────────────────────┤
│ ▸  postgres  ───────────────────────────── 88pts   [WARN]  │  ← collapsed
└─────────────────────────────────────────────────────────────┘
```

- Section header: SLO name (blue) + raw score `Xpts` + result badge
- Expand/collapse shared with heatmap accordion (same `Map` from `AssetPanel`)
- Clicking an indicator row scrolls the chart section to that metric's trend block

### Trend charts — wireframe

```
30-day trend for checkout-api

▾ nginx ─────────────────────────────────────────  [click to collapse]
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │ request_rate │  │ error_rate   │  │ p99_latency  │
  │ [trend graph]│  │ [trend graph]│  │ [trend graph]│
  └──────────────┘  └──────────────┘  └──────────────┘

▸ redis ──────────────────────────────────────────  [click to expand]

▸ postgres ───────────────────────────────────────  [click to expand]
```

- Same `Map` expand state — heatmap, table, and charts all collapse/expand together
- Each section header mirrors the SLO section pattern from the table (name + score + result badge)

---

## Testing

### Backend

- New integration tests: `test_evaluations_repository.py` — CRUD, status rollup, worst-case result aggregation.
- Update `test_trigger_service.py`: `POST /evaluate` creates parent + N children; `POST /evaluate/batch` with `by_date` and `by_asset` modes.
- Update `test_heatmap_endpoints.py`: grouped response shape, one column per `evaluation_id`.
- Update `test_heatmap_query.py`: multi-SLO asset produces one column per parent evaluation.
- Migration test: drop `evaluation_batches`, rename old `evaluations` → `slo_evaluations`, create new `evaluations`, add `evaluation_id NOT NULL`.

### Frontend

- Update `AssetHeatmap.test.tsx`: multi-SLO grouped response renders correct column count.
- Update `utils.test.ts`: `buildAssetHeatmapData` with grouped response, expand/collapse row counts.
- New `SLIBreakdownGrouped.test.tsx`: section headers render, expand/collapse toggles rows.
- Mock handlers updated to return new grouped `MetricHeatmapResponse` shape.

---

## Phasing

1. **DB + migration** — create new `evaluations` parent, rename old `evaluations` → `slo_evaluations`, add `evaluation_id NOT NULL FK`, rename child FK columns, drop `evaluation_batches`.
2. **Trigger layer** — `POST /evaluate`, `POST /evaluate/batch` (by_date + by_asset), worker rollup logic.
3. **Heatmap API** — new grouped endpoint at `GET /evaluate/metric-heatmap`.
4. **Frontend types + data layer** — update `MetricHeatmapResponse` types, rewrite `buildAssetHeatmapData`, update mock handlers.
5. **Heatmap accordion UI** — expand/collapse state wired from config, SLO header rows, Overall row.
6. **SLI table** — `SLIBreakdownGrouped` replacing `EvaluationTabs` + `SLIBreakdownTable`.
7. **Trend charts** — SLO-grouped collapsible sections.
8. **Config** — `heatmap_slo_groups_expanded_by_default` flag wired end-to-end.
