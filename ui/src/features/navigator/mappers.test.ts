import { describe, it, expect } from 'vitest'
import { overallScoreToMiniView, sloGroupToMiniView } from './mappers'
import type { HeatmapSummaryCellDto, HeatmapCellGroupedDto } from './mappers'

// ---------------------------------------------------------------------------
// Per-segment mapper fixtures
// ---------------------------------------------------------------------------

const MINI_COLUMN_A = {
  evaluation_id: 'eval-a',
  period_start: '2026-04-01T10:00:00Z',
  period_end: '2026-04-01T10:05:00Z',
  eval_name: 'Run A',
  has_notes: false,
}

const MINI_COLUMN_B = {
  evaluation_id: 'eval-b',
  period_start: '2026-04-01T10:05:00Z',
  period_end: '2026-04-01T10:10:00Z',
  eval_name: 'Run B',
  has_notes: false,
}

const MINI_COLUMNS = [MINI_COLUMN_A, MINI_COLUMN_B]

function makeSummaryCell(
  evaluation_id: string,
  result: string,
  score: number,
  invalidated = false,
): HeatmapSummaryCellDto {
  return {
    evaluation_id,
    period_start: '2026-04-01T10:00:00Z',
    result,
    score,
    invalidated,
    total_score_pass_threshold: 90,
    total_score_warning_threshold: 70,
    sli_metadata: null,
    invalidation_note: null,
  }
}

function makeIndicatorCell(
  evaluation_id: string,
  slo_evaluation_id: string,
  metric: string,
  result: string,
  score: number,
): HeatmapCellGroupedDto {
  return {
    evaluation_id,
    slo_evaluation_id,
    period_start: '2026-04-01T10:00:00Z',
    metric,
    display_name: `Display ${metric}`,
    result,
    score,
    value: 123,
    compared_value: null,
    change_relative_pct: null,
    weight: 1,
    key_sli: false,
    pass_targets: null,
    warning_targets: null,
    tab_group: null,
    aggregation: null,
  }
}

const COMPOSITE_CELL_A = makeSummaryCell('eval-a', 'pass', 95)
const COMPOSITE_CELL_B = makeSummaryCell('eval-b', 'warning', 72)
const MINI_COMPOSITE = [COMPOSITE_CELL_A, COMPOSITE_CELL_B]

const SUMMARY_SLO_A = makeSummaryCell('eval-a', 'pass', 100)
const SUMMARY_SLO_B = makeSummaryCell('eval-b', 'fail', 50)

const INDICATOR_A_M1 = makeIndicatorCell('eval-a', 'slo-eval-a1', 'metric_one', 'pass', 100)
const INDICATOR_A_M2 = makeIndicatorCell('eval-a', 'slo-eval-a2', 'metric_two', 'warning', 80)
const INDICATOR_B_M1 = makeIndicatorCell('eval-b', 'slo-eval-b1', 'metric_one', 'fail', 40)
const INDICATOR_B_M2 = makeIndicatorCell('eval-b', 'slo-eval-b2', 'metric_two', 'pass', 95)

const SLO_GROUP = {
  slo_name: 'slo-one',
  slo_display_name: 'SLO One Display',
  metrics: [
    { name: 'metric_one', display_name: 'Display metric_one' },
    { name: 'metric_two', display_name: 'Display metric_two' },
  ],
  cells: [INDICATOR_A_M1, INDICATOR_A_M2, INDICATOR_B_M1, INDICATOR_B_M2],
  summary: [SUMMARY_SLO_A, SUMMARY_SLO_B],
}

// ---------------------------------------------------------------------------
// overallScoreToMiniView
// ---------------------------------------------------------------------------

describe('overallScoreToMiniView', () => {
  it('produces a single-row view with one cell per column', () => {
    const view = overallScoreToMiniView(MINI_COLUMNS, MINI_COMPOSITE)

    expect(view.rows).toEqual(['Overall Score'])
    expect(view.cells).toHaveLength(2)
    expect(view.headerRowIndices.size).toBe(0)
  })

  it('assigns correct x-indices and y=0 for all cells', () => {
    const view = overallScoreToMiniView(MINI_COLUMNS, MINI_COMPOSITE)

    const cellA = view.cells.find(c => c.columnKey === 'eval-a')
    const cellB = view.cells.find(c => c.columnKey === 'eval-b')

    expect(cellA?.value).toEqual([0, 0])
    expect(cellB?.value).toEqual([1, 0])
  })

  it('attaches slot, periodStart, columnKey, and evaluation_name to each cell', () => {
    const view = overallScoreToMiniView(MINI_COLUMNS, MINI_COMPOSITE)

    const cellA = view.cells[0]
    expect(cellA.slot).toBe('eval-a')
    expect(cellA.periodStart).toBe('2026-04-01T10:00:00Z')
    expect(cellA.columnKey).toBe('eval-a')
    expect(cellA.evaluation_name).toBe('Run A')
  })

  it('maps result and score from the composite summary cell', () => {
    const view = overallScoreToMiniView(MINI_COLUMNS, MINI_COMPOSITE)

    const cellA = view.cells.find(c => c.columnKey === 'eval-a')
    const cellB = view.cells.find(c => c.columnKey === 'eval-b')

    expect(cellA?.result).toBe('pass')
    expect(cellA?.score).toBe(95)
    expect(cellB?.result).toBe('warning')
    expect(cellB?.score).toBe(72)
  })

  it('returns result=none when composite is empty (column has no summary)', () => {
    const view = overallScoreToMiniView(MINI_COLUMNS, [])

    expect(view.cells[0].result).toBe('none')
    expect(view.cells[0].score).toBe(0)
  })

  it('returns result=invalidated for an invalidated composite cell', () => {
    const invalidatedComposite = [
      makeSummaryCell('eval-a', 'pass', 90, true),
      COMPOSITE_CELL_B,
    ]
    const view = overallScoreToMiniView(MINI_COLUMNS, invalidatedComposite)

    const cellA = view.cells.find(c => c.columnKey === 'eval-a')
    expect(cellA?.result).toBe('invalidated')
  })
})

// ---------------------------------------------------------------------------
// sloGroupToMiniView — collapsed
// ---------------------------------------------------------------------------

describe('sloGroupToMiniView collapsed', () => {
  it('produces a single header row only', () => {
    const view = sloGroupToMiniView(SLO_GROUP, MINI_COLUMNS, false)

    expect(view.rows).toHaveLength(1)
    expect(view.rows[0]).toBe('SLO One Display')
    expect(view.cells).toHaveLength(2)
  })

  it('marks y=0 as a header row', () => {
    const view = sloGroupToMiniView(SLO_GROUP, MINI_COLUMNS, false)

    expect(view.headerRowIndices.has(0)).toBe(true)
    expect(view.headerRowIndices.size).toBe(1)
  })

  it('sets isSloHeader=true and sloName on all header cells', () => {
    const view = sloGroupToMiniView(SLO_GROUP, MINI_COLUMNS, false)

    for (const cell of view.cells) {
      expect(cell.isSloHeader).toBe(true)
      expect(cell.sloName).toBe('slo-one')
    }
  })

  it('maps result and score from the SLO summary', () => {
    const view = sloGroupToMiniView(SLO_GROUP, MINI_COLUMNS, false)

    const cellA = view.cells.find(c => c.columnKey === 'eval-a')
    const cellB = view.cells.find(c => c.columnKey === 'eval-b')

    expect(cellA?.result).toBe('pass')
    expect(cellA?.score).toBe(100)
    expect(cellB?.result).toBe('fail')
    expect(cellB?.score).toBe(50)
  })

  it('falls back to slo_name when slo_display_name is null', () => {
    const groupWithoutDisplayName = { ...SLO_GROUP, slo_display_name: null }
    const view = sloGroupToMiniView(groupWithoutDisplayName, MINI_COLUMNS, false)

    expect(view.rows[0]).toBe('slo-one')
  })
})

// ---------------------------------------------------------------------------
// sloGroupToMiniView — expanded
// ---------------------------------------------------------------------------

describe('sloGroupToMiniView expanded', () => {
  it('produces header + indicator rows (total rowCount = 1 + metrics.length)', () => {
    const view = sloGroupToMiniView(SLO_GROUP, MINI_COLUMNS, true)

    // 1 header + 2 indicators = 3 rows; cells = 3 × 2 columns = 6
    expect(view.rows).toHaveLength(3)
    expect(view.cells).toHaveLength(6)
  })

  it('orders rows bottom-to-top: indicator rows first, header row last in array', () => {
    const view = sloGroupToMiniView(SLO_GROUP, MINI_COLUMNS, true)

    // ECharts category axis is bottom-to-top. The header (displayed at top)
    // must appear LAST in the rows array (highest y-index = rowCount-1).
    expect(view.rows[view.rows.length - 1]).toBe('SLO One Display')
    expect(view.rows[0]).toBe('Display metric_two')
    expect(view.rows[1]).toBe('Display metric_one')
  })

  it('assigns the highest y-index to the header row', () => {
    const view = sloGroupToMiniView(SLO_GROUP, MINI_COLUMNS, true)
    const rowCount = 3
    const headerYIndex = rowCount - 1

    expect(view.headerRowIndices.has(headerYIndex)).toBe(true)
    expect(view.headerRowIndices.size).toBe(1)
  })

  it('assigns reversed y-indices to indicator rows', () => {
    const view = sloGroupToMiniView(SLO_GROUP, MINI_COLUMNS, true)

    // display order (top-to-bottom): [0]=header, [1]=metric_one, [2]=metric_two
    // yIndex = rowCount-1 - displayIndex
    // header → yIndex=2, metric_one → yIndex=1, metric_two → yIndex=0
    const metricOneCells = view.cells.filter(c => c.metricName === 'metric_one')
    const metricTwoCells = view.cells.filter(c => c.metricName === 'metric_two')

    expect(metricOneCells[0].value[1]).toBe(1)
    expect(metricTwoCells[0].value[1]).toBe(0)
  })

  it('attaches evalId and metricName to indicator cells', () => {
    const view = sloGroupToMiniView(SLO_GROUP, MINI_COLUMNS, true)

    const cellA1 = view.cells.find(
      c => c.columnKey === 'eval-a' && c.metricName === 'metric_one',
    )
    expect(cellA1?.evalId).toBe('slo-eval-a1')
    expect(cellA1?.metricName).toBe('metric_one')
  })

  it('maps result and score correctly for indicator cells', () => {
    const view = sloGroupToMiniView(SLO_GROUP, MINI_COLUMNS, true)

    const cellA1 = view.cells.find(
      c => c.columnKey === 'eval-a' && c.metricName === 'metric_one',
    )
    const cellB2 = view.cells.find(
      c => c.columnKey === 'eval-b' && c.metricName === 'metric_two',
    )

    expect(cellA1?.result).toBe('pass')
    expect(cellA1?.score).toBe(100)
    expect(cellB2?.result).toBe('pass')
    expect(cellB2?.score).toBe(95)
  })

  it('header cells in expanded view carry isSloHeader=true', () => {
    const view = sloGroupToMiniView(SLO_GROUP, MINI_COLUMNS, true)
    const rowCount = 3
    const headerYIndex = rowCount - 1

    const headerCells = view.cells.filter(c => c.value[1] === headerYIndex)
    expect(headerCells).toHaveLength(2)
    for (const cell of headerCells) {
      expect(cell.isSloHeader).toBe(true)
    }
  })

  it('maps change_point from DTO to camelCase on indicator cells', () => {
    const cellWithChangePoint: HeatmapCellGroupedDto = {
      ...INDICATOR_A_M1,
      change_point: { direction: 'regression', change_relative_pct: -12.5 },
    }
    const group = {
      ...SLO_GROUP,
      cells: [cellWithChangePoint, INDICATOR_A_M2, INDICATOR_B_M1, INDICATOR_B_M2],
    }
    const view = sloGroupToMiniView(group, MINI_COLUMNS, true)

    const cellWithCp = view.cells.find(
      c => c.columnKey === 'eval-a' && c.metricName === 'metric_one',
    )
    expect(cellWithCp?.changePoint).toEqual({
      direction: 'regression',
      changeRelativePct: -12.5,
    })
  })

  it('leaves changePoint undefined when DTO has no change_point', () => {
    const view = sloGroupToMiniView(SLO_GROUP, MINI_COLUMNS, true)

    const cell = view.cells.find(
      c => c.columnKey === 'eval-a' && c.metricName === 'metric_one',
    )
    expect(cell?.changePoint).toBeUndefined()
  })
})
