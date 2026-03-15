# Navigator Redesign — Design Spec

## Problem Statement

The first Navigator implementation built a parallel set of custom visualisations (GroupHeatmap, AssetHeatmap, GroupScoreChart) that duplicated work already done in the Evaluations feature and diverged from what the user expected. Four concrete issues need fixing:

1. **Evaluations nav tab is redundant** — Navigator is now the sole entry point for evaluation data; the Evaluations tab must be removed.
2. **Group Heatmap is wrong** — The custom GroupHeatmap replaced the existing `EvaluationHeatmap` + `EvaluationTable` rather than embedding them. The interaction model (first-click = select column, second-click on selected column = navigate to that asset in the Navigator) was misunderstood.
3. **Asset Panel is wrong** — It shows a custom AssetHeatmap that navigates away on click, and an all-evaluations table at the bottom. The intended layout mirrors `EvaluationDetailPage`: Header → Notes → Metric Heatmap → SLI Breakdown → Metric Trend Charts.
4. **Member count is broken** — Groups with subgroups show 0 because only `group.members` (direct members) is counted; the tree panel must count leaf members recursively.

---

## Agreed Design

### 1. Navigation Changes

Remove the "Evaluations" entry from `NAV_ITEMS` in `App.tsx`. The nav bar will contain: Navigator · SLOs · Assets.

The root route (`/`) continues to redirect to `/navigator`.

The `/evaluations/:id` route stays (evaluation detail page is still reachable via links in the Navigator).

The "Evaluations" page at `/evaluations` is no longer linked from the nav bar but its route is preserved for backwards-compatibility (direct URL access still works).

### 2. AssetTreePanel — "All" entry + recursive member count

**"All" entry:** Add a synthetic entry at the top of the sidebar — above all tree nodes — labelled "All". Clicking it clears both `group` and `asset` URL params, rendering the empty-state message in the main panel. The empty-state message text is: "Select a group or asset from the tree to load evaluations." (preserving the existing string in `AssetNavigatorPage.tsx`).

`AssetTreePanel` receives a new `onClearSelection: () => void` prop. Clicking "All" calls this callback. `AssetNavigatorPage` provides `() => setParams({})`. The "All" entry is highlighted (same `bg-muted text-foreground` active style) when neither `selectedGroup` nor `selectedAsset` is set.

**Recursive member count badge:** When a group has subgroups, its member count badge must reflect *all leaf assets* in the subtree, not just `group.members.length`. Add a `countLeafMembers(group: AssetGroup, tree: AssetGroupTree): number` helper function at the top of `AssetTreePanel.tsx` (not in `utils.ts` — it is only used here). It recursively sums `group.members.length + sum(countLeafMembers(subgroup, tree) for each resolved subgroup)`, resolving subgroup IDs via `tree.all_groups` — same lookup pattern already used in `TreeNode`. This ensures Performance Lab 1 (which has Linux and Windows subgroups each with members) shows 11 instead of 0.

### 3. Group Panel — Heatmap mode

**Replace custom GroupHeatmap with `EvaluationHeatmap` + `EvaluationTable`.**

The `EvaluationHeatmap` component already implements the correct single-click toggle: clicking a column selects it (white border on all cells in that column); clicking the same column again deselects it. `selectedDate` / `onDateSelect` manage this state in the parent.

**Second-click = navigate to asset in Navigator.** Add an optional `onAssetSelect?: (assetName: string) => void` prop to `EvaluationHeatmap`. The click handler in `EvaluationHeatmap` follows these rules:

- Column **not** selected → select it (`onDateSelect(slot)`) — same as today
- Column **already** selected AND `onAssetSelect` is provided → extract asset name from `p.data.row.split(' · ')[0]`; if non-empty, call `onAssetSelect(assetName)` — **do not** call `onDateSelect(null)`
- Column **already** selected AND `onAssetSelect` is **not** provided → deselect (`onDateSelect(null)`) — same as today on `EvaluationsPage`

If the asset name extracted from the row label is empty or whitespace-only, `onAssetSelect` is not called (silent no-op). Asset names containing the literal substring ` · ` are not expected in practice.

The `EvaluationsPage` is not affected: it does not pass `onAssetSelect`, so the existing deselect-on-second-click behaviour is preserved.

**`EvaluationTable` below the heatmap** is filtered by `selectedDate` (the selected slot's ISO timestamp), forwarding to `useEvaluations({ group_name, date: selectedDate })`. The `date` field in `EvaluationFilters` matches evaluations by exact `period_start` value — the same ISO string stored in `EvaluationSummary.period_start` and in `CellData.slot`. When no column is selected, `date` is `undefined` and the table shows all evaluations for the group.

**GroupPanel layout:**
```
[Header: group display name | count of evals | score | Heatmap / Chart toggle]
[EvaluationHeatmap — selectedDate / onDateSelect / onAssetSelect]
[EvaluationTable — filtered by selectedDate, or all evals if no selection]
```

The `GroupHeatmap` component is deleted.

**Chart mode** is unchanged: `GroupScoreChart` with absolute/normalised toggle.

### 4. Asset Panel — Full Redesign

The Asset Panel is redesigned to mirror `EvaluationDetailPage`'s layout, with the Metric Heatmap inserted between Notes and SLI Breakdown.

**Data requirements:**
- `useAssetEvaluations(assetName)` → list of `EvaluationSummary` for this asset
- `useMetricHeatmap(assetName)` → `MetricHeatmapResponse` (slots × metrics grid)
- `useEvaluationDetail(selectedEvalId)` → full detail (indicators, annotations) for the currently selected evaluation. The hook signature in `hooks.ts` must be widened from `(id: string)` to `(id: string | undefined)`. The `queryFn` should use `id!` (non-null assertion — safe because `enabled: !!id` prevents the fn from ever running when `id` is undefined): `{ queryFn: () => fetchEvaluationDetail(id!), enabled: !!id }`.

**Default selection:** `selectedEvalId` is initialised to `undefined` while `useAssetEvaluations` is loading. Once the list resolves, the component derives the default: the latest non-invalidated eval sorted descending by `period_start`. If all evaluations are invalidated, fall back to the most recent one. While `selectedEvalId` is `undefined` (loading or empty list), the score in the header shows `—`, and the Notes, SLI Breakdown, and Metric Trend sections render a loading/empty placeholder.

**Annotations source:** `AnnotationForm` receives `evalId={selectedEvalId}` and `annotations={ev?.annotations ?? []}` where `ev` is the result of `useEvaluationDetail(selectedEvalId)`. This matches the existing `AnnotationForm` props signature.

**Layout (Heatmap mode):**

```
[Header — compact row]
  asset name (mono)  |  {score}%  |  result badge  |  [Invalidate]  |  [Heatmap / Charts toggle]

[Notes — AnnotationForm for selectedEvalId]

[Metric Heatmap]
  AssetHeatmap with selectedEvalId + onEvalSelect callback
  Clicking a column selects that evaluation (highlights column; no navigation away)

[SLI Breakdown — for selectedEvalId]
  EvaluationTabs (tab_group tabs from ev.indicator_results) + SLIBreakdownTable

[Metric Trend Charts — for selectedEvalId, 2-column grid]
  MetricTrendBlock × N (all indicators, no 8-metric cap)
```

**Layout (Charts mode):**

```
[Header — same as above]

[Metric group filter tabs: All | <tab_group values>]

[Metric Trend Charts — 2-column grid, filtered by selected group]
  MetricTrendBlock × N (all indicators or filtered subset)
```

Charts mode does not show the heatmap, notes, or SLI table. It is a clean view for comparing metric trends side-by-side.

**`AssetHeatmap` changes:**
- Add `selectedEvalId?: string` prop — the currently-selected column is highlighted (same white-border pattern as `EvaluationHeatmap`).
- Add `onEvalSelect?: (evalId: string) => void` prop — called on click instead of navigating to `/evaluations/${evalId}`.
- Remove the `useNavigate` call; `AssetHeatmap` no longer navigates.
- Update the tooltip text from "Click to open evaluation detail" to "Click to select this evaluation" to reflect the new column-selection behaviour.
- The `evalId` is available in each cell's data because `MetricHeatmapCell` already includes `eval_id`.

**Default selection:** On first load, `selectedEvalId` defaults to the latest non-invalidated eval's ID (from `useAssetEvaluations` sorted descending by `period_start`).

**Invalidate button:** Renders the same inline invalidation form as `EvaluationDetailPage` (reason textarea + confirm/cancel). This mutates `selectedEvalId`'s evaluation. When `ev.invalidated` is true, the button is hidden and replaced with an "invalidated" label. While `useInvalidateEvaluation` is pending (`isPending === true`), the confirm button shows "Invalidating…" and is disabled — same pattern as `EvaluationDetailPage`.

**Score display:** The `{score}%` in the header reflects the *selected* evaluation's score (from `useEvaluationDetail`), not the latest. This updates as the user clicks different columns in the heatmap.

**Result badge:** Uses `ResultBadge` component with `displayResult = ev.invalidated ? 'invalidated' : ev.result`.

**Simplification vs current:** Remove the `EvaluationTable` at the bottom of AssetPanel (previously "Evaluation History"). The heatmap itself serves as the historical overview; clicking a column replaces the need for a table row click.

### 5. AssetNavigatorPage — Wiring

`AssetNavigatorPage` manages `group` and `asset` URL params. It must also expose `onSelectAsset` to `GroupPanel` so the group heatmap's second-click can change the `asset` param without leaving the Navigator.

`GroupPanel` receives an `onSelectAsset: (name: string) => void` prop. It passes this into the `EvaluationHeatmap`'s `onAssetSelect`.

`AssetNavigatorPage` uses a single `selectAsset` handler for both the tree panel and `GroupPanel`. This handler **always** clears `?group=` and sets `?asset=<name>` (`setParams({ asset: name })`). When a user picks an asset from the tree, the group context is already visible in the sidebar tree — the URL does not need to preserve it. This keeps URLs clean and avoids stale group params persisting into asset view.

The empty state ("Pick a group or asset to load data") is shown when neither `group` nor `asset` param is set.

---

## Components Affected

| Component | Change |
|---|---|
| `App.tsx` | Remove `Evaluations` from `NAV_ITEMS` |
| `AssetTreePanel.tsx` | Add `onClearSelection` prop; add "All" entry at top; `countLeafMembers` helper; recursive member count badge |
| `EvaluationHeatmap.tsx` | Add optional `onAssetSelect?: (assetName: string) => void`; three-case click handler |
| `GroupPanel.tsx` | Replace `GroupHeatmap` → `EvaluationHeatmap` + `EvaluationTable`; receive + pass `onSelectAsset` |
| `GroupHeatmap.tsx` | **Delete** |
| `AssetHeatmap.tsx` | Add `selectedEvalId?`, `onEvalSelect?`; remove `useNavigate`; update tooltip text |
| `AssetPanel.tsx` | Full redesign per layout above; `useEvaluationDetail`; `useInvalidateEvaluation`; remove `EvaluationTable` from bottom |
| `AssetNavigatorPage.tsx` | Wire `onSelectAsset` and `onClearSelection` from panels; `selectAsset` clears `?group=` param |
| `hooks.ts` (evaluations) | Widen `useEvaluationDetail(id: string)` to `id: string \| undefined`; guard with `enabled: !!id` |

Components **not changed:** `GroupScoreChart`, `MetricTrendBlock`, `SLIBreakdownTable`, `EvaluationTable`, `EvaluationTabs`, `AnnotationForm`, `ResultBadge`, `EvaluationsPage`.

---

## Data Flow

### Group Heatmap second-click

```
User first-click on column C
  → EvaluationHeatmap.onDateSelect(slot)        [selectedDate = slot, column highlighted]

User second-click on cell in column C (already selected)
  → EvaluationHeatmap.onAssetSelect(assetName)  [extracted from row label]
  → GroupPanel calls props.onSelectAsset(assetName)
  → AssetNavigatorPage sets ?asset=<assetName>   [Asset Panel renders]
```

### Asset Heatmap column selection

```
User clicks column (eval) in AssetHeatmap
  → AssetHeatmap.onEvalSelect(evalId)
  → AssetPanel sets selectedEvalId = evalId
  → useEvaluationDetail(selectedEvalId) fetches detail
  → AnnotationForm, SLIBreakdownTable, MetricTrendBlocks all update
```

---

## Testing

- Unit: `countLeafMembers` helper with nested group fixtures
- Unit: `EvaluationHeatmap` click handler — first click sets selectedDate; second click on same slot calls onAssetSelect with correct asset name (parsed from row label)
- Unit: `AssetHeatmap` — click calls onEvalSelect, not navigate; selectedEvalId column gets white border cells
- MSW mocks already exist for all API endpoints; no new endpoints needed

---

## Implementation Rules for Agents

**Use simple, single commands only.** Compound shell commands (pipes `|`, chains `&&`/`||`/`;`,
subshells `$(...)`, redirects `>`) require manual user approval and slow down the work. Each
bash call must be one command with no composition.

✗ `cd ui && npx vitest run | head -n 20`
✓ `npx --prefix ui vitest run`  — then read the output normally

**Use dedicated tools before bash:** Read/Grep/Glob for file access; use `--directory` or
`--prefix` flags instead of `cd`. If a compound is truly unavoidable, create a named script
in `scripts/` and call that script — it is version-controlled and auto-approved.

**Git in worktrees:** always `git -C <path> <cmd>`, never `cd <path> && git <cmd>`. Issue
`git add` and `git commit` as separate bash calls, never chained.

**Tests:** `uv run --directory api pytest ...` — never `cd api && uv run pytest ...`.
