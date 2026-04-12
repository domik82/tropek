# Charting Unification Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the two heatmap components into a shared render core, add asset score chart for view parity, and redesign MetricExplorerPage as a full-screen dual-chart workspace.

**Architecture:** Extract a generic `HeatmapChart` ECharts renderer consumed by thin domain wrappers (`EvaluationHeatmap`, `AssetHeatmap`). Add `AssetScoreChart` for the asset view's chart mode. Rebuild `MetricExplorerPage` with two stacked chart sections (Values + Scores), each with a label toggle panel on the left and a multi-series line chart on the right.

**Tech Stack:** React 19, TypeScript, ECharts (via echarts-for-react), TanStack Query, Tailwind CSS v4

**Spec:** `docs/superpowers/specs/2026-03-16-charting-unification-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `ui/src/components/charts/HeatmapChart.tsx` | NEW — Generic ECharts heatmap renderer. No domain knowledge. |
| `ui/src/components/charts/ViewToggle.tsx` | NEW — Heatmap/Chart mode toggle button group (extracted from AssetPanel). |
| `ui/src/components/charts/MultiSeriesChart.tsx` | NEW — ECharts multi-series line chart for explorer. |
| `ui/src/components/charts/MetricLabelPanel.tsx` | NEW — Paginated 2-column label toggle panel grouped by tab_group. |
| `ui/src/components/charts/colors.ts` | NEW — Deterministic OKLCH color generator for 150+ series. |
| `ui/src/features/navigator/components/AssetScoreChart.tsx` | NEW — Score-over-time line chart for single asset. |
| `ui/src/features/evaluations/components/EvaluationHeatmap.tsx` | REFACTOR — Thin wrapper: maps EvaluationSummary[] → HeatmapChart props. |
| `ui/src/features/navigator/components/AssetHeatmap.tsx` | REFACTOR — Thin wrapper: maps MetricHeatmapResponse → HeatmapChart props. |
| `ui/src/features/navigator/components/AssetPanel.tsx` | MODIFY — Wire AssetScoreChart into chart mode, extract ViewToggle. |
| `ui/src/features/navigator/components/GroupPanel.tsx` | MODIFY — Import shared ViewToggle. |
| `ui/src/pages/MetricExplorerPage.tsx` | REWRITE — Full-screen dual-chart layout with label panels. |
| `ui/src/features/navigator/types.ts` | EXTEND — Add `hasNote?`, `noteContent?` to HeatmapCell. |
| `ui/src/features/evaluations/types.ts` | EXTEND — Add `score` to TrendPoint. |
| `ui/src/mocks/generate.ts` | MODIFY — Include score in generateTrendData output. |

---

## Chunk 1: HeatmapChart shared core + wrappers

### Task 1: Extend HeatmapCell type

**Files:**
- Modify: `ui/src/features/navigator/types.ts:4-11`

- [ ] **Step 1: Add hasNote and noteContent to HeatmapCell**

```ts
export interface HeatmapCell {
  value: [number, number]       // [xIndex (slot), yIndex (row)]
  result: string                // pass | warning | fail | error | invalidated | none
  score: number
  slot: string                  // ISO timestamp for column
  rowLabel: string              // asset name (group view) or metric display name (asset view)
  evalId?: string               // defined in asset view — for click navigation
  hasNote?: boolean             // triggers annotation triangle in HeatmapChart
  noteContent?: string          // shown in tooltip
}
```

- [ ] **Step 2: Commit**

```
git add ui/src/features/navigator/types.ts
git commit -m "feat(ui): add hasNote and noteContent to HeatmapCell type"
```

---

### Task 2: Create HeatmapChart shared render core

**Files:**
- Create: `ui/src/components/charts/HeatmapChart.tsx` (NOTE: create `ui/src/components/charts/` directory first — it does not exist yet)

**Reference files to read before implementing:**
- `ui/src/features/evaluations/components/EvaluationHeatmap.tsx` — source of renderItem, brighten, legend, tooltip patterns
- `ui/src/features/navigator/components/AssetHeatmap.tsx` — second implementation to unify
- `ui/src/features/navigator/types.ts` — HeatmapCell interface
- `ui/src/lib/theme-context.tsx` — useTheme hook
- `ui/src/lib/theme.ts` — RESULT_COLOUR, CHART_THEME, ResultColours
- `ui/src/lib/format.ts` — fmtSlot, fmtDateTime

- [ ] **Step 1: Create the HeatmapChart component**

This component extracts ALL rendering logic from the two existing heatmaps into one place. It must:

1. Accept the props interface from the spec:
   ```ts
   interface HeatmapChartProps {
     rows: string[]
     columns: string[]
     cells: HeatmapCell[]
     selectedColumn?: number
     onCellClick: (cell: HeatmapCell) => void
     annotations?: boolean
     height?: number | 'auto'
     formatTooltip: (cell: HeatmapCell) => string
     formatColumnLabel?: (slot: string) => string
     instructionText?: string
   }
   ```

2. Call `useTheme()` internally to get `RESULT_COLOUR[theme]` and `CHART_THEME[theme]`.

3. In a `useMemo`, map each `HeatmapCell` to an internal `RenderCell` that adds:
   - `itemStyle.color` — looked up from `colours[cell.result]` or `ct.bg` for 'none'
   - `itemStyle.borderColor` — `'#ffffff'` if cell's column index matches `selectedColumn`, else `'transparent'`
   - `itemStyle.borderWidth` — `2` if selected, `0` otherwise
   - `hoverColor` — computed via `brighten(color, 1.4)`

4. Include the `brighten()` utility (copied from EvaluationHeatmap, with the `hex.startsWith('#')` guard from AssetHeatmap).

5. Build the ECharts option with:
   - `type: 'custom'` series with `renderItem` producing rounded rects (`r: 3`)
   - Emphasis style: `{ fill: hoverColor, stroke: '#ffffff', lineWidth: 2 }`
   - When `annotations` is true and cell has `hasNote`, render a white triangle polygon in top-right corner
   - `emphasis: { focus: 'self' }`
   - `grid: { top: 10, bottom: 80, left: 210, right: 20 }`
   - Both axes: `fontSize: 14`, yAxis `width: 210, overflow: 'truncate'`
   - Dynamic padding: `pad = columns.length > 40 ? 1 : 2`

6. The tooltip uses the caller's `formatTooltip` callback — not an internal formatter. Set `trigger: 'item'`, pass `formatTooltip(cell)` in the ECharts formatter.

7. Render the instruction text + color legend bar above the chart (same JSX pattern as both existing heatmaps). Use `instructionText` prop for the left side text.

8. The `onEvents.click` handler calls `onCellClick(cell)` with the HeatmapCell.

9. Height: if `'auto'`, compute `Math.max(200, rows.length * 28 + 100)`.

- [ ] **Step 2: Verify it compiles**

Run: `npx tsc --noEmit --project ui/tsconfig.json 2>&1 | head -20`

- [ ] **Step 3: Commit**

```
git add ui/src/components/charts/HeatmapChart.tsx
git commit -m "feat(ui): add HeatmapChart shared render core"
```

---

### Task 3: Refactor EvaluationHeatmap as thin wrapper

**Files:**
- Modify: `ui/src/features/evaluations/components/EvaluationHeatmap.tsx`

**Reference:** The existing `buildGroupHeatmapData()` in `ui/src/features/navigator/utils.ts` already produces `{ slots, rows, cells: HeatmapCell[] }`. The inline `buildHeatmapData()` in EvaluationHeatmap does the SAME grouping but also adds annotation data and pre-computes styles. After the refactor, annotations go into HeatmapCell fields and styles are handled by HeatmapChart.

- [ ] **Step 1: Rewrite EvaluationHeatmap**

Replace the entire file. The new version:

1. Imports `HeatmapChart` from `@/components/charts/HeatmapChart`
2. Imports `buildGroupHeatmapData` from `@/features/navigator/utils` (NOTE: this function currently uses `asset_snapshot.name` as row label but EvaluationHeatmap uses `asset · eval_name`. Either update `buildGroupHeatmapData` to accept a row-label builder, or build the data inline. The simplest approach: keep a small inline `buildData()` that produces HeatmapCell[] with the `asset · eval` row format AND enriches with `hasNote`/`noteContent` from annotation data.)
3. Keeps the same Props interface: `{ evaluations, selectedDate, onDateSelect, onAssetSelect }`
4. Computes `selectedColumn = selectedDate ? slots.indexOf(selectedDate) : undefined`
5. Provides a `formatTooltip(cell)` that returns the HTML string (same format as current: bold row, datetime, score with color, result badge, note if present)
6. The `onCellClick` handler: if `cell.slot !== selectedDate`, call `onDateSelect(cell.slot)`; else if `onAssetSelect`, extract asset name from `cell.rowLabel.split(' · ')[0]` and call it; else call `onDateSelect(null)`.
7. Passes `annotations={true}` and `instructionText="Click any cell to filter the table below."`

The file should be ~60-70 lines total (imports + data mapping + JSX return).

- [ ] **Step 2: Verify the group view still renders**

Open `http://localhost:5173/navigator`, select a group (e.g. "Monthly Lab"), verify the heatmap looks identical — same colors, hover effects, annotation triangles, tooltip content, click-to-filter behavior.

- [ ] **Step 3: Commit**

```
git add ui/src/features/evaluations/components/EvaluationHeatmap.tsx
git commit -m "refactor(ui): EvaluationHeatmap as thin wrapper over HeatmapChart"
```

---

### Task 4: Refactor AssetHeatmap as thin wrapper

**Files:**
- Modify: `ui/src/features/navigator/components/AssetHeatmap.tsx`

- [ ] **Step 1: Rewrite AssetHeatmap**

Replace the entire file. The new version:

1. Imports `HeatmapChart` from `@/components/charts/HeatmapChart`
2. Imports `buildAssetHeatmapData` from `../utils`
3. Keeps the same Props: `{ data: MetricHeatmapResponse, selectedEvalId?, onEvalSelect? }`
4. Calls `buildAssetHeatmapData(data)` to get `{ slots, rows, cells }`
5. Computes `selectedColumn`: find the column index where any cell has `evalId === selectedEvalId`
6. Provides a `formatTooltip(cell)` returning: bold metric name, datetime, score · result, "click to select" hint if evalId present
7. The `onCellClick` handler: if `cell.evalId && onEvalSelect`, call `onEvalSelect(cell.evalId)`
8. Passes `instructionText="Click a cell to select that evaluation."`
9. Does NOT pass `annotations` (defaults to false/undefined)

The file should be ~40-50 lines total.

- [ ] **Step 2: Verify the asset view heatmap still renders**

Open `http://localhost:5173/navigator?asset=win-toolset-01`, verify the metric heatmap looks identical — same cell colors, hover, tooltip, click-to-select behavior.

- [ ] **Step 3: Commit**

```
git add ui/src/features/navigator/components/AssetHeatmap.tsx
git commit -m "refactor(ui): AssetHeatmap as thin wrapper over HeatmapChart"
```

---

## Chunk 2: AssetScoreChart + ViewToggle extraction

### Task 5: Extract ViewToggle to shared component

**Files:**
- Create: `ui/src/components/charts/ViewToggle.tsx`
- Modify: `ui/src/features/navigator/components/AssetPanel.tsx`
- Modify: `ui/src/features/navigator/components/GroupPanel.tsx`

**Reference:** The current `ViewToggle` is an inline function in `AssetPanel.tsx:25-42` (uses label "Charts"). GroupPanel has two duplicated inline toggle blocks at lines 67-80 and 104-117.

- [ ] **Step 1: Create shared ViewToggle**

```tsx
// ui/src/components/charts/ViewToggle.tsx
type ViewMode = 'heatmap' | 'chart'

interface ViewToggleProps {
  mode: ViewMode
  setMode: (m: ViewMode) => void
}

export type { ViewMode }

export function ViewToggle({ mode, setMode }: ViewToggleProps) {
  return (
    <div className="flex border border-slate-700 rounded overflow-hidden text-xs">
      <button
        onClick={() => setMode('heatmap')}
        className={`px-3 py-1.5 transition-colors ${mode === 'heatmap' ? 'bg-gray-800 text-slate-200' : 'text-slate-400 hover:bg-gray-800/50'}`}
      >
        Heatmap
      </button>
      <button
        onClick={() => setMode('chart')}
        className={`px-3 py-1.5 transition-colors ${mode === 'chart' ? 'bg-gray-800 text-slate-200' : 'text-slate-400 hover:bg-gray-800/50'}`}
      >
        Charts
      </button>
    </div>
  )
}
```

- [ ] **Step 2: Update AssetPanel to import shared ViewToggle**

Remove the inline `ViewToggle` function (lines 25-42) and the local `type ViewMode`. Add:

```ts
import { ViewToggle } from '@/components/charts/ViewToggle'
import type { ViewMode } from '@/components/charts/ViewToggle'
```

- [ ] **Step 3: Update GroupPanel to import shared ViewToggle**

Remove the two duplicated inline toggle button groups (lines 67-80, 104-117) and the local `type ViewMode`. Import `ViewToggle` and `ViewMode` from the shared location. Replace each inline toggle with `<ViewToggle mode={mode} setMode={setMode} />`. **Important:** Preserve the surrounding `<div className="flex items-center gap-3">` wrapper and the adjacent `explorerButton` — only replace the inline toggle buttons, not the container.

- [ ] **Step 4: Verify both views render correctly**

Open `http://localhost:5173/navigator`, click a group → verify Heatmap/Chart toggle works. Click an asset → verify toggle works.

- [ ] **Step 5: Commit**

```
git add ui/src/components/charts/ViewToggle.tsx
git add ui/src/features/navigator/components/AssetPanel.tsx
git add ui/src/features/navigator/components/GroupPanel.tsx
git commit -m "refactor(ui): extract ViewToggle to shared component"
```

---

### Task 6: Create AssetScoreChart

**Files:**
- Create: `ui/src/features/navigator/components/AssetScoreChart.tsx`

**Reference:** Follow the same patterns as `GroupScoreChart.tsx` (`ui/src/features/navigator/components/GroupScoreChart.tsx`) for ECharts config, tooltip, axis styling.

- [ ] **Step 1: Create AssetScoreChart component**

```tsx
// ui/src/features/navigator/components/AssetScoreChart.tsx
import ReactECharts from 'echarts-for-react'
import { useMemo } from 'react'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import { fmtSlot } from '@/lib/format'
import type { EvaluationSummary } from '@/features/evaluations/types'

interface Props {
  evaluations: EvaluationSummary[]
  selectedEvalId?: string
}
```

Implementation details:
- Sort evaluations by `period_start`
- X axis: `period_start` timestamps formatted with `fmtSlot`
- Y axis: 0-100, `type: 'value'`
- Single line series with per-point `itemStyle`:
  - `color` from `RESULT_COLOUR[theme][effectiveResult]` where `effectiveResult = e.invalidated ? 'invalidated' : e.result`
  - `borderColor: '#ffffff'` and `borderWidth: 2` for the point matching `selectedEvalId`
  - `symbolSize: 10` for selected point, `6` for others
- Invalidated evaluations: render as disconnected points (broken line segment). Set the data
  value to an object with `{ value: score, symbol: 'diamond' }` and insert `null` gaps before
  and after invalidated points in the data array so ECharts does not connect them to neighbors
- Tooltip: show date, score, result
- Same grid/axis styling as GroupScoreChart: `{ top: 20, bottom: 80, left: 50, right: 20 }`
- Use `animation: false` for consistency

- [ ] **Step 2: Wire into AssetPanel chart mode**

In `AssetPanel.tsx`, find the Charts mode section (around line 231 `{!isLoading && mode === 'chart' && (`). Currently it shows the ViewToggle + MetricTrendBlock grid. Add the `AssetScoreChart` at the top of this section (before the metric group filter):

```tsx
import { AssetScoreChart } from './AssetScoreChart'

// Inside the chart mode block, add before the metric group filter:
<div className="rounded-lg border border-slate-700 bg-gray-900 p-4">
  <AssetScoreChart evaluations={evals} selectedEvalId={effectiveEvalId} />
</div>
```

- [ ] **Step 3: Verify**

Open `http://localhost:5173/navigator?asset=win-toolset-01`, switch to Chart mode. Verify:
- Score line chart appears with colored dots
- Selected evaluation point is highlighted
- Tooltip shows score and result

- [ ] **Step 4: Commit**

```
git add ui/src/features/navigator/components/AssetScoreChart.tsx
git add ui/src/features/navigator/components/AssetPanel.tsx
git commit -m "feat(ui): add AssetScoreChart for asset view chart mode parity"
```

---

## Chunk 3: Color generation + MetricLabelPanel + MultiSeriesChart

### Task 7: Create color generator

**Files:**
- Create: `ui/src/components/charts/colors.ts`

- [ ] **Step 1: Implement generateSeriesColor**

```ts
// ui/src/components/charts/colors.ts

/**
 * Generate a deterministic, visually distinct color for chart series.
 *
 * Uses OKLCH color space with golden-angle hue distribution to maximize
 * visual separation between adjacent indices. Varies lightness and chroma
 * in a secondary cycle to avoid the "too many similar greens" problem.
 */
export function generateSeriesColor(index: number): string {
  // Golden angle (~137.5°) distributes hues with maximum separation
  const hue = (index * 137.508) % 360

  // Vary lightness and chroma in 3-step cycle to differentiate similar hues
  const cycle = index % 3
  const lightness = cycle === 0 ? 65 : cycle === 1 ? 50 : 75
  const chroma = cycle === 0 ? 0.15 : cycle === 1 ? 0.2 : 0.12

  return `oklch(${lightness}% ${chroma} ${hue})`
}

/**
 * Build a stable color map for a sorted list of metric names.
 * The color is determined by sorted position, not by toggle state or pagination.
 */
export function buildColorMap(
  metrics: Array<{ metric: string }>,
): Map<string, string> {
  const sorted = [...metrics].sort((a, b) => a.metric.localeCompare(b.metric))
  const map = new Map<string, string>()
  for (let i = 0; i < sorted.length; i++) {
    map.set(sorted[i].metric, generateSeriesColor(i))
  }
  return map
}
```

- [ ] **Step 2: Commit**

```
git add ui/src/components/charts/colors.ts
git commit -m "feat(ui): add OKLCH color generator for chart series"
```

---

### Task 8: Create MetricLabelPanel

**Files:**
- Create: `ui/src/components/charts/MetricLabelPanel.tsx`

- [ ] **Step 1: Implement MetricLabelPanel**

Props (from spec):
```ts
interface MetricLabelPanelProps {
  indicators: Array<{ metric: string; display_name: string; tab_group?: string }>
  colors: Map<string, string>
  enabled: Set<string>
  onToggle: (metric: string) => void
  onGroupAll: (group: string) => void
  onGroupNone: (group: string) => void
}
```

Implementation details:
- Group indicators by `tab_group` (ungrouped go under "Other")
- Maintain a `page` state (starts at 0)
- Compute `labelsPerPage` based on available height: use a fixed estimate of ~50 labels per page (25 rows × 2 columns)
- Flatten all grouped labels into a single ordered list, then paginate
- Each label is a clickable `<button>`:
  - If enabled: `bg-[#1e293b] border border-{color} text-slate-200`
  - If disabled: `bg-transparent border-transparent text-slate-500`
  - Contains a color dot (8×8px rounded square) and truncated metric display_name
- Group headers: uppercase text-slate-400 with "All" / "None" buttons on the right
- Pagination footer: `◀ {page}/{totalPages} ▶` centered at bottom
- Toggle state is global (managed by parent) — pagination only controls which labels are visible, not which are enabled

- [ ] **Step 2: Commit**

```
git add ui/src/components/charts/MetricLabelPanel.tsx
git commit -m "feat(ui): add MetricLabelPanel with grouped labels and pagination"
```

---

### Task 9: Create MultiSeriesChart

**Files:**
- Create: `ui/src/components/charts/MultiSeriesChart.tsx`

- [ ] **Step 1: Implement MultiSeriesChart**

Props (from spec):
```ts
interface MultiSeriesChartProps {
  series: Array<{
    metric: string
    displayName: string
    color: string
    data: Array<{ timestamp: string; value: number }>
  }>
  yAxisLabel?: string
  yAxisMax?: number
  height?: number
}
```

Implementation details:
- Calls `useTheme()` for `CHART_THEME[theme]` (axis colors, grid, tooltip bg)
- X axis: union of all timestamps from all series, sorted. Format with `fmtSlot`.
- One ECharts line series per entry in `series` prop:
  - `name: displayName`, `type: 'line'`
  - `lineStyle: { color: series.color, width: 1.5 }`
  - `itemStyle: { color: series.color }`
  - `symbol: 'circle'`, `symbolSize: 4`
- Y axis: `type: 'value'`, `max: yAxisMax` if provided (for scores chart = 100).
  If `yAxisLabel` is provided, render it as the Y axis `name` (e.g. "Score" or "Value")
- Missing data: when series have different timestamps, use `connectNulls: false` and
  map missing timestamps to `null` values so ECharts leaves gaps rather than interpolating
- Tooltip: `trigger: 'axis'`. Custom formatter that lists all series values at the
  hovered X position. Each row: colored dot + metric name + value. If more than 10
  rows, add `max-height: 300px; overflow-y: auto` to the tooltip container via
  `extraCssText`.
- `grid: { top: 16, bottom: 52, left: 56, right: 16 }`
- `animation: false`

- [ ] **Step 2: Commit**

```
git add ui/src/components/charts/MultiSeriesChart.tsx
git commit -m "feat(ui): add MultiSeriesChart for multi-series line rendering"
```

---

## Chunk 4: TrendPoint extension + MetricExplorerPage redesign

### Task 10: Extend TrendPoint with score field

**Files:**
- Modify: `ui/src/features/evaluations/types.ts:81-87`
- Modify: `ui/src/mocks/generate.ts:525-527`

- [ ] **Step 1: Add score to TrendPoint type**

In `ui/src/features/evaluations/types.ts`, add `score` field:

```ts
export interface TrendPoint {
  timestamp: string
  value: number
  score: number                // per-indicator score for this data point
  eval_id: string
  result: 'pass' | 'warning' | 'fail'
  baseline?: number | null
}
```

- [ ] **Step 2: Update mock to include score**

In `ui/src/mocks/generate.ts`, find `generateTrendData` around line 525-527 where it returns:

```ts
return { timestamp: ev.period_start, value, eval_id: ev.id, result: status, baseline }
```

Change to include the score from `scoreIndicator`:

```ts
const { status, score } = scoreIndicator(metric, value, baseline)
return { timestamp: ev.period_start, value, score, eval_id: ev.id, result: status, baseline }
```

Note: the current code on line 525 is `const { status } = scoreIndicator(...)` — just destructure `score` as well.

- [ ] **Step 3: Verify existing trend charts still work**

Open `http://localhost:5173/navigator?asset=win-toolset-01`, verify MetricTrendBlock charts still render (the new field is additive, nothing should break).

- [ ] **Step 4: Commit**

```
git add ui/src/features/evaluations/types.ts
git add ui/src/mocks/generate.ts
git commit -m "feat(ui): add score field to TrendPoint type and mock data"
```

---

### Task 11: Rewrite MetricExplorerPage

**Files:**
- Modify: `ui/src/pages/MetricExplorerPage.tsx`

**Reference files to read before implementing (created in earlier tasks):**
- `ui/src/components/charts/MetricLabelPanel.tsx` — label toggle panel (Task 8)
- `ui/src/components/charts/MultiSeriesChart.tsx` — chart component (Task 9)
- `ui/src/components/charts/colors.ts` — color generation (Task 7)

**Existing files to reference:**
- `ui/src/features/evaluations/hooks.ts:41-48` — useTrend hook, fetchTrend, evaluationKeys
- `ui/src/features/navigator/hooks.ts` — useMetricHeatmap
- `ui/src/features/evaluations/api.ts` — fetchTrend function

- [ ] **Step 1: Rewrite MetricExplorerPage**

The page manages:

```ts
const [valuesEnabled, setValuesEnabled] = useState<Set<string>>(new Set())
const [scoresEnabled, setScoresEnabled] = useState<Set<string>>(new Set())
```

Layout structure (full-screen):
```tsx
<div className="flex flex-col" style={{ height: 'calc(100vh - 49px)' }}>
  {/* Header bar: Back link + title */}
  <div className="px-6 py-3 border-b border-slate-700 flex items-center gap-3 shrink-0">
    <Link to={backHref} className="text-sm text-slate-400 hover:text-slate-200">← Back</Link>
    <h1 className="text-lg font-semibold text-slate-100">Metric Explorer</h1>
    {(groupName || assetName) && (
      <span className="text-sm text-slate-400">— {assetName ?? groupName}</span>
    )}
  </div>

  {/* Two chart sections, each taking ~50% height */}
  <div className="flex-1 overflow-y-auto">
    {/* VALUES section */}
    <ChartSection
      title="Values"
      subtitle="Raw metric values over time"
      indicators={allIndicators}
      colors={colorMap}
      enabled={valuesEnabled}
      setEnabled={setValuesEnabled}
      evalId={latestEval?.id}
      dataKey="value"
    />

    {/* SCORES section */}
    <ChartSection
      title="Scores"
      subtitle="Per-indicator scores (0–100) over time"
      indicators={allIndicators}
      colors={colorMap}
      enabled={scoresEnabled}
      setEnabled={setScoresEnabled}
      evalId={latestEval?.id}
      dataKey="score"
      yAxisMax={100}
    />
  </div>
</div>
```

The `ChartSection` is a local component (or extracted to a separate file if it grows large) that:
1. Renders the section title + subtitle
2. Renders a flex row: `MetricLabelPanel` (width ~280px) + `MultiSeriesChart` (flex-1)
3. For each enabled metric, calls `useTrend(evalId, metric)` to get trend data
4. Maps trend data to the `series` prop format, using the `dataKey` to pick either `value` or `score` from each `TrendPoint`
5. Passes the `colorMap` and `enabled` state to the label panel

Toggle callbacks:
```ts
function handleToggle(metric: string) {
  setEnabled(prev => {
    const next = new Set(prev)
    next.has(metric) ? next.delete(metric) : next.add(metric)
    return next
  })
}

function handleGroupAll(group: string) {
  const groupMetrics = indicators.filter(i => i.tab_group === group).map(i => i.metric)
  setEnabled(prev => {
    const next = new Set(prev)
    for (const m of groupMetrics) next.add(m)
    return next
  })
}

function handleGroupNone(group: string) {
  const groupMetrics = new Set(indicators.filter(i => i.tab_group === group).map(i => i.metric))
  setEnabled(prev => {
    const next = new Set(prev)
    for (const m of groupMetrics) next.delete(m)
    return next
  })
}
```

**Indicator list source:**
- Asset view: `useMetricHeatmap(assetName)` returns metrics with `tab_group`
- Group view: extract indicator list from evaluation data (the `indicators` array on
  each `EvaluationSummary`). Do NOT import from `ui/src/mocks/generate.ts` — mock
  modules must never be imported in production page code.
- Build color map: `const colorMap = useMemo(() => buildColorMap(allIndicators), [allIndicators])`

**Trend data fetching — `useEnabledTrends` hook:**

Define this hook inside `MetricExplorerPage.tsx` (it is page-specific, not reusable).
Uses `useQueries` from `@tanstack/react-query` to handle a dynamic number of queries
(one per enabled metric). This diverges from the spec's MVP approach of per-metric
`useTrend` hooks, which cannot be called conditionally in React. `useQueries` is the
idiomatic TanStack Query solution for dynamic query counts.

```ts
import { useQueries } from '@tanstack/react-query'
import { evaluationKeys, fetchTrend } from '@/features/evaluations/api'
import type { TrendPoint } from '@/features/evaluations/types'

function useEnabledTrends(
  evalId: string | undefined,
  enabledMetrics: string[],
): Map<string, TrendPoint[]> {
  const results = useQueries({
    queries: enabledMetrics.map(metric => ({
      queryKey: evaluationKeys.trend(evalId ?? '', metric),
      queryFn: () => fetchTrend(evalId!, metric),
      enabled: !!evalId,
      staleTime: Infinity,
    })),
  })

  const map = new Map<string, TrendPoint[]>()
  for (let i = 0; i < enabledMetrics.length; i++) {
    const data = results[i]?.data
    if (data) map.set(enabledMetrics[i], data)
  }
  return map
}
```

The `ChartSection` component calls `useEnabledTrends` and maps the result into
`MultiSeriesChart` series format, using `dataKey` to pick `value` or `score`.

- [ ] **Step 2: Verify the explorer page**

Open `http://localhost:5173/explorer?asset=win-toolset-01`:
- Two chart sections visible (Values + Scores)
- Label panels show grouped indicators with All/None buttons
- Click a label → series appears on the chart
- Click All on a group → all group metrics appear
- Pagination works when there are many indicators
- Tooltip shows all visible series at hovered X position

- [ ] **Step 3: Commit**

```
git add ui/src/pages/MetricExplorerPage.tsx
git commit -m "feat(ui): redesign MetricExplorerPage as full-screen dual-chart workspace

Uses useQueries for dynamic trend fetching, MetricLabelPanel for
grouped label toggles, and MultiSeriesChart for dual Values/Scores view."
```

---

### Task 12: Final integration verification

- [ ] **Step 1: Full flow verification**

Test the complete flow:
1. `http://localhost:5173/navigator` — select a group → heatmap renders with HeatmapChart
2. Toggle to Chart → GroupScoreChart stacked bars
3. Click explorer button → navigates to `/explorer?group=...` with dual charts
4. Go back → select an asset → AssetHeatmap renders with HeatmapChart
5. Toggle to Chart → AssetScoreChart line chart
6. Click explorer button → navigates to `/explorer?asset=...` with dual charts
7. In explorer: toggle labels, verify charts update, pagination works, tooltips functional

- [ ] **Step 2: Commit any fixes**

If any issues found during verification, fix and commit each fix separately.
