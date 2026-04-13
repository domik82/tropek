import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useTabState } from './useTabState'
import type { Indicator } from '../domain'

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
    ...overrides,
  }
}

describe('useTabState', () => {
  it('returns empty groups for undefined input', () => {
    const { result } = renderHook(() => useTabState(undefined))
    expect(result.current.availableGroups).toEqual([])
    expect(result.current.counts).toEqual({})
    expect(result.current.activeTab).toBe('all')
    expect(result.current.tabIndicators).toEqual([])
  })

  it('returns empty groups for empty array', () => {
    const { result } = renderHook(() => useTabState([]))
    expect(result.current.availableGroups).toEqual([])
    expect(result.current.tabIndicators).toEqual([])
  })

  it('extracts unique tab groups from indicator results', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tabGroup: 'latency' }),
      makeIndicator({ metric: 'b', tabGroup: 'throughput' }),
      makeIndicator({ metric: 'c', tabGroup: 'latency' }),
    ]
    const { result } = renderHook(() => useTabState(indicators))
    expect(result.current.availableGroups).toEqual(['latency', 'throughput'])
  })

  it('counts indicators per group', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tabGroup: 'latency' }),
      makeIndicator({ metric: 'b', tabGroup: 'throughput' }),
      makeIndicator({ metric: 'c', tabGroup: 'latency' }),
      makeIndicator({ metric: 'd', tabGroup: 'latency' }),
    ]
    const { result } = renderHook(() => useTabState(indicators))
    expect(result.current.counts).toEqual({ latency: 3, throughput: 1 })
  })

  it('defaults to "all" tab', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tabGroup: 'latency' }),
    ]
    const { result } = renderHook(() => useTabState(indicators))
    expect(result.current.activeTab).toBe('all')
  })

  it('setActiveTab updates the active tab', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tabGroup: 'latency' }),
      makeIndicator({ metric: 'b', tabGroup: 'throughput' }),
    ]
    const { result } = renderHook(() => useTabState(indicators))

    act(() => result.current.setActiveTab('latency'))
    expect(result.current.activeTab).toBe('latency')
  })

  it('filters indicators by active tab', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tabGroup: 'latency' }),
      makeIndicator({ metric: 'b', tabGroup: 'throughput' }),
      makeIndicator({ metric: 'c', tabGroup: 'latency' }),
    ]
    const { result } = renderHook(() => useTabState(indicators))

    act(() => result.current.setActiveTab('latency'))
    expect(result.current.tabIndicators).toHaveLength(2)
    expect(result.current.tabIndicators.map(i => i.metric)).toEqual(['a', 'c'])
  })

  it('returns all indicators when activeTab is "all"', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tabGroup: 'latency' }),
      makeIndicator({ metric: 'b', tabGroup: 'throughput' }),
    ]
    const { result } = renderHook(() => useTabState(indicators))
    expect(result.current.tabIndicators).toHaveLength(2)
  })

  it('resets to "all" when activeTab becomes invalid', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tabGroup: 'latency' }),
    ]
    const { result } = renderHook(() => useTabState(indicators))

    act(() => result.current.setActiveTab('nonexistent'))
    expect(result.current.activeTab).toBe('all')
  })

  it('ignores indicators without tab_group when extracting groups', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tabGroup: 'latency' }),
      makeIndicator({ metric: 'b', tabGroup: null }),
    ]
    const { result } = renderHook(() => useTabState(indicators))
    expect(result.current.availableGroups).toEqual(['latency'])
  })
})
