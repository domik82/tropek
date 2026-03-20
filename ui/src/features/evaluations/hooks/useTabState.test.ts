import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useTabState } from './useTabState'
import type { IndicatorResult } from '../types'

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
      makeIndicator({ metric: 'a', tab_group: 'latency' }),
      makeIndicator({ metric: 'b', tab_group: 'throughput' }),
      makeIndicator({ metric: 'c', tab_group: 'latency' }),
    ]
    const { result } = renderHook(() => useTabState(indicators))
    expect(result.current.availableGroups).toEqual(['latency', 'throughput'])
  })

  it('counts indicators per group', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tab_group: 'latency' }),
      makeIndicator({ metric: 'b', tab_group: 'throughput' }),
      makeIndicator({ metric: 'c', tab_group: 'latency' }),
      makeIndicator({ metric: 'd', tab_group: 'latency' }),
    ]
    const { result } = renderHook(() => useTabState(indicators))
    expect(result.current.counts).toEqual({ latency: 3, throughput: 1 })
  })

  it('defaults to "all" tab', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tab_group: 'latency' }),
    ]
    const { result } = renderHook(() => useTabState(indicators))
    expect(result.current.activeTab).toBe('all')
  })

  it('setActiveTab updates the active tab', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tab_group: 'latency' }),
      makeIndicator({ metric: 'b', tab_group: 'throughput' }),
    ]
    const { result } = renderHook(() => useTabState(indicators))

    act(() => result.current.setActiveTab('latency'))
    expect(result.current.activeTab).toBe('latency')
  })

  it('filters indicators by active tab', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tab_group: 'latency' }),
      makeIndicator({ metric: 'b', tab_group: 'throughput' }),
      makeIndicator({ metric: 'c', tab_group: 'latency' }),
    ]
    const { result } = renderHook(() => useTabState(indicators))

    act(() => result.current.setActiveTab('latency'))
    expect(result.current.tabIndicators).toHaveLength(2)
    expect(result.current.tabIndicators.map(i => i.metric)).toEqual(['a', 'c'])
  })

  it('returns all indicators when activeTab is "all"', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tab_group: 'latency' }),
      makeIndicator({ metric: 'b', tab_group: 'throughput' }),
    ]
    const { result } = renderHook(() => useTabState(indicators))
    expect(result.current.tabIndicators).toHaveLength(2)
  })

  it('resets to "all" when activeTab becomes invalid', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tab_group: 'latency' }),
    ]
    const { result } = renderHook(() => useTabState(indicators))

    act(() => result.current.setActiveTab('nonexistent'))
    expect(result.current.activeTab).toBe('all')
  })

  it('ignores indicators without tab_group when extracting groups', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tab_group: 'latency' }),
      makeIndicator({ metric: 'b', tab_group: undefined }),
    ]
    const { result } = renderHook(() => useTabState(indicators))
    expect(result.current.availableGroups).toEqual(['latency'])
  })
})
