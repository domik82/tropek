// ui/src/features/evaluations/hooks/useMetricTrendState.ts
import { useState, useMemo } from 'react'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import type { TrendPoint, IndicatorResult, TrendTargetEntry } from '../types'

// ── Types ────────────────────────────────────────────────────────────────────

export interface TargetToggle {
  key: string
  level: 'pass' | 'warn' | 'baseline'
  criteria: string
  visible: boolean
  toggle: () => void
}

export interface ChartTarget {
  key: string
  level: 'pass' | 'warn' | 'baseline'
  criteria: string
  visible: boolean
}

export interface MetricTrendState {
  yMin: string
  yMax: string
  setYMin: (v: string) => void
  setYMax: (v: string) => void
  targets: TargetToggle[]
  chartOption: object
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Returns true if a criteria string is relative (contains % or explicit +/- sign). */
function isRelative(criteria: string): boolean {
  return /[%]/.test(criteria) || /^[<>=]+=?\s*[+-]/.test(criteria)
}

interface DiscoveredTarget {
  key: string
  level: 'pass' | 'warn'
  criteria: string
  alwaysZero: boolean
}

/**
 * Scan all trend points and collect the union of distinct {level, criteria} pairs.
 * A target is "always zero" if target_value === 0 on every point where it appears.
 */
function discoverTargets(trend: TrendPoint[]): DiscoveredTarget[] {
  const map = new Map<
    string,
    { level: 'pass' | 'warn'; criteria: string; hasNonZero: boolean }
  >()
  for (const p of trend) {
    if (!p.targets) continue
    for (const level of ['pass', 'warn'] as const) {
      const entries = p.targets[level]
      if (!entries) continue
      for (const e of entries) {
        const key = `${level}:${e.criteria}`
        const existing = map.get(key)
        if (existing) {
          if (e.target_value !== 0) existing.hasNonZero = true
        } else {
          map.set(key, {
            level,
            criteria: e.criteria,
            hasNonZero: e.target_value !== 0,
          })
        }
      }
    }
  }
  const result: DiscoveredTarget[] = []
  for (const [key, info] of map) {
    result.push({
      key,
      level: info.level,
      criteria: info.criteria,
      alwaysZero: !info.hasNonZero,
    })
  }
  // Stable order: pass first, then warn; fixed thresholds before relative within level
  result.sort((a, b) => {
    if (a.level !== b.level) return a.level === 'pass' ? -1 : 1
    const aRel = isRelative(a.criteria)
    const bRel = isRelative(b.criteria)
    if (aRel !== bRel) return aRel ? 1 : -1
    return a.criteria.localeCompare(b.criteria)
  })
  return result
}

/**
 * For a given criteria key and level, extract the target_value from a trend point.
 * Returns null if the point doesn't have that criteria.
 */
function getTargetValue(
  point: TrendPoint,
  level: 'pass' | 'warn',
  criteria: string,
): number | null {
  const entries: TrendTargetEntry[] | undefined = point.targets?.[level]
  if (!entries) return null
  const entry = entries.find(e => e.criteria === criteria)
  return entry?.target_value ?? null
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useMetricTrendState(
  trend: TrendPoint[] | undefined,
  evalId: string,
  _indicator: IndicatorResult,
  onEvalSelect?: (evalId: string) => void,
  selectedEvalIds?: ReadonlySet<string>,
  selectedPeriodStart?: string,
): MetricTrendState {
  const [yMin, setYMin] = useState('')
  const [yMax, setYMax] = useState('')
  const [visibility, setVisibility] = useState<Record<string, boolean>>({})

  const { theme, fontSize } = useTheme()
  const colours = RESULT_COLOUR[theme]
  const ct = CHART_THEME[theme]

  const trendData = useMemo(() => trend ?? [], [trend])

  const discovered = useMemo(() => discoverTargets(trendData), [trendData])

  const hasBaseline = trendData.some(p => p.baseline != null)

  const targets: TargetToggle[] = useMemo(() => {
    const result: TargetToggle[] = []

    // Criteria targets (filter out always-zero)
    for (const d of discovered) {
      if (d.alwaysZero) continue
      const visible = visibility[d.key] ?? true // default ON
      result.push({
        key: d.key,
        level: d.level,
        criteria: d.criteria,
        visible,
        toggle: () =>
          setVisibility(v => ({ ...v, [d.key]: !(v[d.key] ?? true) })),
      })
    }

    // Baseline toggle (always last)
    if (hasBaseline) {
      const visible = visibility['baseline'] ?? false // default OFF
      result.push({
        key: 'baseline',
        level: 'baseline',
        criteria: 'baseline',
        visible,
        toggle: () =>
          setVisibility(v => ({
            ...v,
            baseline: !(v['baseline'] ?? false),
          })),
      })
    }

    return result
  }, [discovered, hasBaseline, visibility])

  const chartTargets: ChartTarget[] = useMemo(
    () =>
      targets.map(t => ({
        key: t.key,
        level: t.level,
        criteria: t.criteria,
        visible: t.visible,
      })),
    [targets],
  )

  const chartOption = useMemo(
    () =>
      buildChartOption({
        trend: trendData,
        evalId,
        selectedEvalIds,
        selectedPeriodStart,
        colours,
        ct,
        fontSize,
        yMin,
        yMax,
        targets: chartTargets,
        onEvalSelect,
      }),
    [
      trendData,
      evalId,
      selectedEvalIds,
      selectedPeriodStart,
      colours,
      ct,
      fontSize,
      yMin,
      yMax,
      chartTargets,
      onEvalSelect,
    ],
  )

  return { yMin, yMax, setYMin, setYMax, targets, chartOption }
}

// ── Pure chart option builder (testable without React) ─────────────────────

interface ChartOptionInput {
  trend: TrendPoint[]
  evalId: string
  selectedEvalIds?: ReadonlySet<string>
  selectedPeriodStart?: string
  colours: {
    pass: string
    warning: string
    fail: string
    error: string
    invalidated: string
  }
  ct: {
    bg: string
    border: string
    line: string
    axisLabel: string
    grid: string
    baseline: string
  }
  fontSize: number
  yMin: string
  yMax: string
  targets: ChartTarget[]
  onEvalSelect?: (evalId: string) => void
}

export function buildChartOption(input: ChartOptionInput): object {
  const {
    trend,
    evalId,
    selectedEvalIds,
    selectedPeriodStart,
    colours,
    ct,
    fontSize,
    yMin,
    yMax,
    targets,
    onEvalSelect,
  } = input

  const fontScale = fontSize / 14

  const hasIdMatch = trend.some(
    p =>
      (!!selectedEvalIds && selectedEvalIds.has(p.eval_id)) ||
      p.eval_id === evalId,
  )

  const isSelected = (p: TrendPoint): boolean => {
    if (
      (!!selectedEvalIds && selectedEvalIds.has(p.eval_id)) ||
      p.eval_id === evalId
    )
      return true
    if (
      !hasIdMatch &&
      selectedPeriodStart &&
      p.timestamp === selectedPeriodStart
    )
      return true
    return false
  }

  const times = trend.map(p =>
    p.timestamp.slice(0, 16).replace('T', ' '),
  )

  const chartData = trend.map(p => ({
    value: p.value,
    itemStyle: {
      color:
        colours[p.result as keyof typeof colours] ?? '#6b7280',
      borderColor: isSelected(p) ? '#ffffff' : 'transparent',
      borderWidth: 2,
    },
  }))

  // ── Target line series ──────────────────────────────────────────────────
  const targetSeries: object[] = []
  for (const t of targets) {
    if (!t.visible) continue

    // Baseline series
    if (t.level === 'baseline') {
      const data = trend.map(p => p.baseline ?? null)
      targetSeries.push({
        type: 'line',
        data,
        symbol: 'none',
        silent: true,
        lineStyle: {
          color: ct.baseline,
          type: 'dotted' as const,
          width: 1,
          opacity: 0.6,
        },
        tooltip: { show: false },
      })
      continue
    }

    // Criteria target series
    const color =
      t.level === 'pass' ? colours.pass : colours.warning
    const lineType = isRelative(t.criteria)
      ? ('dashed' as const)
      : ('solid' as const)
    const level = t.level as 'pass' | 'warn'
    const data = trend.map(p =>
      getTargetValue(p, level, t.criteria),
    )

    targetSeries.push({
      type: 'line',
      data,
      symbol: 'none',
      silent: true,
      lineStyle: { color, type: lineType, width: 1.5 },
      tooltip: { show: false },
    })
  }

  return {
    animation: false,
    backgroundColor: 'transparent',
    grid: { top: 16, bottom: 52, left: 56, right: 16 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: ct.bg,
      borderColor: ct.border,
      textStyle: {
        color: ct.axisLabel,
        fontSize: Math.round(12 * fontScale),
      },
      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : [params]
        const first = arr[0] as
          | { dataIndex?: number }
          | undefined
        const idx = first?.dataIndex
        const p = idx != null ? trend[idx] : undefined
        if (!p) return ''
        const lines = [
          `<b style="color:#58a6ff">${p.evaluation_name ?? '(no evaluation_name)'}</b>`,
          `<b>${times[idx as number]}</b>`,
          `value: <b>${p.value}</b>`,
          `result: <b style="color:${colours[p.result as keyof typeof colours] ?? '#6b7280'}">${p.result.toUpperCase()}</b>`,
        ]
        return lines.join('<br/>')
      },
    },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: {
        color: ct.axisLabel,
        fontSize: Math.round(9 * fontScale),
        rotate: 35,
      },
      axisLine: { lineStyle: { color: ct.grid } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      min: yMin !== '' ? parseFloat(yMin) : undefined,
      max: yMax !== '' ? parseFloat(yMax) : undefined,
      axisLabel: {
        color: ct.axisLabel,
        fontSize: Math.round(10 * fontScale),
      },
      splitLine: { lineStyle: { color: ct.grid } },
    },
    series: [
      {
        type: 'line',
        data: chartData,
        cursor: onEvalSelect ? 'pointer' : 'default',
        symbol: 'circle',
        symbolSize: (
          _val: unknown,
          params: { dataIndex: number },
        ) => {
          const p = trend[params.dataIndex]
          return p && isSelected(p) ? 10 : 6
        },
        lineStyle: { color: ct.line, width: 1.5 },
      },
      ...targetSeries,
    ],
  }
}
