# Trend Chart Baselines & Multi-Target Thresholds

**Date:** 2026-04-10
**Status:** Draft
**Scope:** Backend (DB, worker, trend API) + Frontend (MetricTrendBlock, useMetricTrendState)

## Problem

The metric trend chart has several issues with threshold/baseline visualization:

1. **Only reads `[0]`** from `pass_targets` and `warning_targets` arrays -- misses additional criteria
2. **`>0` targets render at y=0** -- overlaps x-axis, visually useless
3. **Static and dynamic thresholds are mutually exclusive** -- showing `<=+10%` hides `<=400`
4. **Baseline value is not shown** -- no reference line for what the engine compared against
5. **Relative thresholds computed client-side** -- `computeRelativeThresholdSeries` only handles `<=+N%`, ignoring other relative formats the engine supports
6. **Client-side computation doesn't scale** -- 24 SLOs x 8 SLIs x hundreds of trend points = heavy browser work
7. **SLO version changes are invisible** -- a threshold changing from `<=400` to `<=500` mid-series can't be shown with a flat markLine

## Design

### Core idea

Store resolved targets per indicator row at eval time. The trend API includes them per point. The UI plots what it receives -- zero engine logic client-side.

### Backend: Store resolved targets

**Schema change:** Add `targets` JSONB column to `indicator_results` table:

```python
# In IndicatorResultRow (api/app/db/models.py)
targets: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
```

Column shape:

```json
{
  "pass": [
    {"criteria": ">0", "target_value": 0.0, "violated": false},
    {"criteria": "<=400", "target_value": 400.0, "violated": false},
    {"criteria": "<=+10%", "target_value": 253.0, "violated": false}
  ],
  "warn": [
    {"criteria": ">0", "target_value": 0.0, "violated": false},
    {"criteria": "<=+15%", "target_value": 264.5, "violated": true}
  ]
}
```

**Write path:** `_write_indicator_rows()` in the worker serializes the engine's already-computed `pass_targets` and `warning_targets` (from `IndicatorResult`) into this column. No new computation -- just persist what the engine already produces in `evaluator.py:_build_targets()`.

**Presenter:** `_indicators_from_orm_rows()` reads stored targets from the column. No fallback needed -- this is beta with no legacy prod data to worry about.

### Backend: Enrich trend API

The `get_trend_by_domain()` query joins `IndicatorResultRow` -- add the `targets` JSONB column to the SELECT and include it in the returned dict.

Trend point shape becomes:

```json
{
  "timestamp": "2026-03-15T10:30:00Z",
  "value": 245.3,
  "score": 33.33,
  "eval_id": "uuid",
  "result": "pass",
  "baseline": 230.0,
  "evaluation_name": "daily",
  "targets": {
    "pass": [
      {"criteria": ">0", "target_value": 0.0, "violated": false},
      {"criteria": "<=400", "target_value": 400.0, "violated": false},
      {"criteria": "<=+10%", "target_value": 253.0, "violated": false}
    ],
    "warn": [
      {"criteria": ">0", "target_value": 0.0, "violated": false},
      {"criteria": "<=+15%", "target_value": 264.5, "violated": true}
    ]
  }
}
```

### Frontend: TrendPoint type

Update the `TrendPoint` type to include targets:

```typescript
export interface TrendTargetEntry {
  criteria: string
  target_value: number
  violated: boolean
}

export interface TrendPoint {
  timestamp: string
  value: number
  score: number
  eval_id: string
  result: 'pass' | 'warning' | 'fail'
  baseline?: number | null
  evaluation_name?: string | null
  targets?: {
    pass?: TrendTargetEntry[]
    warn?: TrendTargetEntry[]
  } | null
}
```

### Frontend: Chart rendering

**Line types and visual hierarchy:**

| Line | Style | Color | Labels |
|------|-------|-------|--------|
| Metric value | Connected dots | Per-point status color (green/yellow/red) | None (existing) |
| Static thresholds (`<=400`) | Solid line series | Green (pass) / Yellow (warn) | None -- label in dropdown only |
| Relative thresholds (`<=+10%`) | Dashed line series | Green (pass) / Yellow (warn) | None -- label in dropdown only |
| Baseline | Thin dotted line | Blue (sky-9 from Radix palette) | None -- label in dropdown only |

No text labels on chart lines. The dropdown is the legend.

**Building lines from per-point data:** The hook scans all trend points, collects the union of distinct `{level, criteria}` pairs across the dataset. Each unique pair becomes one ECharts line series. Static thresholds are rendered as regular line series (not markLines) so they naturally handle SLO version changes -- the line steps from 400 to 500 when the SLO changes.

**Filtering `>0`:** Any criteria where `target_value === 0` on ALL points is excluded from the dropdown and chart.

**SLO version changes:** When a criteria changes from `<=200` to `<=300`, both appear in the dropdown as separate entries. The `<=200` line has data in the earlier range and gaps after, the `<=300` line has gaps before and data after. Over time as old points scroll out of the time window, the old entry disappears from the dropdown naturally.

### Frontend: Dropdown toggle component

Replace the current 2 hardcoded pill buttons with a single `Tags` icon button (from lucide-react) that opens a dropdown/popover.

**Dropdown contents:** Each row has:
- Checkbox (checked = line visible)
- Small colored marker dot matching the line color (green for pass, yellow for warn, blue for baseline)
- Criteria label text (e.g. `<=400`, `<=+10%`, `baseline`)

**Order:** Pass entries first, then warn entries, then baseline at the bottom.

**Defaults:** All non-zero thresholds ON, baseline OFF.

**State:** Local `useState<Record<string, boolean>>` keyed by `"pass:<=400"`, `"warn:<=+15%"`, `"baseline"` etc. Fully dynamic -- rebuilt from whatever criteria appear in the current trend data.

### Frontend: Theme addition

Add baseline color to `ChartTheme` interface and all theme definitions:

```typescript
// In ChartTheme interface
baseline: string

// Values
current: { baseline: '#58a6ff' }   // GitHub-style blue, already used for action accents
dark:    { baseline: '#70b8ff' }   // Radix sky-9
light:   { baseline: '#3b82f6' }   // TBD
```

### Scope: What does NOT change

- **`MultiSeriesChart` / MetricExplorerPage** -- different use case (multi-metric overlay for comparative analysis). No threshold lines needed. Not affected.
- **`AssetScoreChart`** -- shows overall score, not per-SLI thresholds. Not affected.
- **`SLIBreakdownTable`** -- reads indicator targets from the detail API, not from trend data. Not affected by this change (already works correctly via presenter).
- **`resolve_targets()`** -- kept as utility, still used by presenter and router for detail/summary APIs.

### Cleanup

**Remove from UI:**
- `computeRelativeThresholdSeries` from `ui/src/utils/metrics.ts` (+ tests)
- `isRelativeCriteria` from `useMetricTrendState.ts` (+ tests)
- Old `showPass` / `showWarn` / `togglePass` / `toggleWarn` from hook interface
- Old `passTarget` / `warnTarget` / `passCriteria` / `warnCriteria` scalars from hook
- `isRelativeCriteria` import from `MetricTrendBlock.tsx`

**UI derives line style from criteria string:** If it contains `%` or a sign (`+`/`-`) = dashed line (relative), otherwise = solid line (static). Simple string check, no parser needed.

### Side effect: Navigator fix

`AssetPanelChartView` currently builds fake `IndicatorResult` objects with `pass_targets: null` because it gets indicators from heatmap data, not eval detail. This means navigator trend charts show no threshold buttons today. With the new approach, targets come from the trend API response (per-point), not from the `indicator` prop -- so the navigator automatically gets full threshold support without any changes to how it constructs `IndicatorResult`.

## File map

| File | Action | What changes |
|------|--------|--------------|
| `api/app/db/models.py` | Modify | Add `targets` JSONB column to `IndicatorResultRow` |
| `api/alembic/versions/...` | New | Migration for `targets` column |
| `api/app/modules/quality_gate/indicator_repository.py` | Modify | Persist `targets` in `bulk_insert` |
| `api/app/modules/quality_gate/worker.py` | Modify | Build targets dict from engine result in `_write_indicator_rows` |
| `api/app/modules/quality_gate/trend_repository.py` | Modify | Include `targets` in `get_trend_by_domain` query + response |
| `api/app/modules/quality_gate/presenter.py` | Modify | Read stored targets, fallback to `resolve_targets` |
| `ui/src/features/evaluations/types.ts` | Modify | Add `TrendTargetEntry`, update `TrendPoint` |
| `ui/src/features/evaluations/hooks/useMetricTrendState.ts` | Rewrite | New dropdown-based toggle state, targets from trend data, baseline series |
| `ui/src/features/evaluations/hooks/useMetricTrendState.test.ts` | Rewrite | Tests for new hook interface and buildChartOption |
| `ui/src/features/evaluations/components/MetricTrendBlock.tsx` | Modify | Replace pill buttons with Tags dropdown |
| `ui/src/lib/theme.ts` | Modify | Add `baseline` to `ChartTheme` |
| `ui/src/utils/metrics.ts` | Modify | Remove `computeRelativeThresholdSeries` |
| `ui/src/utils/metrics.test.ts` | Modify | Remove related tests |
