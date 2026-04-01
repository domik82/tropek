// ui/src/features/navigator/utils.test.ts
import { describe, it, expect } from 'vitest'
import { buildGroupHeatmapData, buildGroupScoreData, buildAssetHeatmapData } from './utils'
import type { EvaluationSummary } from '@/features/evaluations/types'
import type { MetricHeatmapResponse } from './types'

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

const EVAL_ID_1 = 'aaaaaaaa-0000-0000-0000-000000000001'
const EVAL_ID_2 = 'aaaaaaaa-0000-0000-0000-000000000002'
const SLO_EVAL_ID_1 = 'bbbbbbbb-0000-0000-0000-000000000001'
const SLO_EVAL_ID_2 = 'bbbbbbbb-0000-0000-0000-000000000002'

const RESP: MetricHeatmapResponse = {
  asset_name: 'test-asset',
  columns: [
    { evaluation_id: EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', period_end: '2026-01-15T23:59:59Z', eval_name: 'daily' },
    { evaluation_id: EVAL_ID_2, period_start: '2026-01-16T00:00:00Z', period_end: '2026-01-16T23:59:59Z', eval_name: 'daily' },
  ],
  groups: [
    {
      slo_name: 'nginx',
      metrics: [
        { name: 'error_rate', display_name: 'Error Rate' },
        { name: 'p99_latency', display_name: 'P99 Latency' },
      ],
      cells: [
        { evaluation_id: EVAL_ID_1, slo_evaluation_id: SLO_EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', metric: 'error_rate', display_name: 'Error Rate', result: 'pass', score: 100 },
        { evaluation_id: EVAL_ID_1, slo_evaluation_id: SLO_EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', metric: 'p99_latency', display_name: 'P99 Latency', result: 'warning', score: 50 },
        { evaluation_id: EVAL_ID_2, slo_evaluation_id: SLO_EVAL_ID_2, period_start: '2026-01-16T00:00:00Z', metric: 'error_rate', display_name: 'Error Rate', result: 'pass', score: 100 },
        { evaluation_id: EVAL_ID_2, slo_evaluation_id: SLO_EVAL_ID_2, period_start: '2026-01-16T00:00:00Z', metric: 'p99_latency', display_name: 'P99 Latency', result: 'pass', score: 90 },
      ],
      summary: [
        { evaluation_id: EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', result: 'warning', score: 75 },
        { evaluation_id: EVAL_ID_2, period_start: '2026-01-16T00:00:00Z', result: 'pass', score: 95 },
      ],
    },
  ],
  composite: [
    { evaluation_id: EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', result: 'warning', score: 75 },
    { evaluation_id: EVAL_ID_2, period_start: '2026-01-16T00:00:00Z', result: 'pass', score: 95 },
  ],
}

describe('buildAssetHeatmapData', () => {
  it('returns 2 columns', () => {
    const d = buildAssetHeatmapData(RESP, new Map())
    expect(d.slots).toHaveLength(2)
  })

  it('with all groups collapsed: rows = Overall + 1 header = 2 rows', () => {
    const d = buildAssetHeatmapData(RESP, new Map([['nginx', false]]))
    // Overall + nginx header
    expect(d.rows).toHaveLength(2)
  })

  it('with nginx expanded: rows = Overall + 1 header + 2 indicators = 4 rows', () => {
    const d = buildAssetHeatmapData(RESP, new Map([['nginx', true]]))
    expect(d.rows).toHaveLength(4)
  })

  it('Overall row cells carry composite result', () => {
    const d = buildAssetHeatmapData(RESP, new Map())
    const overallCells = d.cells.filter(c => c.rowLabel === 'Overall Score')
    expect(overallCells).toHaveLength(2)
    expect(overallCells[0].result).toBe('warning')
    expect(overallCells[1].result).toBe('pass')
  })

  it('SLO header cells carry summary result', () => {
    const d = buildAssetHeatmapData(RESP, new Map([['nginx', false]]))
    const headerCells = d.cells.filter(c => c.isSloHeader)
    expect(headerCells).toHaveLength(2)
    expect(headerCells[0].result).toBe('warning')
  })

  it('expanded indicator cells carry slo_evaluation_id in evalId', () => {
    const d = buildAssetHeatmapData(RESP, new Map([['nginx', true]]))
    const indCells = d.cells.filter(c => c.evalId)
    expect(indCells[0].evalId).toBe(SLO_EVAL_ID_1)
  })

  it('headerRowIndices marks SLO header rows', () => {
    const d = buildAssetHeatmapData(RESP, new Map([['nginx', true]]))
    expect(d.headerRowIndices.size).toBe(1)
  })
})
