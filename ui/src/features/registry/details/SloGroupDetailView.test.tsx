import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
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
}))

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('SloGroupDetailView', () => {
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
})
