import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DatasourceDetailView } from './DatasourceDetailView'
import type { Datasource } from '@/features/datasources'
import type { Sli } from '@/features/slis'

vi.mock('@/features/datasources/hooks', () => ({
  useDatasource: vi.fn(),
  useDeleteDatasource: vi.fn(),
}))

vi.mock('@/features/slis/hooks', () => ({
  useSliDefinitions: vi.fn(),
}))

import { useDatasource, useDeleteDatasource } from '@/features/datasources/hooks'
import { useSliDefinitions } from '@/features/slis/hooks'

const mockDs: Datasource = {
  id: 'ds-1',
  name: 'prom-main',
  displayName: 'Prometheus Main',
  adapterType: 'prometheus',
  adapterUrl: 'http://prometheus:9090',
  tags: { env: 'prod', team: 'platform' },
  hasToken: true,
  createdAt: new Date('2024-01-01T00:00:00Z'),
  updatedAt: new Date('2024-01-02T00:00:00Z'),
}

const mockSlis: Sli[] = [
  {
    id: 'sli-1',
    name: 'http-sli',
    displayName: 'HTTP SLI',
    adapterType: 'prometheus',
    version: 1,
    comparableFromVersion: 1,
    indicators: {},
    mode: 'raw',
    queryTemplate: null,
    interval: null,
    methods: null,
    notes: null,
    author: null,
    tags: {},
    active: true,
    createdAt: new Date('2024-01-01T00:00:00Z'),
  },
  {
    id: 'sli-2',
    name: 'db-sli',
    displayName: 'DB SLI',
    adapterType: 'datadog',
    version: 1,
    comparableFromVersion: 1,
    indicators: {},
    mode: 'raw',
    queryTemplate: null,
    interval: null,
    methods: null,
    notes: null,
    author: null,
    tags: {},
    active: true,
    createdAt: new Date('2024-01-01T00:00:00Z'),
  },
]

let queryClient: QueryClient

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('DatasourceDetailView', () => {
  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    vi.mocked(useDatasource).mockReturnValue({
      data: mockDs,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useDatasource>)

    vi.mocked(useSliDefinitions).mockReturnValue({
      data: mockSlis,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useSliDefinitions>)

    vi.mocked(useDeleteDatasource).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useDeleteDatasource>)
  })

  afterEach(() => {
    queryClient.cancelQueries()
    queryClient.clear()
    cleanup()
  })

  it('renders display_name, name, and adapter_type badge', () => {
    render(
      <DatasourceDetailView name="prom-main" onNavigate={vi.fn()} onEdit={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText('Prometheus Main')).toBeInTheDocument()
    expect(screen.getByText('prom-main')).toBeInTheDocument()
    expect(screen.getByText('prometheus')).toBeInTheDocument()
  })

  it('shows masked token (••••••••) when has_token is true', () => {
    render(
      <DatasourceDetailView name="prom-main" onNavigate={vi.fn()} onEdit={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText('••••••••')).toBeInTheDocument()
  })

  it('shows "None" when has_token is false', () => {
    vi.mocked(useDatasource).mockReturnValue({
      data: { ...mockDs, hasToken: false },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useDatasource>)

    render(
      <DatasourceDetailView name="prom-main" onNavigate={vi.fn()} onEdit={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText('None')).toBeInTheDocument()
  })

  it('renders adapter_url in monospace', () => {
    render(
      <DatasourceDetailView name="prom-main" onNavigate={vi.fn()} onEdit={vi.fn()} />,
      { wrapper: Wrapper }
    )
    const urlEl = screen.getByText('http://prometheus:9090')
    expect(urlEl).toBeInTheDocument()
    expect(urlEl).toHaveClass('font-mono')
  })

  it('renders tag pills', () => {
    render(
      <DatasourceDetailView name="prom-main" onNavigate={vi.fn()} onEdit={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText('env: prod')).toBeInTheDocument()
    expect(screen.getByText('team: platform')).toBeInTheDocument()
  })

  it('clicking SLI in "Used by" calls onNavigate with sli node', () => {
    const onNavigate = vi.fn()
    render(
      <DatasourceDetailView name="prom-main" onNavigate={onNavigate} onEdit={vi.fn()} />,
      { wrapper: Wrapper }
    )
    // Only prometheus SLI should appear (not datadog) — shown by display_name
    const sliLink = screen.getByText('HTTP SLI')
    fireEvent.click(sliLink)
    expect(onNavigate).toHaveBeenCalledWith({ type: 'sli', name: 'http-sli' })
  })

  it('does not show datadog SLI in "Used by" section', () => {
    render(
      <DatasourceDetailView name="prom-main" onNavigate={vi.fn()} onEdit={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.queryByText('DB SLI')).not.toBeInTheDocument()
  })

  it('renders Edit and Delete buttons', () => {
    render(
      <DatasourceDetailView name="prom-main" onNavigate={vi.fn()} onEdit={vi.fn()} />,
      { wrapper: Wrapper }
    )
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
  })
})
