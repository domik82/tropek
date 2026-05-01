# Known Issues & Technical Debt

Tracked issues, gaps, and improvement opportunities in the TROPEK UI. Updated 2026-05-01.

## Code Quality

### Large Components (>300 lines)

| File | Lines | Notes |
|---|---|---|
| `navigator/components/AssetPanel.tsx` | ~620 | Largest component. Action form orchestration, heatmap state, annotations, SLO scope. Would benefit from extracting action-handling into a custom hook. |
| `charts/HeatmapChart.tsx` | ~450 | Core render component. Complexity justified by ECharts option assembly. |
| `registry/forms/SloWizard.tsx` | ~362 | Multi-step wizard managing 4 steps and form state. |
| `navigator/components/AssetPanelHeatmapView.tsx` | ~336 | Heatmap view extracted from AssetPanel. |
| `evaluations/components/SLIBreakdownTable.tsx` | ~328 | Contains main table + GroupRows + IndicatorRow sub-components. |
| `slos/components/SloCreateForm.tsx` | ~328 | SLO creation form. Possibly legacy (SloWizard is newer). |
| `components/AssetTree/AssetTree.tsx` | ~311 | Tree with search, context menu, rename, dialogs. |

### Dead Code

| File | Export | Issue |
|---|---|---|
| `lib/types.ts` | `PagedResponse<T>` | Zero imports. The generated API has its own `PagedResponse_*` schemas. Orphaned. |
| `components/charts/colors.ts` | `generateSeriesColor` | Only used internally by `buildColorMap`. Unnecessarily exported. |

### TODOs in Code

| File | Description |
|---|---|
| `lib/theme.ts:44` | `// TODO: Radix grass-9 light` — light theme colour stub |
| `lib/theme.ts:76` | `// TODO: Radix light scales` — light theme background stub |

### Duplicated Code

| What | Where | Notes |
|---|---|---|
| `highlightVariables()` | `SliDetailView.tsx` and `SloObjectiveTable.tsx` | Identical function for `$variable` highlighting. Should be shared. |
| `TagRowEditor` | `SliForm.tsx` and `DatasourceForm.tsx` | Identical component for tag key-value editing. Should be extracted. |
| `normalizeResult` | `navigator/mappers.ts` and `AssetPanel.tsx` | Duplicated result normalisation logic. |
| `TagKeyCount` / `TagValueCount` | `assets/domain.ts` and `datasources/domain.ts` | Identical interfaces. Should be in a shared location. |
| `fetchAssetGroupTree` / `fetchGroupTree` | `assets/api.ts` | Same endpoint, same return type. Added at different times. |
| SLO Link Dialogs | `slos/SloLinkDialog.tsx` and `registry/SloLinkDialogRevised.tsx` | Two coexisting versions with different UI patterns. |

## Accessibility

| Component | Issue | Severity |
|---|---|---|
| `SLIBreakdownTable.tsx` | `<tr onClick>` without `role`, `tabIndex`, or `onKeyDown`. Rows not keyboard-accessible. | High |
| `AssetScoreChart.tsx` | `<div onClick>` for chart click-to-select without keyboard equivalent. | Medium |
| `NoteIndicatorRow.tsx` | `<div onClick>` on note indicator slots without keyboard support. | Medium |
| `CollapsedStrip.tsx` | `<div onClick>` toggle without keyboard handler. | Low |
| Navigator loading states | "Loading..." as plain text, not `aria-live` or `role="status"`. | Low |

Components with **good accessibility**: `TreeNode` (Enter/Space keyboard), `AssetTree` (proper tree roles, aria-expanded/selected), `HeatmapChart` (role="img", aria-label), `EvaluationTable` (proper button elements), all dialogs (shadcn focus trapping).

## Error Handling

### Silent Error Swallowing

Most panel components check `isLoading` but **never check `isError`**. If a fetch fails, the component shows loading state indefinitely or renders empty.

| Component | Impact |
|---|---|
| `AssetPanel.tsx` | Heatmap/evaluation fetch failure shows "Loading..." forever |
| `GroupPanel.tsx` | Same pattern |
| `AllEvaluationsPanel.tsx` | Same pattern |
| `EvaluationDetailPage.tsx` | Shows loading spinner indefinitely on failure |

### Missing Error Boundaries

Only one `ErrorBoundary` wraps the entire route outlet in `App.tsx`. No feature-level error boundaries. A single component crash takes down the entire page.

### Fetch Error Body Loss

Most `api.ts` fetch functions throw `new Error(...)` without parsing the response body. Only `reEvaluate` in `evaluations/api.ts` extracts a server error message. Other endpoints lose useful backend error details.

## Test Coverage

~40 component files lack tests out of ~110 non-UI-primitive component files. See [testing.md](testing.md) for the full gap analysis.

**Highest priority gaps:** HeatmapChart, EvaluationTable, MetricTrendBlock, AssetPanelHeatmapView, SloObjectiveEditor, AssetTree (main component).

## Performance

### N+1 Query Pattern in RegistrySidebar

`RegistrySidebar` issues individual `useQueries` calls for every group name and every asset name to fetch SLO assignments. For large registries, this creates O(groups + assets) parallel requests.

### GroupEditDialog Parent Detection

Scans `tree.allGroups` to find the current parent — O(n×m) where n = groups, m = max subgroups per group. Would benefit from a parent reference in the domain type.

## Migration Debt

### Navigator DTO-to-Domain

`AssetPanel` contains a ~80-line inline `scopeHeatmapData` useMemo that manually converts snake_case DTO to camelCase domain types. This exists because `useMetricHeatmap` returns raw DTO but `useSloScope` consumes domain types. Pending the full Navigator migration.

### ESLint Suppressions

Multiple files suppress `react-hooks/set-state-in-effect` for intentional state resets from async data or prop changes:
- `AssetPanel.tsx` (3 blocks)
- `SloWizard.tsx`, `SliForm.tsx`, `DatasourceForm.tsx` (form resets)
- `SloLinkDialogRevised.tsx`, `SloLinkDialog.tsx`, `LabelsEditorDialog.tsx` (prop sync)
- `AssetEditDialog.tsx`, `GroupEditDialog.tsx` (data sync)

These are legitimate patterns but acknowledged as lint smells.

### Input Types in Barrels

`assets/index.ts` and `slos/index.ts` re-export DTO-adjacent input shapes. Per the layering spec, `index.ts` should never re-export DTOs — input types are a grey area.

## Light Theme

The light theme is a **stub**. Only meta-timeline colours are defined for `[data-theme="light"]` in `index.css`. All other functional tokens are undefined. The theme toggle in NavControls deliberately omits a "Light" button.

**To complete:** Define all ~100 functional CSS token categories for the light theme in `index.css`, add corresponding JS hex values in `lib/theme.ts`, and expose the Light toggle in NavControls.

## Other Issues

### `AddAssetToGroupDialog` Custom Modal

Uses its own `fixed inset-0 z-50` overlay instead of shadcn `Dialog`. May cause z-index stacking issues or miss dialog accessibility features.

### `SloGroupForm` No Schema Validation

Unlike `SliForm` and `DatasourceForm` which use Zod, `SloGroupForm` uses raw `useState` with manual `name && templateSloName` check. Generator variables textarea parses `key=val1,val2` per line with no validation.

### Template Kind Type Safety

SLO `kind` field (`'standard' | 'template'`) is narrowed from DTO's `string` via type assertion in the mapper — no runtime validation.

### Mock Data Divergence

Mock handler for `/api/config/ui` returns `{ maxEvaluations: 1000, pageSize: 200 }`, differing from defaults in `config.ts` (`maxEvaluations: 5000`). Missing `heatmapSloGroupsExpandedByDefault`, `heatmapSlowThresholdDays`, `dataStartDate`.

### `overridden: false` Hardcoded in Trend Mapper

`dtoToTrendPoint()` sets `overridden: false` unconditionally. The DTO apparently does not expose override status per trend point, but the chart checks `p.overridden` for styling — effectively dead code on the trend side.

### Void `columnEvalId` in Action Forms

All action forms accept `columnEvalId` but void it with a comment "reserved for future cache-scoping logic". Currently unused.

### ECharts CSS Variable Limitation

ECharts cannot resolve CSS custom properties. The entire `RESULT_COLOUR` and `CHART_THEME` system in `theme.ts` duplicates colours as JS hex strings. Colour changes must be synchronised between `index.css` and `theme.ts`.

### `useSloLinkCounts` Stub

In `AssetTree.tsx`, `useSloLinkCounts()` returns an empty map. The SLO link count feature is not yet implemented.

### Coming Soon Features

"Move to" and "Duplicate group" actions in `AssetTreeContextMenu` are disabled with "(coming soon)" labels.
