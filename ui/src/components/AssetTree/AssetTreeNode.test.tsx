import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { AssetGroup, AssetGroupTree } from '@/features/assets'
import { AssetTreeNode } from './AssetTreeNode'

vi.mock('@/features/navigator/components/treeUtils', () => ({
  countLeafMembers: vi.fn(() => 1),
}))

vi.mock('./AssetTreeInlineRename', () => ({
  AssetTreeInlineRename: () => <div data-testid="inline-rename" />,
}))

const TS = new Date('2026-01-01T00:00:00Z')

const ROOT_GROUP: AssetGroup = {
  id: 'g1',
  name: 'infra',
  displayName: 'Infrastructure',
  description: null,
  color: null,
  members: [
    {
      assetId: 'a1',
      assetName: 'db-primary',
      assetDisplayName: null,
      assetTypeName: 'service',
      weight: 1.0,
    },
  ],
  subgroups: [{ groupId: 'g2', groupName: 'infra-eu', weight: 1.0 }],
  createdAt: TS,
  updatedAt: TS,
}

const CHILD_GROUP: AssetGroup = {
  id: 'g2',
  name: 'infra-eu',
  displayName: 'Infra EU',
  description: null,
  color: null,
  members: [],
  subgroups: [],
  createdAt: TS,
  updatedAt: TS,
}

const TREE: AssetGroupTree = {
  topLevel: [ROOT_GROUP],
  allGroups: [ROOT_GROUP, CHILD_GROUP],
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
      />,
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
      />,
    )
    expect(screen.queryByText('db-primary')).not.toBeInTheDocument()
  })

  it('renders when filter matches group name', () => {
    render(<AssetTreeNode group={ROOT_GROUP} {...defaultProps} filter="infra" />)
    expect(screen.getByText('Infrastructure')).toBeInTheDocument()
  })

  it('returns null when filter does not match group or children', () => {
    const { container } = render(
      <AssetTreeNode group={CHILD_GROUP} {...defaultProps} filter="zzz-no-match" />,
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
      />,
    )
    await user.click(screen.getByText('Infrastructure'))
    expect(onToggleExpand).toHaveBeenCalledWith('infra')
    expect(onSelectGroup).toHaveBeenCalledWith('infra')
  })

  it('clicking a leaf asset calls onSelectAsset with asset name AND parent group name', async () => {
    const user = userEvent.setup()
    const onSelectAsset = vi.fn()
    render(
      <AssetTreeNode
        group={ROOT_GROUP}
        {...defaultProps}
        expandedGroups={new Set(['infra'])}
        onSelectAsset={onSelectAsset}
      />,
    )
    await user.click(screen.getByText('db-primary'))
    expect(onSelectAsset).toHaveBeenCalledWith('db-primary', 'infra')
  })

  it('highlights asset only when both selectedAsset and selectedGroup match', () => {
    const GROUP_A: AssetGroup = {
      id: 'ga',
      name: 'data-tier',
      displayName: null,
      description: null,
      color: null,
      members: [
        {
          assetId: 'a1',
          assetName: 'orders-db',
          assetDisplayName: null,
          assetTypeName: 'service',
          weight: 1.0,
        },
      ],
      subgroups: [],
      createdAt: TS,
      updatedAt: TS,
    }
    const GROUP_B: AssetGroup = {
      id: 'gb',
      name: 'infra-prod',
      displayName: null,
      description: null,
      color: null,
      members: [
        {
          assetId: 'a2',
          assetName: 'orders-db',
          assetDisplayName: null,
          assetTypeName: 'service',
          weight: 1.0,
        },
      ],
      subgroups: [],
      createdAt: TS,
      updatedAt: TS,
    }
    const tree: AssetGroupTree = {
      topLevel: [GROUP_A, GROUP_B],
      allGroups: [GROUP_A, GROUP_B],
    }

    const { container } = render(
      <>
        <AssetTreeNode
          group={GROUP_A}
          {...defaultProps}
          tree={tree}
          expandedGroups={new Set(['data-tier', 'infra-prod'])}
          selectedGroup="data-tier"
          selectedAsset="orders-db"
        />
        <AssetTreeNode
          group={GROUP_B}
          {...defaultProps}
          tree={tree}
          expandedGroups={new Set(['data-tier', 'infra-prod'])}
          selectedGroup="data-tier"
          selectedAsset="orders-db"
        />
      </>,
    )

    const assetLeaves = container.querySelectorAll('[role="button"]')
    const leafRows = Array.from(assetLeaves).filter(
      (el) =>
        el.textContent?.includes('orders-db') &&
        !el.textContent?.includes('data-tier') &&
        !el.textContent?.includes('infra-prod'),
    )
    expect(leafRows).toHaveLength(2)
    expect(leafRows[0].getAttribute('data-selected')).toBe('true')
    expect(leafRows[1].getAttribute('data-selected')).toBe('false')
  })
})
