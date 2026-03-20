import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TestWrapper } from '@/test-wrapper'
import { GroupDetailPanel } from './GroupDetailPanel'
import { useAssetGroup, useRemoveGroupMember } from '@/features/assets/hooks'
import { useDeleteGroupSloLink } from '@/features/slos/hooks'

vi.mock('@/features/assets/hooks', () => ({
  useAssetGroup: vi.fn(() => ({
    data: {
      id: 'g1',
      name: 'payments',
      display_name: 'Payments',
      description: 'Payment services',
      members: [
        { asset_id: 'a1', asset_name: 'cart-service', weight: 1.0 },
        { asset_id: 'a2', asset_name: 'checkout-api', weight: 2.0 },
      ],
      subgroups: [{ group_id: 'g2', group_name: 'payments-eu', weight: 1.0 }],
    },
  })),
  useAssets: vi.fn(() => ({
    data: [
      {
        id: 'a1',
        name: 'cart-service',
        display_name: 'Cart Service',
        type_name: 'service',
        labels: { env: 'prod' },
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
      {
        id: 'a2',
        name: 'checkout-api',
        display_name: null,
        type_name: 'api',
        labels: {},
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ],
  })),
  useRemoveGroupMember: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useAssetGroups: vi.fn(() => ({
    data: {
      top_level: [
        {
          id: 'g1',
          name: 'payments',
          display_name: 'Payments',
          description: 'Payment services',
          members: [
            { asset_id: 'a1', asset_name: 'cart-service', weight: 1.0 },
            { asset_id: 'a2', asset_name: 'checkout-api', weight: 2.0 },
          ],
          subgroups: [{ group_id: 'g2', group_name: 'payments-eu', weight: 1.0 }],
        },
      ],
      all_groups: [
        {
          id: 'g1',
          name: 'payments',
          display_name: 'Payments',
          description: 'Payment services',
          members: [
            { asset_id: 'a1', asset_name: 'cart-service', weight: 1.0 },
            { asset_id: 'a2', asset_name: 'checkout-api', weight: 2.0 },
          ],
          subgroups: [{ group_id: 'g2', group_name: 'payments-eu', weight: 1.0 }],
        },
        {
          id: 'g2',
          name: 'payments-eu',
          display_name: 'Payments EU',
          description: '',
          members: [],
          subgroups: [],
        },
      ],
    },
  })),
  useUpdateAsset: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}))

vi.mock('@/features/slos/hooks', () => ({
  useGroupSloLinks: vi.fn(() => ({
    data: [
      {
        id: 'l1',
        link_name: 'link-1',
        slo_name: 'availability',
        sli_name: 'error_rate',
        data_source_name: 'prometheus-prod',
        group_name: 'payments',
      },
    ],
  })),
  useDeleteGroupSloLink: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}))

vi.mock('@/features/slos/components/GroupEditDialog', () => ({
  GroupEditDialog: vi.fn(() => null),
}))

vi.mock('@/features/slos/components/GroupDeleteDialog', () => ({
  GroupDeleteDialog: vi.fn(() => null),
}))

vi.mock('@/features/slos/components/GroupCreateDialog', () => ({
  GroupCreateDialog: vi.fn(() => null),
}))

vi.mock('@/features/slos/components/SloLinkDialog', () => ({
  SloLinkDialog: vi.fn(() => null),
}))

vi.mock('./AddAssetToGroupDialog', () => ({
  AddAssetToGroupDialog: vi.fn(() => null),
}))

vi.mock('./AssetEditDialog', () => ({
  AssetEditDialog: vi.fn(() => null),
}))

vi.mock('@/components/labels/LabelsEditorDialog', () => ({
  LabelsEditorDialog: vi.fn(() => null),
}))

describe('GroupDetailPanel', () => {
  it('renders group display name and stats line', () => {
    render(
      <GroupDetailPanel groupName="payments" onSelectGroup={() => {}} />,
      { wrapper: TestWrapper }
    )
    expect(screen.getByText('Payments')).toBeInTheDocument()
    expect(screen.getByText('2 assets · 1 subgroups · 1 linked SLOs')).toBeInTheDocument()
  })

  it('renders group description', () => {
    render(
      <GroupDetailPanel groupName="payments" onSelectGroup={() => {}} />,
      { wrapper: TestWrapper }
    )
    expect(screen.getByText('Payment services')).toBeInTheDocument()
  })

  it('renders subgroup cards with name and member count', () => {
    render(
      <GroupDetailPanel groupName="payments" onSelectGroup={() => {}} />,
      { wrapper: TestWrapper }
    )
    expect(screen.getByText('Payments EU')).toBeInTheDocument()
    expect(screen.getByText('0 assets')).toBeInTheDocument()
  })

  it('clicking subgroup card calls onSelectGroup with subgroup name', async () => {
    const onSelectGroup = vi.fn()
    const user = userEvent.setup()
    render(
      <GroupDetailPanel groupName="payments" onSelectGroup={onSelectGroup} />,
      { wrapper: TestWrapper }
    )
    await user.click(screen.getByText('Payments EU'))
    expect(onSelectGroup).toHaveBeenCalledWith('payments-eu')
  })

  it('renders members table with display names and types', () => {
    render(
      <GroupDetailPanel groupName="payments" onSelectGroup={() => {}} />,
      { wrapper: TestWrapper }
    )
    // cart-service has display_name 'Cart Service'
    expect(screen.getByText('Cart Service')).toBeInTheDocument()
    // checkout-api has display_name null, so falls back to asset_name
    expect(screen.getByText('checkout-api')).toBeInTheDocument()
    expect(screen.getByText('service')).toBeInTheDocument()
    expect(screen.getByText('api')).toBeInTheDocument()
  })

  it('renders linked SLOs with slo_name, sli_name, data_source_name columns', () => {
    render(
      <GroupDetailPanel groupName="payments" onSelectGroup={() => {}} />,
      { wrapper: TestWrapper }
    )
    expect(screen.getByText('availability')).toBeInTheDocument()
    expect(screen.getByText('error_rate')).toBeInTheDocument()
    expect(screen.getByText('prometheus-prod')).toBeInTheDocument()
  })

  it('calls removeMember when X button clicked on member row', async () => {
    const mockMutate = vi.fn()
    vi.mocked(useRemoveGroupMember).mockReturnValue({ mutate: mockMutate } as any)

    const user = userEvent.setup()
    render(
      <GroupDetailPanel groupName="payments" onSelectGroup={() => {}} />,
      { wrapper: TestWrapper }
    )
    const removeButtons = screen.getAllByTitle('Remove from group')
    await user.click(removeButtons[0])
    expect(mockMutate).toHaveBeenCalledWith({ groupName: 'payments', assetId: 'a1' })
  })

  it('calls unlinkSlo when X clicked on SLO row', async () => {
    const mockMutate = vi.fn()
    vi.mocked(useDeleteGroupSloLink).mockReturnValue({ mutate: mockMutate } as any)

    const user = userEvent.setup()
    render(
      <GroupDetailPanel groupName="payments" onSelectGroup={() => {}} />,
      { wrapper: TestWrapper }
    )
    const unlinkButton = screen.getByTitle('Unlink')
    await user.click(unlinkButton)
    expect(mockMutate).toHaveBeenCalledWith({ groupName: 'payments', linkName: 'link-1' })
  })

  it("shows 'Loading…' when group data not yet available", () => {
    vi.mocked(useAssetGroup).mockReturnValueOnce({ data: undefined } as any)

    render(
      <GroupDetailPanel groupName="payments" onSelectGroup={() => {}} />,
      { wrapper: TestWrapper }
    )
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })
})
