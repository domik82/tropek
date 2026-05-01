# Charts

Guide to TROPEK's chart components, data flow, and extension patterns.

## Chart Stack

All charts use [ECharts](https://echarts.apache.org/) via `echarts-for-react`. SVG renderer, animations disabled. Theme colours come from `RESULT_COLOUR[theme]` and `CHART_THEME[theme]` in `lib/theme.ts` — JS hex strings because ECharts cannot resolve CSS custom properties.

## HeatmapChart

**File:** `src/components/charts/HeatmapChart.tsx` (~450 lines)

The core shared heatmap component. Accepts pre-computed `rows`, `columns`, and `cells` arrays — owns only rendering, not data fetching.

### Key Props

| Prop | Type | Purpose |
|---|---|---|
| `rows` | `string[]` | Y-axis labels |
| `columns` | `string[]` | Column keys (ISO timestamps or identifiers) |
| `cells` | `HeatmapEChartsCell[]` | Flat array of grid cells |
| `selectedColumn` | `number?` | Highlighted column index |
| `onCellClick` | `(cell) => void` | Click handler |
| `compact` | `boolean` | Tight spacing for stacked mini-heatmaps |
| `showXAxis` / `showLegend` | `boolean` | Toggle axis/legend visibility |
| `annotations` | `boolean` | Show amber badges on cells with notes |
| `headerRowIndices` | `Set<number>` | Rows rendered as blue bold SLO group headers |

### Architecture Decisions

**Custom series via `renderItem`:** Uses ECharts `type: 'custom'` instead of the built-in heatmap series. The `renderItem` callback draws each cell as a `rect`, enabling per-cell annotation badges, selection borders, and hover effects.

**Selection border split from renderCells memo:** The `renderCells` memo pre-computes `itemStyle.color` and `hoverColor` for every cell. Selection border is computed *inside* `renderItem` from the live `selectedColumn` prop. Clicking a column triggers a cheap ECharts option rebuild (~1ms) without invalidating the memo that remaps every cell.

**Progressive rendering:** `progressive: 1000`, `progressiveThreshold: 1500`. Below 1500 cells, sync render is faster than frame scheduling. Above, cells draw in data-order chunks per animation frame.

**containerReady guard:** `ResizeObserver` + `useLayoutEffect` defers ECharts mounting until the container has non-zero dimensions. Prevents "Can't get DOM width or height" errors.

**Grid constants:** `HEATMAP_GRID_LEFT = 210`, `HEATMAP_GRID_RIGHT = 20`. Exported for alignment with `NoteIndicatorRow`.

### Data Flow

```
Caller (e.g., AssetHeatmap)
  ↓  builds rows/columns/cells from API data
HeatmapChart
  ↓  renderCells memo: cells → RenderCell[] with pre-computed colours
  ↓  ECharts custom series: renderItem reads RenderCell by dataIndex
  ↓  NoteIndicatorRow receives column pixel positions (computed via convertToPixel)
```

## Stacked Mini-Heatmaps (Navigator)

**Orchestrator:** `src/features/navigator/components/AssetHeatmap.tsx`
**Segment:** `src/features/navigator/components/SloMiniHeatmap.tsx`
**Lazy wrapper:** `src/features/navigator/components/LazyHeatmap.tsx`

The Navigator's asset-level heatmap is split into independent segments — one "overall score" row plus one segment per SLO group. Each segment is a separate `HeatmapChart` instance.

### Why Split?

Each SLO group can independently expand/collapse, changing its row count. Splitting into separate chart instances means only the toggled segment re-renders. A monolithic chart would re-compute all rows on every toggle.

### Rendering Pipeline

1. `AssetHeatmap` receives raw DTO data and expand state
2. `useMemo` calls `overallScoreToMiniView` and `sloGroupToMiniView` mappers to produce `MiniHeatmapView` objects
3. Each view renders as an independent `SloMiniHeatmap` inside a `VisibilityTrackedSegment`
4. A final axis-only `HeatmapChart` (0 rows) renders the shared x-axis below all segments
5. A single colour legend appears at the bottom

### Performance: VisibilityTrackedSegment + useDeferredValue

Each segment is wrapped in a `VisibilityTrackedSegment` that tracks viewport intersection via `IntersectionObserver`. A mutable `Set<string>` ref (not state — no re-renders) records which segments are visible.

When the user clicks a column:
- Visible segments receive the immediate `selectedColumn` — high-priority render
- Off-screen segments receive `useDeferredValue(selectedColumn)` — low-priority deferred render

This avoids layout thrashing when many expanded SLOs exist off-screen.

### Lazy Mounting

Expanded SLO segments with >3 rows are wrapped in `LazyHeatmap`, which uses `IntersectionObserver` with `rootMargin: '400px 0px'` to mount children just before they scroll into view. Observer fires once and disconnects.

### Mapper Exception

The standard TROPEK pattern maps DTOs in `queryFn` (React Query caches domain types). The Navigator deviates: mappers run in `useMemo` because `overallScoreToMiniView` and `sloGroupToMiniView` depend on `expandState`. React Query caches the raw DTO; mappers recompute when DTO or expand state changes. Documented in `mappers.ts` header comment.

## MultiSeriesChart

**File:** `src/components/charts/MultiSeriesChart.tsx`

Multi-line or stacked-bar time-series chart on a shared X axis.

### Key Props

| Prop | Type | Purpose |
|---|---|---|
| `series` | `Array<{metric, displayName, color, data}>` | Series with name, colour, data points |
| `chartType` | `'line' \| 'bar'` | Chart type |
| `stacked` | `boolean` | Stack series with area fill |
| `height` | `number \| string` | Chart height (default 300) |

### Data Alignment

Builds a sorted union of all timestamps across all series. Each series is mapped to the union, filling missing timestamps with `null`. ECharts leaves gaps via `connectNulls: false`.

## MetricTrendBlock

**File:** `src/features/evaluations/components/MetricTrendBlock.tsx`

Per-metric trend chart card used in evaluation detail and Navigator. Shows an ECharts line chart with status-coloured dots, target threshold lines, annotation markers, and Y-axis controls.

### State Management

Chart state is managed by `useMetricTrendState` hook (`src/features/evaluations/hooks/useMetricTrendState.ts`), which builds the full ECharts option via a pure function `buildChartRender()`. This function is testable without React.

### Click Interaction

Uses `useChartAreaClick` hook (`src/lib/useChartAreaClick.ts`) for click-anywhere-on-x-axis selection — converts mouse position to data index via `convertFromPixel` with bounds checking.

## Colour Generation

**File:** `src/components/charts/colors.ts`

`generateSeriesColor(index)` uses golden-angle hue distribution (`hue = (index * 137.508) % 360`) with a secondary lightness/chroma cycle (`index % 3`) in OKLCH colour space. This maximises visual separation between adjacent indices and avoids the "too many similar greens" problem.

`buildColorMap(metrics)` sorts metrics alphabetically before assigning indices, ensuring deterministic colours regardless of data arrival order.

## NoteIndicatorRow

**File:** `src/components/charts/NoteIndicatorRow.tsx`

Renders annotation icons above the heatmap grid, aligned to specific columns. Column positions are computed by `HeatmapChart` calling `convertToPixel('grid', [idx, 0])`, then passed as `ColumnPosition[]` props. Each icon lazily fetches annotation data on hover with a 150ms hide timer to prevent flicker.

## Shared Patterns

- **Theme awareness:** All chart components consume `useTheme()` and use `RESULT_COLOUR[theme]` / `CHART_THEME[theme]` for colours. No hardcoded colours for data-dependent rendering.
- **SVG renderer:** Both HeatmapChart and MultiSeriesChart use `opts={{ renderer: 'svg' }}` for print quality and DOM tooltip interaction.
- **Animation disabled:** `animation: false` on all charts to avoid performance issues with dense data.
- **Callback stability:** Heavy use of `useCallback` for event handlers passed to ECharts.

## Adding a New Chart

1. Create the component in `src/components/charts/` or `src/features/<feature>/components/`
2. Use `echarts-for-react` with `opts={{ renderer: 'svg' }}` and `animation: false`
3. Consume colours from `useTheme()` + `RESULT_COLOUR[theme]` / `CHART_THEME[theme]`
4. If the chart needs click interaction, use `useChartAreaClick`
5. Export from `src/components/charts/index.ts` if shared
