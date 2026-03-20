import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SloCreateForm } from './SloCreateForm'

const mockMutate = vi.fn()

vi.mock('../hooks', () => ({
  useCreateSlo: () => ({
    mutate: mockMutate,
    isPending: false,
    isError: false,
  }),
}))

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

describe('SloCreateForm', () => {
  beforeEach(() => {
    mockMutate.mockReset()
  })

  it('renders all required form sections', () => {
    renderWithQuery(<SloCreateForm onCancel={vi.fn()} onSaved={vi.fn()} />)
    expect(screen.getByText('Basic Info')).toBeInTheDocument()
    expect(screen.getByText('Comparison')).toBeInTheDocument()
    expect(screen.getByText('Score Thresholds')).toBeInTheDocument()
    expect(screen.getByText('Labels')).toBeInTheDocument()
    expect(screen.getByText('Objectives')).toBeInTheDocument()
  })

  it('renders name field with required indicator', () => {
    renderWithQuery(<SloCreateForm onCancel={vi.fn()} onSaved={vi.fn()} />)
    expect(screen.getByPlaceholderText('my-slo-name')).toBeInTheDocument()
    expect(screen.getByText('*')).toBeInTheDocument()
  })

  it('shows validation error when name is empty on submit', async () => {
    renderWithQuery(<SloCreateForm onCancel={vi.fn()} onSaved={vi.fn()} />)
    fireEvent.click(screen.getByText('Create SLO'))
    await waitFor(() => {
      expect(screen.getByText('Required')).toBeInTheDocument()
    })
    expect(mockMutate).not.toHaveBeenCalled()
  })

  it('shows validation error for invalid name format', async () => {
    const user = userEvent.setup()
    renderWithQuery(<SloCreateForm onCancel={vi.fn()} onSaved={vi.fn()} />)
    await user.type(screen.getByPlaceholderText('my-slo-name'), 'Invalid Name!')
    fireEvent.click(screen.getByText('Create SLO'))
    await waitFor(() => {
      expect(screen.getByText('Lowercase, numbers and hyphens only')).toBeInTheDocument()
    })
  })

  it('calls onCancel when Cancel button is clicked', () => {
    const onCancel = vi.fn()
    renderWithQuery(<SloCreateForm onCancel={onCancel} onSaved={vi.fn()} />)
    fireEvent.click(screen.getByText('Cancel'))
    expect(onCancel).toHaveBeenCalled()
  })

  it('adds an objective row when + Add objective is clicked', () => {
    renderWithQuery(<SloCreateForm onCancel={vi.fn()} onSaved={vi.fn()} />)
    expect(screen.getByText('No objectives yet.')).toBeInTheDocument()
    fireEvent.click(screen.getByText('+ Add objective'))
    expect(screen.queryByText('No objectives yet.')).not.toBeInTheDocument()
    expect(screen.getByPlaceholderText('indicator')).toBeInTheDocument()
  })

  it('adds a label row when + Add label is clicked', () => {
    renderWithQuery(<SloCreateForm onCancel={vi.fn()} onSaved={vi.fn()} />)
    expect(screen.getByText('No labels yet.')).toBeInTheDocument()
    fireEvent.click(screen.getByText('+ Add label'))
    expect(screen.queryByText('No labels yet.')).not.toBeInTheDocument()
    expect(screen.getByPlaceholderText('env')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('production')).toBeInTheDocument()
  })

  it('does not call mutate when name is empty (validation blocks submit)', async () => {
    renderWithQuery(<SloCreateForm onCancel={vi.fn()} onSaved={vi.fn()} />)
    fireEvent.click(screen.getByText('Create SLO'))
    await waitFor(() => {
      expect(screen.getByText('Required')).toBeInTheDocument()
    })
    expect(mockMutate).not.toHaveBeenCalled()
  })

  it('renders submit button with Create SLO label', () => {
    renderWithQuery(<SloCreateForm onCancel={vi.fn()} onSaved={vi.fn()} />)
    const submitButton = screen.getByText('Create SLO')
    expect(submitButton).toBeInTheDocument()
    expect(submitButton).toHaveAttribute('type', 'submit')
  })

  it('renders comparison section with select dropdowns', () => {
    renderWithQuery(<SloCreateForm onCancel={vi.fn()} onSaved={vi.fn()} />)
    // The form renders select elements for comparison settings
    const selects = document.querySelectorAll('select')
    expect(selects.length).toBeGreaterThanOrEqual(3)
    // compare_with select defaults to several_results
    const compareSelect = document.querySelector('select[name="compare_with"]') as HTMLSelectElement
    expect(compareSelect.value).toBe('several_results')
    // aggregate_function select defaults to avg
    const aggregateSelect = document.querySelector('select[name="aggregate_function"]') as HTMLSelectElement
    expect(aggregateSelect.value).toBe('avg')
  })
})
