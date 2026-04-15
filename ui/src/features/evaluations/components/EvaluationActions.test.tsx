import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EvaluationActionsButton } from './EvaluationActions'

afterEach(() => cleanup())

describe('EvaluationActionsButton menu', () => {
  it('shows a single "Override result" item instead of pass/fail branching', async () => {
    const user = userEvent.setup()
    render(
      <EvaluationActionsButton
        currentResult='pass'
        allRowsInvalidated={false}
        noRowsInvalidated
        activeAction={null}
        onSelectAction={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: /actions/i }))
    expect(screen.getByRole('menuitem', { name: /override result/i })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /mark as successful/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /mark as failure/i })).not.toBeInTheDocument()
  })

  it('disables Invalidate when all rows are already invalidated', async () => {
    const user = userEvent.setup()
    render(
      <EvaluationActionsButton
        currentResult='pass'
        allRowsInvalidated
        noRowsInvalidated={false}
        activeAction={null}
        onSelectAction={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: /actions/i }))
    const invalidate = screen.getByRole('menuitem', { name: /^invalidate$/i })
    expect(invalidate).toHaveAttribute('aria-disabled', 'true')
  })

  it('hides Restore when no rows are invalidated', async () => {
    const user = userEvent.setup()
    render(
      <EvaluationActionsButton
        currentResult='pass'
        allRowsInvalidated={false}
        noRowsInvalidated
        activeAction={null}
        onSelectAction={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: /actions/i }))
    expect(screen.queryByRole('menuitem', { name: /^restore$/i })).not.toBeInTheDocument()
  })

  it('shows Restore when at least one row is invalidated', async () => {
    const user = userEvent.setup()
    render(
      <EvaluationActionsButton
        currentResult='pass'
        allRowsInvalidated={false}
        noRowsInvalidated={false}
        activeAction={null}
        onSelectAction={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: /actions/i }))
    expect(screen.getByRole('menuitem', { name: /restore/i })).toBeInTheDocument()
  })

  it('does not invoke onSelectAction when a disabled item is clicked', async () => {
    const onSelectAction = vi.fn()
    const user = userEvent.setup()
    render(
      <EvaluationActionsButton
        currentResult='pass'
        allRowsInvalidated
        noRowsInvalidated={false}
        activeAction={null}
        onSelectAction={onSelectAction}
      />,
    )
    await user.click(screen.getByRole('button', { name: /actions/i }))
    await user.click(screen.getByRole('menuitem', { name: /^invalidate$/i }))
    expect(onSelectAction).not.toHaveBeenCalled()
  })

  it('shows the Add Note item when onAddNote is provided', async () => {
    const onAddNote = vi.fn()
    const user = userEvent.setup()
    render(
      <EvaluationActionsButton
        currentResult='pass'
        allRowsInvalidated={false}
        noRowsInvalidated
        activeAction={null}
        onSelectAction={vi.fn()}
        onAddNote={onAddNote}
      />,
    )
    await user.click(screen.getByRole('button', { name: /actions/i }))
    await user.click(screen.getByRole('menuitem', { name: /add note/i }))
    expect(onAddNote).toHaveBeenCalledOnce()
  })
})
