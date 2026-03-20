# Otava Change Point Detection Integration

**Date:** 2026-03-20
**Status:** Draft
**Depends on:** DB Normalization + Redis Caching Layer (2026-03-20) — **hard prerequisite**, must land first. The `change_points` table FK targets `indicator_results.id` which is created by the normalization spec.

## Problem

TROPEK's SLO criteria evaluation detects threshold violations ("is this value bad right now?") but is blind to slow degradation within thresholds. A metric creeping from 10 → 12 → 15 over weeks never triggers a warning if the fail threshold is at 30 — yet something clearly changed.

Apache Otava's E-Divisive Means algorithm detects distributional shifts (change points) in time series, catching exactly this class of regression. Combined with threshold-based SLO evaluation, it provides a complete picture: thresholds catch acute failures, change points catch gradual drift.

## Decisions

1. **Otava is indicator-only** — it never gates the build (pass/fail). Change points are supplementary intelligence displayed alongside SLO results. The pass/fail decision always comes from SLO criteria.
2. **Per-metric detection** — each SLI objective gets independent change point detection on its own time series.
3. **30-sample default window** — configurable per-SLO, 30 evaluations of history per metric is the sweet spot for the algorithm.
4. **Inline worker step with fault isolation** — Otava runs inside the existing evaluation worker after SLO scoring, wrapped in try/except. If it fails, the evaluation still succeeds with no change point data.
5. **"Remember forever" persistence** — detected change points are stored permanently in a dedicated table. Re-runs of the algorithm compare against stored points for dedup. Triaged points (acknowledged/hidden) are never re-detected.
6. **Both regression and improvement markers** — the UI distinguishes direction with distinct visual treatments (red for regression, green for improvement).

### Why not use Otava as a gate?

Change point detection is a transition detector, not a state detector. It fires once at the shift boundary (day 11: value goes from 1→2), then goes silent for the degraded plateau (days 12-20: all 2s, no new change point detected). Subsequent evaluations in the degraded state would "pass" since no new change point is detected — defeating the purpose of gating. The criteria-based system handles sustained-state gating correctly (it checks every value against thresholds every time).

## Data Model

### New table: `change_points`

```
change_points
├── id: UUID (PK)
├── indicator_result_id: UUID | null → indicator_results.id (FK, indexed, ON DELETE SET NULL)
├── direction: str                     -- "regression" | "improvement"
├── change_relative_pct: float               -- % change between pre/post segments
├── change_absolute: float          -- absolute change between segment means
├── t_statistic: float                 -- significance score from Otava
├── pre_segment_mean: float            -- mean of segment before change point
├── post_segment_mean: float           -- mean of segment after change point
├── status: str                        -- "unprocessed" | "acknowledged" | "hidden"
│                                         default: "unprocessed"
├── triage_author: str | null
├── triage_note: str | null
├── triage_at: datetime | null
├── linked_ticket: str | null          -- URL or issue key (e.g., "PROJ-123" or full URL)
├── created_at: datetime
├── updated_at: datetime               -- set by onupdate=func.now() on triage actions
```

All identity fields (asset, SLO, metric, timestamp) are derived through the join chain: `change_points` → `indicator_results` → `evaluations` (for asset_id, slo_name, period_start) and `indicator_results` → `slo_objectives` (for metric_name).

**Indexes:**
- `(indicator_result_id)` — join from evaluation detail
- `(status)` partial where `status = 'unprocessed'` — triage dashboard
- `(created_at DESC)` — recent change points list

### Change point configuration

These are **operational knobs**, not SLO content. Since `slo_definitions` rows are immutable (versioned, append-only), putting config there would force a version bump just to toggle detection on/off, which breaks baseline continuity.

New table: `change_point_config`

```
change_point_config
├── id: UUID (PK)
├── asset_id: UUID → assets.id (FK)
├── slo_name: str
├── enabled: bool (default false)
├── window_size: int (default 30)        -- samples per metric
├── min_sample_size: int (default 10)    -- skip detection below this
├── created_at: datetime
├── updated_at: datetime
```

**Unique constraint:** `(asset_id, slo_name)` — one config per asset+SLO binding.

The config is managed via the existing asset-SLO binding UI/API, not inside the SLO YAML. This allows enabling/disabling detection per-asset without touching SLO definitions.

### Dedup logic

When Otava detects a change point for a given metric, before inserting:

1. Join `change_points` → `indicator_results` → `evaluations` + `slo_objectives`
2. Check if an existing change point exists for the same (asset_id, slo_name, metric_name) within ±2 evaluations **by ordinal position** (not time window). This means: fetch the 2 evaluations immediately before and after the current one by `period_start` order for this asset+SLO, and check if any of those 5 positions (current ± 2) have an existing change point for this metric.
3. If match exists (any status including "hidden"), skip insertion
4. If no match, insert as "unprocessed"

This prevents the duplicate-alert problem described in the Otava/MongoDB research: a point marked as a false positive stays muted and doesn't re-appear.

### Re-evaluation and FK orphaning

When an evaluation is re-run, its `indicator_results` rows are deleted and recreated (see normalization spec). The `change_points.indicator_result_id` FK uses `ON DELETE SET NULL` — the change point record survives (remember forever) but loses its direct link. The change point's `created_at` and the evaluation's `period_start` (via the dedup join) still provide historical context.

## Evaluation Worker Flow

The existing worker flow extends with one new step:

```
1. Load SLO definition (from cache)
2. Gather SLI metrics from adapter
3. Fetch baselines (from cache or DB)
4. Run SLO criteria evaluation (pure function)
5. Write evaluation + indicator_results to DB
6. Write SLI values to TimescaleDB hypertable
7. [NEW] If change_point_config exists for this asset+SLO and is enabled:
   try (in a SEPARATE transaction from step 5 — fault isolation):
     For each indicator_result:
       a. Fetch last N values for this metric from SLIValue hypertable
          Query: JOIN sli_values sv ON sv.eval_id = e.id
          WHERE e.asset_id = :asset_id AND sv.metric_name = :metric
          ORDER BY sv.eval_start DESC LIMIT :window_size
          (the sli_values table has denormalized asset_name for Grafana;
          use the evaluations join via eval_id for the canonical asset_id filter)
       b. If fewer than min_sample_size values, skip this metric
       c. Run Otava E-Divisive detection on the series
       d. Check if the latest detected change point is at or near
          the current evaluation's position
       e. If yes, dedup-check against change_points table
       f. If new, insert change_point row linked to this indicator_result
   except Exception:
     Log warning, continue — evaluation result is already saved
8. Return evaluation result
```

### Otava engine integration

Otava is a Python library (Apache Otava, incubating). The integration layer:

```python
# api/app/modules/quality_gate/engine/change_point_detector.py

def detect_change_points(
    values: list[float],
    timestamps: list[datetime],
    higher_is_better: bool = False,
) -> list[ChangePoint]:
    """Run E-Divisive detection on a single metric time series.

    Returns change points with their position, direction, magnitude,
    and statistical significance. Uses Student's t-test for
    deterministic results (same input always produces same output).

    The higher_is_better flag determines direction labeling:
    - False (default): increase = regression (latency, error rate)
    - True: decrease = regression (throughput, availability)
    """
    ...

@dataclass
class ChangePoint:
    position: int                # index in the input series
    timestamp: datetime          # from the timestamps list
    direction: str               # "regression" | "improvement"
    change_relative_pct: float
    change_absolute: float
    t_statistic: float
    pre_segment_mean: float
    post_segment_mean: float
```

The detector is a pure function (no I/O) wrapping Otava's API. Direction is determined by comparing pre/post segment means against the metric's "higher is better" or "lower is better" semantics (derivable from the SLO criteria direction — `<600` implies lower is better).

### Metric directionality

To determine whether a change is a "regression" or "improvement," the detector needs to know the metric's polarity. The caller derives `higher_is_better` from the SLO objective's `pass_criteria` using this algorithm:

1. Take the **first** criterion in `pass_criteria`
2. Parse its operator:
   - `<`, `<=` → lower is better → `higher_is_better = False`
   - `>`, `>=` → higher is better → `higher_is_better = True`
   - Relative criteria (`<=+10%`, `<=+50`) → lower is better (the `+` means "allow up to X% increase")
3. If `pass_criteria` is empty (info-only objective) or contains conflicting operators (range check like `>=95` + `<=100`), default to `higher_is_better = False` (most metrics are latency/error-like)

This is computed by the caller before invoking `detect_change_points`, not inside the detector itself.

## UI Treatment

### Heatmap indicators

On both `EvaluationHeatmap` and `AssetHeatmap`:

- **Regression:** red diamond icon overlaid on the cell
- **Improvement:** green diamond icon overlaid on the cell
- Icons appear regardless of the cell's pass/warn/fail color — a green "pass" cell with a red diamond means "passed thresholds but something shifted"
- Tooltip includes: "Change point detected: response_time_p95 regression +15.2%"

### Trend chart markers

On `MetricTrendBlock`:

- Change points rendered as diamond markers on the data line at the detection timestamp
- Red fill for regression, green fill for improvement
- Larger than normal data point markers
- Tooltip shows magnitude and segment means

### Asset score chart

On `AssetScoreChart`:

- Diamond markers on the score line where any change point was detected for that evaluation
- Color follows worst-direction change point in that eval (if both regression and improvement exist, show red)

### SLI breakdown table

On `SLIBreakdownTable`:

- New column or icon in the existing row for metrics that have a change point on this evaluation
- Red/green diamond + magnitude percentage
- Clicking opens change point detail (triage controls)

### Evaluation detail page — inline triage

When viewing an evaluation with change points, a collapsible "Change Points" section shows:

- List of detected change points for this evaluation
- Per change point: metric name, direction, magnitude, segment means, status
- Triage actions: Acknowledge (with optional note), Hide (mark as false positive), Link ticket
- Status badge showing current triage state

### Dedicated change points page (`/change-points`)

Top-level route with a filterable, sortable table:

**Columns:**
- Status (unprocessed/acknowledged/hidden) — with filter
- Direction (regression/improvement) — with filter
- Metric name
- Asset name (from join chain)
- SLO name
- Magnitude (% and absolute)
- Detected at (timestamp)
- Linked ticket
- Triage author + date

**Actions:**
- Bulk triage (select multiple → acknowledge/hide)
- Click row → jump to evaluation detail
- Filter by: status, direction, asset, SLO, date range, metric
- Default view: unprocessed only, newest first

## API Endpoints

### New endpoints

```
GET  /api/change-points
     ?status=unprocessed&direction=regression&asset_name=X&slo_name=Y
     &metric=Z&from=2026-01-01&to=2026-03-20&limit=50&offset=0
     → paginated list of change points with joined identity fields

GET  /api/change-points/{id}
     → single change point with full context

PATCH /api/change-points/{id}
      body: {status, triage_note, linked_ticket}
      → update triage state

PATCH /api/change-points/bulk
      body: {ids: [...], status, triage_note}
      → bulk triage
```

### Modified endpoints

```
GET /api/evaluations/{id}
    → EvaluationDetail response adds change_points list per indicator_result

GET /api/evaluations/metric-heatmap
    → HeatmapCell adds change_point: {direction, change_relative_pct} | null

GET /api/evaluations/trend
    → TrendPoint adds change_point: {direction, change_relative_pct, status} | null
```

## Caching considerations

Change point dedup lookups benefit from the Redis caching layer (Spec 1):

- SLO objectives (needed to derive metric polarity) → cached as immutable
- The dedup query itself could be cached: `cp:dedup:{asset_id}:{slo_name}:{metric}` → set of recent change point timestamps, invalidated on new detection

The SLI value history query (last 30 values for a metric) hits the TimescaleDB hypertable which is already optimized for this access pattern — no caching needed there.

## Affected Components

### Backend — new files
- `api/app/modules/quality_gate/engine/change_point_detector.py` — pure detection wrapper
- `api/app/modules/change_points/` — router, repository, schemas for the change points domain
- Alembic migration for `change_points` table and `slo_definitions` columns

### Backend — modified files
- `api/app/modules/quality_gate/worker.py` — add Otava step after scoring
- `api/app/modules/quality_gate/repository.py` — queries that return indicator data include change point join
- `api/app/modules/quality_gate/schemas.py` — response models add change point fields
- `api/app/modules/slo_registry/schemas.py` — SLO create/read adds detection config fields

### Frontend — new files
- `ui/src/features/change-points/` — dedicated page, list component, triage controls
- `ui/src/pages/ChangePointsPage.tsx` — route-level page

### Frontend — modified files
- `ui/src/features/evaluations/components/EvaluationHeatmap.tsx` — diamond overlays
- `ui/src/features/navigator/components/AssetHeatmap.tsx` — diamond overlays
- `ui/src/features/evaluations/components/MetricTrendBlock.tsx` — diamond markers
- `ui/src/features/evaluations/components/SLIBreakdownTable.tsx` — change point column
- `ui/src/features/navigator/components/AssetScoreChart.tsx` — diamond markers
- Evaluation detail page — inline triage section
- Router config — new `/change-points` route

### Dependencies
- Apache Otava Python package — **risk: verify availability**. Otava is primarily a CLI tool; the E-Divisive implementation may need to be imported as a library. Verify the exact PyPI package name and confirm the detection function is importable (not just CLI-wrapped). Fallback: vendor the core E-Divisive + t-test implementation (it's a well-documented algorithm, ~200 lines of Python). The Otava codebase is Apache-licensed.

### AssetScoreChart consideration

The `AssetScoreChart` shows aggregate score over time. Overlaying per-metric change point diamonds on an aggregate line conflates detail levels. Implementation should evaluate whether this adds clarity or noise — consider showing change points only on the per-metric `MetricTrendBlock` charts and the per-metric `AssetHeatmap`, not on the aggregate score line. Decision can be made during implementation based on visual testing.
