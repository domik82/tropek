import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { buildChartOption, isRelativeCriteria, useMetricTrendState } from './useMetricTrendState'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import type { TrendPoint, IndicatorResult } from '../types'

// ── Helpers ───────────────────────────────────────────────────────────────────

const colours = RESULT_COLOUR.current
const ct = CHART_THEME.current

function baseInput(overrides: Record<string, unknown> = {}) {
  return {
    trend: [] as TrendPoint[],
    evalId: 'eval-1',
    colours,
    ct,
    fontSize: 14,
    yMin: '',
    yMax: '',
    showPass: false,
    showWarn: false,
    passTarget: null,
    warnTarget: null,
    passCriteria: null,
    warnCriteria: null,
    ...overrides,
  }
}

function makeTrendPoint(overrides: Partial<TrendPoint> = {}): TrendPoint {
  return {
    timestamp: '2026-03-15T10:30:00Z',
    value: 100,
    score: 1,
    eval_id: 'eval-1',
    result: 'pass',
    ...overrides,
  }
}

function makeIndicator(overrides: Partial<IndicatorResult> = {}): IndicatorResult {
  return {
    metric: 'response_time',
    display_name: 'Response Time',
    value: 100,
    compared_value: null,
    change_absolute: null,
    change_relative_pct: null,
    aggregation: 'avg',
    status: 'pass',
    score: 1,
    weight: 1,
    key_sli: false,
    pass_targets: null,
    warning_targets: null,
    ...overrides,
  }
}

// ── isRelativeCriteria ────────────────────────────────────────────────────────

describe('isRelativeCriteria', () => {
  it('returns true for <=+N% format', () => {
    expect(isRelativeCriteria('<=+10%')).toBe(true)
    expect(isRelativeCriteria('<=+0.5%')).toBe(true)
  })

  it('returns false for fixed thresholds', () => {
    expect(isRelativeCriteria('<600')).toBe(false)
    expect(isRelativeCriteria('<=100')).toBe(false)
  })

  it('returns false for null/undefined', () => {
    expect(isRelativeCriteria(null)).toBe(false)
    expect(isRelativeCriteria(undefined)).toBe(false)
  })
})

// ── buildChartOption ──────────────────────────────────────────────────────────

describe('buildChartOption', () => {
  it('creates series for metric values', () => {
    const trend = [
      makeTrendPoint({ value: 100, result: 'pass' }),
      makeTrendPoint({ value: 200, result: 'warning', timestamp: '2026-03-16T10:30:00Z' }),
    ]
    const option = buildChartOption(baseInput({ trend })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series).toHaveLength(1)
    const data = series[0].data as Array<{ value: number }>
    expect(data).toHaveLength(2)
    expect(data[0].value).toBe(100)
    expect(data[1].value).toBe(200)
  })

  it('adds pass threshold markLine when showPass is true and target exists', () => {
    const passTarget = { criteria: '<600', target_value: 600, violated: false }
    const option = buildChartOption(baseInput({
      showPass: true,
      passTarget,
      passCriteria: '<600',
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    const mainSeries = series[0]
    const markLine = mainSeries.markLine as { data: Array<{ yAxis: number }> }
    expect(markLine).toBeDefined()
    expect(markLine.data).toHaveLength(1)
    expect(markLine.data[0].yAxis).toBe(600)
  })

  it('adds warning threshold markLine when showWarn is true and target exists', () => {
    const warnTarget = { criteria: '<800', target_value: 800, violated: false }
    const option = buildChartOption(baseInput({
      showWarn: true,
      warnTarget,
      warnCriteria: '<800',
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    const mainSeries = series[0]
    const markLine = mainSeries.markLine as { data: Array<{ yAxis: number }> }
    expect(markLine).toBeDefined()
    expect(markLine.data).toHaveLength(1)
    expect(markLine.data[0].yAxis).toBe(800)
  })

  it('does not add markLine when showPass is false', () => {
    const passTarget = { criteria: '<600', target_value: 600, violated: false }
    const option = buildChartOption(baseInput({
      showPass: false,
      passTarget,
      passCriteria: '<600',
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series[0].markLine).toBeUndefined()
  })

  it('sets yAxis min/max from state', () => {
    const option = buildChartOption(baseInput({ yMin: '10', yMax: '500' })) as Record<string, unknown>
    const yAxis = option.yAxis as { min: number; max: number }
    expect(yAxis.min).toBe(10)
    expect(yAxis.max).toBe(500)
  })

  it('leaves yAxis min/max undefined when empty', () => {
    const option = buildChartOption(baseInput()) as Record<string, unknown>
    const yAxis = option.yAxis as { min: unknown; max: unknown }
    expect(yAxis.min).toBeUndefined()
    expect(yAxis.max).toBeUndefined()
  })

  it('handles empty data points', () => {
    const option = buildChartOption(baseInput({ trend: [] })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series[0].data).toEqual([])
  })

  it('highlights current evaluation point with white border', () => {
    const trend = [
      makeTrendPoint({ eval_id: 'eval-1' }),
      makeTrendPoint({ eval_id: 'eval-2' }),
    ]
    const option = buildChartOption(baseInput({ trend, evalId: 'eval-1' })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    const data = series[0].data as Array<{ itemStyle: { borderColor: string } }>
    expect(data[0].itemStyle.borderColor).toBe('#ffffff')
    expect(data[1].itemStyle.borderColor).toBe('transparent')
  })

  it('adds relative threshold series for pass when criteria is relative', () => {
    const trend = [
      makeTrendPoint({ value: 100, baseline: 90 }),
      makeTrendPoint({ value: 110, baseline: 100 }),
    ]
    const option = buildChartOption(baseInput({
      trend,
      showPass: true,
      passTarget: { criteria: '<=+10%', target_value: 99, violated: false },
      passCriteria: '<=+10%',
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    // Main series + relative threshold series
    expect(series.length).toBeGreaterThanOrEqual(2)
  })

  it('sets cursor to pointer when onEvalSelect is provided', () => {
    const option = buildChartOption(baseInput({ onEvalSelect: () => {} })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series[0].cursor).toBe('pointer')
  })

  it('sets cursor to default when no onEvalSelect', () => {
    const option = buildChartOption(baseInput()) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series[0].cursor).toBe('default')
  })
})

// ── useMetricTrendState ───────────────────────────────────────────────────────

vi.mock('@/lib/theme-context', () => ({
  useTheme: () => ({ theme: 'current' as const, fontSize: 14 }),
}))

describe('useMetricTrendState', () => {
  it('initializes with empty yMin/yMax', () => {
    const { result } = renderHook(() =>
      useMetricTrendState([], 'eval-1', makeIndicator()),
    )
    expect(result.current.yMin).toBe('')
    expect(result.current.yMax).toBe('')
  })

  it('initializes with showPass and showWarn true', () => {
    const { result } = renderHook(() =>
      useMetricTrendState([], 'eval-1', makeIndicator()),
    )
    expect(result.current.showPass).toBe(true)
    expect(result.current.showWarn).toBe(true)
  })

  it('togglePass flips showPass state', () => {
    const { result } = renderHook(() =>
      useMetricTrendState([], 'eval-1', makeIndicator()),
    )
    expect(result.current.showPass).toBe(true)
    act(() => result.current.togglePass())
    expect(result.current.showPass).toBe(false)
    act(() => result.current.togglePass())
    expect(result.current.showPass).toBe(true)
  })

  it('toggleWarn flips showWarn state', () => {
    const { result } = renderHook(() =>
      useMetricTrendState([], 'eval-1', makeIndicator()),
    )
    expect(result.current.showWarn).toBe(true)
    act(() => result.current.toggleWarn())
    expect(result.current.showWarn).toBe(false)
  })

  it('exposes passTarget and warnTarget from indicator', () => {
    const passTargets = [{ criteria: '<600', target_value: 600, violated: false }]
    const warnTargets = [{ criteria: '<800', target_value: 800, violated: false }]
    const { result } = renderHook(() =>
      useMetricTrendState([], 'eval-1', makeIndicator({
        pass_targets: passTargets,
        warning_targets: warnTargets,
      })),
    )
    expect(result.current.passTarget).toEqual(passTargets[0])
    expect(result.current.warnTarget).toEqual(warnTargets[0])
  })

  it('returns chartOption object', () => {
    const { result } = renderHook(() =>
      useMetricTrendState([], 'eval-1', makeIndicator()),
    )
    expect(result.current.chartOption).toBeDefined()
    expect(typeof result.current.chartOption).toBe('object')
  })
})
