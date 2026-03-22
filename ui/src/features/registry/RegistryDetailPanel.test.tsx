import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RegistryDetailPanel } from './RegistryDetailPanel'

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('RegistryDetailPanel', () => {
  it('shows empty state when nothing selected', () => {
    render(<RegistryDetailPanel selected={null} onNavigate={vi.fn()} />, { wrapper: Wrapper })
    expect(screen.getByText(/select an item/i)).toBeInTheDocument()
  })
})
