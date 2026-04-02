import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RegistrySidebar } from './RegistrySidebar'
import type { RegistryMode, SelectedNode } from './types'

vi.mock('@/features/slo-groups/hooks', () => ({
  useSloGroups: () => ({ data: [] }),
}))

vi.mock('@/features/slos/hooks', () => ({
  useSlos: () => ({ data: [] }),
  useGroupTree: () => ({ data: { top_level: [], all_groups: [] } }),
  useSloTagKeys: () => ({ data: [], isLoading: false }),
  useSloTagValues: () => ({ data: [], isLoading: false }),
}))

vi.mock('@/features/slos/api', () => ({
  fetchGroupSloAssignments: () => Promise.resolve([]),
}))

vi.mock('@/features/slis/hooks', () => ({
  useSliDefinitions: () => ({ data: [] }),
}))

vi.mock('@/features/datasources/hooks', () => ({
  useDatasources: () => ({ data: [] }),
  useDatasourceTagKeys: () => ({ data: [], isLoading: false }),
  useDatasourceTagValues: () => ({ data: [], isLoading: false }),
}))

vi.mock('@/features/assets/hooks', () => ({
  useTagKeys: () => ({ data: [], isLoading: false }),
  useTagValues: () => ({ data: [], isLoading: false }),
}))

let queryClient: QueryClient

beforeEach(() => {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})

afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}

describe('RegistrySidebar', () => {
  const defaultProps = {
    mode: 'asset' as RegistryMode,
    onModeChange: vi.fn(),
    selected: null as SelectedNode | null,
    onSelect: vi.fn(),
    onCreateAction: vi.fn() as (type: 'datasource' | 'sli' | 'slo' | 'group' | 'slo-template' | 'slo-group', context?: { adapterType?: string }) => void,
  }

  it('renders segmented control with Asset as default/first', () => {
    render(<RegistrySidebar {...defaultProps} />, { wrapper: Wrapper })
    expect(screen.getByText('Asset')).toBeInTheDocument()
    expect(screen.getByText('SLO')).toBeInTheDocument()
    expect(screen.getByText('Datasource')).toBeInTheDocument()
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
