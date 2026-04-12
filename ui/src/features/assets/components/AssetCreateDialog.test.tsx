import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TestWrapper } from '@/test-wrapper'
import { AssetCreateDialog } from './AssetCreateDialog'

const TYPES = [
  { id: 't1', name: 'service', isDefault: true, assetCount: 5 },
  { id: 't2', name: 'endpoint', isDefault: false, assetCount: 2 },
]

const TREE = {
  topLevel: [],
  allGroups: [
    {
      id: 'g1',
      name: 'payments',
      displayName: 'Payments',
      description: null,
      color: null,
      members: [],
      subgroups: [],
      createdAt: new Date(0),
      updatedAt: new Date(0),
    },
  ],
}

const mockCreateAsset = vi.fn().mockResolvedValue({ id: 'new-id' })
const mockAddGroupMember = vi.fn().mockResolvedValue({})

vi.mock('@/features/assets/hooks', () => ({
  useAssetTypes: () => ({ data: TYPES }),
  useAssetGroups: () => ({ data: TREE }),
  useCreateAsset: () => ({ mutateAsync: mockCreateAsset, isPending: false }),
  useAddGroupMember: () => ({ mutateAsync: mockAddGroupMember, isPending: false }),
}))

vi.mock('@/components/labels/LabelsEditorDialog', () => ({
  LabelsEditorDialog: () => null,
}))

function renderDialog(props?: Partial<React.ComponentProps<typeof AssetCreateDialog>>) {
  return render(
    <TestWrapper>
      <AssetCreateDialog open={true} onOpenChange={vi.fn()} {...props} />
    </TestWrapper>
  )
}

describe('AssetCreateDialog', () => {
  it('shows validation error when name contains uppercase or special chars', async () => {
    const user = userEvent.setup()
    renderDialog()

    const input = screen.getByPlaceholderText('linux-cache-01')
    await user.type(input, 'Bad Name!')

    expect(screen.getByText(/lowercase letters, numbers, hyphens only/)).toBeInTheDocument()
  })

  it('enables Add button when name is valid', async () => {
    const user = userEvent.setup()
    renderDialog()

    const input = screen.getByPlaceholderText('linux-cache-01')
    await user.type(input, 'my-service')

    expect(screen.getByRole('button', { name: 'Add' })).not.toBeDisabled()
  })

  it('pre-selects default asset type', () => {
    renderDialog()

    expect(screen.getByDisplayValue('service (default)')).toBeInTheDocument()
  })

  it('calls createAsset mutation on submit', async () => {
    mockCreateAsset.mockClear()
    const user = userEvent.setup()
    renderDialog()

    const input = screen.getByPlaceholderText('linux-cache-01')
    await user.type(input, 'my-service')
    await user.click(screen.getByRole('button', { name: 'Add' }))

    expect(mockCreateAsset).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'my-service', type_name: 'service' })
    )
  })
})
