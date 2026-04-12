import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { SloGroupForm } from './SloGroupForm'

vi.mock('@/features/slos/hooks', () => ({
  useSlos: () => ({
    data: [
      { name: 'plugin-tpl', kind: 'template', version: 1, active: true },
    ],
  }),
}))

vi.mock('@/features/slo-groups', () => ({
  useCreateSloGroup: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

let queryClient: QueryClient

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('SloGroupForm', () => {
  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  })

  afterEach(() => {
    queryClient.cancelQueries()
    queryClient.clear()
    cleanup()
  })
  it('renders name field and template selector', () => {
    render(<SloGroupForm onClose={vi.fn()} />, { wrapper })
    expect(screen.getByLabelText(/^name$/i)).toBeInTheDocument()
    expect(screen.getByText(/template slo/i)).toBeInTheDocument()
  })

  it('shows generate button', () => {
    render(<SloGroupForm onClose={vi.fn()} />, { wrapper })
    expect(screen.getByRole('button', { name: /generate/i })).toBeInTheDocument()
  })
})
