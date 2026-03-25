import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { TemplateDetailView } from './TemplateDetailView'

vi.mock('@/features/slos/hooks', () => ({
  useSloDetail: () => ({
    data: {
      name: 'plugin-tpl',
      version: 1,
      kind: 'template',
      active: true,
      display_name: 'Plugin Health',
      objectives: [],
      tags: {},
      variables: { process_name: '$__gen_process_name', AGGREGATION_WINDOW: '5m' },
      comparison: {},
      notes: null,
      author: null,
      total_score_pass_pct: 90,
      total_score_warning_pct: 75,
      sli_name: 'plugin-sli',
      sli_version: 1,
      created_at: '2026-01-01',
      comparable_from_version: 1,
      id: '1',
    },
    isLoading: false,
  }),
}))

vi.mock('@/features/slo-groups/hooks', () => ({
  useSloGroups: () => ({
    data: [
      {
        name: 'app-x-plugins',
        display_name: null,
        template_slo_name: 'plugin-tpl',
        generated_slo_count: 3,
        active: true,
      },
    ],
  }),
}))

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('TemplateDetailView', () => {
  it('renders template name and template badge', () => {
    render(<TemplateDetailView name="plugin-tpl" onNavigate={vi.fn()} />, { wrapper })
    expect(screen.getByText('Plugin Health')).toBeInTheDocument()
    expect(screen.getByText('template')).toBeInTheDocument()
  })

  it('shows groups referencing this template', () => {
    render(<TemplateDetailView name="plugin-tpl" onNavigate={vi.fn()} />, { wrapper })
    expect(screen.getByText('app-x-plugins')).toBeInTheDocument()
  })

  it('highlights gen variables', () => {
    render(<TemplateDetailView name="plugin-tpl" onNavigate={vi.fn()} />, { wrapper })
    expect(screen.getByText(/\$__gen_process_name/)).toBeInTheDocument()
  })
})
