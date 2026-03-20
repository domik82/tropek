import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AssetTreeContextMenu } from './AssetTreeContextMenu'
import type { ContextMenuState } from './types'

const groupTarget: ContextMenuState['target'] = { type: 'group', name: 'My Group' }
const assetTarget: ContextMenuState['target'] = { type: 'asset', name: 'My Asset', groupName: 'My Group', assetId: 'asset-1' }

const baseState = (target: ContextMenuState['target'] = groupTarget): ContextMenuState => ({ x: 100, y: 100, target })

describe('AssetTreeContextMenu', () => {
  it('renders group context menu items', () => {
    const onAction = vi.fn()
    const onClose = vi.fn()
    render(
      <AssetTreeContextMenu
        state={baseState(groupTarget)}
        mode="navigator"
        onAction={onAction}
        onClose={onClose}
      />
    )
    expect(screen.getByText('Rename')).toBeInTheDocument()
    expect(screen.getByText('Edit details\u2026')).toBeInTheDocument()
    expect(screen.getByText('Add subgroup')).toBeInTheDocument()
    expect(screen.getByText('Delete group')).toBeInTheDocument()
  })

  it('renders asset context menu items', () => {
    const onAction = vi.fn()
    const onClose = vi.fn()
    render(
      <AssetTreeContextMenu
        state={baseState(assetTarget)}
        mode="navigator"
        onAction={onAction}
        onClose={onClose}
      />
    )
    expect(screen.getByText('View evaluations')).toBeInTheDocument()
    expect(screen.getByText('Remove from group')).toBeInTheDocument()
    expect(screen.getByText('Edit asset\u2026')).toBeInTheDocument()
    expect(screen.getByText('Delete asset')).toBeInTheDocument()
  })

  it('navigator mode shows "Add asset to group" and not "Link SLO\u2026"', () => {
    const onAction = vi.fn()
    const onClose = vi.fn()
    render(
      <AssetTreeContextMenu
        state={baseState(groupTarget)}
        mode="navigator"
        onAction={onAction}
        onClose={onClose}
      />
    )
    expect(screen.getByText('Add asset to group')).toBeInTheDocument()
    expect(screen.queryByText('Link SLO\u2026')).not.toBeInTheDocument()
  })

  it('slo mode shows "Link SLO\u2026" and not "Add asset to group"', () => {
    const onAction = vi.fn()
    const onClose = vi.fn()
    render(
      <AssetTreeContextMenu
        state={baseState(groupTarget)}
        mode="slo"
        onAction={onAction}
        onClose={onClose}
      />
    )
    expect(screen.getByText('Link SLO\u2026')).toBeInTheDocument()
    expect(screen.queryByText('Add asset to group')).not.toBeInTheDocument()
  })

  it('disabled items do not fire onAction when clicked', async () => {
    const user = userEvent.setup()
    const onAction = vi.fn()
    const onClose = vi.fn()
    render(
      <AssetTreeContextMenu
        state={baseState(groupTarget)}
        mode="navigator"
        onAction={onAction}
        onClose={onClose}
      />
    )
    const disabledButton = screen.getByText('Move to\u2026 (coming soon)').closest('button')!
    await user.click(disabledButton)
    expect(onAction).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('clicking enabled item fires onAction with (action, target) and calls onClose', async () => {
    const user = userEvent.setup()
    const onAction = vi.fn()
    const onClose = vi.fn()
    render(
      <AssetTreeContextMenu
        state={baseState(groupTarget)}
        mode="navigator"
        onAction={onAction}
        onClose={onClose}
      />
    )
    await user.click(screen.getByText('Rename'))
    expect(onAction).toHaveBeenCalledWith('rename', groupTarget)
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
