import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'
import { SloRegistryPage } from './SloRegistryPage'

const mockUseSlos = vi.fn()
const mockUseGroupTree = vi.fn()
const mockUseGroupSloLinks = vi.fn()

vi.mock('@/features/slos/hooks', () => ({
  useSlos: () => mockUseSlos(),
  useGroupTree: () => mockUseGroupTree(),
  useGroupSloLinks: () => mockUseGroupSloLinks(),
  useCreateGroup: () => ({ mutateAsync: vi.fn() }),
  useAddSubgroup: () => ({ mutateAsync: vi.fn() }),
  useDatasources: () => ({ data: [] }),
  useSliDefinitions: () => ({ data: [] }),
  useCreateGroupSloLink: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/components/AssetTree', () => ({
  AssetTree: ({ onCreateGroup }: { onCreateGroup: () => void }) => (
    <div data-testid="asset-tree">
      <button onClick={onCreateGroup} data-testid="create-group-btn">Create Group</button>
    </div>
  ),
}))

vi.mock('@/features/slos/components/SloList', () => ({
  SloList: ({ slos }: { slos: Array<{ name: string }> }) => (
    <div data-testid="slo-list">
      {slos.map((s: { name: string }) => (
        <div key={s.name} data-testid={`slo-${s.name}`}>{s.name}</div>
      ))}
    </div>
  ),
}))

vi.mock('@/features/slos/components/SloGroupDialogs', () => ({
  SloGroupDialogs: ({ createGroupOpen }: { createGroupOpen: boolean }) => (
    <div data-testid="group-dialogs" data-create-open={createGroupOpen} />
  ),
}))

vi.mock('@/features/slos/components/SloCreateForm', () => ({
  SloCreateForm: () => <div data-testid="create-form">create form</div>,
}))

const sloList = [
  { name: 'latency-slo', display_name: 'Latency SLO', active: true },
  { name: 'error-rate-slo', display_name: 'Error Rate SLO', active: true },
]

function renderPage(search = '') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/slos${search}`]}>
        <SloRegistryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('SloRegistryPage', () => {
  beforeEach(() => {
    mockUseSlos.mockReturnValue({ data: sloList, isLoading: false, isError: false })
    mockUseGroupTree.mockReturnValue({ data: { all_groups: [], root_groups: [] } })
    mockUseGroupSloLinks.mockReturnValue({ data: [] })
  })

  it('renders loading state', () => {
    mockUseSlos.mockReturnValue({ data: undefined, isLoading: true, isError: false })
    renderPage()
    expect(screen.getByText(/Loading/)).toBeInTheDocument()
  })

  it('renders error state', () => {
    mockUseSlos.mockReturnValue({ data: undefined, isLoading: false, isError: true })
    renderPage()
    expect(screen.getByText(/Failed to load/)).toBeInTheDocument()
  })

  it('renders SLO list', () => {
    renderPage()
    expect(screen.getByTestId('slo-list')).toBeInTheDocument()
    expect(screen.getByTestId('slo-latency-slo')).toBeInTheDocument()
    expect(screen.getByTestId('slo-error-rate-slo')).toBeInTheDocument()
  })

  it('renders page heading', () => {
    renderPage()
    expect(screen.getByText('SLO Registry')).toBeInTheDocument()
  })

  it('renders asset tree sidebar', () => {
    renderPage()
    expect(screen.getByTestId('asset-tree')).toBeInTheDocument()
  })

  it('shows create form when button clicked', () => {
    renderPage()
    expect(screen.queryByTestId('create-form')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('+ Create SLO'))
    expect(screen.getByTestId('create-form')).toBeInTheDocument()
  })

  it('opens create group dialog when create group button clicked', () => {
    renderPage()
    fireEvent.click(screen.getByTestId('create-group-btn'))
    expect(screen.getByTestId('group-dialogs').getAttribute('data-create-open')).toBe('true')
  })
})
