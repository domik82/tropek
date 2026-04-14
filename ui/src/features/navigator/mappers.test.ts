import { describe, it, expect } from 'vitest'
import { assetHeatmapDtoToDomain } from './mappers'
import type { GroupedMetricHeatmapResponseDto } from './mappers'

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
