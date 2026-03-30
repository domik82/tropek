import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SliDetailView } from './SliDetailView'
import type { SliDefinition } from '@/features/slis/types'
import type { SloDefinition } from '@/features/slos/types'

vi.mock('@/features/slis/hooks', () => ({
  useSliDetail: vi.fn(),
  useDeleteSli: vi.fn(),
}))

vi.mock('@/features/slos/hooks', () => ({
  useSlos: vi.fn(),
}))

import { useSliDetail, useDeleteSli } from '@/features/slis/hooks'
import { useSlos } from '@/features/slos/hooks'

const mockSli: SliDefinition = {
  id: 'sli-1',
  name: 'http-error-rate',
  display_name: 'HTTP Error Rate',
  adapter_type: 'prometheus',
  version: 3,
  comparable_from_version: 2,
  indicators: {
    error_rate: 'sum(rate(http_requests_total{status=~"5..",job="$service"}[5m]))',
    latency: 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))',
  },
  notes: 'Tracks HTTP error rate and latency',
  author: 'alice',
  tags: { env: 'prod', team: 'platform' },
  active: true,
  created_at: '2024-01-01T00:00:00Z',
}

const mockSlos: SloDefinition[] = [
  {
    id: 'slo-1',
    name: 'api-slo',
    version: 1,
    comparable_from_version: 1,
    display_name: 'API SLO',
    kind: 'standard',
    sli_name: null,
    sli_version: null,
    author: null,
    notes: null,
    tags: {},
    variables: {},
    kind: 'standard',
    sli_name: null,
    sli_version: null,
    created_at: '2024-01-01T00:00:00Z',
    active: true,
    objectives: [
      {
        sli: 'http-error-rate',
        display_name: 'Error Rate',
        pass_threshold: ['<1%'],
        warning_threshold: ['<5%'],
        weight: 1,
        key_sli: true,
        sort_order: 0,
      },
    ],
    total_score_pass_pct: 90,
    total_score_warning_pct: 75,
    comparison: {},
  },
  {
    id: 'slo-2',
    name: 'db-slo',
    version: 1,
    comparable_from_version: 1,
    display_name: 'DB SLO',
    kind: 'standard',
    sli_name: null,
    sli_version: null,
    author: null,
    notes: null,
    tags: {},
    variables: {},
    kind: 'standard',
    sli_name: null,
    sli_version: null,
    created_at: '2024-01-01T00:00:00Z',
    active: true,
    objectives: [
      {
        sli: 'db-latency',
        display_name: 'DB Latency',
        pass_threshold: ['<200ms'],
        warning_threshold: ['<500ms'],
        weight: 1,
        key_sli: false,
        sort_order: 0,
      },
    ],
    total_score_pass_pct: 90,
    total_score_warning_pct: 75,
    comparison: {},
  },
]

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('SliDetailView', () => {
  beforeEach(() => {
    vi.mocked(useSliDetail).mockReturnValue({
      data: mockSli,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useSliDetail>)

    vi.mocked(useSlos).mockReturnValue({
      data: mockSlos,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useSlos>)

    vi.mocked(useDeleteSli).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useDeleteSli>)
  })

  it('renders name, version badge, and adapter_type badge', () => {
    render(
      <SliDetailView name="http-error-rate" onNavigate={vi.fn()} onNewVersion={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText('HTTP Error Rate')).toBeInTheDocument()
    expect(screen.getByText('http-error-rate')).toBeInTheDocument()
    expect(screen.getByText('v3')).toBeInTheDocument()
    expect(screen.getByText('prometheus')).toBeInTheDocument()
  })

  it('renders indicators table with Name and Query columns', () => {
    render(
      <SliDetailView name="http-error-rate" onNavigate={vi.fn()} onNewVersion={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Query')).toBeInTheDocument()
    expect(screen.getByText('error_rate')).toBeInTheDocument()
    expect(screen.getByText('latency')).toBeInTheDocument()
  })

  it('highlights $variable tokens in queries in orange', () => {
    render(
      <SliDetailView name="http-error-rate" onNavigate={vi.fn()} onNewVersion={vi.fn()} />,
      { wrapper: Wrapper }
    )
    // The $service variable should be highlighted in orange
    const highlighted = document.querySelectorAll('span[style*="#FFA657"]')
    expect(highlighted.length).toBeGreaterThan(0)
    const texts = Array.from(highlighted).map(el => el.textContent)
    expect(texts).toContain('$service')
  })

  it('"New Version" button calls onNewVersion with current SLI data', () => {
    const onNewVersion = vi.fn()
    render(
      <SliDetailView name="http-error-rate" onNavigate={vi.fn()} onNewVersion={onNewVersion} />,
      { wrapper: Wrapper }
    )
    fireEvent.click(screen.getByRole('button', { name: /new version/i }))
    expect(onNewVersion).toHaveBeenCalledWith(mockSli)
  })

  it('"Deactivate" button is present', () => {
    render(
      <SliDetailView name="http-error-rate" onNavigate={vi.fn()} onNewVersion={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByRole('button', { name: /deactivate/i })).toBeInTheDocument()
  })

  it('shows SLOs that use this SLI in "Used by" section and clicking navigates', () => {
    const onNavigate = vi.fn()
    render(
      <SliDetailView name="http-error-rate" onNavigate={onNavigate} onNewVersion={vi.fn()} />,
      { wrapper: Wrapper }
    )
    // api-slo uses http-error-rate; db-slo uses db-latency, not this SLI
    const sloLink = screen.getByText('api-slo')
    expect(sloLink).toBeInTheDocument()
    expect(screen.queryByText('db-slo')).not.toBeInTheDocument()

    fireEvent.click(sloLink)
    expect(onNavigate).toHaveBeenCalledWith({ type: 'slo', name: 'api-slo' })
  })

  it('renders active badge when SLI is active', () => {
    render(
      <SliDetailView name="http-error-rate" onNavigate={vi.fn()} onNewVersion={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText('active')).toBeInTheDocument()
  })

  it('renders tag pills', () => {
    render(
      <SliDetailView name="http-error-rate" onNavigate={vi.fn()} onNewVersion={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText('env: prod')).toBeInTheDocument()
    expect(screen.getByText('team: platform')).toBeInTheDocument()
  })
})
