import { describe, it, expect } from 'vitest'
import { assetHeatmapDtoToDomain, overallScoreToMiniView, sloGroupToMiniView } from './mappers'
import type { GroupedMetricHeatmapResponseDto, HeatmapSummaryCellDto, HeatmapCellGroupedDto } from './mappers'

// Fixture builder — two columns, two SLO groups (availability, latency),
// one indicator per group. Groups are arranged so availability sorts before
// latency alphabetically. Caller can override individual fields.
function makeDto(overrides: Partial<GroupedMetricHeatmapResponseDto> = {}): GroupedMetricHeatmapResponseDto {
  return {
    asset_name: 'shop-api',
    columns: [
      { evaluation_id: 'run-1', period_start: '2026-04-01T00:00:00Z', period_end: '2026-04-01T01:00:00Z', eval_name: 'hourly', has_notes: false },
      { evaluation_id: 'run-2', period_start: '2026-04-01T01:00:00Z', period_end: '2026-04-01T02:00:00Z', eval_name: 'hourly', has_notes: false },
    ],
    composite: [
      { evaluation_id: 'run-1', period_start: '2026-04-01T00:00:00Z', result: 'pass', score: 90, invalidated: false, invalidation_note: null, sli_metadata: null, total_score_pass_threshold: 80, total_score_warning_threshold: 60 },
      { evaluation_id: 'run-2', period_start: '2026-04-01T01:00:00Z', result: 'fail', score: 40, invalidated: false, invalidation_note: null, sli_metadata: null, total_score_pass_threshold: 80, total_score_warning_threshold: 60 },
    ],
    groups: [
      {
        slo_name: 'latency',
        slo_display_name: 'Latency SLO',
        metrics: [{ name: 'p95', display_name: 'p95 response time' }],
        cells: [
          { evaluation_id: 'run-1', slo_evaluation_id: 'sev-1', period_start: '2026-04-01T00:00:00Z', metric: 'p95', display_name: 'p95 response time', result: 'pass', score: 100, value: 250, compared_value: 240, change_relative_pct: 4, weight: 1, key_sli: false, pass_targets: null, warning_targets: null, tab_group: null, aggregation: 'avg' },
          { evaluation_id: 'run-2', slo_evaluation_id: 'sev-2', period_start: '2026-04-01T01:00:00Z', metric: 'p95', display_name: 'p95 response time', result: 'fail', score: 0, value: 900, compared_value: 250, change_relative_pct: 260, weight: 1, key_sli: false, pass_targets: null, warning_targets: null, tab_group: null, aggregation: 'avg' },
        ],
        summary: [
          { evaluation_id: 'run-1', period_start: '2026-04-01T00:00:00Z', result: 'pass', score: 100, invalidated: false, invalidation_note: null, sli_metadata: null, total_score_pass_threshold: 80, total_score_warning_threshold: 60 },
          { evaluation_id: 'run-2', period_start: '2026-04-01T01:00:00Z', result: 'fail', score: 0, invalidated: false, invalidation_note: null, sli_metadata: null, total_score_pass_threshold: 80, total_score_warning_threshold: 60 },
        ],
      },
      {
        slo_name: 'availability',
        slo_display_name: null,
        metrics: [{ name: 'uptime', display_name: 'Uptime %' }],
        cells: [
          { evaluation_id: 'run-1', slo_evaluation_id: 'sev-3', period_start: '2026-04-01T00:00:00Z', metric: 'uptime', display_name: 'Uptime %', result: 'pass', score: 100, value: 99.99, compared_value: 99.99, change_relative_pct: 0, weight: 1, key_sli: true, pass_targets: null, warning_targets: null, tab_group: null, aggregation: 'avg' },
          { evaluation_id: 'run-2', slo_evaluation_id: 'sev-4', period_start: '2026-04-01T01:00:00Z', metric: 'uptime', display_name: 'Uptime %', result: 'warning', score: 60, value: 98.5, compared_value: 99.99, change_relative_pct: -1.5, weight: 1, key_sli: true, pass_targets: null, warning_targets: null, tab_group: null, aggregation: 'avg' },
        ],
        summary: [
          { evaluation_id: 'run-1', period_start: '2026-04-01T00:00:00Z', result: 'pass', score: 100, invalidated: false, invalidation_note: null, sli_metadata: null, total_score_pass_threshold: 80, total_score_warning_threshold: 60 },
          { evaluation_id: 'run-2', period_start: '2026-04-01T01:00:00Z', result: 'warning', score: 60, invalidated: false, invalidation_note: null, sli_metadata: null, total_score_pass_threshold: 80, total_score_warning_threshold: 60 },
        ],
      },
    ],
    ...overrides,
  }
}

describe('assetHeatmapDtoToDomain', () => {
  it('sorts SLO groups alphabetically and places Overall Score row visually on top', () => {
    // availability sorts before latency → displayRows (top-to-bottom) are
    // [Overall Score, availability, Latency SLO]. rows is the ECharts
    // (bottom-to-top) label order, which is the reverse.
    const view = assetHeatmapDtoToDomain(makeDto(), new Map())
    expect(view.rows).toEqual(['Latency SLO', 'availability', 'Overall Score'])
  })

  it('expands indicators under an expanded SLO group only', () => {
    const view = assetHeatmapDtoToDomain(
      makeDto(),
      new Map([['latency', true]]),
    )
    // overall + 2 headers + 1 indicator (latency expanded) = 4 rows
    expect(view.rows.length).toBe(4)
    expect(view.rows).toContain('p95 response time')
    expect(view.rows).not.toContain('Uptime %')
  })

  it('attaches value = [xi, yi] at map time for every emitted cell', () => {
    const view = assetHeatmapDtoToDomain(makeDto(), new Map())
    for (const cell of view.cells) {
      expect(cell.value).toHaveLength(2)
      expect(cell.value[0]).toBeGreaterThanOrEqual(0)
      expect(cell.value[1]).toBeGreaterThanOrEqual(0)
    }
  })

  it('collapses invalidated sentinel into canonical result union on composite cells', () => {
    const dto = makeDto()
    dto.composite[0].invalidated = true
    const view = assetHeatmapDtoToDomain(dto, new Map())
    const overallRun1 = view.cells.find(c =>
      c.rowLabel === 'Overall Score' && c.columnKey === 'run-1',
    )
    expect(overallRun1?.result).toBe('invalidated')
  })

  it('collapses invalidated sentinel on per-SLO summary cells', () => {
    const dto = makeDto()
    // latency group is index 0 in the fixture; summary[0] is run-1
    dto.groups[0].summary[0].invalidated = true
    const view = assetHeatmapDtoToDomain(dto, new Map())
    const latencyHeaderRun1 = view.cells.find(c =>
      c.isSloHeader && c.sloName === 'latency' && c.columnKey === 'run-1',
    )
    expect(latencyHeaderRun1?.result).toBe('invalidated')
  })

  it('marks SLO header rows in headerRowIndices with ECharts y-coordinates', () => {
    const view = assetHeatmapDtoToDomain(makeDto(), new Map())
    expect(view.headerRowIndices.size).toBe(2)
    // All y indices must be within the row count
    for (const yi of view.headerRowIndices) {
      expect(yi).toBeGreaterThanOrEqual(0)
      expect(yi).toBeLessThan(view.rows.length)
    }
  })

  it('builds per-SLO summary lookup so header cells carry the right score and result', () => {
    const view = assetHeatmapDtoToDomain(makeDto(), new Map())
    const latencyHeaderRun2 = view.cells.find(c =>
      c.isSloHeader && c.sloName === 'latency' && c.columnKey === 'run-2',
    )
    expect(latencyHeaderRun2?.score).toBe(0)
    expect(latencyHeaderRun2?.result).toBe('fail')
  })

  it('slots array uses evaluation_id as the unique column key', () => {
    const view = assetHeatmapDtoToDomain(makeDto(), new Map())
    // Slot key = evaluation_id (unique per run) so load-test + prod-validation
    // at the same period_start stay as distinct columns.
    expect(view.slots).toEqual(['run-1', 'run-2'])
    expect(view.slotLabels.get('run-1')).toBe('2026-04-01T00:00:00Z')
    expect(view.slotLabels.get('run-2')).toBe('2026-04-01T01:00:00Z')
  })

  it('keeps distinct columns when two runs share a period_start', () => {
    const dto = makeDto()
    // Second run shares period_start with first but has a different eval_name
    dto.columns[1].period_start = '2026-04-01T00:00:00Z'
    dto.columns[1].eval_name = 'prod-validation'
    const view = assetHeatmapDtoToDomain(dto, new Map())
    expect(view.slots).toEqual(['run-1', 'run-2'])
    expect(view.slotLabels.get('run-1')).toBe('2026-04-01T00:00:00Z')
    expect(view.slotLabels.get('run-2')).toBe('2026-04-01T00:00:00Z')
  })

  it('ECharts y-index places Overall Score at the top visually (highest y)', () => {
    const view = assetHeatmapDtoToDomain(makeDto(), new Map())
    const overallCell = view.cells.find(c => c.rowLabel === 'Overall Score')!
    const maxY = Math.max(...view.cells.map(c => c.value[1]))
    expect(overallCell.value[1]).toBe(maxY)
  })

  it('falls back to slo_name when slo_display_name is null', () => {
    // availability group has slo_display_name: null → label should be 'availability'
    const view = assetHeatmapDtoToDomain(makeDto(), new Map())
    expect(view.rows).toContain('availability')
  })

  it('emits cells for every displayRow × every column (no gaps)', () => {
    const view = assetHeatmapDtoToDomain(makeDto(), new Map([['latency', true], ['availability', true]]))
    // 1 overall + 2 headers + 2 indicators = 5 rows × 2 columns = 10 cells
    expect(view.cells.length).toBe(10)
  })
})

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
})
