// ui/src/features/navigator/components/AssetHeatmap.tsx
import ReactECharts from 'echarts-for-react'
import { useMemo } from 'react'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import { fmtSlot, fmtDateTime } from '@/lib/format'
import { buildAssetHeatmapData } from '../utils'
import type { MetricHeatmapResponse, HeatmapCell } from '../types'

interface Props {
  data: MetricHeatmapResponse
  selectedEvalId?: string
  onEvalSelect?: (evalId: string) => void
}

const PAD = 2

function brighten(hex: string, factor: number): string {
  if (!hex.startsWith('#')) return hex
  const r = Math.min(255, Math.round(parseInt(hex.slice(1, 3), 16) * factor))
  const g = Math.min(255, Math.round(parseInt(hex.slice(3, 5), 16) * factor))
  const b = Math.min(255, Math.round(parseInt(hex.slice(5, 7), 16) * factor))
  return `rgb(${r},${g},${b})`
}

export function AssetHeatmap({ data, selectedEvalId, onEvalSelect }: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]
  const ct = CHART_THEME[theme]

  const { slots, rows, cells } = useMemo(() => buildAssetHeatmapData(data), [data])

  const chartCells = useMemo(
    () => cells.map(cell => {
      const isSelected = !!selectedEvalId && cell.evalId === selectedEvalId
      const colour = cell.result === 'none'
        ? ct.bg
        : colours[cell.result as keyof typeof colours] ?? ct.bg
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
    [cells, colours, ct, selectedEvalId],
  )

  const option = useMemo(() => ({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: ct.bg,
      borderColor: ct.border,
      textStyle: { color: ct.axisLabel },
      formatter: (p: { data: HeatmapCell }) => {
        const d = p.data
        if (d.result === 'none') return `${d.rowLabel}<br/>${fmtDateTime(d.slot)}<br/><em>no data</em>`
        const rc = colours[d.result as keyof typeof colours] ?? '#ccc'
        return [
          `<b>${d.rowLabel}</b>`,
          fmtDateTime(d.slot),
          `Score: <b style="color:${rc}">${d.score}</b> · <b style="color:${rc}">${d.result.toUpperCase()}</b>`,
          d.evalId ? `<span style="color:#888;font-size:10px">Click to select this evaluation</span>` : '',
        ].join('<br/>')
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
    series: [{
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
        const rx = cx - w / 2 + PAD
        const ry = cy - h / 2 + PAD
        const rw = w - PAD * 2
        const rh = h - PAD * 2

        const cellData = chartCells[params.dataIndex]
        const is = cellData?.itemStyle
        return {
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
        }
      },
      emphasis: { focus: 'self' },
      data: chartCells,
      encode: { x: 0, y: 1 },
    }],
    grid: { top: 10, bottom: 80, left: 190, right: 20 },
  }), [slots, rows, chartCells, ct, colours])

  return (
    <>
    <div className="flex items-center justify-between mb-1 px-1">
      <span className="text-xs text-gray-400">Click a cell to select that evaluation.</span>
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
        click: (p: { data: HeatmapCell }) => {
          if (p?.data?.evalId && onEvalSelect) {
            onEvalSelect(p.data.evalId)
          }
        },
      }}
    />
    </>
  )
}
