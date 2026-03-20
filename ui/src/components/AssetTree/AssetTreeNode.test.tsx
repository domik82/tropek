import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { AssetGroup, AssetGroupTree } from '@/features/assets/types'
import { AssetTreeNode } from './AssetTreeNode'

vi.mock('@/features/navigator/components/treeUtils', () => ({
  countLeafMembers: vi.fn(() => 1),
}))

vi.mock('./AssetTreeInlineRename', () => ({
  AssetTreeInlineRename: () => <div data-testid="inline-rename" />,
}))

const ROOT_GROUP: AssetGroup = {
  id: 'g1',
  name: 'infra',
  display_name: 'Infrastructure',
  members: [{ asset_id: 'a1', asset_name: 'db-primary', weight: 1.0 }],
  subgroups: [{ group_id: 'g2', group_name: 'infra-eu', weight: 1.0 }],
}

const CHILD_GROUP: AssetGroup = {
  id: 'g2',
  name: 'infra-eu',
  display_name: 'Infra EU',
  members: [],
  subgroups: [],
}

const TREE: AssetGroupTree = {
  top_level: [ROOT_GROUP],
  all_groups: [ROOT_GROUP, CHILD_GROUP],
}

const defaultProps = {
  tree: TREE,
  mode: 'navigator' as const,
  depth: 0,
  filter: '',
  selectedGroup: null,
  selectedAsset: null,
  expandedGroups: new Set<string>(),
  renamingGroup: null,
  sloLinkCounts: undefined,
  isLastChild: false,
  onToggleExpand: vi.fn(),
  onSelectGroup: vi.fn(),
  onSelectAsset: vi.fn(),
  onOpenContextMenu: vi.fn(),
  onStartRename: vi.fn(),
  onFinishRename: vi.fn(),
  onCancelRename: vi.fn(),
}

describe('AssetTreeNode', () => {
  it('renders group display name', () => {
    render(<AssetTreeNode group={ROOT_GROUP} {...defaultProps} />)
    expect(screen.getByText('Infrastructure')).toBeInTheDocument()
  })

  it('shows asset leaves when expanded in navigator mode', () => {
    render(
      <AssetTreeNode
        group={ROOT_GROUP}
        {...defaultProps}
        expandedGroups={new Set(['infra'])}
        mode="navigator"
      />
    )
    expect(screen.getByText('db-primary')).toBeInTheDocument()
  })

  it('hides asset leaves in slo mode', () => {
    render(
      <AssetTreeNode
        group={ROOT_GROUP}
        {...defaultProps}
        expandedGroups={new Set(['infra'])}
        mode="slo"
      />
    )
    expect(screen.queryByText('db-primary')).not.toBeInTheDocument()
  })

  it('renders when filter matches group name', () => {
    render(<AssetTreeNode group={ROOT_GROUP} {...defaultProps} filter="infra" />)
    expect(screen.getByText('Infrastructure')).toBeInTheDocument()
  })

  it('returns null when filter does not match group or children', () => {
    const { container } = render(
      <AssetTreeNode group={CHILD_GROUP} {...defaultProps} filter="zzz-no-match" />
    )
    expect(container.innerHTML).toBe('')
  })

  it('clicking group row calls onToggleExpand and onSelectGroup', async () => {
    const user = userEvent.setup()
    const onToggleExpand = vi.fn()
    const onSelectGroup = vi.fn()
    render(
      <AssetTreeNode
        group={ROOT_GROUP}
        {...defaultProps}
        onToggleExpand={onToggleExpand}
        onSelectGroup={onSelectGroup}
      />
    )
    await user.click(screen.getByText('Infrastructure'))
    expect(onToggleExpand).toHaveBeenCalledWith('infra')
    expect(onSelectGroup).toHaveBeenCalledWith('infra')
  })
})
