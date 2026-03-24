import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { SloLinkDialog } from './SloLinkDialog'

const mockCreateBinding = vi.fn().mockResolvedValue({})

vi.mock('@/features/datasources/hooks', () => ({
  useDatasources: () => ({
    data: [
      { id: 'ds-1', name: 'prom-prod', display_name: 'Prometheus Prod', adapter_type: 'prometheus' },
    ],
  }),
}))

vi.mock('@/features/slis/hooks', () => ({
  useSliDefinitions: () => ({
    data: [
      { id: 'sli-1', name: 'response-time', display_name: 'Response Time', active: true },
    ],
  }),
}))

vi.mock('../hooks', () => ({
  useGroupTree: () => ({
    data: {
      all_groups: [{ id: 'g-1', name: 'production', display_name: 'Production' }],
      root_groups: [],
    },
  }),
  useSlos: () => ({
    data: [
      { name: 'latency-slo', display_name: 'Latency SLO', active: true },
    ],
  }),
  useGroupSloBindings: () => ({ data: [] }),
  useCreateGroupSloBinding: () => ({ mutateAsync: mockCreateBinding, isPending: false }),
}))

describe('SloLinkDialog', () => {
  const onOpenChange = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders dialog title when open', () => {
    render(<SloLinkDialog open={true} onOpenChange={onOpenChange} />)
    expect(screen.getByText('Link SLO to Asset Group')).toBeInTheDocument()
  })

  it('renders datasource selector', () => {
    render(<SloLinkDialog open={true} onOpenChange={onOpenChange} />)
    expect(screen.getByText('Select datasource...')).toBeInTheDocument()
  })

  it('renders cancel and link buttons', () => {
    render(<SloLinkDialog open={true} onOpenChange={onOpenChange} />)
    expect(screen.getByText('Cancel')).toBeInTheDocument()
    expect(screen.getByText('Link')).toBeInTheDocument()
  })

  it('disables link button when form is incomplete', () => {
    render(<SloLinkDialog open={true} onOpenChange={onOpenChange} />)
    expect(screen.getByText('Link')).toBeDisabled()
  })

  it('shows locked SLO when lockedSloName provided', () => {
    render(
      <SloLinkDialog
        open={true}
        onOpenChange={onOpenChange}
        lockedSloName="latency-slo"
      />,
    )
    expect(screen.getByText('latency-slo')).toBeInTheDocument()
    expect(screen.getByText('(locked)')).toBeInTheDocument()
  })

  it('shows locked group when lockedGroupName provided', () => {
    render(
      <SloLinkDialog
        open={true}
        onOpenChange={onOpenChange}
        lockedGroupName="production"
      />,
    )
    expect(screen.getByText('production')).toBeInTheDocument()
    expect(screen.getAllByText('(locked)').length).toBeGreaterThanOrEqual(1)
  })

  it('does not render content when closed', () => {
    render(<SloLinkDialog open={false} onOpenChange={onOpenChange} />)
    expect(screen.queryByText('Link SLO to Asset Group')).not.toBeInTheDocument()
  })

  it('calls createLink when all fields filled and link clicked', async () => {
    render(
      <SloLinkDialog
        open={true}
        onOpenChange={onOpenChange}
        lockedSloName="latency-slo"
        lockedGroupName="production"
      />,
    )

    // Select datasource
    const dsSelect = screen.getAllByRole('combobox')[0]
    fireEvent.change(dsSelect, { target: { value: 'prom-prod' } })

    // Select SLI
    const sliSelect = screen.getAllByRole('combobox')[1]
    fireEvent.change(sliSelect, { target: { value: 'response-time' } })

    // Click link
    fireEvent.click(screen.getByText('Link'))

    await waitFor(() => {
      expect(mockCreateBinding).toHaveBeenCalledWith({
        groupName: 'production',
        slo_name: 'latency-slo',
        data_source_name: 'prom-prod',
      })
    })
  })
})
