import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SloDetailView } from './SloDetailView'
import type { SloDefinition } from '@/features/slos/types'

vi.mock('@/features/slos/hooks', () => ({
  useSloDetail: vi.fn(),
  useSloVersions: vi.fn(),
  useDeleteSlo: vi.fn(),
}))

import { useSloDetail, useSloVersions, useDeleteSlo } from '@/features/slos/hooks'

const mockSlo: SloDefinition = {
  id: 'slo-1',
  name: 'api-availability',
  version: 2,
  comparable_from_version: 1,
  display_name: 'API Availability SLO',
  author: 'alice',
  notes: 'Tracks API availability and error rate',
  tags: { env: 'prod', team: 'platform' },
  variables: { service: 'api-service', region: 'us-east-1' },
  created_at: '2024-01-01T00:00:00Z',
  active: true,
  objectives: [
    {
      sli: 'error-rate',
      display_name: 'Error Rate',
      pass_criteria: ['<1%', '<100'],
      warning_criteria: ['<5%'],
      weight: 2,
      key_sli: true,
      sort_order: 0,
    },
    {
      sli: 'latency-p99',
      display_name: 'P99 Latency',
      pass_criteria: ['<200ms'],
      warning_criteria: ['<500ms', '<1000ms'],
      weight: 1,
      key_sli: false,
      sort_order: 1,
    },
  ],
  total_score_pass_pct: 90,
  total_score_warning_pct: 75,
  comparison: {
    compare_with: 'several_results',
    number_of_comparison_results: 3,
    include_result_with_score: 'pass_or_warn',
    aggregate_function: 'avg',
  },
}

const mockVersions: SloDefinition[] = [
  { ...mockSlo, version: 1, created_at: '2023-06-01T00:00:00Z' },
  { ...mockSlo, version: 2, created_at: '2024-01-01T00:00:00Z' },
]

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('SloDetailView', () => {
  beforeEach(() => {
    vi.mocked(useSloDetail).mockReturnValue({
      data: mockSlo,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useSloDetail>)

    vi.mocked(useSloVersions).mockReturnValue({
      data: mockVersions,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useSloVersions>)

    vi.mocked(useDeleteSlo).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useDeleteSlo>)
  })

  it('renders name, version badge, and active badge', () => {
    render(
      <SloDetailView name="api-availability" onNavigate={vi.fn()} onNewVersion={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText('API Availability SLO')).toBeInTheDocument()
    expect(screen.getByText('api-availability')).toBeInTheDocument()
    // version badge appears in the header (may also appear in version history list)
    expect(screen.getAllByText('v2').length).toBeGreaterThan(0)
    expect(screen.getByText('active')).toBeInTheDocument()
  })

  it('renders SloObjectiveTable with indicator names and criteria', () => {
    render(
      <SloDetailView name="api-availability" onNavigate={vi.fn()} onNewVersion={vi.fn()} />,
      { wrapper: Wrapper }
    )
    // Column headers (SloObjectiveTable uses these)
    expect(screen.getByText('Indicator')).toBeInTheDocument()
    expect(screen.getByText('Pass')).toBeInTheDocument()
    expect(screen.getByText('Warning')).toBeInTheDocument()
    expect(screen.getByText('Weight')).toBeInTheDocument()
    // Objective rows — SLI names
    expect(screen.getByText('error-rate')).toBeInTheDocument()
    expect(screen.getByText('latency-p99')).toBeInTheDocument()
    // Key SLI diamond (SloObjectiveTable uses ◆ not ★)
    expect(screen.getAllByText('◆').length).toBeGreaterThan(0)
    // Criteria comma-separated (SloObjectiveTable uses .join(', '))
    expect(screen.getByText('<1%, <100')).toBeInTheDocument()
    expect(screen.getByText('<5%')).toBeInTheDocument()
    expect(screen.getByText('<200ms')).toBeInTheDocument()
    expect(screen.getByText('<500ms, <1000ms')).toBeInTheDocument()
  })

  it('shows score thresholds in SloObjectiveTable footer', () => {
    render(
      <SloDetailView name="api-availability" onNavigate={vi.fn()} onNewVersion={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText('90%')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
  })

  it('"New Version" button calls onNewVersion with SLO data', () => {
    const onNewVersion = vi.fn()
    render(
      <SloDetailView name="api-availability" onNavigate={vi.fn()} onNewVersion={onNewVersion} />,
      { wrapper: Wrapper }
    )
    fireEvent.click(screen.getByRole('button', { name: /new version/i }))
    expect(onNewVersion).toHaveBeenCalledWith(mockSlo)
  })

  it('"Deactivate" button is present', () => {
    render(
      <SloDetailView name="api-availability" onNavigate={vi.fn()} onNewVersion={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByRole('button', { name: /deactivate/i })).toBeInTheDocument()
  })

  it('renders linked groups', () => {
    render(
      <SloDetailView name="api-availability" onNavigate={vi.fn()}
        onNewVersion={vi.fn()} linkedGroups={['core-services', 'data-tier']} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText(/Linked Groups/)).toBeInTheDocument()
    expect(screen.getByText('core-services')).toBeInTheDocument()
    expect(screen.getByText('data-tier')).toBeInTheDocument()
  })
})
