import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RegistrySidebar } from './RegistrySidebar'
import type { RegistryMode, SelectedNode } from './types'

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('RegistrySidebar', () => {
  const defaultProps = {
    mode: 'asset' as RegistryMode,
    onModeChange: vi.fn(),
    selected: null as SelectedNode | null,
    onSelect: vi.fn(),
    onCreateAction: vi.fn() as (type: 'datasource' | 'sli' | 'slo' | 'group', context?: { adapterType?: string }) => void,
    allLinks: [] as { slo_name: string; sli_name: string; data_source_name: string }[],
    groupLinksMap: {} as Record<string, { slo_name: string; sli_name: string; data_source_name: string }[]>,
  }

  it('renders segmented control with Asset as default/first', () => {
    render(<RegistrySidebar {...defaultProps} />, { wrapper: Wrapper })
    const assetBtn = screen.getByText('Asset')
    const sloBtn = screen.getByText('SLO')
    const dsBtn = screen.getByText('Datasource')
    expect(assetBtn).toBeInTheDocument()
    expect(sloBtn).toBeInTheDocument()
    expect(dsBtn).toBeInTheDocument()
  })

  it('switches mode on click', () => {
    render(<RegistrySidebar {...defaultProps} />, { wrapper: Wrapper })
    fireEvent.click(screen.getByText('SLO'))
    expect(defaultProps.onModeChange).toHaveBeenCalledWith('slo')
  })

  it('renders search input', () => {
    render(<RegistrySidebar {...defaultProps} />, { wrapper: Wrapper })
    expect(screen.getByPlaceholderText('Filter...')).toBeInTheDocument()
  })

  it('renders create button', () => {
    render(<RegistrySidebar {...defaultProps} />, { wrapper: Wrapper })
    expect(screen.getByText(/create/i)).toBeInTheDocument()
  })
})
