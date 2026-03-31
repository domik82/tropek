import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { SloGroupDetailView } from './SloGroupDetailView'

vi.mock('@/features/slo-groups/hooks', () => ({
  useSloGroupDetail: () => ({
    data: {
      id: '1',
      name: 'app-x-plugins',
      display_name: 'App-X Plugins',
      template_slo_name: 'plugin-tpl',
      template_slo_version: 1,
      gen_variables: { process_name: ['auth', 'cache', 'db'] },
      tags: { app: 'app-x' },
      author: 'admin',
      version: 1,
      active: true,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
      generated_slo_count: 3,
    },
    isLoading: false,
  }),
  useDeleteSloGroup: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateSloGroup: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}))

vi.mock('@/features/slos/hooks', () => ({
  useSloVersions: () => ({ data: [] }),
}))

let queryClient: QueryClient

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('SloGroupDetailView', () => {
  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  })

  afterEach(() => {
    queryClient.cancelQueries()
    queryClient.clear()
    cleanup()
  })
  it('renders group name and template link', () => {
    render(<SloGroupDetailView name="app-x-plugins" onNavigate={vi.fn()} />, { wrapper })
    expect(screen.getByText('App-X Plugins')).toBeInTheDocument()
    expect(screen.getByText('plugin-tpl v1')).toBeInTheDocument()
  })

  it('shows gen_variables as a table', () => {
    render(<SloGroupDetailView name="app-x-plugins" onNavigate={vi.fn()} />, { wrapper })
    expect(screen.getByText('process_name')).toBeInTheDocument()
    expect(screen.getByText('auth')).toBeInTheDocument()
    expect(screen.getByText('cache')).toBeInTheDocument()
    expect(screen.getByText('db')).toBeInTheDocument()
  })

  it('shows generated SLO count', () => {
    render(<SloGroupDetailView name="app-x-plugins" onNavigate={vi.fn()} />, { wrapper })
    expect(screen.getByText('3 SLOs generated')).toBeInTheDocument()
  })

  it('shows new version button', () => {
    render(<SloGroupDetailView name="app-x-plugins" onNavigate={vi.fn()} />, { wrapper })
    expect(screen.getByText('New Version')).toBeInTheDocument()
  })

  it('opens regenerate panel with editable variables on click', () => {
    render(<SloGroupDetailView name="app-x-plugins" onNavigate={vi.fn()} />, { wrapper })
    fireEvent.click(screen.getByText('New Version'))
    // Should show editable inputs pre-filled with current values
    const inputs = screen.getAllByRole('textbox')
    expect(inputs).toHaveLength(3)
    expect(inputs[0]).toHaveValue('auth')
    expect(inputs[1]).toHaveValue('cache')
    expect(inputs[2]).toHaveValue('db')
    // Should show Add row link
    expect(screen.getByText('Add row')).toBeInTheDocument()
  })

  it('adds a row when Add row is clicked', () => {
    render(<SloGroupDetailView name="app-x-plugins" onNavigate={vi.fn()} />, { wrapper })
    fireEvent.click(screen.getByText('New Version'))
    fireEvent.click(screen.getByText('Add row'))
    const inputs = screen.getAllByRole('textbox')
    expect(inputs).toHaveLength(4)
    expect(inputs[3]).toHaveValue('')
  })
})
