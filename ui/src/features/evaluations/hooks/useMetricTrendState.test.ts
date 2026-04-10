import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { buildChartOption, useMetricTrendState } from './useMetricTrendState'
import type { ChartTarget } from './useMetricTrendState'
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
    targets: [] as ChartTarget[],
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

  it('adds static pass target as solid line series', () => {
    const trend = [makeTrendPoint({ value: 100 })]
    const option = buildChartOption(baseInput({
      trend,
      targets: [
        { key: 'pass:<=600', level: 'pass', criteria: '<=600', visible: true },
      ],
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series).toHaveLength(2)
    expect((series[1].lineStyle as { type: string }).type).toBe('solid')
  })

  it('adds relative warn target as dashed line series', () => {
    const trend = [
      makeTrendPoint({ value: 100, targets: { warn: [{ criteria: '<=+15%', target_value: 230, violated: false }] } }),
    ]
    const option = buildChartOption(baseInput({
      trend,
      targets: [
        { key: 'warn:<=+15%', level: 'warn', criteria: '<=+15%', visible: true },
      ],
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series).toHaveLength(2)
    expect((series[1].lineStyle as { type: string }).type).toBe('dashed')
  })

  it('does not add series for hidden targets', () => {
    const trend = [makeTrendPoint({ value: 100 })]
    const option = buildChartOption(baseInput({
      trend,
      targets: [
        { key: 'pass:<=600', level: 'pass', criteria: '<=600', visible: false },
      ],
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series).toHaveLength(1)
  })

  it('adds baseline series when visible', () => {
    const trend = [
      makeTrendPoint({ value: 100, baseline: 90 }),
      makeTrendPoint({ value: 110, baseline: 100, timestamp: '2026-03-16T10:30:00Z' }),
    ]
    const option = buildChartOption(baseInput({
      trend,
      targets: [
        { key: 'baseline', level: 'baseline', criteria: 'baseline', visible: true },
      ],
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series).toHaveLength(2)
    expect((series[1].lineStyle as { type: string }).type).toBe('dotted')
    const data = series[1].data as Array<number | null>
    expect(data).toEqual([90, 100])
  })

  it('renders static and relative targets simultaneously', () => {
    const trend = [
      makeTrendPoint({
        value: 100,
        baseline: 90,
        targets: {
          pass: [
            { criteria: '<=600', target_value: 600, violated: false },
            { criteria: '<=+10%', target_value: 99, violated: false },
          ],
        },
      }),
    ]
    const option = buildChartOption(baseInput({
      trend,
      targets: [
        { key: 'pass:<=600', level: 'pass', criteria: '<=600', visible: true },
        { key: 'pass:<=+10%', level: 'pass', criteria: '<=+10%', visible: true },
      ],
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series).toHaveLength(3)
  })

  it('renders all four targets when all visible', () => {
    const trend = [
      makeTrendPoint({
        value: 100,
        baseline: 90,
        targets: {
          pass: [
            { criteria: '<=600', target_value: 600, violated: false },
            { criteria: '<=+10%', target_value: 99, violated: false },
          ],
          warn: [
            { criteria: '<=800', target_value: 800, violated: false },
            { criteria: '<=+15%', target_value: 103, violated: false },
          ],
        },
      }),
    ]
    const option = buildChartOption(baseInput({
      trend,
      targets: [
        { key: 'pass:<=600', level: 'pass', criteria: '<=600', visible: true },
        { key: 'pass:<=+10%', level: 'pass', criteria: '<=+10%', visible: true },
        { key: 'warn:<=800', level: 'warn', criteria: '<=800', visible: true },
        { key: 'warn:<=+15%', level: 'warn', criteria: '<=+15%', visible: true },
      ],
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series).toHaveLength(5)
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

  it('builds targets from trend data', () => {
    const trend: TrendPoint[] = [
      makeTrendPoint({
        targets: {
          pass: [
            { criteria: '<=600', target_value: 600, violated: false },
            { criteria: '<=+10%', target_value: 99, violated: false },
          ],
          warn: [
            { criteria: '<=+15%', target_value: 103, violated: false },
          ],
        },
      }),
    ]
    const { result } = renderHook(() =>
      useMetricTrendState(trend, 'eval-1', makeIndicator()),
    )
    // 3 criteria targets + baseline = 4 toggles
    expect(result.current.targets).toHaveLength(4)
    expect(result.current.targets[0]).toMatchObject({ key: 'pass:<=600', level: 'pass' })
    expect(result.current.targets[1]).toMatchObject({ key: 'pass:<=+10%', level: 'pass' })
    expect(result.current.targets[2]).toMatchObject({ key: 'warn:<=+15%', level: 'warn' })
    expect(result.current.targets[3]).toMatchObject({ key: 'baseline', level: 'baseline' })
  })

  it('filters out >0 targets where target_value is always 0', () => {
    const trend: TrendPoint[] = [
      makeTrendPoint({
        targets: {
          pass: [
            { criteria: '>0', target_value: 0, violated: false },
            { criteria: '<=600', target_value: 600, violated: false },
          ],
        },
      }),
    ]
    const { result } = renderHook(() =>
      useMetricTrendState(trend, 'eval-1', makeIndicator()),
    )
    // Only <=600 + baseline
    expect(result.current.targets).toHaveLength(2)
    expect(result.current.targets[0].key).toBe('pass:<=600')
    expect(result.current.targets[1].key).toBe('baseline')
  })

  it('toggling a target flips its visibility', () => {
    const trend: TrendPoint[] = [
      makeTrendPoint({
        targets: { pass: [{ criteria: '<=600', target_value: 600, violated: false }] },
      }),
    ]
    const { result } = renderHook(() =>
      useMetricTrendState(trend, 'eval-1', makeIndicator()),
    )
    expect(result.current.targets[0].visible).toBe(true)
    act(() => result.current.targets[0].toggle())
    expect(result.current.targets[0].visible).toBe(false)
    act(() => result.current.targets[0].toggle())
    expect(result.current.targets[0].visible).toBe(true)
  })

  it('baseline defaults to hidden', () => {
    const trend: TrendPoint[] = [
      makeTrendPoint({ baseline: 90, targets: {} }),
    ]
    const { result } = renderHook(() =>
      useMetricTrendState(trend, 'eval-1', makeIndicator()),
    )
    const baseline = result.current.targets.find(t => t.key === 'baseline')
    expect(baseline).toBeDefined()
    expect(baseline!.visible).toBe(false)
  })

  it('returns chartOption object', () => {
    const { result } = renderHook(() =>
      useMetricTrendState([], 'eval-1', makeIndicator()),
    )
    expect(result.current.chartOption).toBeDefined()
    expect(typeof result.current.chartOption).toBe('object')
  })
})
