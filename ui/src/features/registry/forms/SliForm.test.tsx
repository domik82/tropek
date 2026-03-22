import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SliForm } from './SliForm'
import type { SliDefinition } from '@/features/slis/types'

vi.mock('@/features/slis/hooks', () => ({
  useCreateSli: vi.fn(),
}))

import { useCreateSli } from '@/features/slis/hooks'

const mockCreate = vi.fn()

const mockSli: SliDefinition = {
  id: 'sli-1',
  name: 'http-error-rate',
  display_name: 'HTTP Error Rate',
  adapter_type: 'prometheus',
  version: 3,
  comparable_from_version: 2,
  indicators: {
    error_rate: 'sum(rate(http_requests_total[5m]))',
    latency: 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))',
  },
  notes: 'Error rate SLI',
  author: 'alice',
  tags: { env: 'prod' },
  active: true,
  created_at: '2024-01-01T00:00:00Z',
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('SliForm', () => {
  beforeEach(() => {
    mockCreate.mockReset()
    vi.mocked(useCreateSli).mockReturnValue({
      mutate: mockCreate,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateSli>)
  })

  it('renders all form fields in create mode', () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Display Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Adapter Type')).toBeInTheDocument()
    expect(screen.getByLabelText('Author')).toBeInTheDocument()
    expect(screen.getByLabelText('Notes')).toBeInTheDocument()
  })

  it('can add and remove indicator rows', () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper }
    )
    // Initially no indicator rows
    expect(screen.queryByPlaceholderText('metric_name')).not.toBeInTheDocument()

    // Add one
    fireEvent.click(screen.getByRole('button', { name: /add indicator/i }))
    expect(screen.getByPlaceholderText('metric_name')).toBeInTheDocument()

    // Add another
    fireEvent.click(screen.getByRole('button', { name: /add indicator/i }))
    expect(screen.getAllByPlaceholderText('metric_name')).toHaveLength(2)

    // Remove one
    const removeButtons = screen.getAllByRole('button', { name: /remove indicator/i })
    fireEvent.click(removeButtons[0])
    expect(screen.getAllByPlaceholderText('metric_name')).toHaveLength(1)
  })

  it('edit mode pre-fills values from editFrom prop', () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} editFrom={mockSli} />,
      { wrapper: Wrapper }
    )
    // Name should be pre-filled and disabled
    expect(screen.getByLabelText('Name')).toHaveValue('http-error-rate')
    expect(screen.getByLabelText('Name')).toBeDisabled()

    expect(screen.getByLabelText('Display Name')).toHaveValue('HTTP Error Rate')
    expect(screen.getByLabelText('Adapter Type')).toHaveValue('prometheus')
    expect(screen.getByLabelText('Author')).toHaveValue('alice')
    expect(screen.getByLabelText('Notes')).toHaveValue('Error rate SLI')
  })

  it('edit mode pre-fills indicator rows', () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} editFrom={mockSli} />,
      { wrapper: Wrapper }
    )
    const nameInputs = screen.getAllByPlaceholderText('metric_name')
    expect(nameInputs).toHaveLength(2)
    // Both indicator names should appear as values
    const values = nameInputs.map(el => (el as HTMLInputElement).value)
    expect(values).toContain('error_rate')
    expect(values).toContain('latency')
  })

  it('pre-fills adapter_type when defaultAdapterType prop is provided', () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} defaultAdapterType="datadog" />,
      { wrapper: Wrapper }
    )
    expect(screen.getByLabelText('Adapter Type')).toHaveValue('datadog')
  })

  it('calls useCreateSli on submit', () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper }
    )
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'my-sli' } })
    fireEvent.change(screen.getByLabelText('Adapter Type'), { target: { value: 'prometheus' } })

    // Add an indicator
    fireEvent.click(screen.getByRole('button', { name: /add indicator/i }))
    const nameInput = screen.getByPlaceholderText('metric_name')
    const queryInput = screen.getByPlaceholderText('rate(metric[5m])')
    fireEvent.change(nameInput, { target: { value: 'error_rate' } })
    fireEvent.change(queryInput, { target: { value: 'sum(rate(errors[5m]))' } })

    fireEvent.click(screen.getByRole('button', { name: /create/i }))

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'my-sli',
        adapter_type: 'prometheus',
        indicators: { error_rate: 'sum(rate(errors[5m]))' },
      }),
      expect.anything()
    )
  })

  it('does not render when open is false', () => {
    render(
      <SliForm open={false} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
