import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SloLinkDialogRevised } from './SloLinkDialogRevised'

const mockMutateAsync = vi.fn().mockResolvedValue({})
let mockExistingAssignments: { sloName: string }[] = []

vi.mock('@/features/datasources/hooks', () => ({
  useDatasources: () => ({
    data: [
      { id: 'ds-1', name: 'prom-prod', displayName: 'Prometheus Prod', adapterType: 'prometheus' },
      { id: 'ds-2', name: 'dynatrace-prod', displayName: 'Dynatrace Prod', adapterType: 'dynatrace' },
    ],
  }),
}))

vi.mock('@/features/slos/hooks', () => ({
  useGroupTree: () => ({
    data: {
      all_groups: [
        { id: 'g-1', name: 'production', display_name: 'Production' },
        { id: 'g-2', name: 'staging', display_name: 'Staging' },
      ],
      top_level: [],
    },
  }),
  useSlos: () => ({
    data: [
      { id: 'slo-def-1', name: 'latency-slo', displayName: 'Latency SLO', active: true, sliName: 'response-time', sliVersion: 1 },
      { id: 'slo-def-2', name: 'error-slo', displayName: 'Error SLO', active: true, sliName: null, sliVersion: null },
    ],
  }),
  useGroupSloAssignments: () => ({ data: mockExistingAssignments }),
  useCreateGroupSloAssignment: () => ({ mutateAsync: mockMutateAsync, isPending: false }),
}))

let queryClient: QueryClient

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('SloLinkDialogRevised', () => {
  const onOpenChange = vi.fn()

  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    vi.clearAllMocks()
    mockExistingAssignments = []
  })

  afterEach(() => {
    queryClient.cancelQueries()
    queryClient.clear()
    cleanup()
  })

  it('renders 3-step cascade (SLO, Datasource, Group)', () => {
    render(
      <SloLinkDialogRevised open={true} onOpenChange={onOpenChange} />,
      { wrapper: Wrapper },
    )

    expect(screen.getByText('SLO')).toBeInTheDocument()
    expect(screen.getByText('Datasource')).toBeInTheDocument()
    expect(screen.getByText('Asset Group')).toBeInTheDocument()
  })

  it('shows duplicate assignment detection message', () => {
    mockExistingAssignments = [{ sloName: 'latency-slo' }]

    render(
      <SloLinkDialogRevised
        open={true}
        onOpenChange={onOpenChange}
        lockedSloName="latency-slo"
        lockedGroupName="production"
      />,
      { wrapper: Wrapper },
    )

    expect(screen.getByText('This SLO is already assigned to this group')).toBeInTheDocument()
  })

  it('calls createGroupSloAssignment on submit', async () => {
    render(
      <SloLinkDialogRevised
        open={true}
        onOpenChange={onOpenChange}
        lockedSloName="latency-slo"
        lockedGroupName="production"
      />,
      { wrapper: Wrapper },
    )

    // Select datasource
    fireEvent.click(screen.getByText('Select datasource...'))
    const dsItems = await screen.findAllByRole('option')
    const dsOption = dsItems.find(el => el.textContent?.includes('Prometheus Prod'))!
    fireEvent.click(dsOption)

    // Click Assign button
    fireEvent.click(screen.getByRole('button', { name: /^assign$/i }))

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        groupName: 'production',
        slo_definition_id: 'slo-def-1',
        data_source_name: 'prom-prod',
      })
    })
  })

  it('shows locked values as non-editable text', () => {
    render(
      <SloLinkDialogRevised
        open={true}
        onOpenChange={onOpenChange}
        lockedSloName="latency-slo"
        lockedGroupName="production"
      />,
      { wrapper: Wrapper },
    )

    expect(screen.getByText('latency-slo')).toBeInTheDocument()
    expect(screen.getByText('production')).toBeInTheDocument()
    expect(screen.getAllByText('(locked)').length).toBe(2)
  })

  it('does not render when closed', () => {
    render(
      <SloLinkDialogRevised open={false} onOpenChange={onOpenChange} />,
      { wrapper: Wrapper },
    )

    expect(screen.queryByText('Assign SLO to Asset Group')).not.toBeInTheDocument()
  })

  it('disables Assign button when form is incomplete', () => {
    render(
      <SloLinkDialogRevised open={true} onOpenChange={onOpenChange} />,
      { wrapper: Wrapper },
    )

    const assignButton = screen.getByRole('button', { name: /^assign$/i })
    expect(assignButton).toBeDisabled()
  })

  it('shows SLI context when SLO with sli_name is selected', async () => {
    render(
      <SloLinkDialogRevised
        open={true}
        onOpenChange={onOpenChange}
        lockedSloName="latency-slo"
        lockedGroupName="production"
      />,
      { wrapper: Wrapper },
    )

    expect(screen.getByText('response-time')).toBeInTheDocument()
  })
})
