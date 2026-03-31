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

  it('renders TemplateDetailView when type is template', () => {
    render(
      <RegistryDetailPanel
        selected={{ type: 'template', name: 'plugin-tpl' }}
        onNavigate={vi.fn()}
      />,
      { wrapper: Wrapper },
    )
    // TemplateDetailView shows "Loading..." (dots); AssetBindingView fallback shows "Loading…" (ellipsis)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders SloGroupDetailView when type is slo-group', () => {
    render(
      <RegistryDetailPanel
        selected={{ type: 'slo-group', name: 'app-plugins' }}
        onNavigate={vi.fn()}
      />,
      { wrapper: Wrapper },
    )
    // SloGroupDetailView shows "Loading..." (dots); AssetBindingView fallback shows "Loading…" (ellipsis)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })
})
