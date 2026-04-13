// ui/src/features/navigator/components/AssetScoreChart.tsx
import ReactECharts from 'echarts-for-react'
import { useCallback, useMemo } from 'react'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import { fmtSlot, fmtDateTime } from '@/lib/format'
import { useChartAreaClick } from '@/lib/useChartAreaClick'
import type { Evaluation, Outcome } from '@/features/evaluations'

interface Props {
  evaluations: Evaluation[]
  selectedEvalId?: string
  onEvalSelect?: (evalId: string) => void
}

export function AssetScoreChart({ evaluations, selectedEvalId, onEvalSelect }: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]
  const ct = CHART_THEME[theme]

  const sorted = useMemo(
    () => [...evaluations].sort((a, b) => a.period.from.localeCompare(b.period.from)),
    [evaluations],
  )

  const handleClickIndex = useCallback(
    (idx: number) => {
      const e = sorted[idx]
      if (e && onEvalSelect) onEvalSelect(e.id)
    },
    [sorted, onEvalSelect],
  )

  const { chartRef, onContainerClick } = useChartAreaClick(
    onEvalSelect ? handleClickIndex : undefined,
    sorted.length,
  )

  const data = useMemo(
    () => sorted.map(e => {
      const effectiveResult: Outcome = e.invalidated ? 'invalidated' : (e.outcome ?? 'error')
      const color = colours[effectiveResult] ?? colours.error
      const isSelected = e.id === selectedEvalId
      return {
        value: e.score != null ? Math.round(e.score) : 0,
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
    () => sorted.map(e => e.period.from),
    [sorted],
  )

  const option = {
    animation: false,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: ct.bg,
      borderColor: ct.border,
      textStyle: { color: ct.axisLabel },
      formatter: (params: Array<{ dataIndex: number; data: { value: number } }>) => {
        const p = params[0]
        if (!p) return ''
        const e = sorted[p.dataIndex]
        if (!e) return ''
        const score = p.data.value
        const effectiveResult: Outcome = e.invalidated ? 'invalidated' : (e.outcome ?? 'error')
        const rc = colours[effectiveResult] ?? colours.error
        return [
          `<b>${fmtDateTime(e.period.from)}</b>`,
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
        cursor: 'pointer',
        lineStyle: { color: ct.line, width: 2 },
      },
    ],
    grid: { top: 20, bottom: 80, left: 50, right: 20 },
  }

  return (
    <div onClick={onContainerClick} style={{ cursor: onEvalSelect ? 'crosshair' : undefined }}>
      <ReactECharts
        ref={chartRef}
        option={option}
        style={{ height: 260 }}
        opts={{ renderer: 'svg' }}
        notMerge
      />
    </div>
  )
}
