import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SLIBreakdownTable } from './SLIBreakdownTable'
import type { Indicator, SliMetadata } from '../domain'

const indicators: Indicator[] = [
  {
    metric: 'response_time_p95',
    displayName: 'Response Time P95',
    tabGroup: null,
    value: 245.5,
    comparedValue: 230.0,
    changeAbsolute: 15.5,
    changeRelativePct: 6.74,
    aggregation: 'p95',
    status: 'pass',
    score: 1,
    weight: 2,
    keySli: true,
    passTargets: [{ criteria: '<=+10%', targetValue: 253, violated: false }],
    warningTargets: [{ criteria: '<=+15%', targetValue: 264.5, violated: false }],
  },
  {
    metric: 'error_rate',
    displayName: 'Error Rate',
    tabGroup: null,
    value: 5.2,
    comparedValue: 2.0,
    changeAbsolute: 3.2,
    changeRelativePct: 160.0,
    aggregation: 'avg',
    status: 'fail',
    score: 0,
    weight: 1,
    keySli: false,
    passTargets: [{ criteria: '<=+10%', targetValue: 2.2, violated: true }],
    warningTargets: [],
  },
]

describe('SLIBreakdownTable', () => {
  it('renders a row for each indicator result', () => {
    render(<SLIBreakdownTable indicators={indicators} />)
    expect(screen.getByText('Response Time P95')).toBeInTheDocument()
    expect(screen.getByText('Error Rate')).toBeInTheDocument()
  })

  it('shows metric value and compared value', () => {
    render(<SLIBreakdownTable indicators={indicators} />)
    expect(screen.getByText('245.50')).toBeInTheDocument()
    expect(screen.getByText('230.00')).toBeInTheDocument()
  })

  it('shows status text for each indicator', () => {
    render(<SLIBreakdownTable indicators={indicators} />)
    expect(screen.getByText('pass')).toBeInTheDocument()
    expect(screen.getByText('fail')).toBeInTheDocument()
  })

  it('shows key SLI marker for key indicators', () => {
    render(<SLIBreakdownTable indicators={indicators} />)
    const keyMarkers = screen.getAllByTitle('Key SLI')
    // One in header, one for the keySli indicator
    expect(keyMarkers.length).toBeGreaterThanOrEqual(1)
  })

  it('shows pass criteria for indicators', () => {
    render(<SLIBreakdownTable indicators={indicators} />)
    const criteriaElements = screen.getAllByText(/<=\+10%/)
    expect(criteriaElements.length).toBe(2) // both indicators have <=+10%
  })

  it('calls onIndicatorClick when trend button is clicked', () => {
    const onClick = vi.fn()
    render(<SLIBreakdownTable indicators={indicators} onIndicatorClick={onClick} />)
    fireEvent.click(screen.getAllByTitle('Go to trend chart')[0])
    expect(onClick).toHaveBeenCalledWith('response_time_p95', 'summary')
  })

  it('renders trend button when onIndicatorClick is provided', () => {
    render(<SLIBreakdownTable indicators={indicators} onIndicatorClick={vi.fn()} />)
    const button = screen.getAllByTitle('Go to trend chart')
    expect(button.length).toBeGreaterThan(0)
  })

  it('renders metric name as plain text without trend button when onIndicatorClick is not provided', () => {
    render(<SLIBreakdownTable indicators={indicators} />)
    expect(screen.queryByTitle('Go to trend chart')).not.toBeInTheDocument()
    expect(screen.getByText('Response Time P95')).toBeInTheDocument()
  })

  it('handles empty indicator results', () => {
    render(<SLIBreakdownTable indicators={[]} />)
    expect(screen.getByText('Indicator')).toBeInTheDocument()
    expect(screen.queryByRole('row')).toBeInTheDocument() // header row
  })

  it('shows weight and score columns', () => {
    render(<SLIBreakdownTable indicators={indicators} />)
    expect(screen.getByText('Weight')).toBeInTheDocument()
    expect(screen.getByText('Score')).toBeInTheDocument()
  })

  it('shows relative change percentage', () => {
    render(<SLIBreakdownTable indicators={indicators} />)
    expect(screen.getByText('+6.74%')).toBeInTheDocument()
    expect(screen.getByText('+160.00%')).toBeInTheDocument()
  })
})

const aggregatedIndicators: Indicator[] = [
  {
    metric: 'cpu.mean',
    displayName: 'cpu.mean',
    tabGroup: null,
    value: 4.3,
    comparedValue: 4.1,
    changeAbsolute: 0.2,
    changeRelativePct: 4.88,
    aggregation: 'mean',
    status: 'pass',
    score: 1,
    weight: 1,
    keySli: false,
    passTargets: [{ criteria: '<10', targetValue: 10, violated: false }],
    warningTargets: [],
  },
  {
    metric: 'cpu.p99',
    displayName: 'cpu.p99',
    tabGroup: null,
    value: 18.7,
    comparedValue: 17.0,
    changeAbsolute: 1.7,
    changeRelativePct: 10.0,
    aggregation: 'p99',
    status: 'pass',
    score: 1,
    weight: 2,
    keySli: true,
    passTargets: [{ criteria: '<25', targetValue: 25, violated: false }],
    warningTargets: [],
  },
  {
    metric: 'cpu.max',
    displayName: 'cpu.max',
    tabGroup: null,
    value: 31.2,
    comparedValue: 28.0,
    changeAbsolute: 3.2,
    changeRelativePct: 11.43,
    aggregation: 'max',
    status: 'pass',
    score: 1,
    weight: 1,
    keySli: false,
    passTargets: [{ criteria: '<40', targetValue: 40, violated: false }],
    warningTargets: [],
  },
  {
    metric: 'error_rate',
    displayName: 'Error Rate',
    tabGroup: null,
    value: 0.02,
    comparedValue: 0.01,
    changeAbsolute: 0.01,
    changeRelativePct: 100.0,
    aggregation: 'avg',
    status: 'pass',
    score: 1,
    weight: 3,
    keySli: false,
    passTargets: [{ criteria: '<0.05', targetValue: 0.05, violated: false }],
    warningTargets: [],
  },
]

const sliMetadata: Record<string, SliMetadata> = {
  cpu: {
    mode: 'aggregated',
    expectedSamples: 1440,
    actualSamples: 1387,
    missingPct: 3.7,
    chunksFailed: 0,
  },
}

describe('SLIBreakdownTable grouped display', () => {
  it('renders a group header for aggregated SLI metrics', () => {
    render(
      <SLIBreakdownTable
        indicators={aggregatedIndicators}
        sliMetadata={sliMetadata}
      />,
    )
    expect(screen.getByText(/cpu/)).toBeInTheDocument()
    expect(screen.getByText(/1387.*1440/)).toBeInTheDocument()
  })

  it('renders ungrouped rows for non-aggregated metrics', () => {
    render(
      <SLIBreakdownTable
        indicators={aggregatedIndicators}
        sliMetadata={sliMetadata}
      />,
    )
    expect(screen.getByText('Error Rate')).toBeInTheDocument()
  })

  it('shows method suffix in grouped rows instead of full metric name', () => {
    render(
      <SLIBreakdownTable
        indicators={aggregatedIndicators}
        sliMetadata={sliMetadata}
      />,
    )
    expect(screen.getByText('mean')).toBeInTheDocument()
    expect(screen.getByText('p99')).toBeInTheDocument()
    expect(screen.getByText('max')).toBeInTheDocument()
  })

  it('shows low-confidence warning when missingPct exceeds threshold', () => {
    const highMissing: Record<string, SliMetadata> = {
      cpu: { ...sliMetadata.cpu, missingPct: 25.0 },
    }
    render(
      <SLIBreakdownTable
        indicators={aggregatedIndicators}
        sliMetadata={highMissing}
      />,
    )
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument()
  })

  it('works without sliMetadata (backward compatible)', () => {
    render(<SLIBreakdownTable indicators={aggregatedIndicators} />)
    expect(screen.getByText('cpu.mean')).toBeInTheDocument()
    expect(screen.getByText('Error Rate')).toBeInTheDocument()
  })
})
