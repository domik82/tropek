import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SloWizard } from './SloWizard'
import type { SloDefinition } from '@/features/slos/types'

vi.mock('@/features/slos/hooks', () => ({
  useCreateSlo: vi.fn(),
}))

vi.mock('@/features/datasources/hooks', () => ({
  useDatasources: vi.fn().mockReturnValue({ data: [] }),
}))

vi.mock('@/features/slis/hooks', () => ({
  useSliDefinitions: vi.fn().mockReturnValue({ data: [] }),
}))

import { useCreateSlo } from '@/features/slos/hooks'

const mockMutate = vi.fn()

const mockSlo: SloDefinition = {
  id: 'slo-1',
  name: 'perf-slo',
  version: 2,
  comparable_from_version: 1,
  display_name: 'Performance SLO',
  author: 'alice',
  notes: 'Performance evaluation',
  tags: { env: 'prod' },
  variables: { stage: 'production' },
  created_at: '2024-01-01T00:00:00Z',
  active: true,
  objectives: [
    {
      sli: 'response_time',
      display_name: 'Response Time',
      pass_criteria: ['<600'],
      warning_criteria: ['<800'],
      weight: 1,
      key_sli: true,
      sort_order: 0,
    },
    {
      sli: 'error_rate',
      display_name: 'Error Rate',
      pass_criteria: ['<5%'],
      warning_criteria: ['<10%'],
      weight: 2,
      key_sli: false,
      sort_order: 1,
    },
  ],
  total_score_pass_pct: 90,
  total_score_warning_pct: 75,
  comparison: {
    baseline_mode: 'previous',
    number_of_comparison_results: 3,
    aggregate_function: 'avg',
    include_result_with_score: 'pass_or_warn',
  },
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('SloWizard', () => {
  beforeEach(() => {
    mockMutate.mockReset()
    vi.mocked(useCreateSlo).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateSlo>)
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
