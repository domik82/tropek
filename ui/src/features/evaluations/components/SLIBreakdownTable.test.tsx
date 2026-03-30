import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SLIBreakdownTable } from './SLIBreakdownTable'
import type { IndicatorResult, SliMetadata } from '../types'

const indicators: IndicatorResult[] = [
  {
    metric: 'response_time_p95',
    display_name: 'Response Time P95',
    value: 245.5,
    compared_value: 230.0,
    change_absolute: 15.5,
    change_relative_pct: 6.74,
    aggregation: 'p95',
    status: 'pass',
    score: 1,
    weight: 2,
    key_sli: true,
    pass_targets: [{ criteria: '<=+10%', target_value: 253, violated: false }],
    warning_targets: [{ criteria: '<=+15%', target_value: 264.5, violated: false }],
  },
  {
    metric: 'error_rate',
    display_name: 'Error Rate',
    value: 5.2,
    compared_value: 2.0,
    change_absolute: 3.2,
    change_relative_pct: 160.0,
    aggregation: 'avg',
    status: 'fail',
    score: 0,
    weight: 1,
    key_sli: false,
    pass_targets: [{ criteria: '<=+10%', target_value: 2.2, violated: true }],
    warning_targets: null,
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
    // One in header, one for the key_sli indicator
    expect(keyMarkers.length).toBeGreaterThanOrEqual(1)
  })

  it('shows pass criteria for indicators', () => {
    render(<SLIBreakdownTable indicators={indicators} />)
    const criteriaElements = screen.getAllByText(/<=\+10%/)
    expect(criteriaElements.length).toBe(2) // both indicators have <=+10%
  })

  it('calls onIndicatorClick when a row is clicked', () => {
    const onClick = vi.fn()
    render(<SLIBreakdownTable indicators={indicators} onIndicatorClick={onClick} />)
    fireEvent.click(screen.getByText('Response Time P95'))
    expect(onClick).toHaveBeenCalledWith('response_time_p95', 'summary')
  })

  it('renders metric name as clickable button when onIndicatorClick is provided', () => {
    render(<SLIBreakdownTable indicators={indicators} onIndicatorClick={vi.fn()} />)
    const button = screen.getByTitle('response_time_p95 — click to go to trend chart')
    expect(button).toBeInTheDocument()
  })

  it('renders metric name as plain text when onIndicatorClick is not provided', () => {
    render(<SLIBreakdownTable indicators={indicators} />)
    expect(screen.queryByTitle('response_time_p95 — click to go to trend chart')).not.toBeInTheDocument()
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

const aggregatedIndicators: IndicatorResult[] = [
  {
    metric: 'cpu.mean',
    display_name: 'cpu.mean',
    value: 4.3,
    compared_value: 4.1,
    change_absolute: 0.2,
    change_relative_pct: 4.88,
    aggregation: 'mean',
    status: 'pass',
    score: 1,
    weight: 1,
    key_sli: false,
    pass_targets: [{ criteria: '<10', target_value: 10, violated: false }],
    warning_targets: null,
  },
  {
    metric: 'cpu.p99',
    display_name: 'cpu.p99',
    value: 18.7,
    compared_value: 17.0,
    change_absolute: 1.7,
    change_relative_pct: 10.0,
    aggregation: 'p99',
    status: 'pass',
    score: 1,
    weight: 2,
    key_sli: true,
    pass_targets: [{ criteria: '<25', target_value: 25, violated: false }],
    warning_targets: null,
  },
  {
    metric: 'cpu.max',
    display_name: 'cpu.max',
    value: 31.2,
    compared_value: 28.0,
    change_absolute: 3.2,
    change_relative_pct: 11.43,
    aggregation: 'max',
    status: 'pass',
    score: 1,
    weight: 1,
    key_sli: false,
    pass_targets: [{ criteria: '<40', target_value: 40, violated: false }],
    warning_targets: null,
  },
  {
    metric: 'error_rate',
    display_name: 'Error Rate',
    value: 0.02,
    compared_value: 0.01,
    change_absolute: 0.01,
    change_relative_pct: 100.0,
    aggregation: 'avg',
    status: 'pass',
    score: 1,
    weight: 3,
    key_sli: false,
    pass_targets: [{ criteria: '<0.05', target_value: 0.05, violated: false }],
    warning_targets: null,
  },
]

const sliMetadata: Record<string, SliMetadata> = {
  cpu: {
    mode: 'aggregated',
    expected_samples: 1440,
    actual_samples: 1387,
    missing_pct: 3.7,
    chunks_failed: 0,
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

  it('shows low-confidence warning when missing_pct exceeds threshold', () => {
    const highMissing: Record<string, SliMetadata> = {
      cpu: { ...sliMetadata.cpu, missing_pct: 25.0 },
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
