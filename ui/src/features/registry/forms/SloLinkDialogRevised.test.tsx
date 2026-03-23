import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SloLinkDialogRevised } from './SloLinkDialogRevised'

const mockMutateAsync = vi.fn().mockResolvedValue({})
let mockExistingLinks: { slo_name: string }[] = []

vi.mock('@/features/datasources/hooks', () => ({
  useDatasources: () => ({
    data: [
      { id: 'ds-1', name: 'prom-prod', display_name: 'Prometheus Prod', adapter_type: 'prometheus' },
      { id: 'ds-2', name: 'dynatrace-prod', display_name: 'Dynatrace Prod', adapter_type: 'dynatrace' },
    ],
  }),
}))

vi.mock('@/features/slis/hooks', () => ({
  useSliDefinitions: () => ({
    data: [
      { id: 'sli-1', name: 'response-time', display_name: 'Response Time', adapter_type: 'prometheus', active: true },
      { id: 'sli-2', name: 'error-rate', display_name: 'Error Rate', adapter_type: 'prometheus', active: true },
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
      { name: 'latency-slo', display_name: 'Latency SLO', active: true },
      { name: 'error-slo', display_name: 'Error SLO', active: true },
    ],
  }),
  useGroupSloLinks: () => ({ data: mockExistingLinks }),
  useCreateGroupSloLink: () => ({ mutateAsync: mockMutateAsync, isPending: false }),
}))

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('SloLinkDialogRevised', () => {
  const onOpenChange = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    mockExistingLinks = []
  })

  it('renders 4-step cascade (DS, SLI, SLO, Group)', () => {
    render(
      <SloLinkDialogRevised open={true} onOpenChange={onOpenChange} />,
      { wrapper: Wrapper },
    )

    expect(screen.getByText('Datasource')).toBeInTheDocument()
    expect(screen.getByText('SLI')).toBeInTheDocument()
    expect(screen.getByText('SLO')).toBeInTheDocument()
    expect(screen.getByText('Asset Group')).toBeInTheDocument()
  })

  it('SLI section shows placeholder until DS selected', () => {
    render(
      <SloLinkDialogRevised open={true} onOpenChange={onOpenChange} />,
      { wrapper: Wrapper },
    )

    expect(screen.getByText('Select a datasource first')).toBeInTheDocument()
  })

  it('SLI picker appears after selecting a datasource', async () => {
    render(
      <SloLinkDialogRevised open={true} onOpenChange={onOpenChange} />,
      { wrapper: Wrapper },
    )

    // Click the DS combobox and select a datasource
    fireEvent.click(screen.getByText('Select datasource...'))
    const dsItems = await screen.findAllByRole('option')
    const dsOption = dsItems.find(el => el.textContent?.includes('Prometheus Prod'))!
    fireEvent.click(dsOption)

    // Now the SLI placeholder should be gone, replaced by a combobox
    expect(screen.queryByText('Select a datasource first')).not.toBeInTheDocument()
    expect(screen.getByText('Select SLI...')).toBeInTheDocument()
  })

  it('shows duplicate link detection message', () => {
    mockExistingLinks = [{ slo_name: 'latency-slo' }]

    render(
      <SloLinkDialogRevised
        open={true}
        onOpenChange={onOpenChange}
        lockedSloName="latency-slo"
        lockedGroupName="production"
      />,
      { wrapper: Wrapper },
    )

    expect(screen.getByText('This SLO is already linked to this group')).toBeInTheDocument()
  })

  it('calls createGroupSloLink on submit', async () => {
    render(
      <SloLinkDialogRevised
        open={true}
        onOpenChange={onOpenChange}
        lockedSloName="latency-slo"
        lockedGroupName="production"
      />,
      { wrapper: Wrapper },
    )

    // Select datasource — click trigger, then find the option text within the dropdown
    fireEvent.click(screen.getByText('Select datasource...'))
    const dsItems = await screen.findAllByRole('option')
    const dsOption = dsItems.find(el => el.textContent?.includes('Prometheus Prod'))!
    fireEvent.click(dsOption)

    // Select SLI
    fireEvent.click(screen.getByText('Select SLI...'))
    const sliItems = await screen.findAllByRole('option')
    const sliOption = sliItems.find(el => el.textContent?.includes('Response Time'))!
    fireEvent.click(sliOption)

    // Click Link button
    fireEvent.click(screen.getByRole('button', { name: /^link$/i }))

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        groupName: 'production',
        slo_name: 'latency-slo',
        sli_name: 'response-time',
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

    expect(screen.queryByText('Link SLO to Asset Group')).not.toBeInTheDocument()
  })

  it('disables Link button when form is incomplete', () => {
    render(
      <SloLinkDialogRevised open={true} onOpenChange={onOpenChange} />,
      { wrapper: Wrapper },
    )

    const linkButton = screen.getByRole('button', { name: /^link$/i })
    expect(linkButton).toBeDisabled()
  })
})
