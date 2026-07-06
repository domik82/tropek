import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { buildChartOption, useMetricTrendState } from './useMetricTrendState'
import type { ChartTarget } from './useMetricTrendState'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import type { TrendPoint, Indicator, Annotation } from '../domain'
import type { NoteCategory } from '@/features/note-categories'

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
    timestamp: new Date('2026-03-15T10:30:00Z'),
    value: 100,
    score: 1,
    evalId: 'eval-1',
    outcome: 'pass',
    baseline: null,
    evaluationName: null,
    targets: null,
    overridden: false,
    changePoint: null,
    ...overrides,
  }
}

function makeIndicator(overrides: Partial<Indicator> = {}): Indicator {
  return {
    metric: 'response_time',
    displayName: 'Response Time',
    tabGroup: null,
    value: 100,
    comparedValue: null,
    changeAbsolute: null,
    changeRelativePct: null,
    aggregation: 'avg',
    status: 'pass',
    score: 1,
    weight: 1,
    keySli: false,
    passTargets: [],
    warningTargets: [],
    changePoint: null,
    ...overrides,
  }
}

function makeCategory(overrides: Partial<NoteCategory> = {}): NoteCategory {
  return {
    id: 'cat-1',
    name: 'deploy',
    label: 'Deploy',
    color: 'sky',
    showOnGraph: true,
    isSystem: false,
    createdAt: new Date('2026-01-01T00:00:00Z'),
    updatedAt: null,
    ...overrides,
  }
}

function makeAnnotation(overrides: Partial<Annotation> = {}): Annotation {
  return {
    id: 'note-1',
    sloEvaluationId: null,
    evaluationRunId: null,
    content: 'note content',
    author: null,
    categoryId: 'cat-1',
    category: makeCategory(),
    tags: {},
    noteGroupId: null,
    noteGroupName: null,
    hiddenAt: null,
    hiddenBy: null,
    hiddenReason: null,
    createdAt: new Date('2026-01-01T00:00:00Z'),
    updatedAt: null,
    ...overrides,
  }
}

// ── buildChartOption ──────────────────────────────────────────────────────────

describe('buildChartOption', () => {
  it('creates series for metric values', () => {
    const trend = [
      makeTrendPoint({ value: 100, outcome: 'pass' }),
      makeTrendPoint({ value: 200, outcome: 'warning', timestamp: new Date('2026-03-16T10:30:00Z') }),
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
      makeTrendPoint({ value: 100, targets: { pass: [], warn: [{ criteria: '<=+15%', targetValue: 230, violated: false }] } }),
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
      makeTrendPoint({ value: 110, baseline: 100, timestamp: new Date('2026-03-16T10:30:00Z') }),
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
            { criteria: '<=600', targetValue: 600, violated: false },
            { criteria: '<=+10%', targetValue: 99, violated: false },
          ],
          warn: [],
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
            { criteria: '<=600', targetValue: 600, violated: false },
            { criteria: '<=+10%', targetValue: 99, violated: false },
          ],
          warn: [
            { criteria: '<=800', targetValue: 800, violated: false },
            { criteria: '<=+15%', targetValue: 103, violated: false },
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

  // ── Auto Y-axis framing (blank bounds) ──────────────────────────────────────

  function autoBounds(
    input: Record<string, unknown>,
    extent: { min: number; max: number },
  ): { min: number; max: number } {
    const option = buildChartOption(baseInput(input)) as Record<string, unknown>
    const yAxis = option.yAxis as {
      min: (extent: { min: number; max: number }) => number
      max: (extent: { min: number; max: number }) => number
    }
    expect(typeof yAxis.min).toBe('function')
    expect(typeof yAxis.max).toBe('function')
    return { min: yAxis.min(extent), max: yAxis.max(extent) }
  }

  it('auto-frames data with padded nice bounds when yMin/yMax blank', () => {
    expect(autoBounds({}, { min: 100, max: 200 })).toEqual({ min: 80, max: 220 })
  })

  it('auto-frames a flat non-zero series without collapsing the axis', () => {
    expect(autoBounds({}, { min: 500, max: 500 })).toEqual({ min: 490, max: 510 })
  })

  it('auto-frames a flat zero series', () => {
    expect(autoBounds({}, { min: 0, max: 0 })).toEqual({ min: -0.2, max: 0.2 })
  })

  it('auto-frames all-negative data', () => {
    expect(autoBounds({}, { min: -500, max: -100 })).toEqual({ min: -550, max: -50 })
  })

  it('rounds away floating-point noise in auto bounds', () => {
    // Without rounding the max lands on 0.0032500000000000003.
    expect(autoBounds({}, { min: 0.001, max: 0.003 }).max).toBe(0.00325)
  })

  it('auto-frames when a manual bound is non-numeric', () => {
    const option = buildChartOption(baseInput({ yMin: 'abc', yMax: '' })) as Record<string, unknown>
    const yAxis = option.yAxis as { min: unknown; max: unknown }
    expect(typeof yAxis.min).toBe('function')
    expect(typeof yAxis.max).toBe('function')
  })

  it('ignores inverted manual bounds (min >= max) and auto-frames both', () => {
    const option = buildChartOption(baseInput({ yMin: '500', yMax: '10' })) as Record<string, unknown>
    const yAxis = option.yAxis as { min: unknown; max: unknown }
    expect(typeof yAxis.min).toBe('function')
    expect(typeof yAxis.max).toBe('function')
  })

  it('keeps a valid manual bound while auto-framing the blank one', () => {
    const option = buildChartOption(baseInput({ yMin: '0', yMax: '' })) as Record<string, unknown>
    const yAxis = option.yAxis as { min: unknown; max: unknown }
    expect(yAxis.min).toBe(0)
    expect(typeof yAxis.max).toBe('function')
  })

  it('handles empty data points', () => {
    const option = buildChartOption(baseInput({ trend: [] })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series[0].data).toEqual([])
  })

  it('highlights current evaluation point with white border', () => {
    const trend = [
      makeTrendPoint({ evalId: 'eval-1' }),
      makeTrendPoint({ evalId: 'eval-2' }),
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

  it('appends showOnGraph notes to the tooltip and escapes their content', () => {
    const shown = makeAnnotation({
      content: 'deploy <v2>',
      category: makeCategory({ label: 'Deploy', showOnGraph: true, color: 'sky' }),
    })
    const hidden = makeAnnotation({
      id: 'note-2',
      content: 'internal only',
      category: makeCategory({ id: 'cat-2', label: 'Internal', showOnGraph: false, color: 'gray' }),
    })
    const annotations = new Map<string, Annotation[]>([['eval-1', [shown, hidden]]])
    const trend = [makeTrendPoint({ evalId: 'eval-1' })]

    const option = buildChartOption(baseInput({ trend, annotations })) as Record<string, unknown>
    const tooltip = option.tooltip as { formatter: (params: unknown) => string }
    const html = tooltip.formatter([{ dataIndex: 0 }])

    expect(html).toContain('Deploy')
    expect(html).toContain('deploy &lt;v2&gt;') // HTML-escaped
    expect(html).not.toContain('internal only') // hidden category excluded
    expect(html).not.toContain('Internal')
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
        baseline: 90,
        targets: {
          pass: [
            { criteria: '<=600', targetValue: 600, violated: false },
            { criteria: '<=+10%', targetValue: 99, violated: false },
          ],
          warn: [
            { criteria: '<=+15%', targetValue: 103, violated: false },
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

  it('filters out >0 targets where targetValue is always 0', () => {
    const trend: TrendPoint[] = [
      makeTrendPoint({
        targets: {
          pass: [
            { criteria: '>0', targetValue: 0, violated: false },
            { criteria: '<=600', targetValue: 600, violated: false },
          ],
          warn: [],
        },
      }),
    ]
    const { result } = renderHook(() =>
      useMetricTrendState(trend, 'eval-1', makeIndicator()),
    )
    // Only <=600 (no baseline since trend point has no baseline field)
    expect(result.current.targets).toHaveLength(1)
    expect(result.current.targets[0].key).toBe('pass:<=600')
  })

  it('toggling a target flips its visibility', () => {
    const trend: TrendPoint[] = [
      makeTrendPoint({
        targets: { pass: [{ criteria: '<=600', targetValue: 600, violated: false }], warn: [] },
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
      makeTrendPoint({ baseline: 90, targets: { pass: [], warn: [] } }),
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
