import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SloLinkDialogRevised } from './SloLinkDialogRevised'

const mockMutateAsync = vi.fn().mockResolvedValue({})
let mockExistingBindings: { slo_name: string }[] = []

vi.mock('@/features/datasources/hooks', () => ({
  useDatasources: () => ({
    data: [
      { id: 'ds-1', name: 'prom-prod', display_name: 'Prometheus Prod', adapter_type: 'prometheus' },
      { id: 'ds-2', name: 'dynatrace-prod', display_name: 'Dynatrace Prod', adapter_type: 'dynatrace' },
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
      { name: 'latency-slo', display_name: 'Latency SLO', active: true, sli_name: 'response-time', sli_version: 1 },
      { name: 'error-slo', display_name: 'Error SLO', active: true, sli_name: null, sli_version: null },
    ],
  }),
  useGroupSloBindings: () => ({ data: mockExistingBindings }),
  useCreateGroupSloBinding: () => ({ mutateAsync: mockMutateAsync, isPending: false }),
}))

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('SloLinkDialogRevised', () => {
  const onOpenChange = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    mockExistingBindings = []
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

  it('shows duplicate binding detection message', () => {
    mockExistingBindings = [{ slo_name: 'latency-slo' }]

    render(
      <SloLinkDialogRevised
        open={true}
        onOpenChange={onOpenChange}
        lockedSloName="latency-slo"
        lockedGroupName="production"
      />,
      { wrapper: Wrapper },
    )

    expect(screen.getByText('This SLO is already bound to this group')).toBeInTheDocument()
  })

  it('calls createGroupSloBinding on submit', async () => {
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

    // Click Bind button
    fireEvent.click(screen.getByRole('button', { name: /^bind$/i }))

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        groupName: 'production',
        slo_name: 'latency-slo',
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

    expect(screen.queryByText('Bind SLO to Asset Group')).not.toBeInTheDocument()
  })

  it('disables Bind button when form is incomplete', () => {
    render(
      <SloLinkDialogRevised open={true} onOpenChange={onOpenChange} />,
      { wrapper: Wrapper },
    )

    const bindButton = screen.getByRole('button', { name: /^bind$/i })
    expect(bindButton).toBeDisabled()
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
