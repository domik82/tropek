import { MoreHorizontal } from 'lucide-react'
import type { AssetGroup, AssetGroupTree } from '@/features/assets/types'
import { countLeafMembers } from '@/features/navigator/components/treeUtils'
import { TreeNode } from '@/components/tree'
import { getAssetTypeIcon, getEntityIcon } from '@/components/tree'
import { AssetTreeInlineRename } from './AssetTreeInlineRename'
import type { TreeMode, NodeType, ContextMenuState } from './types'

interface AssetTreeNodeProps {
  group: AssetGroup
  tree: AssetGroupTree
  mode: TreeMode
  depth: number
  filter: string
  selectedGroup: string | null
  selectedAsset?: string | null
  expandedGroups: Set<string>
  renamingGroup: string | null
  sloLinkCounts?: Map<string, number>
  isLastChild: boolean
  onToggleExpand: (name: string) => void
  onSelectGroup: (name: string) => void
  onSelectAsset?: (name: string, groupName: string) => void
  onOpenContextMenu: (state: ContextMenuState) => void
  onStartRename: (name: string) => void
  onFinishRename: (name: string, newDisplayName: string) => void
  onCancelRename: () => void
}

function matchesFilter(group: AssetGroup, tree: AssetGroupTree, filter: string, mode: TreeMode): boolean {
  if (!filter) return true
  const q = filter.toLowerCase()
  const label = (group.display_name ?? group.name).toLowerCase()
  if (label.includes(q)) return true

  if (mode === 'navigator' || mode === 'assets') {
    if (group.members.some(m =>
      m.asset_name.toLowerCase().includes(q) ||
      (m.asset_display_name?.toLowerCase().includes(q) ?? false)
    )) return true
  }

  const subgroups = group.subgroups
    .map(sg => tree.all_groups.find(g => g.id === sg.group_id))
    .filter(Boolean) as AssetGroup[]

  return subgroups.some(sg => matchesFilter(sg, tree, filter, mode))
}

export function AssetTreeNode({
  group, tree, mode, depth, filter, selectedGroup, selectedAsset,
  expandedGroups, renamingGroup, sloLinkCounts, isLastChild,
  onToggleExpand, onSelectGroup, onSelectAsset, onOpenContextMenu,
  onStartRename, onFinishRename, onCancelRename,
}: AssetTreeNodeProps) {
  if (!matchesFilter(group, tree, filter, mode)) return null

  const subgroups = group.subgroups
    .map(sg => tree.all_groups.find(g => g.id === sg.group_id))
    .filter(Boolean) as AssetGroup[]

  const isExpanded = expandedGroups.has(group.name) || (!!filter && matchesFilter(group, tree, filter, mode))
  const isSelected = selectedGroup === group.name
  const isRenaming = renamingGroup === group.name

  const filteredMembers = (mode === 'navigator' || mode === 'assets')
    ? (filter
        ? group.members.filter(m =>
            m.asset_name.toLowerCase().includes(filter.toLowerCase()) ||
            (m.asset_display_name?.toLowerCase().includes(filter.toLowerCase()) ?? false)
          )
        : group.members)
    : []

  const count = mode === 'navigator'
    ? countLeafMembers(group, tree)
    : (sloLinkCounts?.get(group.name) ?? 0)

  const openGroupMenu = (x: number, y: number) => {
    onOpenContextMenu({ x, y, target: { type: 'group' as NodeType, name: group.name } })
  }

  const openAssetMenu = (x: number, y: number, assetName: string, assetId?: string) => {
    onOpenContextMenu({ x, y, target: { type: 'asset' as NodeType, name: assetName, groupName: group.name, assetId } })
  }

  return (
    <div className="relative" role="treeitem" aria-expanded={isExpanded} aria-selected={isSelected}>
      {/* Group row */}
      {isRenaming ? (
        <div className="flex items-center h-8" style={{ paddingLeft: depth * 24 + 20 }}>
          <AssetTreeInlineRename
            currentName={group.display_name ?? group.name}
            onSave={newName => onFinishRename(group.name, newName)}
            onCancel={onCancelRename}
          />
        </div>
      ) : (
        <TreeNode
          icon={getEntityIcon('group')}
          iconColor={group.color ?? '#8b949e'}
          label={group.display_name ?? group.name}
          depth={depth}
          isExpandable={subgroups.length > 0 || filteredMembers.length > 0}
          isExpanded={isExpanded}
          isSelected={isSelected}
          selectionColor={group.color ?? 'var(--primary)'}
          isGroup
          badge={count > 0 ? { type: 'count' as const, value: count } : undefined}
          onClick={() => { onToggleExpand(group.name); onSelectGroup(group.name) }}
          onToggle={() => onToggleExpand(group.name)}
          onContextMenu={e => { e.preventDefault(); openGroupMenu(e.clientX, e.clientY) }}
          onDoubleClick={() => onStartRename(group.name)}
          trailingAction={
            <button
              className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-muted/80 shrink-0"
              aria-label={`Actions for ${group.display_name ?? group.name}`}
              onClick={e => {
                e.stopPropagation()
                const rect = e.currentTarget.getBoundingClientRect()
                openGroupMenu(rect.left, rect.bottom + 2)
              }}
            >
              <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
            </button>
          }
        />
      )}

      {/* Children (subgroups + asset leaves) */}
      {isExpanded && (
        <div role="group">
          {subgroups.map((sg, i) => (
            <AssetTreeNode
              key={sg.id}
              group={sg}
              tree={tree}
              mode={mode}
              depth={depth + 1}
              filter={filter}
              selectedGroup={selectedGroup}
              selectedAsset={selectedAsset}
              expandedGroups={expandedGroups}
              renamingGroup={renamingGroup}
              sloLinkCounts={sloLinkCounts}
              isLastChild={i === subgroups.length - 1 && filteredMembers.length === 0}
              onToggleExpand={onToggleExpand}
              onSelectGroup={onSelectGroup}
              onSelectAsset={onSelectAsset}
              onOpenContextMenu={onOpenContextMenu}
              onStartRename={onStartRename}
              onFinishRename={onFinishRename}
              onCancelRename={onCancelRename}
            />
          ))}

          {(mode === 'navigator' || mode === 'assets') && filteredMembers.map(m => {
            const isAssetSelected = selectedAsset === m.asset_name && selectedGroup === group.name
            return (
              <TreeNode
                key={m.asset_id}
                icon={getAssetTypeIcon(m.asset_type_name ?? 'vm')}
                iconColor="#8b949e"
                label={m.asset_display_name ?? m.asset_name}
                depth={depth + 1}
                isExpandable={false}
                isExpanded={false}
                isSelected={isAssetSelected}
                selectionColor="var(--primary)"
                onClick={() => onSelectAsset?.(m.asset_name, group.name)}
                onContextMenu={e => {
                  e.preventDefault()
                  openAssetMenu(e.clientX, e.clientY, m.asset_name, m.asset_id)
                }}
                trailingAction={
                  <button
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-muted/80 shrink-0"
                    aria-label={`Actions for ${m.asset_display_name ?? m.asset_name}`}
                    onClick={e => {
                      e.stopPropagation()
                      const rect = e.currentTarget.getBoundingClientRect()
                      openAssetMenu(rect.left, rect.bottom + 2, m.asset_name, m.asset_id)
                    }}
                  >
                    <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                  </button>
                }
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
