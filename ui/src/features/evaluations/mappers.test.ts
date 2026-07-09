import { describe, it, expect } from 'vitest'
import type {
  EvaluationSummaryDto,
  EvaluationDetailDto,
  IndicatorResultDto,
  AnnotationDto,
  TrendPointDto,
  EvaluationNameEntryDto,
} from './mappers'
import {
  dtoToEvaluationSummary,
  dtoToEvaluationDetail,
  dtoToEvaluationList,
  dtoToIndicator,
  dtoToAnnotation,
  dtoToTrendPoint,
  dtoToEvaluationNameEntry,
  dtoToReEvaluateResponse,
  triggerEvaluationInputToDto,
  reEvaluateInputToDto,
  overrideStatusInputToDto,
} from './mappers'

function makeSummaryDto(overrides: Partial<EvaluationSummaryDto> = {}): EvaluationSummaryDto {
  return {
    id: '00000000-0000-0000-0000-000000000001',
    evaluation_id: '00000000-0000-0000-0000-000000000002',
    evaluation_name: 'perf-test-linux',
    status: 'completed',
    result: 'pass',
    score: 92.5,
    period_start: '2026-03-15T10:00:00Z',
    period_end: '2026-03-15T10:30:00Z',
    slo_name: 'latency-p95',
    slo_version: 3,
    sli_name: null,
    sli_version: null,
    data_source_name: 'prometheus',
    ingestion_mode: 'streaming',
    adapter_used: 'prometheus',
    invalidated: false,
    original_result: null,
    original_score: null,
    override_reason: null,
    override_author: null,
    asset_snapshot: {
      asset_id: '550e8400-e29b-41d4-a716-446655440000',
      name: 'checkout',
      display_name: 'Checkout Service',
      tags: { team: 'payments' },
      primary_version: '1.4.2',
      build_ref: 'sha-abc',
    },
    variables: { env: 'prod' },
    latest_annotation: null,
    annotation_count: 0,
    created_at: '2026-03-15T10:31:00Z',
    top_failures: [],
    ...overrides,
  }
}

describe('dtoToEvaluationSummary', () => {
  it('converts snake_case DTO to camelCase domain', () => {
    const result = dtoToEvaluationSummary(makeSummaryDto())
    expect(result.id).toBe('00000000-0000-0000-0000-000000000001')
    expect(result.evaluationName).toBe('perf-test-linux')
    expect(result.outcome).toBe('pass')
    expect(result.period.from).toBe('2026-03-15T10:00:00Z')
    expect(result.period.to).toBe('2026-03-15T10:30:00Z')
    expect(result.sloName).toBe('latency-p95')
    expect(result.assetSnapshot.assetId).toBe('550e8400-e29b-41d4-a716-446655440000')
    expect(result.assetSnapshot.displayName).toBe('Checkout Service')
    expect(result.assetSnapshot.primaryVersion).toBe('1.4.2')
    expect(result.baselinePin).toBeNull()
    expect(result.createdAt).toBeInstanceOf(Date)
  })

  it('collapses (result, invalidated) into invalidated outcome', () => {
    const dto = makeSummaryDto({ result: 'pass', invalidated: true })
    expect(dtoToEvaluationSummary(dto).outcome).toBe('invalidated')
  })

  it('maps null result to error outcome', () => {
    const dto = makeSummaryDto({ result: null, invalidated: false })
    expect(dtoToEvaluationSummary(dto).outcome).toBe('error')
  })

  it('builds BaselinePin struct when baseline_pinned_at is set', () => {
    const dto = makeSummaryDto({
      baseline_pin_author: 'alice',
      baseline_pin_reason: 'regression baseline',
      baseline_pinned_at: '2026-03-15T11:00:00Z',
      baseline_unpinned_at: null,
    })
    const domain = dtoToEvaluationSummary(dto)
    expect(domain.baselinePin).not.toBeNull()
    expect(domain.baselinePin!.author).toBe('alice')
    expect(domain.baselinePin!.reason).toBe('regression baseline')
    expect(domain.baselinePin!.pinnedAt).toBeInstanceOf(Date)
    expect(domain.baselinePin!.unpinnedAt).toBeNull()
  })

  it('returns null baselinePin when pinned_at is absent', () => {
    const dto = makeSummaryDto({ baseline_pinned_at: null })
    expect(dtoToEvaluationSummary(dto).baselinePin).toBeNull()
  })
})

describe('dtoToEvaluationDetail', () => {
  it('passes summary fields through and adds detail fields', () => {
    const dto: EvaluationDetailDto = {
      ...makeSummaryDto(),
      invalidation_note: null,
      compared_evaluation_ids: ['eval-a', 'eval-b'],
      annotations: [],
      indicator_results: [],
      total_score_pass_threshold: 90,
      total_score_warning_threshold: 75,
      sli_metadata: null,
    }
    const domain = dtoToEvaluationDetail(dto)
    expect(domain.comparedEvaluationIds).toEqual(['eval-a', 'eval-b'])
    expect(domain.totalScorePassThreshold).toBe(90)
    expect(domain.sliMetadata).toEqual({})
    expect(domain.evaluationName).toBe('perf-test-linux')
  })
})

describe('dtoToEvaluationList', () => {
  it('maps items and passes total/truncated through', () => {
    const list = dtoToEvaluationList({
      items: [makeSummaryDto(), makeSummaryDto({ id: 'id-2' })],
      total: 17,
      truncated: true,
    })
    expect(list.items).toHaveLength(2)
    expect(list.items[1].id).toBe('id-2')
    expect(list.total).toBe(17)
    expect(list.truncated).toBe(true)
  })
})

describe('dtoToIndicator', () => {
  it('converts PassTargets camelCase and keeps criteria as display string', () => {
    const dto: IndicatorResultDto = {
      metric: 'latency_p95',
      display_name: 'P95 Latency',
      tab_group: 'latency',
      value: 412.3,
      compared_value: 400,
      change_absolute: 12.3,
      change_relative_pct: 3.075,
      aggregation: 'p95',
      status: 'pass',
      score: 95,
      weight: 1,
      key_sli: true,
      pass_targets: [{ criteria: '<600', target_value: 600, violated: false }],
      warning_targets: [{ criteria: '<=+10%', target_value: 440, violated: false }],
    }
    const domain = dtoToIndicator(dto)
    expect(domain.displayName).toBe('P95 Latency')
    expect(domain.keySli).toBe(true)
    expect(domain.changeRelativePct).toBeCloseTo(3.075)
    expect(domain.passTargets[0]).toEqual({ criteria: '<600', targetValue: 600, violated: false })
    expect(domain.warningTargets[0].targetValue).toBe(440)
  })

  it('maps a change point with a local relative pct and no transition', () => {
    const dto: IndicatorResultDto = {
      metric: 'latency_p95',
      display_name: 'P95 Latency',
      tab_group: null,
      value: 412.3,
      compared_value: 400,
      change_absolute: 12.3,
      change_relative_pct: 3.075,
      aggregation: 'p95',
      status: 'pass',
      score: 95,
      weight: 1,
      key_sli: true,
      pass_targets: [],
      warning_targets: [],
      change_point: { direction: 'regression', change_relative_pct: 15.7, change_absolute: 12.3 },
    }
    const domain = dtoToIndicator(dto)
    expect(domain.changePoint).toEqual({
      direction: 'regression',
      changeRelativePct: 15.7,
      transition: null,
      changeAbsolute: 12.3,
    })
  })

  it('maps a change point with a null pct and an appeared transition', () => {
    const dto: IndicatorResultDto = {
      metric: 'latency_p95',
      display_name: 'P95 Latency',
      tab_group: null,
      value: 412.3,
      compared_value: 400,
      change_absolute: 12.3,
      change_relative_pct: 3.075,
      aggregation: 'p95',
      status: 'pass',
      score: 95,
      weight: 1,
      key_sli: true,
      pass_targets: [],
      warning_targets: [],
      change_point: { direction: 'regression', change_relative_pct: null, transition: 'appeared', change_absolute: 500 },
    }
    const domain = dtoToIndicator(dto)
    expect(domain.changePoint).toEqual({
      direction: 'regression',
      changeRelativePct: null,
      transition: 'appeared',
      changeAbsolute: 500,
    })
  })

  it('normalizes null pass_targets / warning_targets to empty arrays', () => {
    const dto: IndicatorResultDto = {
      metric: 'm',
      display_name: 'M',
      tab_group: null,
      value: 1,
      compared_value: null,
      change_absolute: null,
      change_relative_pct: null,
      aggregation: null,
      status: 'pass',
      score: 100,
      weight: 1,
      key_sli: false,
      pass_targets: null,
      warning_targets: null,
    }
    const domain = dtoToIndicator(dto)
    expect(domain.passTargets).toEqual([])
    expect(domain.warningTargets).toEqual([])
  })
})

describe('dtoToAnnotation', () => {
  it('parses dates and normalizes nullable fields', () => {
    const dto: AnnotationDto = {
      id: 'ann-1',
      slo_evaluation_id: null,
      evaluation_run_id: 'run-1',
      content: 'flaky run',
      author: 'bob',
      category_id: 'cat-1',
      category: {
        id: 'cat-1',
        name: 'flake',
        label: 'Flake',
        color: 'amber',
        show_on_graph: true,
        is_system: false,
        created_at: '2026-03-01T00:00:00Z',
        updated_at: null,
      },
      tags: { source: 'ui' },
      note_group_id: null,
      note_group_name: null,
      hidden_at: null,
      hidden_by: null,
      hidden_reason: null,
      created_at: '2026-03-15T11:00:00Z',
      updated_at: null,
    }
    const domain = dtoToAnnotation(dto)
    expect(domain.id).toBe('ann-1')
    expect(domain.evaluationRunId).toBe('run-1')
    expect(domain.sloEvaluationId).toBeNull()
    expect(domain.createdAt).toBeInstanceOf(Date)
    expect(domain.updatedAt).toBeNull()
    expect(domain.hiddenAt).toBeNull()
  })
})

describe('dtoToTrendPoint', () => {
  it('parses timestamp to Date and maps result to outcome', () => {
    const dto: TrendPointDto = {
      timestamp: '2026-03-15T12:00:00Z',
      value: 120,
      score: 88,
      eval_id: 'eval-1',
      result: 'warning',
      baseline: 100,
      evaluation_name: 'perf',
      targets: {
        pass: [{ criteria: '<100', target_value: 100, violated: false }],
        warn: null,
      },
    }
    const domain = dtoToTrendPoint(dto)
    expect(domain.timestamp).toBeInstanceOf(Date)
    expect(domain.outcome).toBe('warning')
    expect(domain.targets?.pass[0].targetValue).toBe(100)
    expect(domain.targets?.warn).toEqual([])
  })

  it('maps a vanished-transition change point with a null pct', () => {
    const dto: TrendPointDto = {
      timestamp: '2026-03-15T12:00:00Z',
      value: 0,
      score: 0,
      eval_id: 'eval-1',
      result: 'fail',
      baseline: 100,
      evaluation_name: 'perf',
      change_point: { direction: 'regression', change_relative_pct: null, transition: 'vanished', change_absolute: -13_300_000 },
    }
    const domain = dtoToTrendPoint(dto)
    expect(domain.changePoint).toEqual({
      direction: 'regression',
      changeRelativePct: null,
      transition: 'vanished',
      changeAbsolute: -13_300_000,
    })
  })
})

describe('dtoToEvaluationNameEntry', () => {
  it('parses last_run to Date', () => {
    const dto: EvaluationNameEntryDto = {
      name: 'perf',
      count: 5,
      last_run: '2026-03-15T13:00:00Z',
    }
    const domain = dtoToEvaluationNameEntry(dto)
    expect(domain.lastRun).toBeInstanceOf(Date)
    expect(domain.count).toBe(5)
  })
})

describe('dtoToReEvaluateResponse', () => {
  it('camelCases results and collapses result strings to Outcome', () => {
    const domain = dtoToReEvaluateResponse({
      affected_evaluations: 2,
      slo_version_used: 4,
      results: [{
        id: 'e1',
        evaluation_name: 'perf',
        slo_name: 'latency-p95',
        slo_version: 4,
        period_start: '2026-03-15T10:00:00Z',
        period_end: '2026-03-15T10:30:00Z',
        old_result: 'fail',
        new_result: 'pass',
        old_score: 40,
        new_score: 92,
      }],
    })
    expect(domain.affectedEvaluations).toBe(2)
    expect(domain.sloVersionUsed).toBe(4)
    expect(domain.results[0].sloName).toBe('latency-p95')
    expect(domain.results[0].sloVersion).toBe(4)
    expect(domain.results[0].period.from).toBe('2026-03-15T10:00:00Z')
    expect(domain.results[0].oldOutcome).toBe('fail')
    expect(domain.results[0].newOutcome).toBe('pass')
  })
})

describe('triggerEvaluationInputToDto', () => {
  it('flattens period DateRange into period_start/period_end', () => {
    const dto = triggerEvaluationInputToDto({
      assetName: 'checkout',
      evalName: 'perf-linux',
      period: { from: '2026-03-15T10:00:00Z', to: '2026-03-15T10:30:00Z' },
      variables: { env: 'prod' },
    })
    expect(dto.asset_name).toBe('checkout')
    expect(dto.eval_name).toBe('perf-linux')
    expect(dto.period_start).toBe('2026-03-15T10:00:00Z')
    expect(dto.period_end).toBe('2026-03-15T10:30:00Z')
    expect(dto.variables).toEqual({ env: 'prod' })
  })
})

describe('reEvaluateInputToDto', () => {
  it('maps baseline mode to from-baseline endpoint with scope+selector', () => {
    const result = reEvaluateInputToDto({
      assetName: 'a', sloName: 's', sloNames: null,
      mode: { kind: 'baseline' },
      sloVersion: null, dryRun: false, pinStrategy: null,
    })
    expect(result.endpoint).toBe('/evaluations/re-evaluate/from-baseline')
    expect(result.requestBody.scope).toEqual({ kind: 'asset', asset_name: 'a' })
    expect(result.requestBody.selector).toEqual({ kind: 'slo', slo_name: 's' })
  })

  it('maps date mode to from-date endpoint with from_date in body', () => {
    const result = reEvaluateInputToDto({
      assetName: 'a', sloName: 's', sloNames: null,
      mode: { kind: 'date', fromDate: '2026-03-10T00:00:00Z' },
      sloVersion: 2, dryRun: true, pinStrategy: 'skip_to_pin',
    })
    expect(result.endpoint).toBe('/evaluations/re-evaluate/from-date')
    if (result.endpoint === '/evaluations/re-evaluate/from-date') {
      expect(result.requestBody.from_date).toBe('2026-03-10T00:00:00Z')
      expect(result.requestBody.slo_version).toBe(2)
      expect(result.requestBody.dry_run).toBe(true)
    }
  })

  it('maps evaluation mode to from-evaluation endpoint with id in path', () => {
    const result = reEvaluateInputToDto({
      assetName: 'a', sloName: 's', sloNames: null,
      mode: { kind: 'evaluation', fromEvaluationId: 'eval-7' },
      sloVersion: null, dryRun: false, pinStrategy: null,
    })
    expect(result.endpoint).toBe('/evaluations/re-evaluate/from-evaluation/eval-7')
    expect(result.requestBody.scope).toEqual({ kind: 'asset', asset_name: 'a' })
  })
})

describe('overrideStatusInputToDto', () => {
  it('converts Outcome enum to new_result string', () => {
    const dto = overrideStatusInputToDto({ outcome: 'pass', reason: 'flaky infra', author: 'alice' })
    expect(dto.new_result).toBe('pass')
    expect(dto.reason).toBe('flaky infra')
    expect(dto.author).toBe('alice')
  })
})
