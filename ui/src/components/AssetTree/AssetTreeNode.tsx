import { ChevronRight, MoreHorizontal } from 'lucide-react'
import type { AssetGroup, AssetGroupTree } from '@/features/assets/types'
import { countLeafMembers } from '@/features/navigator/components/treeUtils'
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
    if (group.members.some(m => m.asset_name.toLowerCase().includes(q))) return true
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
  const paddingLeft = depth * 16 + 8

  const filteredMembers = (mode === 'navigator' || mode === 'assets')
    ? (filter
        ? group.members.filter(m => m.asset_name.toLowerCase().includes(filter.toLowerCase()))
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
      {/* Tree connector lines */}
      {depth > 0 && (
        <>
          {/* Horizontal stub */}
          <div
            className="absolute bg-border/35"
            style={{
              left: (depth - 1) * 16 + 14,
              top: 14,
              width: 8,
              height: 1,
            }}
          />
          {/* Junction dot */}
          <div
            className="absolute rounded-full bg-border/60"
            style={{
              left: (depth - 1) * 16 + 12,
              top: 12,
              width: 4,
              height: 4,
            }}
          />
          {/* Vertical line from parent */}
          {!isLastChild && (
            <div
              className="absolute bg-border/35"
              style={{
                left: (depth - 1) * 16 + 13,
                top: 0,
                width: 1,
                height: '100%',
              }}
            />
          )}
          {isLastChild && (
            <div
              className="absolute bg-border/35"
              style={{
                left: (depth - 1) * 16 + 13,
                top: 0,
                width: 1,
                height: 14,
              }}
            />
          )}
        </>
      )}

      {/* Group row */}
      <div
        className={`group flex items-center gap-1 cursor-pointer rounded-sm transition-colors relative ${
          isSelected
            ? 'bg-primary/15 border-l-2 border-primary'
            : 'hover:bg-muted/50'
        }`}
        style={{ paddingLeft: isSelected ? paddingLeft - 2 : paddingLeft, paddingRight: 8 }}
        role="button"
        tabIndex={0}
        onClick={() => {
          onToggleExpand(group.name)
          onSelectGroup(group.name)
        }}
        onKeyDown={e => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onToggleExpand(group.name)
            onSelectGroup(group.name)
          }
        }}
        onContextMenu={e => {
          e.preventDefault()
          openGroupMenu(e.clientX, e.clientY)
        }}
        onDoubleClick={e => {
          e.stopPropagation()
          onStartRename(group.name)
        }}
      >
        <ChevronRight
          className={`w-3.5 h-3.5 shrink-0 text-muted-foreground transition-transform ${
            isExpanded ? 'rotate-90' : ''
          } ${subgroups.length === 0 && filteredMembers.length === 0 ? 'opacity-30' : ''}`}
        />

        <div className="flex-1 min-w-0 py-1.5">
          {isRenaming ? (
            <AssetTreeInlineRename
              currentName={group.display_name ?? group.name}
              onSave={newName => onFinishRename(group.name, newName)}
              onCancel={onCancelRename}
            />
          ) : (
            <span className={`text-[14px] font-semibold truncate block ${
              isSelected ? 'text-primary' : ''
            }`}>
              {group.display_name ?? group.name}
            </span>
          )}
        </div>

        {count > 0 && !isRenaming && (
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium shrink-0 ${
            isSelected
              ? 'bg-primary/20 text-primary'
              : 'bg-muted text-muted-foreground'
          }`}>
            {count}
          </span>
        )}

        {!isRenaming && (
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
        )}
      </div>

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
            const assetPadding = (depth + 1) * 16 + 8
            return (
              <div
                key={m.asset_id}
                className={`group flex items-center gap-1 cursor-pointer rounded-sm transition-colors ${
                  isAssetSelected
                    ? 'bg-primary/15 border-l-2 border-primary'
                    : 'hover:bg-muted/50'
                }`}
                style={{ paddingLeft: isAssetSelected ? assetPadding - 2 : assetPadding, paddingRight: 8 }}
                role="button"
                tabIndex={0}
                onClick={() => onSelectAsset?.(m.asset_name, group.name)}
                onKeyDown={e => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onSelectAsset?.(m.asset_name, group.name)
                  }
                }}
                onContextMenu={e => {
                  e.preventDefault()
                  openAssetMenu(e.clientX, e.clientY, m.asset_name, m.asset_id)
                }}
              >
                <span className="font-mono text-[13px] text-muted-foreground truncate py-1 flex-1">
                  {m.asset_name}
                </span>
                <button
                  className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-muted/80 shrink-0"
                  aria-label={`Actions for ${m.asset_name}`}
                  onClick={e => {
                    e.stopPropagation()
                    const rect = e.currentTarget.getBoundingClientRect()
                    openAssetMenu(rect.left, rect.bottom + 2, m.asset_name, m.asset_id)
                  }}
                >
                  <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
