import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DeletionConfirmForm } from './DeletionConfirmForm'

describe('DeletionConfirmForm', () => {
  it('renders title and buttons', () => {
    render(
      <DeletionConfirmForm
        title="Delete this item?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    )
    expect(screen.getByText('Delete this item?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
  })

  it('calls onCancel when cancel clicked', () => {
    const onCancel = vi.fn()
    render(
      <DeletionConfirmForm
        title="Delete?"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('disables confirm when reason is empty and required', () => {
    render(
      <DeletionConfirmForm
        title="Delete?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        requireReason
      />
    )
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeDisabled()
  })

  it('calls onConfirm with reason and author', () => {
    const onConfirm = vi.fn()
    render(
      <DeletionConfirmForm
        title="Delete?"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
        requireReason
        requireAuthor
      />
    )

    fireEvent.change(screen.getByPlaceholderText(/Reason/), {
      target: { value: 'no longer needed' },
    })
    fireEvent.change(screen.getByPlaceholderText('Your name'), {
      target: { value: 'tester' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))

    expect(onConfirm).toHaveBeenCalledWith('no longer needed', 'tester')
  })

  it('shows pending label when isPending is true', () => {
    render(
      <DeletionConfirmForm
        title="Delete?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        isPending
        pendingLabel="Deleting..."
        requireReason={false}
      />
    )
    expect(screen.getByRole('button', { name: 'Deleting...' })).toBeDisabled()
  })

  it('uses custom confirm label', () => {
    render(
      <DeletionConfirmForm
        title="Delete?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        confirmLabel="Delete note"
        requireReason={false}
      />
    )
    expect(screen.getByRole('button', { name: 'Delete note' })).toBeInTheDocument()
  })
})
