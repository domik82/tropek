import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TestWrapper } from '@/test-wrapper'
import { AddAssetToGroupDialog } from './AddAssetToGroupDialog'

const TS = new Date(0)

const ALL_ASSETS = [
  { id: 'a1', name: 'cart-service', displayName: 'Cart', typeName: 'service', color: null, tags: {}, variables: {}, heatmapConfig: null, createdAt: TS, updatedAt: TS },
  { id: 'a2', name: 'checkout-api', displayName: null, typeName: 'api', color: null, tags: {}, variables: {}, heatmapConfig: null, createdAt: TS, updatedAt: TS },
  { id: 'a3', name: 'order-worker', displayName: null, typeName: 'worker', color: null, tags: {}, variables: {}, heatmapConfig: null, createdAt: TS, updatedAt: TS },
]

const MOCK_GROUP = {
  id: 'g1', name: 'payments', displayName: 'Payments', description: '', color: null,
  members: [{ assetId: 'a1', assetName: 'cart-service', assetDisplayName: null, assetTypeName: 'service', weight: 1.0 }],
  subgroups: [],
  createdAt: TS,
  updatedAt: TS,
}

const MOCK_TREE = { topLevel: [MOCK_GROUP], allGroups: [MOCK_GROUP] }

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
