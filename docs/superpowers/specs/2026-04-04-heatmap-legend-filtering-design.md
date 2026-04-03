# Heatmap Legend Filtering Design

**Date:** 2026-04-04
**Status:** Approved

## Problem

Invalidated evaluation results are excluded from baselines and trend queries but still
appear as grey columns in the navigator heatmap. Users have no way to hide them from
the visual display, and no way to toggle them back on for forensic investigation.
The heatmap legend labels (pass/warning/fail/error/invalidated) exist but are static
and non-interactive.

## Solution

Make all heatmap legend items clickable toggles that control column visibility on the
heatmap and point visibility on the trend charts. Invalidated results are hidden by
default; all other result types are shown by default.

## Design Decisions

- **Client-side filtering.** The API returns all data including invalidated results.
  Filtering happens entirely in the UI via React state. No network round-trip on toggle.
- **Column-level filtering.** Toggling a result type hides/shows entire heatmap columns.
  A column is visible if it contains at least one cell with an active result type.
  All cells in a visible column render normally regardless of individual cell result.
- **Single control point.** The heatmap legend is the only toggle. Trend charts follow
  the same filter state with no independent controls.
- **Per-asset scope.** Filter state is local to each asset panel. Navigating away resets
  to defaults.
- **Override is authoritative.** When an evaluation result is overridden (e.g., fail to
  pass), both heatmap and trend chart show the overridden result. The trend query uses
  `SLOEvaluation.result` (which reflects overrides) instead of `IndicatorResultRow.status`.
- **Navigator only.** The EvaluationHeatmap on the evaluations list page is not affected.
  Evaluation detail panels are not affected.

## Backend Changes

### trend_repository.py -- `get_trend_by_domain()`

1. Remove the `SLOEvaluation.invalidated == False` filter so invalidated points are
   returned to the client.
2. Add `SLOEvaluation.invalidated` to the SELECT columns.
3. Change the result source to respect overrides and invalidation:
   - If `invalidated` is true: result = `'invalidated'`
   - Else if `original_result` is not null (overridden): result = `SLOEvaluation.result`
   - Else: result = `IndicatorResultRow.status`

### TrendPoint schema

Add `invalidated: bool` field to the Pydantic response model.

### No changes to

- Heatmap queries (already return invalidated results)
- Baseline queries (correctly exclude invalidated)
- Invalidation/restore API endpoints

## Frontend Changes

### New: `useHeatmapFilter` hook

Location: `ui/src/features/navigator/hooks/useHeatmapFilter.ts`

Manages filter state per asset:

```typescript
type ResultFilter = {
  pass: boolean
  warning: boolean
  fail: boolean
  error: boolean
  invalidated: boolean
}

// Default: all true except invalidated
const DEFAULT_FILTER: ResultFilter = {
  pass: true,
  warning: true,
  fail: true,
  error: true,
  invalidated: false,
}
```

Exposes: `filters`, `toggleFilter(resultType)`.

### HeatmapChart.tsx -- Interactive legend

1. Each legend item becomes a clickable toggle button with `cursor: pointer`.
2. Active items: full color swatch + label (as today).
3. Inactive items: reduced opacity (~0.3) on swatch and label.
4. Click calls `onToggleFilter(resultType)` callback.
5. "Invalidated" starts dimmed (off by default).
6. Legend items only appear if the dataset contains that result type.

### AssetPanelHeatmapView.tsx -- State ownership

Owns the `ResultFilter` state via `useHeatmapFilter`. Passes filters down to:
- `AssetHeatmap` (which passes to `buildAssetHeatmapData` and `HeatmapChart`)
- `MetricTrendBlock` components

### utils.ts -- `buildAssetHeatmapData()`

Accepts `activeFilters: ResultFilter` as a new parameter. After building all columns
and cells, filters columns: a column survives if at least one of its cells has a
`result` that is active in the filter. Removed columns are excluded from the output.

### useMetricTrendState.ts -- Point filtering

Accepts `activeFilters: ResultFilter`. Before building the ECharts config, filters
out trend points whose `result` is not active in the filter. Invalidated points that
survive the filter render as grey dots connected into the trend line normally.

### MetricTrendBlock.tsx -- Props passthrough

Accepts and forwards `activeFilters` to `useMetricTrendState`.

## Edge Cases

- **All filters off:** Heatmap shows empty, trend chart shows no points. Legend items
  remain clickable so the user can toggle back.
- **Override + invalidation:** Invalidation takes precedence. An overridden-then-invalidated
  evaluation shows as `'invalidated'`, not the override result.
- **Outliers:** Invalidated points connected into the trend line may cause scale jumps
  (e.g., error value of 100 on a 4-8 range). This is intentional -- the user opted in
  to seeing these points for investigation.

## Files Changed

| File | Change |
|------|--------|
| `api/app/modules/quality_gate/trend_repository.py` | Remove invalidated filter, add invalidated flag, use SLO-level result for overrides |
| `api/app/modules/quality_gate/schemas/evaluations.py` | Add `invalidated: bool` to `TrendPoint` |
| `ui/src/features/navigator/hooks/useHeatmapFilter.ts` | New hook: filter state management |
| `ui/src/components/charts/HeatmapChart.tsx` | Interactive legend toggles |
| `ui/src/features/navigator/components/AssetPanelHeatmapView.tsx` | Own filter state, pass to children |
| `ui/src/features/navigator/utils.ts` | Column filtering in `buildAssetHeatmapData()` |
| `ui/src/features/evaluations/hooks/useMetricTrendState.ts` | Point filtering by active filters |
| `ui/src/features/evaluations/components/MetricTrendBlock.tsx` | Pass filters through |
