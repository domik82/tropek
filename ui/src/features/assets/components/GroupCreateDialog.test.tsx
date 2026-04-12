import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { GroupCreateDialog } from './GroupCreateDialog'

const mockMutateAsync = vi.fn().mockResolvedValue({ id: 'group-1', name: 'test-group' })

vi.mock('@/features/assets', () => ({
  useCreateGroup: () => ({ mutateAsync: mockMutateAsync, isPending: false }),
  useAddSubgroup: () => ({ mutateAsync: vi.fn() }),
  useGroupTree: () => ({ data: { all_groups: [], root_groups: [] } }),
}))

vi.mock('@/features/assets/components/GroupTreeSelector', () => ({
  GroupTreeSelector: () => <select data-testid="parent-selector" />,
}))

describe('GroupCreateDialog', () => {
  const onOpenChange = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders dialog title when open', () => {
    render(<GroupCreateDialog open={true} onOpenChange={onOpenChange} />)
    expect(screen.getByText('New Asset Group')).toBeInTheDocument()
  })

  it('renders name input', () => {
    render(<GroupCreateDialog open={true} onOpenChange={onOpenChange} />)
    expect(screen.getByPlaceholderText('production-apis')).toBeInTheDocument()
  })

  it('disables submit when name is empty', () => {
    render(<GroupCreateDialog open={true} onOpenChange={onOpenChange} />)
    const createBtn = screen.getByText('Create')
    expect(createBtn).toBeDisabled()
  })

  it('enables submit when valid name is entered', () => {
    render(<GroupCreateDialog open={true} onOpenChange={onOpenChange} />)
    fireEvent.change(screen.getByPlaceholderText('production-apis'), {
      target: { value: 'test-group' },
    })
    const createBtn = screen.getByText('Create')
    expect(createBtn).not.toBeDisabled()
  })

  it('shows validation error for invalid name format', () => {
    render(<GroupCreateDialog open={true} onOpenChange={onOpenChange} />)
    fireEvent.change(screen.getByPlaceholderText('production-apis'), {
      target: { value: 'INVALID NAME!' },
    })
    expect(screen.getByText(/lowercase letters, numbers, hyphens only/)).toBeInTheDocument()
  })

  it('calls onCreate with group data when submitted', async () => {
    render(<GroupCreateDialog open={true} onOpenChange={onOpenChange} />)
    fireEvent.change(screen.getByPlaceholderText('production-apis'), {
      target: { value: 'test-group' },
    })
    fireEvent.click(screen.getByText('Create'))
    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        name: 'test-group',
        display_name: undefined,
        description: undefined,
      })
    })
  })

  it('renders cancel button', () => {
    render(<GroupCreateDialog open={true} onOpenChange={onOpenChange} />)
    expect(screen.getByText('Cancel')).toBeInTheDocument()
  })

  it('does not render content when closed', () => {
    render(<GroupCreateDialog open={false} onOpenChange={onOpenChange} />)
    expect(screen.queryByText('New Asset Group')).not.toBeInTheDocument()
  })
})
