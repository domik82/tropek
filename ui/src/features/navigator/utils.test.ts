// ui/src/features/navigator/utils.test.ts
import { describe, it, expect } from 'vitest'
import { buildGroupHeatmapData, buildGroupScoreData } from './utils'
import type { EvaluationSummary } from '@/features/evaluations/types'

function mkEval(asset: string, slot: string, result: 'pass' | 'warning' | 'fail', score: number, evalName = 'test'): EvaluationSummary {
  return {
    id: `${asset}-${slot}-${evalName}`,
    evaluation_id: `run-${asset}-${slot}`,
    evaluation_name: evalName,
    status: 'completed',
    result,
    score,
    period_start: slot,
    period_end: slot,
    slo_name: null, slo_version: null, sli_name: null, sli_version: null,
    data_source_name: null, ingestion_mode: 'pull', adapter_used: null,
    invalidated: false,
    original_result: null, original_score: null,
    override_reason: null, override_author: null,
    asset_snapshot: { name: asset, tags: {} },
    variables: {},
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

describe('buildGroupHeatmapData — collision fix', () => {
  it('creates separate cells for same asset+slot with different evaluation_name', () => {
    const evals: EvaluationSummary[] = [
      mkEval('checkout-api', '2026-03-15T00:00:00Z', 'pass', 90, 'load-test'),
      mkEval('checkout-api', '2026-03-15T00:00:00Z', 'fail', 40, 'ad-hoc-run'),
    ]
    const data = buildGroupHeatmapData(evals)
    const checkoutCells = data.cells.filter(c => c.rowLabel === 'checkout-api' && c.result !== 'none')
    expect(checkoutCells).toHaveLength(2)
  })
})
