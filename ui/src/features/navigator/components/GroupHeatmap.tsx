// ui/src/features/navigator/components/GroupHeatmap.tsx
import ReactECharts from 'echarts-for-react'
import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import { fmtSlot, fmtDateTime } from '@/lib/format'
import { buildGroupHeatmapData } from '../utils'
import type { EvaluationSummary } from '@/features/evaluations/types'
import type { HeatmapCell } from '../types'

interface Props {
  evaluations: EvaluationSummary[]
  groupName: string
}

const PAD = 2

export function GroupHeatmap({ evaluations, groupName }: Props) {
  const navigate = useNavigate()
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]
  const ct = CHART_THEME[theme]

  const { slots, rows, cells } = useMemo(
    () => buildGroupHeatmapData(evaluations),
    [evaluations],
  )

  const chartCells = cells.map(cell => ({
    ...cell,
    itemStyle: {
      color: cell.result === 'none'
        ? ct.bg
        : colours[cell.result as keyof typeof colours] ?? ct.bg,
      borderColor: 'transparent',
      borderWidth: 0,
    },
  }))

  const option = {
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
          `Score: <b style="color:${rc}">${d.score}%</b> · <b style="color:${rc}">${d.result.toUpperCase()}</b>`,
          `<span style="color:#888;font-size:10px">Click to open evaluations</span>`,
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
      axisLabel: { fontSize: 11, color: ct.axisLabel, width: 180, overflow: 'truncate' as const },
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
          shape: { x: cx - w / 2 + PAD, y: cy - h / 2 + PAD, width: w - PAD * 2, height: h - PAD * 2, r: 3 },
          style: api.style(),
        }
      },
      data: chartCells,
      encode: { x: 0, y: 1 },
    }],
    grid: { top: 10, bottom: 80, left: 190, right: 20 },
  }

  return (
    <ReactECharts
      option={option}
      style={{ height: Math.max(200, rows.length * 28 + 100) }}
      opts={{ renderer: 'svg' }}
      onEvents={{
        click: (p: { data: HeatmapCell }) => {
          if (!p?.data?.slot) return
          const slotEnd = new Date(new Date(p.data.slot).getTime() + 1000).toISOString().slice(0, 19) + 'Z'
          navigate(`/evaluations?group_name=${encodeURIComponent(groupName)}&from=${p.data.slot}&to=${slotEnd}`)
        },
      }}
    />
  )
}
