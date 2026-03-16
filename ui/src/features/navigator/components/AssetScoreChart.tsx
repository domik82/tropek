// ui/src/features/navigator/components/AssetScoreChart.tsx
import ReactECharts from 'echarts-for-react'
import { useMemo } from 'react'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import { fmtSlot, fmtDateTime } from '@/lib/format'
import type { EvaluationSummary } from '@/features/evaluations/types'

interface Props {
  evaluations: EvaluationSummary[]
  selectedEvalId?: string
}

export function AssetScoreChart({ evaluations, selectedEvalId }: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]
  const ct = CHART_THEME[theme]

  const sorted = useMemo(
    () => [...evaluations].sort((a, b) => a.period_start.localeCompare(b.period_start)),
    [evaluations],
  )

  // One data point per evaluation, aligned 1:1 with xAxis categories.
  // Invalidated points get a diamond symbol but are not connected to neighbors:
  // we set their value to null and render them via a separate scatter-like approach —
  // actually, to keep it simple, we just show them connected with a distinct symbol.
  const data = useMemo(
    () => sorted.map(e => {
      const effectiveResult = e.invalidated ? 'invalidated' : e.result
      const color = colours[effectiveResult] ?? colours.error
      const isSelected = e.id === selectedEvalId
      return {
        value: Math.round(e.score),
        symbol: e.invalidated ? 'diamond' : 'circle',
        symbolSize: isSelected ? 10 : 6,
        itemStyle: {
          color,
          ...(isSelected ? { borderColor: '#ffffff', borderWidth: 2 } : {}),
        },
      }
    }),
    [sorted, selectedEvalId, colours],
  )

  const xAxisData = useMemo(
    () => sorted.map(e => e.period_start),
    [sorted],
  )

  const option = {
    animation: false,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: ct.bg,
      borderColor: ct.border,
      textStyle: { color: ct.axisLabel },
      formatter: (params: { dataIndex: number; data: { value: number } }) => {
        const e = sorted[params.dataIndex]
        if (!e) return ''
        const score = params.data.value
        const effectiveResult = e.invalidated ? 'invalidated' : e.result
        const rc = colours[effectiveResult] ?? colours.error
        return [
          `<b>${fmtDateTime(e.period_start)}</b>`,
          `Score: <b style="color:${rc}">${score}%</b>`,
          `Result: <b style="color:${rc}">${effectiveResult}</b>`,
        ].join('<br/>')
      },
    },
    xAxis: {
      type: 'category' as const,
      data: xAxisData.map(fmtSlot),
      axisLabel: { rotate: 45, fontSize: 11, color: ct.axisLabel },
      axisLine: { lineStyle: { color: ct.grid } },
    },
    yAxis: {
      type: 'value' as const,
      min: 0,
      max: 100,
      axisLabel: {
        color: ct.axisLabel,
        formatter: (v: number) => `${v}%`,
      },
      splitLine: { lineStyle: { color: ct.grid } },
    },
    series: [
      {
        type: 'line' as const,
        data,
        lineStyle: { color: ct.line, width: 2 },
      },
    ],
    grid: { top: 20, bottom: 80, left: 50, right: 20 },
  }

  return (
    <ReactECharts
      option={option}
      style={{ height: 260 }}
      opts={{ renderer: 'svg' }}
      notMerge
    />
  )
}
