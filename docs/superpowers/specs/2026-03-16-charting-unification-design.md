# Charting Unification Design

**Date:** 2026-03-16
**Status:** Draft
**Scope:** Unified heatmap component, asset score chart, full-screen metric explorer

## Problem

The UI has three charting contexts (GroupPanel, AssetPanel, MetricExplorerPage) that evolved
independently. The two heatmap components (`EvaluationHeatmap`, `AssetHeatmap`) duplicate
rendering logic with subtle visual inconsistencies (border radius, emphasis, hover colors,
annotation support). The MetricExplorerPage shows a grid of small individual charts that
won't scale to 150+ indicators. The AssetPanel lacks a chart-mode equivalent to
GroupPanel's `GroupScoreChart`.

## Goals

1. Extract a shared `HeatmapChart` render core consumed by thin domain wrappers
2. Add an `AssetScoreChart` so both Group and Asset views have Heatmap/Chart toggle parity
3. Redesign `MetricExplorerPage` as a full-screen dual-chart workspace with toggleable
   indicator labels — supporting 150+ indicators across ~3 pages

## Non-goals

- Changing the existing MetricTrendBlock grid (kept for the inline asset view)
- Changing GroupScoreChart's stacked bar design

---

## 1. HeatmapChart — shared render core

### Architecture

Option B: shared render core + thin wrappers.

```
EvaluationHeatmap  ──┐
                     ├──> HeatmapChart (ECharts renderItem, emphasis, annotations, legend)
AssetHeatmap       ──┘
```

`HeatmapChart` is a pure rendering component with no domain knowledge. The wrappers handle
data mapping and click behavior.

### New file: `ui/src/components/charts/HeatmapChart.tsx`

**Props:**

```ts
interface HeatmapChartProps {
  rows: string[]
  columns: string[]
  cells: HeatmapCell[]
  selectedColumn?: number          // highlight column index
  onCellClick: (cell: HeatmapCell) => void
  annotations?: boolean            // render triangle markers for hasNote cells
  height?: number | 'auto'         // auto = rows.length * 28 + 100
  formatTooltip: (cell: HeatmapCell) => string
  formatColumnLabel?: (slot: string) => string
  instructionText?: string         // e.g. "Click a cell to filter" — shown above legend
}
```

**Theme access:** `HeatmapChart` calls `useTheme()` internally to access `RESULT_COLOUR`
and `CHART_THEME`. This keeps the wrappers free from color logic. The component maps each
cell's `result` string to the theme's color palette and computes `hoverColor` via
`brighten()` internally.

**Grid margins:** Unified to `{ top: 10, bottom: 80, left: 210, right: 20 }` for both
views. Row labels get `width: 210, overflow: 'truncate'`.

**Internals moved from current EvaluationHeatmap:**
- `brighten()` color utility
- `renderItem` with rounded rects (`r: 3`), emphasis hover with brightened fill + white
  border, annotation triangle markers (rendered when `annotations` prop is true and cell
  has `hasNote: true`)
- Color legend bar (pass / warning / fail / error / invalidated)
- Consistent `fontSize: 14` for both axes
- Dynamic padding: `pad = columns.length > 40 ? 1 : 2`

### HeatmapCell extension

Add optional fields to the existing `HeatmapCell` interface in `navigator/types.ts`:

```ts
export interface HeatmapCell {
  value: [number, number]
  result: string
  score: number
  slot: string
  rowLabel: string
  evalId?: string
  hasNote?: boolean          // NEW — triggers annotation triangle
  noteContent?: string       // NEW — shown in tooltip
}
```

### EvaluationHeatmap wrapper (~50 lines)

Location: stays at `ui/src/features/evaluations/components/EvaluationHeatmap.tsx`

- Takes `EvaluationSummary[]`
- Data mapping: the current inline `buildHeatmapData()` function is extracted to
  `ui/src/features/navigator/utils.ts` as `buildGroupHeatmapData()` (this function
  already exists there — the inline copy in EvaluationHeatmap is removed)
- Enriches cells with `hasNote` / `noteContent` from annotation data on each evaluation
- Maps `selectedDate` string → `selectedColumn` index via `slots.indexOf(selectedDate)`
- Provides `formatTooltip` showing: asset name, eval name, date, score, result, note
- Provides `instructionText`: "Click any cell to filter the table below."
- Click handler: calls `onDateSelect(slot)` on first click; `onAssetSelect(assetName)`
  on second click of the same slot

### AssetHeatmap wrapper (~40 lines)

Location: stays at `ui/src/features/navigator/components/AssetHeatmap.tsx`

- Takes `MetricHeatmapResponse`, calls `buildAssetHeatmapData()` (existing util in
  `navigator/utils.ts`)
- Maps `selectedEvalId` → `selectedColumn` index by finding the slot that contains
  the matching evalId
- Provides `formatTooltip` showing: metric name, date, score, result
- Provides `instructionText`: "Click a cell to select that evaluation."
- Click handler: calls `onEvalSelect(evalId)`
- Extensible for future `hasNote` support on indicators

---

## 2. AssetScoreChart

### New file: `ui/src/features/navigator/components/AssetScoreChart.tsx`

Line chart showing total evaluation score over time for a single asset.

**Data source:** `useAssetEvaluations(assetName)` hook returns `EvaluationSummary[]` which
contains `score`, `period_start`, and `result` per evaluation. Invalidated evaluations
are shown as distinct points with the `invalidated` color but are not connected to
adjacent points (broken line segment) to visually distinguish them.

- X axis: eval run timestamps (formatted with `fmtSlot`)
- Y axis: 0-100 (score)
- Each point color-coded by result (pass/warning/fail/error/invalidated)
- Selected evaluation highlighted with white border + larger symbol (`symbolSize: 10`)
- Same ECharts config patterns as `GroupScoreChart` (tooltip, grid, axis styling)

### Integration

`AssetPanel` gets the same Heatmap/Chart `ViewToggle` it already has, but the Chart mode
renders `AssetScoreChart` instead of nothing. The `ViewToggle` component is extracted from
its current inline location in `AssetPanel.tsx` to a shared location at
`ui/src/components/charts/ViewToggle.tsx` since both `GroupPanel` and `AssetPanel` use it.

Both views link to `MetricExplorerPage` via the existing explorer button icon.

---

## 3. MetricExplorerPage — full-screen dual-chart workspace

### Layout

Full-screen (`calc(100vh - 49px)` matching the nav bar height). Two sections stacked
vertically, each with a label panel on the left and a chart on the right:

```
┌─────────────────────────────────────────────────────┐
│  <- Back    Metric Explorer - {asset/group name}    │
├─────────────────────────────────────────────────────┤
│ VALUES                                              │
│ ┌───────────────┬───────────────────────────────────┐
│ │ Label panel   │ Multi-series line chart           │
│ │ (2-col grid,  │ (raw metric values, auto-colors)  │
│ │  grouped,     │                                   │
│ │  paginated,   │                                   │
│ │  All/None)    │                                   │
│ └───────────────┴───────────────────────────────────┘
│ SCORES                                              │
│ ┌───────────────┬───────────────────────────────────┐
│ │ Label panel   │ Multi-series line chart           │
│ │ (same layout, │ (0-100 Y scale, per-indicator     │
│ │  independent  │  scores over time)                │
│ │  toggles)     │                                   │
│ └───────────────┴───────────────────────────────────┘
└─────────────────────────────────────────────────────┘
```

### Label panel: `MetricLabelPanel`

**New file:** `ui/src/components/charts/MetricLabelPanel.tsx`

**Props:**

```ts
interface MetricLabelPanelProps {
  indicators: Array<{ metric: string; display_name: string; tab_group?: string }>
  colors: Map<string, string>         // metric -> auto-generated color
  enabled: Set<string>                // currently toggled-on metrics
  onToggle: (metric: string) => void
  onGroupAll: (group: string) => void
  onGroupNone: (group: string) => void
}
```

**Layout:**
- Labels arranged in a 2-column CSS grid, grouped by `tab_group`
- Each group has a header row with group name + All / None buttons
- Active labels: colored left border + bright text + dark background
- Inactive labels: dimmed text, no border
- Pagination at the bottom: `◀ 1/3 ▶` arrows

**Sizing target:** The panel fills available viewport height (each section gets ~50% of
the available space below the header). With ~22px per label row and 2 columns,
approximately 50-60 labels fit per page. For 150 indicators this yields ~3 pages maximum.

**Toggle state is global, not per-page.** The `enabled` Set persists across page
navigation — toggling a label on page 1, navigating to page 2, and toggling more labels
results in ALL enabled metrics being rendered on the chart simultaneously regardless of
which page is currently visible.

**Group-level correlation use case:** Groups are visually separated with headers. A user
can enable CPU and memory from the "Resources" group alongside response_time from
"Performance" to visually identify CPU bottlenecks that correlate with response time
degradation — all overlaid on the same chart. The All/None buttons per group make it
easy to quickly show an entire group's metrics for comparison, then clear them and
switch to a different group.

### State management in MetricExplorerPage

The page manages two independent toggle states:

```ts
const [valuesEnabled, setValuesEnabled] = useState<Set<string>>(new Set())
const [scoresEnabled, setScoresEnabled] = useState<Set<string>>(new Set())
```

Each `MetricLabelPanel` receives its own `enabled` set and toggle callbacks. The chart
below each label panel renders only the metrics in its corresponding enabled set.

The `onGroupAll(group)` callback adds all metrics with that `tab_group` to the enabled
set. `onGroupNone(group)` removes them. The parent knows which metrics belong to which
group because it has the full indicators list.

### Multi-series chart: `MultiSeriesChart`

**New file:** `ui/src/components/charts/MultiSeriesChart.tsx`

**Props:**

```ts
interface MultiSeriesChartProps {
  series: Array<{
    metric: string
    displayName: string
    color: string
    data: Array<{ timestamp: string; value: number }>
  }>
  yAxisLabel?: string              // e.g. "Score" or "Value"
  yAxisMax?: number                // e.g. 100 for scores chart
  height?: number                  // chart pixel height
}
```

- ECharts line chart with one series per enabled indicator
- Auto-scaled Y axis for values; fixed 0-100 for scores
- Tooltip trigger: `'axis'` — shows all visible series values at the hovered X position.
  When many series are active, the tooltip uses `max-height` with overflow scroll to
  remain usable. Each tooltip row shows the series color dot, metric name, and value.
- X axis: eval timestamps formatted with `fmtSlot`
- Uses `useTheme()` for axis colors, grid lines, tooltip background (same pattern as
  existing charts)

### Color generation: `colors.ts`

**New file:** `ui/src/components/charts/colors.ts`

```ts
export function generateSeriesColor(index: number, total: number): string
```

Deterministic color generation using OKLCH hue rotation with varying chroma and lightness
to produce 150+ visually distinct colors. Each indicator gets a stable color based on its
sorted index in the full indicator list — not affected by pagination or toggle state.

The function distributes hues evenly across the 360-degree wheel, then varies lightness
and chroma in a second pass to differentiate adjacent hues. This avoids the "too many
similar greens" problem of naive HSL rotation.

### Data flow

1. Page loads indicator list from heatmap API (`useMetricHeatmap`) or METRICS catalogue
   fallback for group view
2. Each indicator gets a stable auto-generated color via `generateSeriesColor`
3. User toggles labels in the Values panel → only those metrics fetch/render trend data
4. Same for Scores panel (independent toggle state)
5. Values chart: Y = `TrendPoint.value` (raw metric value)
6. Scores chart: Y = `TrendPoint.score` (per-indicator score, 0-100)
7. Tooltip at any X position shows all enabled series values in a compact scrollable list

### TrendPoint extension

The existing `TrendPoint` type does not include a `score` field. Add it:

```ts
export interface TrendPoint {
  timestamp: string
  value: number
  score: number               // NEW — per-indicator score (0-100) for this data point
  eval_id: string
  result: 'pass' | 'warning' | 'fail'
  baseline?: number | null
}
```

The mock `generateTrendData()` function in `ui/src/mocks/generate.ts` must be updated to
compute and include the `score` field using the existing `scoreIndicator()` function which
already returns `{ score, status }`.

### Trend data fetching

Currently `useTrend(evalId, metric)` fetches one metric at a time. For the explorer,
multiple metrics are enabled simultaneously.

**MVP approach:** Keep per-metric `useTrend` hooks. React Query deduplicates and caches
with `staleTime: Infinity`. 10 enabled metrics = 10 parallel requests, all cached across
toggle on/off. The browser's 6-connection limit may cause visible staggering with many
simultaneous enables — acceptable for MVP.

**Future:** Batch endpoint `GET /api/evaluations/{id}/trends?metrics=a,b,c` returning all
requested trends in one response. This would eliminate connection staggering.

---

## File changes summary

| Action | File |
|--------|------|
| New | `ui/src/components/charts/HeatmapChart.tsx` |
| New | `ui/src/components/charts/MultiSeriesChart.tsx` |
| New | `ui/src/components/charts/MetricLabelPanel.tsx` |
| New | `ui/src/components/charts/ViewToggle.tsx` |
| New | `ui/src/components/charts/colors.ts` |
| New | `ui/src/features/navigator/components/AssetScoreChart.tsx` |
| Refactor | `ui/src/features/evaluations/components/EvaluationHeatmap.tsx` → thin wrapper over HeatmapChart |
| Refactor | `ui/src/features/navigator/components/AssetHeatmap.tsx` → thin wrapper over HeatmapChart |
| Refactor | `ui/src/pages/MetricExplorerPage.tsx` → full-screen dual-chart layout |
| Extend | `ui/src/features/navigator/types.ts` → add `hasNote?`, `noteContent?` to HeatmapCell |
| Extend | `ui/src/features/evaluations/types.ts` → add `score` to TrendPoint |
| Update | `ui/src/mocks/generate.ts` → include score in trend data generation |

## Implementation order

1. `HeatmapChart` + `HeatmapCell` extension + `ViewToggle` extraction + refactor both wrappers
2. `AssetScoreChart` + wire into AssetPanel chart mode
3. `colors.ts` + `MetricLabelPanel` + `MultiSeriesChart`
4. `TrendPoint.score` extension + mock update
5. `MetricExplorerPage` redesign wiring everything together
