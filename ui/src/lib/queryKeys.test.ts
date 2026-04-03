// src/lib/queryKeys.test.ts
import { describe, it, expect } from 'vitest'
import { evaluationKeys, assetKeys, sloKeys } from './queryKeys'

describe('evaluationKeys', () => {
  it('all returns base key', () => {
    expect(evaluationKeys.all).toEqual(['evaluations'])
  })
  it('list includes filters', () => {
    const filters = { group_name: 'infra-production', date: '2026-03-14' }
    expect(evaluationKeys.list(filters)).toEqual(['evaluations', filters])
  })
  it('heatmap includes asset name', () => {
    expect(evaluationKeys.heatmap('catalog-db')).toEqual(['metric-heatmap', 'catalog-db', undefined])
  })
  it('detail includes id', () => {
    expect(evaluationKeys.detail('abc-123')).toEqual(['evaluations', 'abc-123'])
  })
  it('trend includes id, metric and date range', () => {
    const range = { from: '2026-01-01T00:00:00Z' }
    expect(evaluationKeys.trend('abc-123', 'response_time_p95', range)).toEqual([
      'evaluations', 'abc-123', 'response_time_p95', range,
    ])
  })
})

describe('assetKeys', () => {
  it('all returns base key', () => expect(assetKeys.all).toEqual(['assets']))
  it('groups returns groups key', () => expect(assetKeys.groups()).toEqual(['assets', 'groups']))
})

describe('sloKeys', () => {
  it('all returns base key', () => expect(sloKeys.all).toEqual(['slos']))
  it('detail includes name', () => {
    expect(sloKeys.detail('slo-perf-linux')).toEqual(['slos', 'slo-perf-linux'])
  })
})
