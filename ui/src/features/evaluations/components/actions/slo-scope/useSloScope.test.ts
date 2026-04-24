import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import type { GroupedMetricHeatmap } from '@/features/navigator/domain'
import { useSloScope } from './useSloScope'

function makeHeatmap(): GroupedMetricHeatmap {
  return {
    assetName: 'asset-under-test',
    columns: [
      {
        evaluationId: 'col-1',
        periodStart: '2026-04-10T00:00:00Z',
        periodEnd: '2026-04-10T01:00:00Z',
        evalName: 'run-1',
      },
      {
        evaluationId: 'col-2',
        periodStart: '2026-04-11T00:00:00Z',
        periodEnd: '2026-04-11T01:00:00Z',
        evalName: 'run-2',
      },
    ],
    groups: [
      {
        sloName: 'latency-slo',
        sloDisplayName: 'Latency SLO',
        metrics: [{ name: 'latency-p95', displayName: 'Latency p95' }],
        cells: [
          {
            evaluationId: 'col-1',
            sloEvaluationId: 'sloeval-latency',
            periodStart: '2026-04-10T00:00:00Z',
            metric: 'latency-p95',
            displayName: 'Latency p95',
            result: 'fail',
            score: 0,
            value: 900,
            comparedValue: null,
            changeRelativePct: null,
            weight: 1,
            keySli: false,
            passTargets: null,
            warningTargets: null,
            tabGroup: null,
            aggregation: null,
            changePoint: null,
          },
          {
            evaluationId: 'col-2',
            sloEvaluationId: 'sloeval-latency-2',
            periodStart: '2026-04-11T00:00:00Z',
            metric: 'latency-p95',
            displayName: 'Latency p95',
            result: 'pass',
            score: 1,
            value: 500,
            comparedValue: null,
            changeRelativePct: null,
            weight: 1,
            keySli: false,
            passTargets: null,
            warningTargets: null,
            tabGroup: null,
            aggregation: null,
            changePoint: null,
          },
        ],
        summary: [
          {
            evaluationId: 'col-1',
            periodStart: '2026-04-10T00:00:00Z',
            result: 'fail',
            score: 0,
            totalScorePassThreshold: 90,
            totalScoreWarningThreshold: 75,
            sliMetadata: null,
            invalidationNote: null,
          },
          {
            evaluationId: 'col-2',
            periodStart: '2026-04-11T00:00:00Z',
            result: 'pass',
            score: 100,
            totalScorePassThreshold: 90,
            totalScoreWarningThreshold: 75,
            sliMetadata: null,
            invalidationNote: null,
          },
        ],
      },
      {
        sloName: 'avail-slo',
        sloDisplayName: 'Availability SLO',
        metrics: [{ name: 'availability', displayName: 'Availability' }],
        cells: [
          {
            evaluationId: 'col-1',
            sloEvaluationId: 'sloeval-avail',
            periodStart: '2026-04-10T00:00:00Z',
            metric: 'availability',
            displayName: 'Availability',
            result: 'pass',
            score: 1,
            value: 99.9,
            comparedValue: null,
            changeRelativePct: null,
            weight: 1,
            keySli: false,
            passTargets: null,
            warningTargets: null,
            tabGroup: null,
            aggregation: null,
            changePoint: null,
          },
        ],
        summary: [
          {
            evaluationId: 'col-1',
            periodStart: '2026-04-10T00:00:00Z',
            result: 'invalidated',
            score: 100,
            totalScorePassThreshold: 90,
            totalScoreWarningThreshold: 75,
            sliMetadata: null,
            invalidationNote: 'maintenance window',
          },
        ],
      },
    ],
    composite: [],
  }
}

describe('useSloScope', () => {
  it('derives SLO rows for the selected column only', () => {
    const { result } = renderHook(() =>
      useSloScope({ heatmapData: makeHeatmap(), columnEvalId: 'col-1', initialMode: 'all' }),
    )
    expect(result.current.availableSlos.map(row => row.sloName)).toEqual([
      'latency-slo',
      'avail-slo',
    ])
    expect(result.current.availableSlos[1].currentResult).toBe('invalidated')
  })

  it('defaults selection to ALL when initialMode is "all"', () => {
    const { result } = renderHook(() =>
      useSloScope({ heatmapData: makeHeatmap(), columnEvalId: 'col-1', initialMode: 'all' }),
    )
    expect(result.current.selected).toEqual(new Set(['latency-slo', 'avail-slo']))
  })

  it('defaults selection to a single SLO when initialMode is { singleSlo }', () => {
    const { result } = renderHook(() =>
      useSloScope({
        heatmapData: makeHeatmap(),
        columnEvalId: 'col-1',
        initialMode: { singleSlo: 'latency-slo' },
      }),
    )
    expect(result.current.selected).toEqual(new Set(['latency-slo']))
  })

  it('reset() widens to ALL regardless of initialMode', () => {
    const { result } = renderHook(() =>
      useSloScope({
        heatmapData: makeHeatmap(),
        columnEvalId: 'col-1',
        initialMode: { singleSlo: 'latency-slo' },
      }),
    )
    act(() => result.current.reset())
    expect(result.current.selected).toEqual(new Set(['latency-slo', 'avail-slo']))
  })

  it('lookupEvalId maps sloName to sloEvaluationId for the current column', () => {
    const { result } = renderHook(() =>
      useSloScope({ heatmapData: makeHeatmap(), columnEvalId: 'col-1', initialMode: 'all' }),
    )
    expect(result.current.lookupEvalId('latency-slo')).toBe('sloeval-latency')
    expect(result.current.lookupEvalId('nope')).toBeUndefined()
  })

  it('filter "invalidated-only" removes non-invalidated rows', () => {
    const { result } = renderHook(() =>
      useSloScope({
        heatmapData: makeHeatmap(),
        columnEvalId: 'col-1',
        initialMode: 'all',
        filter: 'invalidated-only',
      }),
    )
    expect(result.current.availableSlos.map(row => row.sloName)).toEqual(['avail-slo'])
    expect(result.current.selected).toEqual(new Set(['avail-slo']))
  })

  it('filter "not-invalidated" removes invalidated rows', () => {
    const { result } = renderHook(() =>
      useSloScope({
        heatmapData: makeHeatmap(),
        columnEvalId: 'col-1',
        initialMode: 'all',
        filter: 'not-invalidated',
      }),
    )
    expect(result.current.availableSlos.map(row => row.sloName)).toEqual(['latency-slo'])
  })

  it('singleSlo fallback to ALL when that SLO is filtered out', () => {
    const { result } = renderHook(() =>
      useSloScope({
        heatmapData: makeHeatmap(),
        columnEvalId: 'col-1',
        initialMode: { singleSlo: 'avail-slo' },
        filter: 'not-invalidated',
      }),
    )
    expect(result.current.availableSlos.map(row => row.sloName)).toEqual(['latency-slo'])
    expect(result.current.selected).toEqual(new Set(['latency-slo']))
  })
})
