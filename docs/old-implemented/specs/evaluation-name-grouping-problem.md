# Problem: Evaluation Name Mixing Breaks Heatmap Selection & Display

**Status:** Problem specification only — no solution designed yet
**Date:** 2026-03-26

## Symptom

Clicking evaluation cells in the asset-level metric heatmap doesn't select the expected
evaluation. Evaluations that appear adjacent in the timeline are actually from different
test runs (different `evaluation_name`), making the heatmap confusing and click behavior
feel broken.

## Background

Every evaluation has an `evaluation_name` field — a user-supplied label identifying the
test run (e.g. `"nightly-perf"`, `"load-test"`, `"compilation-test"`). An asset can have
evaluations from many different named runs over time. These runs may use different SLOs,
different metrics, and run at different cadences.

The database enforces uniqueness on `(asset_id, slo_name, evaluation_name, period_start,
period_end)` for non-failed evaluations, meaning the same asset can have multiple
evaluations at the same timestamp if they have different names.

## Problem 1: Mixed timeline in the metric heatmap

**Where:** `GET /evaluations/metric-heatmap?asset_name=X` → `AssetHeatmap.tsx`

The metric heatmap endpoint fetches the last N completed evaluations for an asset
**without filtering by `evaluation_name`**. It returns all evaluations regardless of name,
ordered by `period_start DESC`.

The UI receives this mixed bag and builds a grid where:
- Columns = unique `period_start` timestamps (sorted)
- Rows = unique metric names

The result is an interleaved timeline: column 1 might be from `"nightly-perf"`, column 2
from `"load-test"`, column 3 from `"nightly-perf"` again. Since different named runs may
evaluate completely different metrics, many cells show "no data" in a seemingly random
pattern. The heatmap looks incoherent.

The backend already accepts `evaluation_name` as a query parameter (added in commit
`264166d`), but the UI never sends it:

```
hooks.ts:  fetchMetricHeatmap(assetName!)       // ← no evaluation_name
api.ts:    /evaluations/metric-heatmap?asset_name=...  // ← no evaluation_name
```

## Problem 2: Cell collision when same asset+timestamp has multiple eval names

**Where:** `buildAssetHeatmapData()` in `utils.ts`

Cells are keyed by `${metric}::${slot}`. If two evaluations with different
`evaluation_name` values share the same `period_start`, only the last one in the
iteration survives — the earlier one is silently overwritten. The cell's `eval_id` then
points to whichever evaluation happened to come last.

Clicking that cell selects an evaluation the user didn't intend to select.

## Problem 3: Same collision in the group-level heatmap

**Where:** `buildData()` in `EvaluationHeatmap.tsx`

The navigator's group-level heatmap (rows = assets, columns = timestamps) also keys cells
by `${assetName}::${period_start}`. When multiple evaluation names exist at the same
timestamp, cells are merged using worst-result logic. The `evaluation_name` is stored only
for tooltip display — it picks the name of whichever evaluation had the worst result.

This means:
- The cell score is an average across unrelated test runs
- The cell result is the worst across unrelated test runs
- The tooltip shows one name but the cell represents a blend of several

## Problem 4: Selection breaks across evaluation name boundaries

**Where:** `AssetPanel.tsx`, `AssetHeatmap.tsx`

When a user clicks cell A (from `"nightly-perf"`) and then cell B (from `"load-test"`),
the detail panel switches to a completely different evaluation context — different SLO,
different metrics, different scoring. This looks like the selection is broken because the
metrics table and scores jump to unrelated data.

The column highlight uses column index matching, so clicking within the same column always
highlights correctly — but the *content* shown is for whichever `eval_id` happened to be
stored in the cell, which may be from any evaluation name.

## Problem 5: No UI to filter or group by evaluation name

There is no UI element anywhere in the navigator that lets the user:
- See which evaluation names exist for an asset
- Filter the heatmap to a single evaluation name
- Switch between evaluation names
- Understand that the heatmap is mixing different test runs

The `evaluation_name` is visible only in:
- Tooltip text in the group heatmap (only shows one name per merged cell)
- The evaluation detail page breadcrumb
- The evaluation table (list view on the navigator page)

## Affected data flow

```
User clicks asset in tree
  → useAssetEvaluations(assetName)     // fetches ALL evals, no name filter
  → useMetricHeatmap(assetName)        // fetches heatmap, no name filter
    → API returns mixed evals
    → buildAssetHeatmapData() merges by metric+slot, losing name identity
    → AssetHeatmap renders interleaved timeline
    → Click stores one eval_id per cell (last writer wins)
    → AssetPanel shows detail for that eval_id
    → User sees unrelated metrics when clicking across eval names
```

## Existing backend support

The plumbing for filtering exists but is not connected:

| Layer | Status |
|-------|--------|
| `trend_repository.get_metric_heatmap()` | ✅ Accepts `evaluation_name: list[str] \| None` |
| `router.get_metric_heatmap()` | ✅ Accepts `evaluation_name` query param |
| `router.list_evaluations()` | ✅ Accepts `evaluation_name` query param |
| `eval_repository.list_with_counts()` | ✅ Accepts `evaluation_name` filter |
| `fetchMetricHeatmap()` (UI) | ❌ Doesn't pass `evaluation_name` |
| `useMetricHeatmap()` hook | ❌ Doesn't accept `evaluation_name` |
| `fetchEvaluations()` (UI) | ❌ Doesn't pass `evaluation_name` |
| `useAssetEvaluations()` hook | ❌ Doesn't accept `evaluation_name` |
| Any UI filter/selector | ❌ Does not exist |

## Scope of impact

- **Navigator page → asset panel**: Primary affected area. Metric heatmap is unusable
  when an asset has evaluations from multiple named runs.
- **Navigator page → group heatmap**: Cells merge unrelated runs, showing blended
  scores/results.
- **Trend charts**: May also mix data from different evaluation names (not investigated).
- **Single-name assets**: Unaffected. If all evaluations for an asset use the same name,
  everything works correctly.
