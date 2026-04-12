import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SloDetailView } from './SloDetailView'
import type { Slo } from '@/features/slos'

vi.mock('@/features/slos', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/slos')>()
  return {
    ...actual,
    useSloDetail: vi.fn(),
    useSloVersions: vi.fn(),
    useDeleteSlo: vi.fn(),
    useGroupTree: vi.fn(),
  }
})

vi.mock('@/features/slis', () => ({
  useSliDetail: vi.fn(() => ({ data: undefined, isLoading: false })),
}))

import { useSloDetail, useSloVersions, useDeleteSlo, useGroupTree } from '@/features/slos'

const mockSlo: Slo = {
  id: 'slo-1',
  name: 'api-availability',
  version: 2,
  comparableFromVersion: 1,
  displayName: 'API Availability SLO',
  author: 'alice',
  notes: 'Tracks API availability and error rate',
  tags: { env: 'prod', team: 'platform' },
  variables: { service: 'api-service', region: 'us-east-1' },
  kind: 'standard',
  sliDefinitionId: null,
  sliName: null,
  sliVersion: null,
  createdAt: new Date('2024-01-01T00:00:00Z'),
  active: true,
  objectives: [
    {
      sli: 'error-rate',
      displayName: 'Error Rate',
      passThreshold: ['<1%', '<100'],
      warningThreshold: ['<5%'],
      weight: 2,
      keySli: true,
      sortOrder: 0,
    },
    {
      sli: 'latency-p99',
      displayName: 'P99 Latency',
      passThreshold: ['<200ms'],
      warningThreshold: ['<500ms', '<1000ms'],
      weight: 1,
      keySli: false,
      sortOrder: 1,
    },
  ],
  totalScorePassThreshold: 90,
  totalScoreWarningThreshold: 75,
  comparison: {
    compareWith: 'several_results',
    numberOfComparisonResults: 3,
    includeResultWithScore: 'pass_or_warn',
    aggregateFunction: 'avg',
  },
  methodCriteria: null,
}

const mockVersions: Slo[] = [
  { ...mockSlo, version: 1, createdAt: new Date('2023-06-01T00:00:00Z') },
  { ...mockSlo, version: 2, createdAt: new Date('2024-01-01T00:00:00Z') },
]

let queryClient: QueryClient

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('SloDetailView', () => {
  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
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

    vi.mocked(useGroupTree).mockReturnValue({
      data: { all_groups: [] },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useGroupTree>)
  })

  afterEach(() => {
    queryClient.cancelQueries()
    queryClient.clear()
    cleanup()
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

  it('renders linked groups section', () => {
    render(
      <SloDetailView name="api-availability" onNavigate={vi.fn()} onNewVersion={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText(/Linked Groups/)).toBeInTheDocument()
  })
})
