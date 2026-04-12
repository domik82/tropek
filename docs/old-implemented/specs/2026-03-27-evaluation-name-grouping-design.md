# Design: Evaluation Name Grouping & Filtering

**Status:** Design approved
**Date:** 2026-03-27
**Problem spec:** `docs/specs/evaluation-name-grouping-problem.md`

## Summary

The navigator heatmaps ignore `evaluation_name`, causing cell collisions, wrong click targets,
and an interleaved timeline of unrelated test runs. The backend already supports filtering by
`evaluation_name` but the UI never passes it. This design adds:

1. A bug fix for heatmap cell keying (include `evaluation_name` in cell identity)
2. A multi-select filter row for evaluation names (and later asset name / tags)
3. Evaluation name visibility in heatmap tooltips
4. API wiring to pass `evaluation_name` filters to the backend

## Non-goals

- Color-coding cells by evaluation name (colors = pass/warning/fail only)
- A/B comparison view (future feature — filter to two names achieves basic comparison)
- Changes to heatmap grid layout (columns stay as timestamps, rows as metrics/assets)

## Design

### 1. Backend: Add `evaluation_name` to metric-heatmap cell response

**File:** `api/app/modules/quality_gate/schemas.py`

The `HeatmapCell` schema currently returns `slot`, `metric`, `display_name`, `result`, `score`,
`eval_id`. Add `evaluation_name: str` so the UI can show it in tooltips and use it for cell keying.

**File:** `api/app/modules/quality_gate/router.py` (line ~153)

Populate `evaluation_name=ev.evaluation_name` when building each `HeatmapCell`.

### 2. Backend: New endpoint for distinct evaluation names

**Endpoint:** `GET /evaluations/names`
**Query params:** `asset_name?: str`, `group_name?: str`
**Response:**
```json
[
  { "name": "daily-load-test", "count": 142, "last_run": "2026-03-27T08:00:00Z" },
  { "name": "ad-hoc-run", "count": 3, "last_run": "2026-03-26T14:30:00Z" }
]
```

Sorted by `last_run DESC` (most recently run name first). This powers the filter dropdown.

**Implementation:** A single `SELECT evaluation_name, COUNT(*), MAX(period_start)` grouped query
on the evaluations table, filtered by `asset_id` or `group_id`. Add to `repository.py`
(the evaluation repository class).

**Route ordering:** Declare `GET /evaluations/names` before `GET /evaluations/{eval_id}` in
`router.py` to avoid FastAPI matching `"names"` as an `eval_id` path parameter.

### 3. UI types: Extend `EvaluationFilters` and `MetricHeatmapCell`

**File:** `ui/src/features/evaluations/types.ts`

Add `evaluation_name?: string[]` to `EvaluationFilters` (line 99).

**File:** `ui/src/features/navigator/types.ts`

Add `evaluation_name: string` to `MetricHeatmapCell` (line 40).
Add `evaluation_name?: string` to `HeatmapCell` (line 4) for tooltip access.

**File:** `ui/src/lib/queryKeys.ts`

Add `evaluation_name?: string[]` to `EvalFilters` (line 9).
Update `evaluationKeys.heatmap` to include evaluation names in the key. When `evalNames` is
undefined or empty, omit it from the key so the cache is shared with the unfiltered case:
```typescript
heatmap: (assetName: string, evalNames?: string[]) =>
  evalNames?.length
    ? ['metric-heatmap', assetName, evalNames] as const
    : ['metric-heatmap', assetName] as const,
```

### 4. UI API layer: Pass `evaluation_name` to fetch functions

**File:** `ui/src/features/evaluations/api.ts`

Update `toParams()` to handle `evaluation_name` as a repeated query param:
```typescript
if (filters.evaluation_name?.length) {
  filters.evaluation_name.forEach(n => p.append('evaluation_name', n))
}
```

Update `fetchMetricHeatmap()` signature to accept optional `evaluationNames: string[]`:
```typescript
export async function fetchMetricHeatmap(
  assetName: string,
  evaluationNames?: string[],
): Promise<MetricHeatmapResponse>
```

Add new `fetchEvaluationNames()` function:
```typescript
export async function fetchEvaluationNames(
  params: { asset_name?: string; group_name?: string }
): Promise<Array<{ name: string; count: number; last_run: string }>>
```

### 5. UI hooks: Wire evaluation name through

**File:** `ui/src/features/navigator/hooks.ts`

Update `useAssetEvaluations` to accept and pass `evaluationNames`:
```typescript
export function useAssetEvaluations(
  assetName: string | undefined,
  evaluationNames?: string[],
)
```

Update `useMetricHeatmap` similarly.

Add new hook:
```typescript
export function useEvaluationNames(
  assetName?: string,
  groupName?: string,
)
```

### 6. Bug fix: Include `evaluation_name` in cell keys

**File:** `ui/src/features/navigator/utils.ts`

`buildAssetHeatmapData`: Change cell key from `${metric}::${slot}` to
`${metric}::${slot}::${cell.evaluation_name}`. This prevents overwriting when two eval names
share the same metric+timestamp.

Store `evaluation_name` on the `HeatmapCell` for tooltip access.

**File:** `ui/src/features/evaluations/components/EvaluationHeatmap.tsx`

`buildData`: Change cell key from `${asset}::${period_start}` to
`${asset}::${period_start}::${evaluation_name}`. Stop merging cells from different eval names.

**File:** `ui/src/features/navigator/utils.ts`

`buildGroupHeatmapData`: Same fix — change cell key from `${assetName}::${period_start}` to
`${assetName}::${period_start}::${evaluation_name}`. This function has the same collision bug:
it merges cells by worst-result and averages scores across unrelated eval names. With the fixed
key, each eval name gets its own cell. `EvaluationSummary` already carries `evaluation_name`.

### 7. UI: Evaluation name filter row

A new `EvaluationNameFilter` component — a horizontal row of toggleable chips placed between
the panel header and the heatmap.

**Behavior:**
- Fetches available names via `useEvaluationNames(assetName | groupName)`
- Chips sorted by most recent run date (same as API response order)
- Each chip shows: name + run count (e.g., `daily-load-test · 142`)
- Default: most recent name is pre-selected
- Special "All" chip at the start — selects/deselects all names
- Multi-select: clicking a chip toggles it. At least one must remain selected (or "All").
- When "All" is selected, the API call **omits** `evaluation_name` entirely (no parameter = all
  names). This avoids sending a long list of names and matches the backend's default behavior.
- Filter selection is passed to `useAssetEvaluations` / `useMetricHeatmap` / `useEvaluations`

**Placement:**
- `AssetPanel.tsx`: Between asset header and the metric heatmap
- `GroupPanel.tsx`: Between group header and the group heatmap
- `AllEvaluationsPanel.tsx`: Between page header and the heatmap

**Group-level filtering:** `GroupPanel` and `AllEvaluationsPanel` pass `evaluation_name` to
`useEvaluations()` (via `EvaluationFilters`). The filtered `EvaluationSummary[]` array is then
passed to `EvaluationHeatmap` and `EvaluationTable` as props. Filtering happens at the query
level, not client-side.

**Filter state management:**
- Local `useState` within each panel, initialized from the first name in the API response
- When the user navigates from group → asset, the asset panel initializes its own filter
  independently (no cross-panel state sharing needed for now)

### 8. UI: Tooltip enhancement

**File:** `ui/src/features/navigator/components/AssetHeatmap.tsx`

Add `evaluation_name` to the heatmap cell tooltip. Format:
```
daily-load-test
Score: 85.0 — Pass
2026-03-27 08:00
```

The evaluation name appears as the first line of the tooltip.

**File:** `ui/src/features/evaluations/components/EvaluationHeatmap.tsx`

Already shows evaluation_name in tooltip via `evalNameMap`. Keep this, but now it will be
accurate (no more "worst result name" merging since cells are keyed correctly).

## Data flow (after fix)

```
User clicks asset in tree
  → useEvaluationNames(assetName)      // fetch available names + counts
  → EvaluationNameFilter renders chips  // user can toggle names
  → selectedNames state updated
  → useAssetEvaluations(assetName, selectedNames)   // filtered list
  → useMetricHeatmap(assetName, selectedNames)       // filtered heatmap
    → API returns only matching evals
    → buildAssetHeatmapData() keys by metric+slot+evalName (no collision)
    → AssetHeatmap renders clean single-name timeline
    → Tooltip shows evaluation_name
    → Click stores correct eval_id per cell
    → AssetPanel shows correct detail
```

## Edge cases

**Asset has only one evaluation name:** Filter row shows one chip (pre-selected) + "All".
Functionally equivalent to today's behavior but now the name is visible.

**Asset has no evaluations:** Filter row is empty / hidden. Heatmap shows empty state as today.

**Same timestamp, different names (rare):** The cell key fix prevents silent data loss in the
Map lookup, but the grid position `[xi, yi]` is still derived from the slot index — so
same-timestamp cells would share a grid position. In practice this is not a problem because:
(a) the filter UI means users almost always view one name at a time, and (b) the backend returns
evaluations ordered by `created_at`, so even same-`period_start` evals get distinct slots in the
response array. If this becomes a real issue, the slot axis can be expanded to compound
`${slot}::${evalName}` keys in a future iteration.

**"All" selected with many names:** The heatmap shows all evaluations interleaved chronologically.
Tooltips distinguish which name each column belongs to. This is the 1% case — most users will
have a single name selected.

## Bug fix: Table row click navigates to wrong evaluation

Clicking an evaluation row in the `EvaluationTable` (visible in group panel, asset panel, and
all-evaluations panel) should navigate to and focus on that specific evaluation's detail view.
Currently it redirects to the wrong place — likely because the click handler uses a cell-based
lookup (same collision bug) or a stale `eval_id` reference rather than the row's own `id`.

**Fix:** The table row click handler must use `evaluation.id` directly from the `EvaluationSummary`
object, not derive it from heatmap cell state. Investigate the current click path in
`EvaluationTable.tsx` and the navigation handler in the parent panel.

## Dev data generator: Realistic evaluation names

**File:** `scripts/dev-start.sh` (and any seed/generator scripts it calls)

The current generator creates evaluations with generic names like `seed-1`, `seed-2`, etc. This
makes it impossible to test name-based filtering because there's no meaningful grouping.

**Changes:**
- Replace `seed-N` names with realistic, repeating evaluation names:
  - `load-test` — recurring daily load test
  - `optimization-testing` — periodic performance tuning validation
  - `user-experience` — production UX monitoring
  - `prod-validation` — production health check
- Each name should have a consistent "story": the same name recurs across multiple days with
  the same SLO/metrics, simulating a real test run cadence
- Different names can share the same asset but should use different SLOs or at least different
  time ranges, reflecting realistic usage
- Some names should appear frequently (e.g., `load-test` daily), others less often
  (e.g., `optimization-testing` weekly)
- Minor data duplication across names is acceptable — the goal is testable filter behavior,
  not perfectly unique data

## Cache invalidation

The `useEvaluationNames` query should be invalidated alongside evaluation list queries — when
a new evaluation completes (trigger, re-evaluate), the names list may have a new entry or
updated count/last_run. Add `evaluationKeys.names` to the invalidation set in mutation
`onSuccess` handlers.

## Testing

- **Unit test:** `buildAssetHeatmapData` with two evals sharing same metric+slot but different
  `evaluation_name` — verify both cells exist, no overwrite
- **Unit test:** `buildData` (group heatmap) with same-timestamp different-name evals — verify
  separate cells
- **Unit test:** `buildGroupHeatmapData` with same-timestamp different-name evals — verify
  separate cells (no worst-result merging across names)
- **Component test:** `EvaluationNameFilter` renders chips, toggles selection, calls onChange
- **Component test:** `AssetPanel` passes selected names to hooks
- **Integration test:** `GET /evaluations/names?asset_name=X` returns correct counts and ordering
- **Integration test:** `GET /evaluations/metric-heatmap` response includes `evaluation_name` per cell
