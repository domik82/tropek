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

  // Build data array with null gaps around invalidated points.
  // Each element is either a data point object or null (gap marker).
  const data = useMemo(() => {
    const result: Array<{
      value: [string, number]
      symbol?: string
      symbolSize?: number
      itemStyle?: { color: string; borderColor?: string; borderWidth?: number }
      evalId?: string
    } | { value: '-'; symbol: 'none' }> = []

    sorted.forEach((e, idx) => {
      const effectiveResult = e.invalidated ? 'invalidated' : e.result
      const color = colours[effectiveResult] ?? colours.error
      const isSelected = e.id === selectedEvalId
      const prevInvalidated = idx > 0 && sorted[idx - 1].invalidated
      const nextInvalidated = idx < sorted.length - 1 && sorted[idx + 1].invalidated

      // Insert a null gap before this invalidated point (if previous wasn't also a gap)
      if (e.invalidated && !prevInvalidated && idx > 0) {
        result.push({ value: '-', symbol: 'none' })
      }

      result.push({
        value: [e.period_start, Math.round(e.score)],
        symbol: e.invalidated ? 'diamond' : 'circle',
        symbolSize: isSelected ? 10 : 6,
        itemStyle: {
          color,
          ...(isSelected ? { borderColor: '#ffffff', borderWidth: 2 } : {}),
        },
        evalId: e.id,
      })

      // Insert a null gap after this invalidated point (if next isn't already invalidated)
      if (e.invalidated && !nextInvalidated && idx < sorted.length - 1) {
        result.push({ value: '-', symbol: 'none' })
      }
    })

    return result
  }, [sorted, selectedEvalId, colours])

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
      formatter: (params: { data: { value: [string, number]; evalId?: string } }) => {
        const d = params.data
        if (!d?.value || d.value === ('-' as unknown)) return ''
        const [ts, score] = d.value
        const evalEntry = sorted.find(e => e.period_start === ts)
        if (!evalEntry) return ''
        const effectiveResult = evalEntry.invalidated ? 'invalidated' : evalEntry.result
        const rc = colours[effectiveResult] ?? colours.error
        return [
          `<b>${fmtDateTime(ts)}</b>`,
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
        connectNulls: false,
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
