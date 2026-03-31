import { useState, useMemo, useCallback } from 'react'
import { Plus, MoreHorizontal, Settings } from 'lucide-react'
import { TreeFilter, TreeNode, getEntityIcon } from '@/components/tree'
import { useAssetGroups } from '@/features/assets'
import { countLeafMembers } from '@/features/navigator'
import { AssetTreeNode } from './AssetTreeNode'
import { AssetTreeContextMenu } from './AssetTreeContextMenu'
import { AssetTreeFooter } from './AssetTreeFooter'
import { AssetTreeDialogs, useDialogState } from './AssetTreeDialogs'
import { useAssetTreeActions } from './useAssetTreeActions'
import { SANS_SERIF } from '@/lib/fonts'
import type { TreeMode, ContextMenuState } from './types'

export interface AssetTreeProps {
  mode: TreeMode
  selectedGroup: string | null
  selectedAsset?: string | null
  onSelectGroup: (name: string | null) => void
  onSelectAsset?: (name: string, groupName: string) => void
  width?: number
  onCreateGroup?: () => void
  onEditGroup?: (name: string) => void
  onDeleteGroup?: (name: string) => void
  onAddSloLink?: (groupName: string) => void
  onAddAsset?: () => void
}

export function AssetTree({
  mode, selectedGroup, selectedAsset,
  onSelectGroup, onSelectAsset, width = 260,
  onCreateGroup: externalCreateGroup,
  onEditGroup: externalEditGroup,
  onDeleteGroup: externalDeleteGroup,
  onAddSloLink: externalAddSloLink,
  onAddAsset: externalAddAsset,
}: AssetTreeProps) {
  const { data: tree, isLoading } = useAssetGroups()

  const [filter, setFilter] = useState('')
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const [renamingGroup, setRenamingGroup] = useState<string | null>(null)
  const [bulkMenuOpen, setBulkMenuOpen] = useState(false)

  // Dialog state
  const { dialogState, updateDialog } = useDialogState()

  // SLO link counts
  const sloLinkCounts = useSloLinkCounts()

  const handleCreateGroup = useCallback((parentName?: string) => {
    if (externalCreateGroup) {
      externalCreateGroup()
    } else {
      void parentName
      updateDialog('createDialogOpen', true)
    }
  }, [externalCreateGroup, updateDialog])

  const handleEditGroup = useCallback((name: string) => {
    if (externalEditGroup) {
      externalEditGroup(name)
    } else {
      updateDialog('editingGroupName', name)
    }
  }, [externalEditGroup, updateDialog])

  const handleDeleteGroup = useCallback((name: string) => {
    if (externalDeleteGroup) {
      externalDeleteGroup(name)
    } else {
      updateDialog('deletingGroupName', name)
    }
  }, [externalDeleteGroup, updateDialog])

  const handleAddSloLink = useCallback((groupName: string) => {
    if (externalAddSloLink) {
      externalAddSloLink(groupName)
    } else {
      updateDialog('linkingGroupName', groupName)
    }
  }, [externalAddSloLink, updateDialog])

  const { dispatch, handleRename } = useAssetTreeActions(mode, {
    onCreateGroup: handleCreateGroup,
    onEditGroup: handleEditGroup,
    onDeleteGroup: handleDeleteGroup,
    onAddSloLink: handleAddSloLink,
    onAddAssetToGroup: (name) => updateDialog('addAssetGroupName', name),
    onEditAsset: (name) => updateDialog('editingAssetName', name),
    onStartRename: setRenamingGroup,
    onSelectAsset,
  })

  const handleToggleExpand = useCallback((name: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }, [])

  const handleOpenContextMenu = useCallback((state: ContextMenuState) => {
    setContextMenu(state)
  }, [])

  const handleFinishRename = useCallback((name: string, newDisplayName: string) => {
    handleRename(name, newDisplayName)
    setRenamingGroup(null)
  }, [handleRename])

  const totalCount = useMemo(() => {
    if (!tree) return 0
    if (mode === 'navigator') {
      return tree.top_level.reduce((sum, g) => sum + countLeafMembers(g, tree), 0)
    }
    let total = 0
    sloLinkCounts.forEach(v => { total += v })
    return total
  }, [tree, mode, sloLinkCounts])

  const expandAll = useCallback(() => {
    if (!tree) return
    setExpandedGroups(new Set(tree.all_groups.map(g => g.name)))
    setBulkMenuOpen(false)
  }, [tree])

  const collapseAll = useCallback(() => {
    setExpandedGroups(new Set())
    setBulkMenuOpen(false)
  }, [])

  return (
    <div
      className="flex flex-col h-full bg-sidebar-bg border-r border-border shrink-0"
      style={{ width, fontFamily: SANS_SERIF }}
    >
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-border flex items-center justify-between">
        <span className="text-[15px] font-bold text-foreground">Asset Groups</span>
        <div className="flex gap-1.5">
          <button
            onClick={() => handleCreateGroup()}
            className="p-1.5 rounded-md bg-primary/15 hover:bg-primary/25 transition-colors text-primary"
            title="New group"
          >
            <Plus className="w-4 h-4" />
          </button>
          <div className="relative">
            <button
              onClick={() => setBulkMenuOpen(v => !v)}
              className="p-1.5 rounded-md border border-border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
              title="Actions"
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>
            {bulkMenuOpen && (
              <div className="absolute right-0 top-full mt-1 z-50 bg-popover border border-border rounded-lg shadow-lg py-1 min-w-[160px]">
                <button
                  className="w-full px-3 py-1.5 text-sm text-left hover:bg-accent transition-colors"
                  onClick={expandAll}
                >
                  Expand all
                </button>
                <button
                  className="w-full px-3 py-1.5 text-sm text-left hover:bg-accent transition-colors"
                  onClick={collapseAll}
                >
                  Collapse all
                </button>
                {(mode === 'navigator' || mode === 'assets') && (
                  <>
                    <div className="my-1 mx-2 border-t border-border" />
                    <button
                      className="w-full px-3 py-1.5 text-sm text-left hover:bg-accent transition-colors flex items-center gap-2 text-link"
                      onClick={() => { updateDialog('typesDialogOpen', true); setBulkMenuOpen(false) }}
                    >
                      <Settings className="w-4 h-4" />
                      Manage Asset Types
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Filter */}
      <div className="px-3 py-2">
        <TreeFilter
          value={filter}
          onChange={setFilter}
          placeholder="Filter groups & assets..."
        />
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto px-1 py-1" role="tree" aria-label="Asset groups">
        {isLoading && (
          <p className="px-3 py-2 text-xs text-muted-foreground">Loading...</p>
        )}

        {!isLoading && tree && (
          <>
            {/* "All" item */}
            <TreeNode
              icon={getEntityIcon('all')}
              iconColor={selectedGroup === null ? 'var(--primary)' : 'var(--entity-group)'}
              label="All"
              depth={0}
              isExpandable={false}
              isExpanded={false}
              isSelected={selectedGroup === null}
              selectionColor="var(--primary)"
              isGroup
              badge={totalCount > 0 ? { type: 'count' as const, value: totalCount } : undefined}
              onClick={() => onSelectGroup(null)}
            />

            <div className="my-1 mx-3 border-t border-border/50" />

            {/* Top-level groups */}
            {tree.top_level.map((group) => (
              <AssetTreeNode
                key={group.id}
                group={group}
                tree={tree}
                mode={mode}
                depth={0}
                filter={filter}
                selectedGroup={selectedGroup}
                selectedAsset={selectedAsset}
                expandedGroups={expandedGroups}
                renamingGroup={renamingGroup}
                sloLinkCounts={sloLinkCounts}
                onToggleExpand={handleToggleExpand}
                onSelectGroup={onSelectGroup}
                onSelectAsset={onSelectAsset}
                onOpenContextMenu={handleOpenContextMenu}
                onStartRename={setRenamingGroup}
                onFinishRename={handleFinishRename}
                onCancelRename={() => setRenamingGroup(null)}
              />
            ))}

            <div className="my-1 mx-3 border-t border-border/50" />

            {/* Ungrouped */}
            <TreeNode
              icon={getEntityIcon('group')}
              iconColor="var(--entity-group)"
              label="Ungrouped"
              depth={0}
              isExpandable={false}
              isExpanded={false}
              isSelected={selectedGroup === '__ungrouped__'}
              selectionColor="var(--primary)"
              onClick={() => onSelectGroup('__ungrouped__')}
            />
          </>
        )}
      </div>

      {/* Footer */}
      <AssetTreeFooter
        mode={mode}
        onCreateGroup={() => handleCreateGroup()}
        onAddAsset={externalAddAsset}
      />

      {/* Context menu */}
      {contextMenu && (
        <AssetTreeContextMenu
          state={contextMenu}
          mode={mode}
          onAction={dispatch}
          onClose={() => setContextMenu(null)}
        />
      )}

      {/* Dialogs */}
      <AssetTreeDialogs
        dialogState={dialogState}
        mode={mode}
        selectedGroup={selectedGroup}
        onSelectGroup={onSelectGroup}
        onCloseCreate={() => updateDialog('createDialogOpen', false)}
        onCloseEdit={() => updateDialog('editingGroupName', null)}
        onCloseDelete={() => updateDialog('deletingGroupName', null)}
        onCloseLink={() => updateDialog('linkingGroupName', null)}
        onCloseTypes={() => updateDialog('typesDialogOpen', false)}
        onCloseAddAsset={() => updateDialog('addAssetGroupName', null)}
        onCloseEditAsset={() => updateDialog('editingAssetName', null)}
        hasExternalCreateGroup={!!externalCreateGroup}
        hasExternalEditGroup={!!externalEditGroup}
        hasExternalDeleteGroup={!!externalDeleteGroup}
        hasExternalAddSloLink={!!externalAddSloLink}
      />
    </div>
  )
}

/**
 * Hook that fetches SLO link counts for all groups in slo mode.
 * In navigator mode, returns an empty map (no fetches).
 */
function useSloLinkCounts(): Map<string, number> {
  return useMemo(() => new Map<string, number>(), [])
}
