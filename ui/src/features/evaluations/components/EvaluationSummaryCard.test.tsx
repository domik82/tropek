import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EvaluationSummaryCard } from './EvaluationSummaryCard'
import type { EvaluationDetail } from '../domain'

vi.mock('@/lib/theme-context', () => ({
  useTheme: () => ({ theme: 'current' as const, fontSize: 14 }),
}))

function makeEvaluation(overrides: Partial<EvaluationDetail> = {}): EvaluationDetail {
  return {
    id: 'eval-1',
    evaluationId: 'run-1',
    evaluationName: 'nightly-perf',
    status: 'completed',
    outcome: 'pass',
    score: 95.5,
    period: { from: '2026-03-15T10:00:00Z', to: '2026-03-15T10:30:00Z' },
    sloName: 'latency-slo',
    sloVersion: 2,
    sliName: null,
    sliVersion: null,
    dataSourceName: null,
    ingestionMode: 'push',
    adapterUsed: 'prometheus',
    invalidated: false,
    originalOutcome: null,
    originalScore: null,
    overrideReason: null,
    overrideAuthor: null,
    invalidationNote: null,
    assetSnapshot: {
      name: 'api-gateway',
      displayName: null,
      tags: { env: 'prod' },
      primaryVersion: null,
      buildRef: null,
    },
    variables: {},
    baselinePin: null,
    comparedEvaluationIds: [],
    annotations: [],
    indicators: [],
    totalScorePassThreshold: 90,
    totalScoreWarningThreshold: 75,
    sliMetadata: {},
    latestAnnotation: null,
    annotationCount: 0,
    createdAt: new Date('2026-03-15T10:30:00Z'),
    topFailures: [],
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
    render(<EvaluationSummaryCard evaluation={makeEvaluation({ outcome: 'warning' })} />)
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
      outcome: 'invalidated',
      invalidationNote: 'bad data',
    })} />)
    expect(screen.getByText('Invalidated')).toBeInTheDocument()
    expect(screen.getByText(/bad data/)).toBeInTheDocument()
  })

  it('shows invalidated as result badge when invalidated', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation({
      invalidated: true,
      outcome: 'invalidated',
      invalidationNote: 'bad data',
    })} />)
    expect(screen.getByText('invalidated')).toBeInTheDocument()
  })

  it('shows override card when status is overridden', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation({
      originalOutcome: 'fail',
      overrideAuthor: 'admin',
      overrideReason: 'false positive',
    })} />)
    expect(screen.getByText('Status overridden')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText(/false positive/)).toBeInTheDocument()
  })

  it('shows original result transition in override card', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation({
      outcome: 'pass',
      originalOutcome: 'fail',
      overrideAuthor: 'admin',
    })} />)
    expect(screen.getByText(/fail → pass/)).toBeInTheDocument()
  })

  it('shows re-evaluated card when originalOutcome set without overrideAuthor', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation({
      outcome: 'pass',
      originalOutcome: 'warning',
      originalScore: 65.0,
      score: 85.0,
    })} />)
    expect(screen.getByText('Re-evaluated')).toBeInTheDocument()
    expect(screen.getByText(/warning → pass/)).toBeInTheDocument()
  })

  it('renders SLO info in metadata', () => {
    render(<EvaluationSummaryCard evaluation={makeEvaluation({
      sloName: 'latency-slo',
      sloVersion: 3,
    })} />)
    expect(screen.getByText(/latency-slo/)).toBeInTheDocument()
    expect(screen.getByText(/v3/)).toBeInTheDocument()
  })
})
