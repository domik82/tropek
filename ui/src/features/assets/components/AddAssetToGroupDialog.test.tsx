import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TestWrapper } from '@/test-wrapper'
import { AddAssetToGroupDialog } from './AddAssetToGroupDialog'

const ALL_ASSETS = [
  { id: 'a1', name: 'cart-service', display_name: 'Cart', type_name: 'service', labels: {}, created_at: '', updated_at: '' },
  { id: 'a2', name: 'checkout-api', display_name: null, type_name: 'api', labels: {}, created_at: '', updated_at: '' },
  { id: 'a3', name: 'order-worker', display_name: null, type_name: 'worker', labels: {}, created_at: '', updated_at: '' },
]

const MOCK_GROUP = {
  id: 'g1', name: 'payments', display_name: 'Payments', description: '',
  members: [{ asset_id: 'a1', asset_name: 'cart-service', weight: 1.0 }],
  subgroups: [],
}

const MOCK_TREE = { top_level: [MOCK_GROUP], all_groups: [MOCK_GROUP] }

const mockMutate = vi.fn()

vi.mock('@/features/assets/hooks', () => ({
  useAssets: () => ({ data: ALL_ASSETS }),
  useAssetGroups: () => ({ data: MOCK_TREE }),
  useAddGroupMember: () => ({ mutate: mockMutate }),
}))

function renderDialog(props?: Partial<React.ComponentProps<typeof AddAssetToGroupDialog>>) {
  return render(
    <TestWrapper>
      <AddAssetToGroupDialog
        open={true}
        onOpenChange={vi.fn()}
        groupName="payments"
        {...props}
      />
    </TestWrapper>
  )
}

describe('AddAssetToGroupDialog', () => {
  it('shows assets not already in the group', () => {
    renderDialog()

    expect(screen.queryByText('Cart')).not.toBeInTheDocument()
    expect(screen.getByText('checkout-api')).toBeInTheDocument()
    expect(screen.getByText('order-worker')).toBeInTheDocument()
  })

  it('search filter narrows list', async () => {
    const user = userEvent.setup()
    renderDialog()

    const searchInput = screen.getByPlaceholderText('Search assets...')
    await user.type(searchInput, 'checkout')

    expect(screen.getByText('checkout-api')).toBeInTheDocument()
    expect(screen.queryByText('order-worker')).not.toBeInTheDocument()
  })

  it('clicking asset calls addMember mutation with correct args', async () => {
    mockMutate.mockClear()
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByText('checkout-api'))

    expect(mockMutate).toHaveBeenCalledWith(
      { groupName: 'payments', assetId: 'a2' },
      expect.any(Object)
    )
  })

  it('renders nothing when open=false', () => {
    const { container } = renderDialog({ open: false })
    expect(container.innerHTML).toBe('')
  })
})
