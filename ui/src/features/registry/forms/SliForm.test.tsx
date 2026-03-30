import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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
  mode: 'raw',
  query_template: null,
  interval: null,
  methods: null,
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
      { wrapper: Wrapper },
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
      { wrapper: Wrapper },
    )
    expect(screen.queryByPlaceholderText('metric_name')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /add indicator/i }))
    expect(screen.getByPlaceholderText('metric_name')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /add indicator/i }))
    expect(screen.getAllByPlaceholderText('metric_name')).toHaveLength(2)

    const removeButtons = screen.getAllByRole('button', { name: /remove indicator/i })
    fireEvent.click(removeButtons[0])
    expect(screen.getAllByPlaceholderText('metric_name')).toHaveLength(1)
  })

  it('edit mode pre-fills values from editFrom prop', () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} editFrom={mockSli} />,
      { wrapper: Wrapper },
    )
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
      { wrapper: Wrapper },
    )
    const nameInputs = screen.getAllByPlaceholderText('metric_name')
    expect(nameInputs).toHaveLength(2)
    const values = nameInputs.map(el => (el as HTMLInputElement).value)
    expect(values).toContain('error_rate')
    expect(values).toContain('latency')
  })

  it('pre-fills adapter_type when defaultAdapterType prop is provided', () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} defaultAdapterType="datadog" />,
      { wrapper: Wrapper },
    )
    expect(screen.getByLabelText('Adapter Type')).toHaveValue('datadog')
  })

  it('calls useCreateSli on submit', async () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'my-sli' } })
    fireEvent.change(screen.getByLabelText('Adapter Type'), { target: { value: 'prometheus' } })

    fireEvent.click(screen.getByRole('button', { name: /add indicator/i }))
    const nameInput = screen.getByPlaceholderText('metric_name')
    const queryInput = screen.getByPlaceholderText('rate(metric[5m])')
    fireEvent.change(nameInput, { target: { value: 'error_rate' } })
    fireEvent.change(queryInput, { target: { value: 'sum(rate(errors[5m]))' } })

    fireEvent.click(screen.getByRole('button', { name: /create/i }))

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'my-sli',
          adapter_type: 'prometheus',
          indicators: { error_rate: 'sum(rate(errors[5m]))' },
        }),
        expect.anything(),
      )
    })
  })

  it('shows validation errors for required fields', async () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )

    fireEvent.click(screen.getByRole('button', { name: /create/i }))

    await waitFor(() => {
      expect(screen.getByText('Name is required')).toBeInTheDocument()
    })
    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('does not render when open is false', () => {
    render(
      <SliForm open={false} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows mode toggle with Raw selected by default', () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )
    expect(screen.getByRole('radio', { name: 'Raw' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Aggregated' })).not.toBeChecked()
  })

  it('shows indicator fields in raw mode', () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )
    expect(screen.getByText('Indicators')).toBeInTheDocument()
    expect(screen.queryByLabelText('Query Template')).not.toBeInTheDocument()
  })

  it('shows aggregated fields when Aggregated mode is selected', () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )
    fireEvent.click(screen.getByRole('radio', { name: 'Aggregated' }))
    expect(screen.getByLabelText('Query Template')).toBeInTheDocument()
    expect(screen.getByLabelText('Interval')).toBeInTheDocument()
    expect(screen.getByLabelText('Mean')).toBeInTheDocument()
    expect(screen.queryByText('Indicators')).not.toBeInTheDocument()
  })

  it('edit mode pre-fills aggregated fields', () => {
    const aggSli: SliDefinition = {
      ...mockSli,
      mode: 'aggregated',
      indicators: {},
      query_template: 'rate(cpu[$interval])',
      interval: '5m',
      methods: ['mean', 'p99'],
    }
    render(
      <SliForm open={true} onOpenChange={vi.fn()} editFrom={aggSli} />,
      { wrapper: Wrapper },
    )
    expect(screen.getByRole('radio', { name: 'Aggregated' })).toBeChecked()
    expect(screen.getByLabelText('Query Template')).toHaveValue('rate(cpu[$interval])')
    expect(screen.getByLabelText('Interval')).toHaveValue('5m')
    expect(screen.getByLabelText('Mean')).toBeChecked()
    expect(screen.getByLabelText('P99')).toBeChecked()
    expect(screen.getByLabelText('Max')).not.toBeChecked()
  })

  it('submits aggregated-mode SLI with correct payload', async () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'agg-sli' } })
    fireEvent.change(screen.getByLabelText('Adapter Type'), { target: { value: 'prometheus' } })
    fireEvent.click(screen.getByRole('radio', { name: 'Aggregated' }))
    fireEvent.change(screen.getByLabelText('Query Template'), {
      target: { value: 'rate(cpu[$interval])' },
    })
    fireEvent.click(screen.getByLabelText('Mean'))
    fireEvent.click(screen.getByLabelText('P99'))

    fireEvent.click(screen.getByRole('button', { name: /create/i }))

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'agg-sli',
          adapter_type: 'prometheus',
          mode: 'aggregated',
          query_template: 'rate(cpu[$interval])',
          interval: '1m',
          methods: ['mean', 'p99'],
        }),
        expect.anything(),
      )
    })
  })
})
