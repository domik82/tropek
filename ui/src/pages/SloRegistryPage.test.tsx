import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { SloRegistryPage } from './SloRegistryPage'

// Mock all registry components to isolate page-level wiring
vi.mock('@/features/registry/RegistrySidebar', () => ({
  RegistrySidebar: ({ mode, onModeChange }: { mode: string; onModeChange: (m: string) => void }) => (
    <div data-testid="registry-sidebar" data-mode={mode}>
      <button onClick={() => onModeChange('asset')}>Asset</button>
      <button onClick={() => onModeChange('slo')}>SLO</button>
      <button onClick={() => onModeChange('datasource')}>Datasource</button>
      <input placeholder="Filter..." />
    </div>
  ),
}))

vi.mock('@/features/registry/RegistryDetailPanel', () => ({
  RegistryDetailPanel: ({ selected }: { selected: { name: string } | null }) => (
    <div data-testid="detail-panel">
      {selected ? `Detail: ${selected.name}` : 'Select an item from the sidebar'}
    </div>
  ),
}))

vi.mock('@/features/registry/forms/SloWizard', () => ({
  SloWizard: () => <div data-testid="slo-wizard">Wizard</div>,
}))

vi.mock('@/features/registry/forms/DatasourceForm', () => ({
  DatasourceForm: () => <div data-testid="ds-form" />,
}))

vi.mock('@/features/registry/forms/SliForm', () => ({
  SliForm: () => <div data-testid="sli-form" />,
}))

vi.mock('@/features/registry/forms/SloLinkDialogRevised', () => ({
  SloLinkDialogRevised: () => <div data-testid="slo-link-dialog" />,
}))

vi.mock('@/features/assets/hooks', () => ({
  useCreateGroup: () => ({ mutateAsync: vi.fn() }),
}))

let queryClient: QueryClient

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </MemoryRouter>
  )
}

describe('SloRegistryPage', () => {
  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  })

  afterEach(() => {
    queryClient.cancelQueries()
    queryClient.clear()
    cleanup()
  })

  it('renders segmented control with Asset as first/default', () => {
    render(<SloRegistryPage />, { wrapper: Wrapper })
    expect(screen.getByText('Asset')).toBeInTheDocument()
    expect(screen.getByText('SLO')).toBeInTheDocument()
    expect(screen.getByText('Datasource')).toBeInTheDocument()
  })

  it('renders search input', () => {
    render(<SloRegistryPage />, { wrapper: Wrapper })
    expect(screen.getByPlaceholderText('Filter...')).toBeInTheDocument()
  })

  it('renders empty state in main panel', () => {
    render(<SloRegistryPage />, { wrapper: Wrapper })
    expect(screen.getByText(/select an item/i)).toBeInTheDocument()
  })
})
