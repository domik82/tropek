// src/features/evaluations/components/EvaluationHeatmap.tsx
//
// Interactive heatmap grid showing evaluation results over time.
//
// Layout:
//   - X axis (columns) = time slots (one per unique evaluation start time)
//   - Y axis (rows)    = "asset · evaluation name" combinations
//   - Each cell        = colored rectangle representing pass/warning/fail/error/invalidated
//
// Rendering approach:
//   We use a single ECharts "custom" series instead of the built-in "heatmap" series.
//   The custom series calls `renderItem` once per cell, giving us full control over
//   each rectangle's color, border, and size. This lets us highlight the selected
//   column by setting a white border on those cells — no overlay series needed.
//
//   The built-in "heatmap" series requires a visualMap and doesn't support per-item
//   borders, which previously forced a two-series overlay hack that caused flickering.
//
// Data flow:
//   1. Parent passes in flat array of EvaluationSummary objects
//   2. buildHeatmapData() groups them into a grid:
//      - Extracts unique time slots (columns) and row labels
//      - When multiple evaluations land in the same cell, keeps the worst result
//        and averages the scores (rare — happens with concurrent runs)
//      - Produces one CellData per grid position with pre-computed itemStyle
//   3. ECharts renders each CellData as a rounded rectangle via renderItem
//   4. Clicking a cell calls onDateSelect to filter the table below the heatmap
//
// # To consider in future
//   Move data computation to a backend endpoint (e.g. GET /evaluations/heatmap)
//   that returns pre-bucketed cells with [xi, yi, color, score, result] tuples.
//   This would:
//   - Eliminate JS grouping/ranking on every render
//   - Allow Redis caching of the computed grid across users
//   - Keep the frontend as a dumb renderer (just map response into ECharts data)
//   Especially worthwhile once the grid grows to hundreds of evaluations.

import ReactECharts from 'echarts-for-react'
import { useMemo } from 'react'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import type { ResultColours } from '@/lib/theme'
import { fmtSlot, fmtDateTime } from '@/lib/format'
import type { EvaluationSummary } from '../types'

interface Props {
  evaluations: EvaluationSummary[]
  selectedDate: string | null
  onDateSelect: (date: string | null) => void
  onAssetSelect?: (assetName: string) => void
}

// Severity ranking — higher number = worse result.
// Used to pick the worst result when multiple evaluations fall in the same cell.
const RESULT_RANK: Record<string, number> = { pass: 0, warning: 1, fail: 2, error: 3, invalidated: 4 }
const SELECTED_BORDER = '#ffffff'

function brighten(hex: string, factor: number): string {
  const r = Math.min(255, Math.round(parseInt(hex.slice(1, 3), 16) * factor))
  const g = Math.min(255, Math.round(parseInt(hex.slice(3, 5), 16) * factor))
  const b = Math.min(255, Math.round(parseInt(hex.slice(5, 7), 16) * factor))
  return `rgb(${r},${g},${b})`
}

interface CellData {
  value: [number, number]
  result: string
  score: number
  slot: string
  row: string
  hasNote: boolean
  noteContent: string
  itemStyle: { color: string; borderColor: string; borderWidth: number }
  hoverColor: string
}

/**
 * Transform a flat list of evaluations into a grid of CellData objects.
 *
 * Steps:
 *   1. Extract unique time slots (columns) and row labels, sort both
 *   2. Group evaluations by (row, slot) — if duplicates exist in the same cell,
 *      keep the worst result and running-average the score
 *   3. For every (column, row) position, emit a CellData with:
 *      - Color from colours (or emptyColour if no evaluation exists there)
 *      - White border if this column is currently selected, transparent otherwise
 */
function buildHeatmapData(
  evals: EvaluationSummary[],
  selectedDate: string | null,
  colours: ResultColours,
  emptyColour: string,
) {
  // Step 1: build sorted axes
  const slots = Array.from(new Set(evals.map(e => e.period_start))).sort()
  const rows = Array.from(
    new Set(evals.map(e => `${e.asset_snapshot.name} · ${e.name}`))
  ).sort()

  // Step 2: group evaluations into cells, merging duplicates
  const cellMap = new Map<string, { result: string; score: number; count: number; hasNote: boolean; noteContent: string }>()

  for (const e of evals) {
    const rowKey = `${e.asset_snapshot.name} · ${e.name}`
    const colKey = e.period_start
    const key = `${rowKey}::${colKey}`
    const existing = cellMap.get(key)
    const effectiveResult = e.invalidated ? 'invalidated' : e.result
    const hasNote = (e.annotation_count ?? 0) > 0
    const note = e.latest_annotation?.content ?? ''
    if (!existing) {
      cellMap.set(key, { result: effectiveResult, score: e.score, count: 1, hasNote, noteContent: note })
    } else {
      const rank = (r: string) => RESULT_RANK[r] ?? 0
      cellMap.set(key, {
        result: rank(effectiveResult) > rank(existing.result) ? effectiveResult : existing.result,
        score: (existing.score * existing.count + e.score) / (existing.count + 1),
        count: existing.count + 1,
        hasNote: existing.hasNote || hasNote,
        noteContent: existing.noteContent || note,
      })
    }
  }

  // Step 3: produce one CellData per grid position
  const selectedIndex = selectedDate ? slots.indexOf(selectedDate) : -1
  // Padding between cells — tighter when there are many columns
  const pad = slots.length > 40 ? 1 : 2

  const data: CellData[] = []
  for (let xi = 0; xi < slots.length; xi++) {
    const isSelected = xi === selectedIndex
    for (let yi = 0; yi < rows.length; yi++) {
      const key = `${rows[yi]}::${slots[xi]}`
      const cell = cellMap.get(key)
      const colour = cell
        ? colours[cell.result as keyof ResultColours] ?? emptyColour
        : emptyColour
      data.push({
        value: [xi, yi],
        result: cell?.result ?? 'none',
        score: cell ? Math.round(cell.score) : 0,
        slot: slots[xi],
        row: rows[yi],
        hasNote: cell?.hasNote ?? false,
        noteContent: cell?.noteContent ?? '',
        hoverColor: colour.startsWith('#') ? brighten(colour, 1.4) : colour,
        itemStyle: {
          color: colour,
          borderColor: isSelected ? SELECTED_BORDER : 'transparent',
          borderWidth: isSelected ? 2 : 0,
        },
      })
    }
  }
  return { slots, rows, data, pad }
}

export function EvaluationHeatmap({ evaluations, selectedDate, onDateSelect, onAssetSelect }: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]
  const ct = CHART_THEME[theme]
  const emptyColour = ct.bg

  // Recompute grid whenever evaluations change or a different column is selected.
  // Selection lives in the data (per-cell border style) so it must be a dependency.
  const { slots, rows, data, pad } = useMemo(
    () => buildHeatmapData(evaluations, selectedDate, colours, emptyColour),
    [evaluations, selectedDate, colours, emptyColour],
  )

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: ct.bg,
      borderColor: ct.border,
      textStyle: { color: ct.axisLabel, fontSize: 16 },
      extraCssText: 'max-width:320px;white-space:normal;word-wrap:break-word;',
      formatter: (p: { data: CellData }) => {
        const d = p.data
        if (d.result === 'none') return `${d.row}<br/>${fmtDateTime(d.slot)}<br/><em>no data</em>`
        const rc = colours[d.result as keyof ResultColours] ?? '#ccc'
        const lines = [
          `<b>${d.row}</b>`,
          fmtDateTime(d.slot),
          `Score: <b style="color:${rc}">${d.score}%</b> · <b style="color:${rc}">${d.result.toUpperCase()}</b>`,
        ]
        if (d.hasNote && d.noteContent) {
          const escaped = d.noteContent.replace(/</g, '&lt;').replace(/>/g, '&gt;')
          lines.push(`<em style="color:#fbbf24">Note: ${escaped}</em>`)
        }
        return lines.join('<br/>')
      },
    },
    xAxis: {
      type: 'category' as const,
      data: slots.map(fmtSlot),
      axisLabel: { rotate: 45, fontSize: 14, color: ct.axisLabel },
      axisLine: { lineStyle: { color: ct.grid } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'category' as const,
      data: rows,
      axisLabel: { fontSize: 14, color: ct.axisLabel, width: 210, overflow: 'truncate' as const },
      axisLine: { lineStyle: { color: ct.grid } },
      splitLine: { lineStyle: { color: ct.bg } },
    },
    series: [
      {
        type: 'custom',
        // renderItem is called once per data point. ECharts provides api helpers:
        //   api.value(dim) — read the data value at dimension `dim`
        //   api.coord([x, y]) — convert data coords to pixel coords (center of cell)
        //   api.size([1, 1]) — pixel dimensions of one grid cell
        //   api.style() — returns the itemStyle object we set on each CellData
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

          const cellData = data[params.dataIndex]
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
          if (cellData?.hasNote) {
            const s = Math.min(6, rw / 3, rh / 3)
            children.push({
              type: 'polygon',
              shape: {
                points: [
                  [rx + rw - s, ry],
                  [rx + rw, ry],
                  [rx + rw, ry + s],
                ],
              },
              style: { fill: '#ffffff' },
            })
          }
          return { type: 'group', children }
        },
        emphasis: { focus: 'self' },
        data,
        encode: { x: 0, y: 1 },
      },
    ],
    grid: { top: 10, bottom: 80, left: 200, right: 20 },
  }

  return (
    <div className="w-full">
      {/* Instruction text + color legend above the chart */}
      <div className="flex items-center justify-between mb-1 px-1">
        <span className="text-xs text-gray-400">Click any cell to filter the table below.</span>
        <div className="flex items-center gap-3 text-xs text-gray-400">
          {(['pass', 'warning', 'fail', 'error', 'invalidated'] as const).map(r => (
            <span key={r} className="flex items-center gap-1">
              <span
                className="inline-block w-3 h-3 rounded-sm"
                style={{ backgroundColor: colours[r] }}
              />
              {r}
            </span>
          ))}
        </div>
      </div>
      <ReactECharts
        option={option}
        style={{ height: Math.max(200, rows.length * 28 + 100) }}
        opts={{ renderer: 'svg' }}
        onEvents={{
          click: (p: { data?: CellData }) => {
            if (!p?.data?.slot) return
            if (selectedDate !== p.data.slot) {
              onDateSelect(p.data.slot)
            } else if (onAssetSelect) {
              const assetName = p.data.row.split(' · ')[0]
              if (assetName.trim()) onAssetSelect(assetName)
            } else {
              onDateSelect(null)
            }
          },
        }}
      />
    </div>
  )
}
