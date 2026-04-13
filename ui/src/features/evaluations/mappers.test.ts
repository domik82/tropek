import { describe, it, expect } from 'vitest'
import type { EvaluationSummaryDto, EvaluationDetailDto } from './mappers'
import {
  dtoToEvaluationSummary,
  dtoToEvaluationDetail,
  dtoToEvaluationList,
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
