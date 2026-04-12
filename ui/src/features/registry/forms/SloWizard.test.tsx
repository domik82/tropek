import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SloWizard } from './SloWizard'
import type { Slo } from '@/features/slos'

vi.mock('@/features/slos/hooks', () => ({
  useCreateSlo: vi.fn(),
}))

vi.mock('@/features/datasources/hooks', () => ({
  useDatasources: vi.fn().mockReturnValue({ data: [] }),
}))

vi.mock('@/features/slis/hooks', () => ({
  useSliDefinitions: vi.fn().mockReturnValue({ data: [] }),
  useSliDetail: vi.fn().mockReturnValue({ data: null }),
  useSliTagKeys: vi.fn().mockReturnValue({ data: [] }),
  useSliTagValues: vi.fn().mockReturnValue({ data: [] }),
}))

import { useCreateSlo } from '@/features/slos/hooks'

const mockMutate = vi.fn()

const mockSlo: Slo = {
  id: 'slo-1',
  name: 'perf-slo',
  version: 2,
  comparableFromVersion: 1,
  displayName: 'Performance SLO',
  author: 'alice',
  notes: 'Performance evaluation',
  tags: { env: 'prod' },
  variables: { stage: 'production' },
  createdAt: new Date('2024-01-01T00:00:00Z'),
  active: true,
  objectives: [
    {
      sli: 'response_time',
      displayName: 'Response Time',
      passThreshold: ['<600'],
      warningThreshold: ['<800'],
      weight: 1,
      keySli: true,
      sortOrder: 0,
    },
    {
      sli: 'error_rate',
      displayName: 'Error Rate',
      passThreshold: ['<5%'],
      warningThreshold: ['<10%'],
      weight: 2,
      keySli: false,
      sortOrder: 1,
    },
  ],
  totalScorePassThreshold: 90,
  totalScoreWarningThreshold: 75,
  comparison: {
    numberOfComparisonResults: 3,
    aggregateFunction: 'avg',
    includeResultWithScore: 'pass_or_warn',
  },
  kind: 'standard',
  sliDefinitionId: null,
  sliName: null,
  sliVersion: null,
  methodCriteria: null,
}

let queryClient: QueryClient

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('SloWizard', () => {
  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    mockMutate.mockReset()
    vi.mocked(useCreateSlo).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateSlo>)
  })

  afterEach(() => {
    queryClient.cancelQueries()
    queryClient.clear()
    cleanup()
  })

  it('initial render shows only Step 1', () => {
    render(<SloWizard />, { wrapper: Wrapper })

    expect(screen.getByText('New SLO Definition')).toBeInTheDocument()
    expect(screen.getByText('Identity')).toBeInTheDocument()
    expect(screen.queryByText('Pick SLI')).not.toBeInTheDocument()
    expect(screen.queryByText('Indicators & Criteria')).not.toBeInTheDocument()
    expect(screen.queryByText('Comparison & Scoring')).not.toBeInTheDocument()
  })

  it('filling name reveals Step 2', () => {
    render(<SloWizard />, { wrapper: Wrapper })

    expect(screen.queryByText('Pick SLI')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'my-slo' } })

    expect(screen.getByText('Pick SLI')).toBeInTheDocument()
  })

  it('shows create title and button in create mode', () => {
    render(<SloWizard />, { wrapper: Wrapper })

    expect(screen.getByText('New SLO Definition')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create slo/i })).toBeInTheDocument()
  })

  it('edit mode shows "New Version" title', () => {
    render(<SloWizard editSlo={mockSlo} />, { wrapper: Wrapper })

    expect(screen.getByText(/perf-slo \u00b7 New Version/)).toBeInTheDocument()
    expect(screen.getByText(/Editing creates version 3/)).toBeInTheDocument()
  })

  it('edit mode shows "Create Version" button', () => {
    render(<SloWizard editSlo={mockSlo} />, { wrapper: Wrapper })

    expect(screen.getByRole('button', { name: /create version/i })).toBeInTheDocument()
  })

  it('Create SLO button disabled until valid', () => {
    render(<SloWizard />, { wrapper: Wrapper })

    const btn = screen.getByRole('button', { name: /create slo/i })
    expect(btn).toBeDisabled()
  })

  it('edit mode pre-fills identity fields', () => {
    render(<SloWizard editSlo={mockSlo} />, { wrapper: Wrapper })

    expect(screen.getByLabelText('Name')).toHaveValue('perf-slo')
    expect(screen.getByLabelText('Name')).toHaveAttribute('readonly')
    expect(screen.getByLabelText('Display Name')).toHaveValue('Performance SLO')
    expect(screen.getByLabelText('Author')).toHaveValue('alice')
    expect(screen.getByLabelText('Notes')).toHaveValue('Performance evaluation')
  })

  it('edit mode shows indicator rows from objectives', () => {
    render(<SloWizard editSlo={mockSlo} />, { wrapper: Wrapper })

    // Step 3 should be visible (edit mode has indicators pre-loaded)
    expect(screen.getByText('response_time')).toBeInTheDocument()
    expect(screen.getByText('error_rate')).toBeInTheDocument()
  })
})
