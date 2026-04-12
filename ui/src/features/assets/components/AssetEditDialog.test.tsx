import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TestWrapper } from '@/test-wrapper'
import { AssetEditDialog } from './AssetEditDialog'

const MOCK_ASSET = {
  id: 'a1',
  name: 'cart-service',
  displayName: 'Cart',
  typeName: 'service',
  color: null,
  tags: { env: 'prod' },
  variables: {},
  heatmapConfig: null,
  createdAt: new Date(0),
  updatedAt: new Date(0),
}

const TYPES = [
  { id: 't1', name: 'service', isDefault: true, assetCount: 5 },
  { id: 't2', name: 'api', isDefault: false, assetCount: 2 },
]

const mockMutate = vi.fn()

vi.mock('@/features/assets/hooks', () => ({
  useAsset: () => ({ data: MOCK_ASSET }),
  useAssetTypes: () => ({ data: TYPES }),
  useUpdateAsset: () => ({ mutate: mockMutate, isPending: false }),
}))

vi.mock('@/components/labels/LabelsEditorDialog', () => ({
  LabelsEditorDialog: () => null,
}))

function renderDialog(props?: Partial<React.ComponentProps<typeof AssetEditDialog>>) {
  return render(
    <TestWrapper>
      <AssetEditDialog open={true} onOpenChange={vi.fn()} assetName="cart-service" {...props} />
    </TestWrapper>
  )
}

describe('AssetEditDialog', () => {
  it('pre-fills display name and type from loaded asset', async () => {
    renderDialog()

    const input = await screen.findByDisplayValue('Cart')
    expect(input).toBeInTheDocument()

    expect(screen.getByDisplayValue('service (default)')).toBeInTheDocument()
  })

  it('calls updateAsset mutation with updated display name on save', async () => {
    mockMutate.mockClear()
    const user = userEvent.setup()
    renderDialog()

    const input = await screen.findByDisplayValue('Cart')
    await user.clear(input)
    await user.type(input, 'Cart Service V2')

    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(mockMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'cart-service',
        display_name: 'Cart Service V2',
      }),
      expect.anything()
    )
  })

  it('shows asset name in dialog title', () => {
    renderDialog()

    expect(screen.getByText('cart-service')).toBeInTheDocument()
  })
})
