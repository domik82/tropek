// ui/src/components/charts/HeatmapChart.tsx
//
// Shared render core for all heatmap charts in TROPEK.
//
// Accepts pre-computed rows, columns, and cells — the caller is responsible for
// building those from raw API data. This component owns only rendering concerns:
// color lookup, border highlight, tooltip formatting, ECharts option assembly,
// and the legend bar above the chart.

import ReactECharts from 'echarts-for-react'
import { useMemo, type ReactNode } from 'react'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import type { ResultColours } from '@/lib/theme'
import { fmtSlot } from '@/lib/format'
import type { HeatmapCell } from '@/features/navigator/types'

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
// Extends HeatmapCell with computed visual properties so renderItem can stay
// a pure lookup (no colour logic inside the ECharts callback).

interface RenderCell extends HeatmapCell {
  itemStyle: { color: string; borderColor: string; borderWidth: number }
  hoverColor: string
}

// ── Public props interface ────────────────────────────────────────────────────

export interface HeatmapChartProps {
  /** Ordered list of row labels (y-axis). */
  rows: string[]
  /** Ordered list of column keys — ISO timestamps or any string identifier. */
  columns: string[]
  /** Flat array of cells covering the grid (sparse grids are fine). */
  cells: HeatmapCell[]
  /**
   * Column index that should receive a white highlight border.
   * Matches `cell.value[0]` (the x-index).
   */
  selectedColumn?: number
  /** Called when the user clicks a cell. */
  onCellClick: (cell: HeatmapCell) => void
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
  formatTooltip: (cell: HeatmapCell) => string
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
}

// ── Component ─────────────────────────────────────────────────────────────────

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
}: HeatmapChartProps) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]
  const ct = CHART_THEME[theme]

  // Dynamic padding: tighter when many columns to avoid crushed cells
  const pad = columns.length > 40 ? 1 : 2

  // Map each incoming HeatmapCell to a RenderCell with visual properties baked in.
  // Recomputes when selection, colours, or underlying data changes.
  const renderCells: RenderCell[] = useMemo(
    () =>
      cells.map(cell => {
        const isSelected =
          selectedColumn !== undefined && cell.value[0] === selectedColumn
        const colour =
          cell.result === 'none'
            ? ct.bg
            : (colours[cell.result as keyof ResultColours] ?? ct.bg)
        return {
          ...cell,
          hoverColor: brighten(colour, 1.4),
          itemStyle: {
            color: colour,
            borderColor: isSelected ? '#ffffff' : 'transparent',
            borderWidth: isSelected ? 2 : 0,
          },
        }
      }),
    [cells, colours, ct, selectedColumn],
  )

  const option = useMemo(
    () => ({
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
        axisLabel: { rotate: 45, fontSize: 14, color: ct.axisLabel },
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
          width: 210,
          overflow: 'truncate' as const,
        },
        axisLine: { lineStyle: { color: ct.grid } },
        splitLine: { lineStyle: { color: ct.bg } },
      },
      series: [
        {
          type: 'custom',
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
            const is = cellData?.itemStyle

            const children: object[] = [
              {
                type: 'rect',
                shape: { x: rx, y: ry, width: rw, height: rh, r: 3 },
                style: {
                  fill: is?.color,
                  stroke: is?.borderColor,
                  lineWidth: is?.borderWidth ?? 0,
                },
                emphasis: {
                  style: {
                    fill: cellData?.hoverColor,
                    stroke: '#ffffff',
                    lineWidth: 2,
                  },
                },
              },
            ]

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

            return { type: 'group', children }
          },
          emphasis: { focus: 'self' },
          data: renderCells,
          encode: { x: 0, y: 1 },
        },
      ],
      grid: { top: 10, bottom: 80, left: 210, right: 20 },
    }),
    [columns, rows, renderCells, ct, pad, annotations, formatTooltip, formatColumnLabel],
  )

  const chartHeight =
    height === 'auto' ? Math.max(200, rows.length * 28 + 100) : height

  return (
    <div className="w-full" role="img" aria-label="Heatmap chart showing evaluation results by metric and time">
      {/* Instruction text above the chart */}
      {instructionText && (
        <div className="mb-1 px-1">
          <span className="text-xs text-muted-foreground">{instructionText}</span>
        </div>
      )}
      {aboveChart}
      <ReactECharts
        option={option}
        style={{ height: chartHeight }}
        opts={{ renderer: 'svg' }}
        onEvents={{
          click: (p: { data?: RenderCell }) => {
            if (p?.data) onCellClick(p.data)
          },
        }}
      />
      {/* Colour legend below the chart */}
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
    </div>
  )
}
