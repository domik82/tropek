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

export function AssetHeatmap({ data, selectedEvalId, onEvalSelect }: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]
  const ct = CHART_THEME[theme]

  const { slots, rows, cells } = useMemo(() => buildAssetHeatmapData(data), [data])

  const chartCells = useMemo(
    () => cells.map(cell => {
      const isSelected = !!selectedEvalId && cell.evalId === selectedEvalId
      return {
        ...cell,
        itemStyle: {
          color: cell.result === 'none'
            ? ct.bg
            : colours[cell.result as keyof typeof colours] ?? ct.bg,
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
      axisLabel: { rotate: 45, fontSize: 11, color: ct.axisLabel },
      axisLine: { lineStyle: { color: ct.grid } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'category' as const,
      data: rows,
      axisLabel: { fontSize: 10, color: ct.axisLabel, width: 180, overflow: 'truncate' as const },
      axisLine: { lineStyle: { color: ct.grid } },
      splitLine: { lineStyle: { color: ct.bg } },
    },
    series: [{
      type: 'custom',
      renderItem: (
        _p: unknown,
        api: {
          value: (d: number) => number
          coord: (pos: [number, number]) => [number, number]
          size: (sz: [number, number]) => [number, number]
          style: (extra?: object) => object
        },
      ) => {
        const xi = api.value(0)
        const yi = api.value(1)
        const [cx, cy] = api.coord([xi, yi])
        const [w, h] = api.size([1, 1])
        return {
          type: 'rect',
          shape: { x: cx - w / 2 + PAD, y: cy - h / 2 + PAD, width: w - PAD * 2, height: h - PAD * 2, r: 2 },
          style: api.style(),
        }
      },
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
      style={{ height: Math.max(200, rows.length * 22 + 100) }}
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
