// ui/src/features/navigator/utils.test.ts
import { describe, it, expect } from 'vitest'
import { buildGroupHeatmapData, buildGroupScoreData, buildAssetHeatmapData } from './utils'
import type { EvaluationSummary } from '@/features/evaluations/types'
import type { MetricHeatmapResponse } from './types'

function mkEval(asset: string, slot: string, result: 'pass' | 'warning' | 'fail', score: number): EvaluationSummary {
  return {
    id: `${asset}-${slot}`,
    name: 'test',
    status: 'completed',
    result,
    score,
    period_start: slot,
    period_end: slot,
    slo_name: null, slo_version: null, sli_name: null, sli_version: null,
    data_source_name: null, ingestion_mode: 'pull', adapter_used: null,
    invalidated: false,
    asset_snapshot: { name: asset, tags: {} },
    evaluation_metadata: {},
    created_at: slot,
  }
}

describe('buildGroupHeatmapData', () => {
  it('builds correct slots and rows from evaluations', () => {
    const evals = [
      mkEval('asset-a', '2026-01-01T06:00:00Z', 'pass', 95),
      mkEval('asset-b', '2026-01-01T06:00:00Z', 'fail', 40),
      mkEval('asset-a', '2026-01-02T06:00:00Z', 'pass', 98),
    ]
    const { slots, rows } = buildGroupHeatmapData(evals)
    expect(slots).toEqual(['2026-01-01T06:00:00Z', '2026-01-02T06:00:00Z'])
    expect(rows).toEqual(['asset-a', 'asset-b'])
  })

  it('produces a cell for every (slot × row) combination', () => {
    const evals = [
      mkEval('asset-a', '2026-01-01T06:00:00Z', 'pass', 95),
      mkEval('asset-b', '2026-01-01T06:00:00Z', 'fail', 40),
    ]
    const { cells } = buildGroupHeatmapData(evals)
    // 1 slot × 2 rows = 2 cells
    expect(cells).toHaveLength(2)
  })

  it('uses result=none for empty cells', () => {
    const evals = [
      mkEval('asset-a', '2026-01-01T06:00:00Z', 'pass', 95),
      mkEval('asset-b', '2026-01-02T06:00:00Z', 'pass', 90),
    ]
    const { cells } = buildGroupHeatmapData(evals)
    // 2 slots × 2 rows = 4 cells; 2 of them are empty
    const emptyCells = cells.filter(c => c.result === 'none')
    expect(emptyCells).toHaveLength(2)
  })

  it('picks worst result when two evaluations share the same cell', () => {
    const evals = [
      mkEval('asset-a', '2026-01-01T06:00:00Z', 'pass', 90),
      mkEval('asset-a', '2026-01-01T06:00:00Z', 'fail', 40),
    ]
    const { cells } = buildGroupHeatmapData(evals)
    const cell = cells.find(c => c.result !== 'none')!
    expect(cell.result).toBe('fail')
  })
})

describe('buildGroupScoreData', () => {
  it('groups scores by slot with one entry per asset', () => {
    const evals = [
      mkEval('asset-a', '2026-01-01T06:00:00Z', 'pass', 90),
      mkEval('asset-b', '2026-01-01T06:00:00Z', 'fail', 40),
    ]
    const data = buildGroupScoreData(evals)
    expect(data).toHaveLength(1)
    expect(data[0].assets).toHaveLength(2)
    expect(data[0].totalAchieved).toBeCloseTo(130)
    expect(data[0].totalMax).toBe(200)
  })
})

describe('buildAssetHeatmapData', () => {
  it('maps metric-heatmap API response to grid data', () => {
    const resp: MetricHeatmapResponse = {
      asset_name: 'asset-a',
      slots: ['2026-01-01T06:00:00Z', '2026-01-02T06:00:00Z'],
      metrics: [{ name: 'error_rate', display_name: 'Error Rate' }],
      cells: [
        { slot: '2026-01-01T06:00:00Z', metric: 'error_rate', display_name: 'Error Rate', result: 'pass', score: 100, eval_id: 'e1' },
        { slot: '2026-01-02T06:00:00Z', metric: 'error_rate', display_name: 'Error Rate', result: 'fail', score: 0, eval_id: 'e2' },
      ],
    }
    const { slots, rows, cells } = buildAssetHeatmapData(resp)
    expect(slots).toHaveLength(2)
    expect(rows).toHaveLength(1)
    expect(cells).toHaveLength(2)
    expect(cells[1].result).toBe('fail')
    expect(cells[1].evalId).toBe('e2')
  })
})
