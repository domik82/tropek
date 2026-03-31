import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SLIBreakdownGrouped } from './SLIBreakdownGrouped'
import type { IndicatorResult } from '../types'

const IND: IndicatorResult = {
  metric: 'error_rate',
  display_name: 'Error Rate',
  tab_group: undefined,
  value: 0.02,
  compared_value: 0.03,
  change_absolute: -0.01,
  change_relative_pct: -33,
  aggregation: 'avg',
  status: 'pass',
  score: 100,
  weight: 1,
  key_sli: false,
  pass_targets: null,
  warning_targets: null,
}

const GROUPS = [
  {
    slo_name: 'nginx',
    slo_display_name: 'NGINX',
    indicators: [IND],
    score: 100,
    result: 'pass',
    achieved_points: 100,
    total_points: 100,
  },
  {
    slo_name: 'redis',
    indicators: [],
    score: 0,
    result: 'none',
    achieved_points: 0,
    total_points: 0,
  },
]

let queryClient: QueryClient
beforeEach(() => {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})
afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('SLIBreakdownGrouped', () => {
  it('renders SLO section headers', () => {
    render(
      <Wrapper>
        <SLIBreakdownGrouped
          groups={GROUPS}
          expandState={new Map([['nginx', true], ['redis', false]])}
          onToggle={vi.fn()}
        />
      </Wrapper>
    )
    expect(screen.getByText('NGINX')).toBeInTheDocument()
    expect(screen.getByText('redis')).toBeInTheDocument()
  })

  it('shows indicators when SLO is expanded', () => {
    render(
      <Wrapper>
        <SLIBreakdownGrouped
          groups={GROUPS}
          expandState={new Map([['nginx', true], ['redis', false]])}
          onToggle={vi.fn()}
        />
      </Wrapper>
    )
    expect(screen.getByText('Error Rate')).toBeInTheDocument()
  })

  it('hides indicators when SLO is collapsed', () => {
    render(
      <Wrapper>
        <SLIBreakdownGrouped
          groups={GROUPS}
          expandState={new Map([['nginx', false], ['redis', false]])}
          onToggle={vi.fn()}
        />
      </Wrapper>
    )
    expect(screen.queryByText('Error Rate')).not.toBeInTheDocument()
  })

  it('calls onToggle when section header is clicked', () => {
    const onToggle = vi.fn()
    render(
      <Wrapper>
        <SLIBreakdownGrouped
          groups={GROUPS}
          expandState={new Map([['nginx', false]])}
          onToggle={onToggle}
        />
      </Wrapper>
    )
    fireEvent.click(screen.getByText('NGINX'))
    expect(onToggle).toHaveBeenCalledWith('nginx')
  })
})
