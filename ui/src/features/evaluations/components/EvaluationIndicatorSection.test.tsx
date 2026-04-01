import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EvaluationIndicatorSection } from './EvaluationIndicatorSection'
import type { EvaluationDetail, IndicatorResult } from '../types'

vi.mock('@/lib/theme-context', () => ({
  useTheme: () => ({ theme: 'current' as const, fontSize: 14 }),
}))

vi.mock('./MetricTrendBlock', () => ({
  MetricTrendBlock: ({ indicator }: { indicator: IndicatorResult }) => (
    <div data-testid={`trend-${indicator.metric}`}>{indicator.display_name} trend</div>
  ),
}))

function makeIndicator(overrides: Partial<IndicatorResult> = {}): IndicatorResult {
  return {
    metric: 'response_time',
    display_name: 'Response Time',
    value: 100,
    compared_value: null,
    change_absolute: null,
    change_relative_pct: null,
    aggregation: 'avg',
    status: 'pass',
    score: 1,
    weight: 1,
    key_sli: false,
    pass_targets: null,
    warning_targets: null,
    ...overrides,
  }
}

function makeEval(indicators: IndicatorResult[]): EvaluationDetail {
  return {
    id: 'eval-1',
    evaluation_id: 'run-1',
    evaluation_name: 'nightly-perf',
    status: 'completed',
    result: 'pass',
    score: 95,
    period_start: '2026-03-15T10:00:00Z',
    period_end: '2026-03-15T10:30:00Z',
    slo_name: null,
    slo_version: null,
    sli_name: null,
    sli_version: null,
    data_source_name: null,
    ingestion_mode: 'push',
    adapter_used: null,
    invalidated: false,
    original_result: null,
    original_score: null,
    override_reason: null,
    override_author: null,
    invalidation_note: null,
    asset_snapshot: { name: 'api-gateway', tags: {} },
    evaluation_metadata: {},
    compared_evaluation_ids: [],
    annotations: [],
    indicator_results: indicators,
    total_score_pass_threshold: 90,
    total_score_warning_threshold: 75,
    created_at: '2026-03-15T10:30:00Z',
  }
}

describe('EvaluationIndicatorSection', () => {
  it('renders SLI Breakdown heading', () => {
    const ev = makeEval([makeIndicator()])
    render(<EvaluationIndicatorSection evaluation={ev} />)
    expect(screen.getByText('SLI Breakdown')).toBeInTheDocument()
  })

  it('renders tab bar with available groups', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tab_group: 'latency', display_name: 'Latency A' }),
      makeIndicator({ metric: 'b', tab_group: 'throughput', display_name: 'Throughput B' }),
    ]
    const ev = makeEval(indicators)
    render(<EvaluationIndicatorSection evaluation={ev} />)
    // "All" appears in both the tab bar and the trend description — use getAllByText
    expect(screen.getAllByText('All').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Latency')).toBeInTheDocument()
    expect(screen.getByText('Throughput')).toBeInTheDocument()
  })

  it('renders SLI breakdown table rows', () => {
    const indicators = [
      makeIndicator({ metric: 'a', display_name: 'Metric A' }),
      makeIndicator({ metric: 'b', display_name: 'Metric B' }),
    ]
    const ev = makeEval(indicators)
    render(<EvaluationIndicatorSection evaluation={ev} />)
    expect(screen.getByText('Metric A')).toBeInTheDocument()
    expect(screen.getByText('Metric B')).toBeInTheDocument()
  })

  it('switches tab when tab button clicked', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tab_group: 'latency', display_name: 'Latency A' }),
      makeIndicator({ metric: 'b', tab_group: 'throughput', display_name: 'Throughput B' }),
    ]
    const ev = makeEval(indicators)
    render(<EvaluationIndicatorSection evaluation={ev} />)

    // Click the Latency tab
    fireEvent.click(screen.getByText('Latency'))

    // Only latency indicator should be shown in the table
    expect(screen.getByText('Latency A')).toBeInTheDocument()
    // Throughput should not be in the breakdown table
    // (It may still appear as a tab label, so check the trend blocks)
    expect(screen.queryByTestId('trend-b')).not.toBeInTheDocument()
    expect(screen.getByTestId('trend-a')).toBeInTheDocument()
  })

  it('shows all indicators when no groups defined', () => {
    const indicators = [
      makeIndicator({ metric: 'a', display_name: 'Metric A' }),
      makeIndicator({ metric: 'b', display_name: 'Metric B' }),
    ]
    const ev = makeEval(indicators)
    render(<EvaluationIndicatorSection evaluation={ev} />)
    expect(screen.getByText('Metric A')).toBeInTheDocument()
    expect(screen.getByText('Metric B')).toBeInTheDocument()
  })

  it('renders trend blocks for each visible indicator', () => {
    const indicators = [
      makeIndicator({ metric: 'rt', display_name: 'Response Time' }),
      makeIndicator({ metric: 'tp', display_name: 'Throughput' }),
    ]
    const ev = makeEval(indicators)
    render(<EvaluationIndicatorSection evaluation={ev} />)
    expect(screen.getByTestId('trend-rt')).toBeInTheDocument()
    expect(screen.getByTestId('trend-tp')).toBeInTheDocument()
  })
})
