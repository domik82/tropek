// ui/src/components/charts/HeatmapChart.tsx
//
// Shared render core for all heatmap charts in TROPEK.
//
// Accepts pre-computed rows, columns, and cells — the caller is responsible for
// building those from raw API data. This component owns only rendering concerns:
// color lookup, border highlight, tooltip formatting, ECharts option assembly,
// and the legend bar above the chart.

import ReactECharts from 'echarts-for-react'
import { useMemo, useRef, useState, useCallback, useEffect, useLayoutEffect, type ReactNode } from 'react'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import type { ResultColours } from '@/lib/theme'
import { fmtSlot } from '@/lib/format'
import { NoteIndicatorRow, type SlotNote, type ColumnPosition } from './NoteIndicatorRow'
import { trackTooltip, releaseTooltip, type TooltipChart } from './tooltipWatchdog'

/** Grid padding shared between HeatmapChart and NoteIndicatorRow for alignment. */
export const HEATMAP_GRID_LEFT = 230
export const HEATMAP_GRID_RIGHT = 20
import type { HeatmapEChartsCell } from '@/features/navigator/ui-types'

// ── brighten ─────────────────────────────────────────────────────────────────
// Lightens a hex colour by multiplying each channel by `factor`.
// Handles non-hex values (rgba strings, named colours) by returning them as-is.

function brighten(hex: string, factor: number): string {
  if (!hex.startsWith('#')) return hex
  const r = Math.min(255, Math.round(parseInt(hex.slice(1, 3), 16) * factor))
  const g = Math.min(255, Math.round(parseInt(hex.slice(3, 5), 16) * factor))
  const b = Math.min(255, Math.round(parseInt(hex.slice(5, 7), 16) * factor))
  return `rgb(${r},${g},${b})`
}

// ── Internal render-ready cell ────────────────────────────────────────────────
// Extends HeatmapEChartsCell with computed visual properties so renderItem can stay
// a pure lookup (no colour logic inside the ECharts callback).
//
// Selection border (stroke / lineWidth) is intentionally NOT baked in here —
// it is computed per-render inside renderItem from the live `selectedColumn`
// prop. Keeping selection out of RenderCell means clicking a cell to change
// selection does not invalidate the renderCells memo, which would otherwise
// remap every cell on every click and make interaction laggy on large grids.

interface RenderCell extends HeatmapEChartsCell {
  itemStyle: { color: string }
  hoverColor: string
}

// ── Public props interface ────────────────────────────────────────────────────

export interface HeatmapChartProps {
  /** Ordered list of row labels (y-axis). */
  rows: string[]
  /** Ordered list of column keys — ISO timestamps or any string identifier. */
  columns: string[]
  /** Flat array of cells covering the grid (sparse grids are fine). */
  cells: HeatmapEChartsCell[]
  /**
   * Column index that should receive a white highlight border.
   * Matches `cell.value[0]` (the x-index).
   */
  selectedColumn?: number
  /** Called when the user clicks a cell. */
  onCellClick: (cell: HeatmapEChartsCell) => void
  /**
   * When true, cells with `hasNote === true` render a small amber square
   * in their top-right corner (annotation indicator).
   */
  annotations?: boolean
  /**
   * Chart height in pixels, or `'auto'` to compute from row count.
   * Auto formula: `Math.max(200, rows.length * 28 + 100)`.
   */
  height?: number | 'auto'
  /** Returns the HTML string shown inside the ECharts tooltip for a given cell. */
  formatTooltip: (cell: HeatmapEChartsCell) => string
  /**
   * Formats each column key into the x-axis label.
   * Defaults to `fmtSlot` (renders ISO timestamps as "MM-DD HH:MM").
   */
  formatColumnLabel?: (slot: string) => string
  /**
   * Short instruction shown in the top-left above the chart.
   * Omit or pass empty string to suppress.
   */
  instructionText?: string
  /** Content rendered between the legend bar and the chart canvas. */
  aboveChart?: ReactNode
  /**
   * Set of row indices that should render with blue bold text (SLO group headers).
   */
  headerRowIndices?: Set<number>
  /** Map of column key → note info for columns that have notes. Renders indicators above the chart grid. */
  notedColumns?: Map<string, SlotNote>
  /** Called when user clicks a note indicator */
  onNoteIndicatorClick?: (slot: string) => void
  /**
   * When false, hides x-axis labels/ticks.
   * Defaults to true.
   */
  showXAxis?: boolean
  /**
   * When false, hides the colour legend below the chart.
   * Defaults to true. Set to false when the legend is rendered once outside.
   */
  showLegend?: boolean
  /**
   * Eliminates grid padding (top/bottom → 0) and uses tight height calculation.
   * Used by stacked mini-heatmaps so cells abut seamlessly.
   */
  compact?: boolean
}

// ── Component ─────────────────────────────────────────────────────────────────

const EMPTY_HEADER_INDICES = new Set<number>()

export function HeatmapChart({
  rows,
  columns,
  cells,
  selectedColumn,
  onCellClick,
  annotations = false,
  height = 'auto',
  formatTooltip,
  formatColumnLabel = fmtSlot,
  instructionText,
  aboveChart,
  headerRowIndices = EMPTY_HEADER_INDICES,
  notedColumns,
  onNoteIndicatorClick,
  showXAxis = true,
  showLegend = true,
  compact = false,
}: HeatmapChartProps) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]
  const ct = CHART_THEME[theme]
  const chartRef = useRef<ReactECharts>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const trackedChartRef = useRef<TooltipChart | null>(null)
  const [columnPositions, setColumnPositions] = useState<ColumnPosition[]>([])
  const [containerReady, setContainerReady] = useState(false)

  // Defer chart mount until the container has non-zero dimensions.
  // Prevents ECharts "Can't get DOM width or height" and visible flicker.
  useLayoutEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0) {
        setContainerReady(true)
        ro.disconnect()
      }
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Dynamic padding: tighter when many columns to avoid crushed cells
  const pad = columns.length > 40 ? 1 : 2

  // Compute column pixel positions from the ECharts grid coordinate system
  const computeColumnPositions = useCallback(() => {
    const instance = chartRef.current?.getEchartsInstance()
    if (!instance || instance.isDisposed() || columns.length === 0) {
      setColumnPositions([])
      return
    }

    const positions: ColumnPosition[] = []
    const toPixel = (idx: number) =>
      (instance.convertToPixel('grid', [idx, 0]) as unknown as number[])[0]

    try {
      // Get the pixel width of one cell
      const cellSize = columns.length > 1 ? Math.abs(toPixel(1) - toPixel(0)) : 50

      for (let i = 0; i < columns.length; i++) {
        const cx = toPixel(i)
        // convertToPixel returns the center of the cell
        positions.push({ x: cx - cellSize / 2, width: cellSize })
      }
    } catch {
      // ECharts coordinate system not ready yet — will retry on next render/resize
      return
    }

    setColumnPositions(positions)
  }, [columns])

  // Recompute positions when chart finishes rendering or window resizes
  useEffect(() => {
    if (!notedColumns || notedColumns.size === 0) return

    // Compute after a short delay to let ECharts finish rendering
    const timer = setTimeout(computeColumnPositions, 100)

    const handleResize = () => {
      computeColumnPositions()
    }

    window.addEventListener('resize', handleResize)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('resize', handleResize)
    }
  }, [notedColumns, computeColumnPositions])

  // Map each incoming HeatmapEChartsCell to a RenderCell with visual properties baked in.
  // Recomputes when colours or underlying data change — but NOT when selection
  // changes. Selection border is drawn dynamically in renderItem from the live
  // `selectedColumn` prop; remapping every cell on every click would be wasted
  // work on large grids.
  const renderCells: RenderCell[] = useMemo(
    () =>
      cells.map(cell => {
        const isHeader = headerRowIndices.has(cell.value[1])
        const baseColour =
          cell.result === 'none'
            ? ct.bg
            : (colours[cell.result as keyof ResultColours] ?? ct.bg)
        const colour = isHeader ? brighten(baseColour, 0.7) : baseColour
        return {
          ...cell,
          hoverColor: brighten(colour, 1.4),
          itemStyle: { color: colour },
        }
      }),
    [cells, colours, ct, headerRowIndices],
  )

  const option = useMemo(
    () => ({
      // Disable the default initial fade-in animation. For dense heatmaps
      // (thousands of cells) the animation runs sequentially across every
      // group, adding hundreds of ms of opacity tweens on first paint.
      // See docs/perf/heatmap-chunk-c.md "Follow-ups" for the full analysis.
      animation: false,
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item' as const,
        backgroundColor: ct.bg,
        borderColor: ct.border,
        textStyle: { color: ct.axisLabel, fontSize: 16 },
        extraCssText: 'max-width:320px;white-space:normal;word-wrap:break-word;',
        formatter: (p: { data: RenderCell }) => formatTooltip(p.data),
      },
      xAxis: {
        type: 'category' as const,
        data: columns.map(formatColumnLabel),
        axisLabel: showXAxis
          ? { rotate: 45, fontSize: 14, color: ct.axisLabel }
          : { show: false },
        axisTick: showXAxis ? {} : { show: false },
        axisLine: { lineStyle: { color: ct.grid } },
        splitLine: { show: false },
      },
      // ECharts category axis renders bottom-to-top, so the last row in
      // the data array appears at the top of the chart. The backend relies
      // on this: it places the "Score" row last so it renders at the top.
      // See also: api/app/modules/quality_gate/router.py (get_metric_heatmap)
      yAxis: {
        type: 'category' as const,
        data: rows,
        axisLabel: {
          fontSize: 14,
          color: ct.axisLabel,
          width: HEATMAP_GRID_LEFT - 5,
          overflow: 'truncate' as const,
          formatter: (value: string, index: number) => {
            const maxChars = 45
            const label = value.length > maxChars
              ? value.slice(0, maxChars - 1) + '…'
              : value
            return headerRowIndices.has(index)
              ? `{sloHeader|${label}}`
              : `{normal|${label}}`
          },
          rich: {
            sloHeader: {
              color: '#58a6ff',
              fontSize: 14,
              fontWeight: 'bold',
            },
            normal: {
              color: ct.axisLabel,
              fontSize: 14,
            },
          },
        },
        axisLine: { lineStyle: { color: ct.grid } },
        splitLine: { lineStyle: { color: ct.bg } },
      },
      series: [
        {
          type: 'custom',
          // Progressive rendering: draw cells in data-array order, one chunk per
          // animation frame, so the browser stays responsive during the render
          // and the visible top-of-chart rows appear before off-screen ones.
          // The mapper emits cells in visual top-to-bottom order, so `sequential`
          // chunk mode naturally renders the viewport first. Only engages above
          // 1500 cells — below that, sync render is faster than the frame
          // scheduling overhead.
          progressive: 1000,
          progressiveThreshold: 1500,
          progressiveChunkMode: 'sequential' as const,
          renderItem: (
            params: { dataIndex: number },
            api: {
              value: (d: number) => number
              coord: (pos: [number, number]) => [number, number]
              size: (sz: [number, number]) => [number, number]
            },
          ) => {
            const xi = api.value(0)
            const yi = api.value(1)
            const [cx, cy] = api.coord([xi, yi])
            const [w, h] = api.size([1, 1])
            const rx = cx - w / 2 + pad
            const ry = cy - h / 2 + pad
            const rw = w - pad * 2
            const rh = h - pad * 2

            const cellData = renderCells[params.dataIndex]
            // Selection border is computed here (not in the renderCells memo)
            // so clicking to change selection does NOT invalidate the full
            // cell mapping — the option rebuild fires but renderCells survives.
            const isSelected = selectedColumn !== undefined && xi === selectedColumn

            const children: object[] = []

            children.push({
              type: 'rect',
              shape: { x: rx, y: ry, width: rw, height: rh, r: 3 },
              style: {
                fill: cellData?.itemStyle.color,
                stroke: isSelected ? ct.selectionRing : 'transparent',
                lineWidth: isSelected ? 2 : 0,
              },
              emphasis: {
                style: {
                  fill: cellData?.hoverColor,
                  stroke: ct.selectionRing,
                  lineWidth: 2,
                },
              },
            })

            if (annotations && cellData?.hasNote) {
              const s = Math.min(10, rw / 3, rh / 3)
              children.push({
                type: 'rect',
                shape: {
                  x: rx + rw - s,
                  y: ry,
                  width: s,
                  height: s,
                },
                style: { fill: 'var(--indicator-note)' },
              })
            }

            if (cellData?.changePoint) {
              const diamondSize = Math.min(12, rw * 0.4, rh * 0.4)
              const diamondColor =
                cellData.changePoint.direction === 'regression'
                  ? 'var(--change-point-regression)'
                  : 'var(--change-point-improvement)'
              children.push({
                type: 'polygon',
                shape: {
                  points: [
                    [cx, cy - diamondSize / 2],
                    [cx + diamondSize / 2, cy],
                    [cx, cy + diamondSize / 2],
                    [cx - diamondSize / 2, cy],
                  ],
                },
                style: {
                  fill: diamondColor,
                  stroke: ct.bg,
                  lineWidth: 1,
                },
                z2: 10,
              })
            }

            return { type: 'group', children }
          },
          emphasis: { focus: 'self' },
          data: renderCells,
          encode: { x: 0, y: 1 },
        },
      ],
      grid: {
        top: compact ? 0 : 10,
        bottom: compact ? (showXAxis ? 95 : 0) : 80,
        left: HEATMAP_GRID_LEFT,
        right: HEATMAP_GRID_RIGHT,
      },
    }),
    // `selectedColumn` is in deps so the renderItem closure picks up the new
    // value when selection changes. Cost is cheap: rebuilding the option
    // object is ~1ms even for large grids because `renderCells` is not
    // re-mapped (it doesn't depend on `selectedColumn`).
    [columns, rows, renderCells, ct, pad, annotations, formatTooltip, formatColumnLabel, headerRowIndices, selectedColumn, showXAxis, compact],
  )

  const chartHeight =
    height === 'auto'
      ? compact
        ? rows.length * 28 + (showXAxis ? 80 : 0)
        : Math.max(200, rows.length * 28 + 100)
      : height

  const hasNotes = notedColumns && notedColumns.size > 0

  const chartEvents = useMemo(() => ({
    click: (p: { data?: RenderCell }) => {
      if (p?.data) onCellClick(p.data)
    },
    finished: () => {
      if (hasNotes) computeColumnPositions()
    },
    // Register this chart's tooltip with the page-level watchdog. Boundary
    // events (pointerout/mouseout) are skipped by Chrome on fast mouse
    // movement across stacked charts, so ECharts' own hide path cannot be
    // relied on — the watchdog hides the tooltip from document-level
    // pointermove instead, and hides any other chart's tooltip immediately.
    showtip: () => {
      const instance = chartRef.current?.getEchartsInstance()
      if (instance && containerRef.current) {
        trackedChartRef.current = instance
        trackTooltip(instance, containerRef.current)
      }
    },
  }), [onCellClick, hasNotes, computeColumnPositions])

  // On unmount, stop tracking without dispatching — the chart (and its
  // tooltip DOM) is being disposed, so there is nothing left to hide.
  useEffect(() => () => {
    if (trackedChartRef.current) releaseTooltip(trackedChartRef.current)
  }, [])

  const handleMouseLeave = useCallback(() => {
    const instance = chartRef.current?.getEchartsInstance()
    if (!instance || instance.isDisposed()) return
    instance.dispatchAction({ type: 'hideTip' })
    instance.dispatchAction({ type: 'downplay' })
  }, [])

  return (
    <div className="w-full" ref={containerRef} role="img" aria-label="Heatmap chart showing evaluation results by metric and time" onMouseLeave={handleMouseLeave}>
      {/* Instruction text above the chart */}
      {instructionText && (
        <div className="mb-1 px-1">
          <span className="text-xs text-muted-foreground">{instructionText}</span>
        </div>
      )}
      {aboveChart}
      <div className="relative" style={{ minHeight: containerReady ? undefined : chartHeight }}>
        {hasNotes && columnPositions.length > 0 && (
          <NoteIndicatorRow
            columns={columns}
            notedColumns={notedColumns}
            columnPositions={columnPositions}
            onIndicatorClick={onNoteIndicatorClick}
          />
        )}
        {containerReady && (
          <ReactECharts
            ref={chartRef}
            option={option}
            style={{ height: chartHeight }}
            opts={{ renderer: 'svg' }}
            onEvents={chartEvents}
          />
        )}
      </div>
      {/* Colour legend below the chart */}
      {showLegend && (
        <div className="flex items-center justify-end gap-3 text-xs text-muted-foreground mt-1 px-1" role="legend" aria-label="Status colour legend">
          {(['pass', 'warning', 'fail', 'error', 'invalidated'] as const).map(r => (
            <span key={r} className="flex items-center gap-1" aria-label={`${r} status`}>
              <span
                className="inline-block w-3 h-3 rounded-sm"
                style={{ backgroundColor: colours[r] }}
                aria-hidden="true"
              />
              {r}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
