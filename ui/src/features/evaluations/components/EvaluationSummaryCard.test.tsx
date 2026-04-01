import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EvaluationSummaryCard } from './EvaluationSummaryCard'
import type { EvaluationDetail } from '../types'

vi.mock('@/lib/theme-context', () => ({
  useTheme: () => ({ theme: 'current' as const, fontSize: 14 }),
}))

function makeEvaluation(overrides: Partial<EvaluationDetail> = {}): EvaluationDetail {
  return {
    id: 'eval-1',
    evaluation_id: 'run-1',
    evaluation_name: 'nightly-perf',
    status: 'completed',
    result: 'pass',
    score: 95.5,
    period_start: '2026-03-15T10:00:00Z',
    period_end: '2026-03-15T10:30:00Z',
    slo_name: 'latency-slo',
    slo_version: 2,
    sli_name: null,
    sli_version: null,
    data_source_name: null,
    ingestion_mode: 'push',
    adapter_used: 'prometheus',
    invalidated: false,
    original_result: null,
    original_score: null,
    override_reason: null,
    override_author: null,
    invalidation_note: null,
    asset_snapshot: { name: 'api-gateway', tags: { env: 'prod' } },
    evaluation_metadata: {},
    compared_evaluation_ids: [],
    annotations: [],
    indicator_results: [],
    total_score_pass_threshold: 90,
    total_score_warning_threshold: 75,
    latest_annotation: undefined,
    annotation_count: 0,
    created_at: '2026-03-15T10:30:00Z',
    ...overrides,
  }
}

describe('EvaluationSummaryCard', () => {
  it('renders evaluation name', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation()} />)
    expect(screen.getByText('nightly-perf')).toBeInTheDocument()
  })

  it('renders asset name', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation()} />)
    expect(screen.getByText('api-gateway')).toBeInTheDocument()
  })

  it('renders result badge with correct status', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation({ result: 'warning' })} />)
    expect(screen.getByText('warning')).toBeInTheDocument()
  })

  it('renders score percentage', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation({ score: 95.5 })} />)
    expect(screen.getByText('95.5%')).toBeInTheDocument()
  })

  it('renders integer score without decimal', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation({ score: 100 })} />)
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('shows invalidation card when evaluation is invalidated', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation({
      invalidated: true,
      invalidation_note: 'bad data',
    })} />)
    expect(screen.getByText('Invalidated')).toBeInTheDocument()
    expect(screen.getByText(/bad data/)).toBeInTheDocument()
  })

  it('shows invalidated as result badge when invalidated', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation({
      invalidated: true,
      invalidation_note: 'bad data',
    })} />)
    expect(screen.getByText('invalidated')).toBeInTheDocument()
  })

  it('shows override card when status is overridden', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation({
      original_result: 'fail',
      override_author: 'admin',
      override_reason: 'false positive',
    })} />)
    expect(screen.getByText('Status overridden')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText(/false positive/)).toBeInTheDocument()
  })

  it('shows original result transition in override card', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation({
      result: 'pass',
      original_result: 'fail',
      override_author: 'admin',
    })} />)
    expect(screen.getByText(/fail → pass/)).toBeInTheDocument()
  })

  it('shows re-evaluated card when original_result set without override_author', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation({
      result: 'pass',
      original_result: 'warning',
      original_score: 65.0,
      score: 85.0,
    })} />)
    expect(screen.getByText('Re-evaluated')).toBeInTheDocument()
    expect(screen.getByText(/warning → pass/)).toBeInTheDocument()
  })

  it('renders SLO info in metadata', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation({
      slo_name: 'latency-slo',
      slo_version: 3,
    })} />)
    expect(screen.getByText(/latency-slo/)).toBeInTheDocument()
    expect(screen.getByText(/v3/)).toBeInTheDocument()
  })
})
