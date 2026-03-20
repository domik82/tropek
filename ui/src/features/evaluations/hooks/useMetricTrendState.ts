// ui/src/features/evaluations/hooks/useMetricTrendState.ts
import { useState } from 'react'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import { computeRelativeThresholdSeries } from '@/utils/metrics'
import type { TrendPoint, IndicatorResult } from '../types'

export function isRelativeCriteria(c?: string | null): boolean {
  return !!c && c.startsWith('<=+')
}

export interface MetricTrendState {
  yMin: string
  yMax: string
  setYMin: (v: string) => void
  setYMax: (v: string) => void
  showPass: boolean
  showWarn: boolean
  togglePass: () => void
  toggleWarn: () => void
  chartOption: object
  passTarget: { criteria: string; target_value: number; violated: boolean } | null
  warnTarget: { criteria: string; target_value: number; violated: boolean } | null
  passCriteria: string | null
  warnCriteria: string | null
}

export function useMetricTrendState(
  trend: TrendPoint[] | undefined,
  evalId: string,
  indicator: IndicatorResult,
  onEvalSelect?: (evalId: string) => void,
): MetricTrendState {
  const [yMin, setYMin] = useState('')
  const [yMax, setYMax] = useState('')
  const [showPass, setShowPass] = useState(true)
  const [showWarn, setShowWarn] = useState(true)

  const { theme, fontSize } = useTheme()
  const colours = RESULT_COLOUR[theme]
  const ct = CHART_THEME[theme]

  const passTarget = indicator.pass_targets?.[0] ?? null
  const warnTarget = indicator.warning_targets?.[0] ?? null
  const passCriteria = passTarget?.criteria ?? null
  const warnCriteria = warnTarget?.criteria ?? null

  const chartOption = buildChartOption({
    trend: trend ?? [],
    evalId,
    colours,
    ct,
    fontSize,
    yMin,
    yMax,
    showPass,
    showWarn,
    passTarget,
    warnTarget,
    passCriteria,
    warnCriteria,
    onEvalSelect,
  })

  return {
    yMin,
    yMax,
    setYMin,
    setYMax,
    showPass,
    showWarn,
    togglePass: () => setShowPass(v => !v),
    toggleWarn: () => setShowWarn(v => !v),
    chartOption,
    passTarget,
    warnTarget,
    passCriteria,
    warnCriteria,
  }
}

// ── Pure chart option builder (testable without React) ─────────────────────

interface ChartOptionInput {
  trend: TrendPoint[]
  evalId: string
  colours: { pass: string; warning: string; fail: string; error: string; invalidated: string }
  ct: { bg: string; border: string; line: string; axisLabel: string; grid: string }
  fontSize: number
  yMin: string
  yMax: string
  showPass: boolean
  showWarn: boolean
  passTarget: { criteria: string; target_value: number; violated: boolean } | null
  warnTarget: { criteria: string; target_value: number; violated: boolean } | null
  passCriteria: string | null
  warnCriteria: string | null
  onEvalSelect?: (evalId: string) => void
}

export function buildChartOption(input: ChartOptionInput): object {
  const {
    trend, evalId, colours, ct, fontSize,
    yMin, yMax, showPass, showWarn,
    passTarget, warnTarget, passCriteria, warnCriteria,
    onEvalSelect,
  } = input

  const fontScale = fontSize / 14

  const times = trend.map(p => p.timestamp.slice(0, 16).replace('T', ' '))

  const chartData = trend.map(p => ({
    value: p.value,
    itemStyle: {
      color: colours[p.result as keyof typeof colours] ?? '#6b7280',
      borderColor: p.eval_id === evalId ? '#ffffff' : 'transparent',
      borderWidth: 2,
    },
  }))

  const passRel = showPass && isRelativeCriteria(passCriteria)
    ? computeRelativeThresholdSeries(trend, passCriteria!)
    : []
  const warnRel = showWarn && isRelativeCriteria(warnCriteria)
    ? computeRelativeThresholdSeries(trend, warnCriteria!)
    : []

  const markLines: object[] = []
  if (showPass && passTarget?.target_value != null && !passRel.length)
    markLines.push({
      yAxis: passTarget.target_value,
      lineStyle: { color: colours.pass, type: 'dashed', width: 1.5 },
      label: { formatter: `pass: ${passCriteria ?? passTarget.target_value}`, color: colours.pass, fontSize: Math.round(10 * fontScale) },
    })
  if (showWarn && warnTarget?.target_value != null && !warnRel.length)
    markLines.push({
      yAxis: warnTarget.target_value,
      lineStyle: { color: colours.warning, type: 'dashed', width: 1.5 },
      label: { formatter: `warn: ${warnCriteria ?? warnTarget.target_value}`, color: colours.warning, fontSize: Math.round(10 * fontScale) },
    })

  return {
    animation: false,
    backgroundColor: 'transparent',
    grid: { top: 16, bottom: 52, left: 56, right: 16 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: ct.bg,
      borderColor: ct.border,
      textStyle: { color: ct.axisLabel, fontSize: Math.round(12 * fontScale) },
    },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { color: ct.axisLabel, fontSize: Math.round(9 * fontScale), rotate: 35 },
      axisLine: { lineStyle: { color: ct.grid } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      min: yMin !== '' ? parseFloat(yMin) : undefined,
      max: yMax !== '' ? parseFloat(yMax) : undefined,
      axisLabel: { color: ct.axisLabel, fontSize: Math.round(10 * fontScale) },
      splitLine: { lineStyle: { color: ct.grid } },
    },
    series: [
      {
        type: 'line',
        data: chartData,
        cursor: onEvalSelect ? 'pointer' : 'default',
        symbol: 'circle',
        symbolSize: (_val: unknown, params: { dataIndex: number }) =>
          trend[params.dataIndex]?.eval_id === evalId ? 10 : 6,
        lineStyle: { color: ct.line, width: 1.5 },
        ...(markLines.length ? {
          markLine: {
            silent: true,
            symbol: 'none',
            data: markLines.map((ml: object) => {
              const m = ml as { yAxis: number; lineStyle: object; label: object }
              return { yAxis: m.yAxis, lineStyle: m.lineStyle, label: { ...m.label, position: 'insideStartTop' } }
            }),
          },
        } : {}),
      },
      ...(passRel.length ? [{
        type: 'line', data: passRel, symbol: 'none', silent: true,
        lineStyle: { color: colours.pass, type: 'dashed' as const, width: 1.5 },
        tooltip: { show: false },
      }] : []),
      ...(warnRel.length ? [{
        type: 'line', data: warnRel, symbol: 'none', silent: true,
        lineStyle: { color: colours.warning, type: 'dashed' as const, width: 1.5 },
        tooltip: { show: false },
      }] : []),
    ],
  }
}
