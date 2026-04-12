import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DatasourceForm } from './DatasourceForm'
import type { Datasource } from '@/features/datasources'

vi.mock('@/features/datasources/hooks', () => ({
  useCreateDatasource: vi.fn(),
  useUpdateDatasource: vi.fn(),
}))

import { useCreateDatasource, useUpdateDatasource } from '@/features/datasources/hooks'

const mockCreate = vi.fn()
const mockUpdate = vi.fn()

const mockDs: Datasource = {
  id: 'ds-1',
  name: 'prom-main',
  displayName: 'Prometheus Main',
  adapterType: 'prometheus',
  adapterUrl: 'http://prometheus:9090',
  tags: { env: 'prod' },
  hasToken: true,
  createdAt: new Date('2024-01-01T00:00:00Z'),
  updatedAt: new Date('2024-01-02T00:00:00Z'),
}

let queryClient: QueryClient

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('DatasourceForm', () => {
  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    mockCreate.mockReset()
    mockUpdate.mockReset()

    vi.mocked(useCreateDatasource).mockReturnValue({
      mutate: mockCreate,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateDatasource>)

    vi.mocked(useUpdateDatasource).mockReturnValue({
      mutate: mockUpdate,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateDatasource>)
  })

  afterEach(() => {
    queryClient.cancelQueries()
    queryClient.clear()
    cleanup()
  })

  it('renders all form fields in create mode', () => {
    render(
      <DatasourceForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Display Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Adapter Type')).toBeInTheDocument()
    expect(screen.getByLabelText('Adapter URL')).toBeInTheDocument()
    expect(screen.getByLabelText('Token')).toBeInTheDocument()
  })

  it('token field is password type', () => {
    render(
      <DatasourceForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )
    expect(screen.getByLabelText('Token')).toHaveAttribute('type', 'password')
  })

  it('submits create mutation with form values', async () => {
    render(
      <DatasourceForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'my-ds' } })
    fireEvent.change(screen.getByLabelText('Adapter Type'), { target: { value: 'prometheus' } })
    fireEvent.change(screen.getByLabelText('Adapter URL'), { target: { value: 'http://prom:9090' } })
    fireEvent.change(screen.getByLabelText('Token'), { target: { value: 'secret' } })

    fireEvent.click(screen.getByRole('button', { name: /create/i }))

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'my-ds',
          adapter_type: 'prometheus',
          adapter_url: 'http://prom:9090',
          token: 'secret',
        }),
        expect.anything(),
      )
    })
  })

  it('shows validation errors for required fields', async () => {
    render(
      <DatasourceForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )

    fireEvent.click(screen.getByRole('button', { name: /create/i }))

    await waitFor(() => {
      expect(screen.getByText('Name is required')).toBeInTheDocument()
    })
    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('edit mode pre-fills values and disables name field', () => {
    render(
      <DatasourceForm open={true} onOpenChange={vi.fn()} editFrom={mockDs} />,
      { wrapper: Wrapper },
    )

    expect(screen.getByLabelText('Name')).toHaveValue('prom-main')
    expect(screen.getByLabelText('Name')).toBeDisabled()
    expect(screen.getByLabelText('Display Name')).toHaveValue('Prometheus Main')
    expect(screen.getByLabelText('Adapter URL')).toHaveValue('http://prometheus:9090')
  })

  it('edit mode shows token placeholder and does not send token if empty', async () => {
    render(
      <DatasourceForm open={true} onOpenChange={vi.fn()} editFrom={mockDs} />,
      { wrapper: Wrapper },
    )

    const tokenInput = screen.getByLabelText('Token')
    expect(tokenInput).toHaveAttribute('placeholder', '••••••••')

    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'prom-main',
          adapter_url: 'http://prometheus:9090',
        }),
        expect.anything(),
      )
    })
    const callArg = mockUpdate.mock.calls[0][0]
    expect(callArg.token).toBeUndefined()
  })

  it('edit mode includes token in payload when user types a new value', async () => {
    render(
      <DatasourceForm open={true} onOpenChange={vi.fn()} editFrom={mockDs} />,
      { wrapper: Wrapper },
    )

    fireEvent.change(screen.getByLabelText('Token'), { target: { value: 'new-secret' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalled()
    })
    const callArg = mockUpdate.mock.calls[0][0]
    expect(callArg.token).toBe('new-secret')
  })
})
