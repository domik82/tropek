import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TestWrapper } from '@/test-wrapper'
import { LabelsEditorDialog } from './LabelsEditorDialog'

vi.mock('@/features/assets/hooks', () => ({
  useTagKeys: () => ({ data: [{ key: 'env', count: 3 }, { key: 'team', count: 2 }, { key: 'region', count: 1 }], isLoading: false }),
  useTagValues: () => ({ data: [{ value: 'prod', count: 3 }, { value: 'staging', count: 2 }, { value: 'dev', count: 1 }], isLoading: false }),
}))

function renderDialog(props: Partial<Parameters<typeof LabelsEditorDialog>[0]> = {}) {
  const defaults = {
    open: true,
    onOpenChange: vi.fn(),
    title: 'Edit Labels',
    labels: {},
    onSave: vi.fn(),
  }
  return render(
    <TestWrapper>
      <LabelsEditorDialog {...defaults} {...props} />
    </TestWrapper>
  )
}

describe('LabelsEditorDialog', () => {
  it('renders existing labels as key-value pairs', () => {
    renderDialog({ labels: { env: 'prod', team: 'payments' } })
    expect(screen.getByText('env')).toBeInTheDocument()
    expect(screen.getByText('prod')).toBeInTheDocument()
    expect(screen.getByText('team')).toBeInTheDocument()
    expect(screen.getByText('payments')).toBeInTheDocument()
  })

  it('removes a label when the X button is clicked', async () => {
    const user = userEvent.setup()
    renderDialog({ labels: { env: 'prod', team: 'payments' } })

    // The X remove buttons sit next to each label row. Each label row renders a span
    // containing the key and value, plus a sibling button with only an SVG <X> icon.
    // We locate them by finding buttons whose only child is an SVG element.
    const allButtons = screen.getAllByRole('button')
    const xButtons = allButtons.filter(btn => {
      const kids = Array.from(btn.children)
      return kids.length === 1 && kids[0].tagName.toLowerCase() === 'svg'
    })

    expect(xButtons.length).toBe(2)
    await user.click(xButtons[0])

    // After removing one label, only one key-value pair should remain
    const envVisible = screen.queryByText('env')
    const teamVisible = screen.queryByText('team')
    const removedCount = [envVisible, teamVisible].filter(el => el === null).length
    expect(removedCount).toBe(1)
  })

  it('calls onSave with current labels when Done is clicked', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    renderDialog({ labels: { env: 'prod' }, onSave })

    await user.click(screen.getByRole('button', { name: /done/i }))

    expect(onSave).toHaveBeenCalledWith({ env: 'prod' })
  })

  it('shows "No labels assigned" when labels is empty', () => {
    renderDialog({ labels: {} })
    expect(screen.getByText(/no labels/i)).toBeInTheDocument()
  })

  it('syncs labels when reopened with different props', async () => {
    const onOpenChange = vi.fn()
    const { rerender } = render(
      <TestWrapper>
        <LabelsEditorDialog
          open={true}
          onOpenChange={onOpenChange}
          title="Edit Labels"
          labels={{ env: 'prod' }}
          onSave={vi.fn()}
        />
      </TestWrapper>
    )

    expect(screen.getByText('env')).toBeInTheDocument()
    expect(screen.getByText('prod')).toBeInTheDocument()

    // Close dialog, then reopen with different labels
    rerender(
      <TestWrapper>
        <LabelsEditorDialog
          open={false}
          onOpenChange={onOpenChange}
          title="Edit Labels"
          labels={{ env: 'prod' }}
          onSave={vi.fn()}
        />
      </TestWrapper>
    )

    rerender(
      <TestWrapper>
        <LabelsEditorDialog
          open={true}
          onOpenChange={onOpenChange}
          title="Edit Labels"
          labels={{ team: 'platform', region: 'eu-west-1' }}
          onSave={vi.fn()}
        />
      </TestWrapper>
    )

    // Should show new labels, not stale ones
    expect(screen.getByText('team')).toBeInTheDocument()
    expect(screen.getByText('platform')).toBeInTheDocument()
    expect(screen.getByText('region')).toBeInTheDocument()
    expect(screen.queryByText('env')).not.toBeInTheDocument()
  })
})
