import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ActionPopover } from './ActionPopover'

afterEach(() => cleanup())

describe('ActionPopover', () => {
  it('renders nothing when open is false', () => {
    const { container } = render(
      <ActionPopover open={false} onClose={vi.fn()}>
        <div>form content</div>
      </ActionPopover>,
    )
    expect(container.textContent).toBe('')
  })

  it('renders children when open is true', () => {
    render(
      <ActionPopover open onClose={vi.fn()}>
        <div data-testid='form-slot'>form content</div>
      </ActionPopover>,
    )
    expect(screen.getByTestId('form-slot')).toBeInTheDocument()
  })

  it('ESC closes the popover', async () => {
    const onClose = vi.fn()
    render(
      <ActionPopover open onClose={onClose}>
        <div>form content</div>
      </ActionPopover>,
    )
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('ESC does nothing when closed', async () => {
    const onClose = vi.fn()
    render(
      <ActionPopover open={false} onClose={onClose}>
        <div>form content</div>
      </ActionPopover>,
    )
    await userEvent.keyboard('{Escape}')
    expect(onClose).not.toHaveBeenCalled()
  })
})
