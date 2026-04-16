import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EvaluationIndicatorSection } from './EvaluationIndicatorSection'
import type { EvaluationDetail, Indicator } from '../domain'

vi.mock('@/lib/theme-context', () => ({
  useTheme: () => ({ theme: 'current' as const, fontSize: 14 }),
}))

vi.mock('./MetricTrendBlock', () => ({
  MetricTrendBlock: ({ indicator }: { indicator: Indicator }) => (
    <div data-testid={`trend-${indicator.metric}`}>{indicator.displayName} trend</div>
  ),
}))

function makeIndicator(overrides: Partial<Indicator> = {}): Indicator {
  return {
    metric: 'response_time',
    displayName: 'Response Time',
    tabGroup: null,
    value: 100,
    comparedValue: null,
    changeAbsolute: null,
    changeRelativePct: null,
    aggregation: 'avg',
    status: 'pass',
    score: 1,
    weight: 1,
    keySli: false,
    passTargets: [],
    warningTargets: [],
    ...overrides,
  }
}

function makeEval(indicators: Indicator[]): EvaluationDetail {
  return {
    id: 'eval-1',
    evaluationId: 'run-1',
    evaluationName: 'nightly-perf',
    status: 'completed',
    outcome: 'pass',
    score: 95,
    period: { from: '2026-03-15T10:00:00Z', to: '2026-03-15T10:30:00Z' },
    sloName: null,
    sloVersion: null,
    sliName: null,
    sliVersion: null,
    dataSourceName: null,
    ingestionMode: 'push',
    adapterUsed: null,
    invalidated: false,
    originalOutcome: null,
    originalScore: null,
    overrideReason: null,
    overrideAuthor: null,
    invalidationNote: null,
    assetSnapshot: {
      assetId: null,
      name: 'api-gateway',
      displayName: null,
      tags: {},
      primaryVersion: null,
      buildRef: null,
    },
    variables: {},
    baselinePin: null,
    comparedEvaluationIds: [],
    annotations: [],
    indicators,
    totalScorePassThreshold: 90,
    totalScoreWarningThreshold: 75,
    sliMetadata: {},
    latestAnnotation: null,
    annotationCount: 0,
    createdAt: new Date('2026-03-15T10:30:00Z'),
    topFailures: [],
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
      makeIndicator({ metric: 'a', tabGroup: 'latency', displayName: 'Latency A' }),
      makeIndicator({ metric: 'b', tabGroup: 'throughput', displayName: 'Throughput B' }),
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
      makeIndicator({ metric: 'a', displayName: 'Metric A' }),
      makeIndicator({ metric: 'b', displayName: 'Metric B' }),
    ]
    const ev = makeEval(indicators)
    render(<EvaluationIndicatorSection evaluation={ev} />)
    expect(screen.getByText('Metric A')).toBeInTheDocument()
    expect(screen.getByText('Metric B')).toBeInTheDocument()
  })

  it('switches tab when tab button clicked', () => {
    const indicators = [
      makeIndicator({ metric: 'a', tabGroup: 'latency', displayName: 'Latency A' }),
      makeIndicator({ metric: 'b', tabGroup: 'throughput', displayName: 'Throughput B' }),
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
      makeIndicator({ metric: 'a', displayName: 'Metric A' }),
      makeIndicator({ metric: 'b', displayName: 'Metric B' }),
    ]
    const ev = makeEval(indicators)
    render(<EvaluationIndicatorSection evaluation={ev} />)
    expect(screen.getByText('Metric A')).toBeInTheDocument()
    expect(screen.getByText('Metric B')).toBeInTheDocument()
  })

  it('renders trend blocks for each visible indicator', () => {
    const indicators = [
      makeIndicator({ metric: 'rt', displayName: 'Response Time' }),
      makeIndicator({ metric: 'tp', displayName: 'Throughput' }),
    ]
    const ev = makeEval(indicators)
    render(<EvaluationIndicatorSection evaluation={ev} />)
    expect(screen.getByTestId('trend-rt')).toBeInTheDocument()
    expect(screen.getByTestId('trend-tp')).toBeInTheDocument()
  })
})
