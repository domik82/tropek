import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
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

vi.mock('@/features/slo-groups/hooks', () => ({
  useCreateSloGroup: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('SloGroupForm', () => {
  it('renders name field and template selector', () => {
    render(<SloGroupForm onClose={vi.fn()} />, { wrapper })
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument()
    expect(screen.getByText(/template slo/i)).toBeInTheDocument()
  })

  it('shows generate button', () => {
    render(<SloGroupForm onClose={vi.fn()} />, { wrapper })
    expect(screen.getByRole('button', { name: /generate/i })).toBeInTheDocument()
  })
})
