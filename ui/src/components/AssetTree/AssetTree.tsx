import { useState, useMemo, useCallback } from 'react'
import { Search, X, Plus, MoreHorizontal, FolderTree, Settings } from 'lucide-react'
import { useAssetGroups } from '@/features/assets/hooks'
import { countLeafMembers } from '@/features/navigator/components/treeUtils'
import { GroupCreateDialog } from '@/features/slos/components/GroupCreateDialog'
import { GroupEditDialog } from '@/features/slos/components/GroupEditDialog'
import { GroupDeleteDialog } from '@/features/slos/components/GroupDeleteDialog'
import { SloLinkDialog } from '@/features/slos/components/SloLinkDialog'
import { AssetTypesDialog } from '@/features/assets/components/AssetTypesDialog'
import { AssetTreeNode } from './AssetTreeNode'
import { AssetTreeContextMenu } from './AssetTreeContextMenu'
import { AssetTreeFooter } from './AssetTreeFooter'
import { useAssetTreeActions } from './useAssetTreeActions'
import type { TreeMode, ContextMenuState } from './types'

export interface AssetTreeProps {
  mode: TreeMode
  selectedGroup: string | null
  selectedAsset?: string | null
  onSelectGroup: (name: string | null) => void
  onSelectAsset?: (name: string) => void
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

  // Filter
  const [filter, setFilter] = useState('')

  // Expand/collapse
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())

  // Context menu
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)

  // Inline rename
  const [renamingGroup, setRenamingGroup] = useState<string | null>(null)

  // Bulk actions menu
  const [bulkMenuOpen, setBulkMenuOpen] = useState(false)

  // Dialog state (only used if external callbacks not provided)
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editingGroupName, setEditingGroupName] = useState<string | null>(null)
  const [deletingGroupName, setDeletingGroupName] = useState<string | null>(null)
  const [linkingGroupName, setLinkingGroupName] = useState<string | null>(null)
  const [typesDialogOpen, setTypesDialogOpen] = useState(false)

  // SLO link counts for slo mode (batch endpoint not yet available)
  const sloLinkCounts = useSloLinkCounts()

  const handleCreateGroup = useCallback((parentName?: string) => {
    if (externalCreateGroup) {
      externalCreateGroup()
    } else {
      void parentName // GroupCreateDialog has its own parent selector
      setCreateDialogOpen(true)
    }
  }, [externalCreateGroup])

  const handleEditGroup = useCallback((name: string) => {
    if (externalEditGroup) {
      externalEditGroup(name)
    } else {
      setEditingGroupName(name)
    }
  }, [externalEditGroup])

  const handleDeleteGroup = useCallback((name: string) => {
    if (externalDeleteGroup) {
      externalDeleteGroup(name)
    } else {
      setDeletingGroupName(name)
    }
  }, [externalDeleteGroup])

  const handleAddSloLink = useCallback((groupName: string) => {
    if (externalAddSloLink) {
      externalAddSloLink(groupName)
    } else {
      setLinkingGroupName(groupName)
    }
  }, [externalAddSloLink])

  const { dispatch, handleRename } = useAssetTreeActions(mode, {
    onCreateGroup: handleCreateGroup,
    onEditGroup: handleEditGroup,
    onDeleteGroup: handleDeleteGroup,
    onAddSloLink: handleAddSloLink,
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

  // Total count for "All" item
  const totalCount = useMemo(() => {
    if (!tree) return 0
    if (mode === 'navigator') {
      return tree.top_level.reduce((sum, g) => sum + countLeafMembers(g, tree), 0)
    }
    let total = 0
    sloLinkCounts.forEach(v => { total += v })
    return total
  }, [tree, mode, sloLinkCounts])

  // Bulk actions
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
      className="flex flex-col h-full bg-card/50 border-r border-border shrink-0"
      style={{ width, fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
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
                      className="w-full px-3 py-1.5 text-sm text-left hover:bg-accent transition-colors flex items-center gap-2 text-[#58A6FF]"
                      onClick={() => { setTypesDialogOpen(true); setBulkMenuOpen(false) }}
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
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-amber-400/70" />
          <input
            type="text"
            placeholder="Filter groups & assets..."
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="w-full bg-input border border-border rounded-md pl-8 pr-7 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary/50"
          />
          {filter && (
            <button
              onClick={() => setFilter('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto px-1 py-1">
        {isLoading && (
          <p className="px-3 py-2 text-xs text-muted-foreground">Loading...</p>
        )}

        {!isLoading && tree && (
          <>
            {/* "All" item */}
            <div
              className={`flex items-center gap-2 px-2 py-1.5 rounded-sm cursor-pointer transition-colors ${
                selectedGroup === null
                  ? 'bg-primary/15 border-l-2 border-primary font-medium'
                  : 'hover:bg-muted/50'
              }`}
              style={{ paddingLeft: selectedGroup === null ? 6 : 8 }}
              onClick={() => onSelectGroup(null)}
            >
              <FolderTree className={`w-4 h-4 shrink-0 ${
                selectedGroup === null ? 'text-primary' : 'text-muted-foreground'
              }`} />
              <span className={`text-[14px] font-medium flex-1 ${
                selectedGroup === null ? 'text-primary' : ''
              }`}>All</span>
              {totalCount > 0 && (
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                  selectedGroup === null
                    ? 'bg-primary/20 text-primary'
                    : 'bg-muted text-muted-foreground'
                }`}>
                  {totalCount}
                </span>
              )}
            </div>

            <div className="my-1 mx-3 border-t border-border/50" />

            {/* Top-level groups */}
            {tree.top_level.map((group, i) => (
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
                isLastChild={i === tree.top_level.length - 1}
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
            <div
              className={`flex items-center gap-2 px-2 py-1.5 rounded-sm cursor-pointer transition-colors ${
                selectedGroup === '__ungrouped__'
                  ? 'bg-primary/15 border-l-2 border-primary font-medium'
                  : 'hover:bg-muted/50 text-muted-foreground italic'
              }`}
              style={{ paddingLeft: selectedGroup === '__ungrouped__' ? 6 : 8 }}
              onClick={() => onSelectGroup('__ungrouped__')}
            >
              <span className="w-2 h-2 rounded-full bg-muted-foreground/40 shrink-0" />
              <span className="text-[14px]">Ungrouped</span>
            </div>
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

      {/* Dialogs (self-managed when no external callbacks) */}
      {!externalCreateGroup && (
        <GroupCreateDialog
          open={createDialogOpen}
          onOpenChange={setCreateDialogOpen}
        />
      )}
      {!externalEditGroup && (
        <GroupEditDialog
          open={editingGroupName !== null}
          onOpenChange={open => { if (!open) setEditingGroupName(null) }}
          groupName={editingGroupName}
        />
      )}
      {!externalDeleteGroup && (
        <GroupDeleteDialog
          open={deletingGroupName !== null}
          onOpenChange={open => { if (!open) setDeletingGroupName(null) }}
          groupName={deletingGroupName}
          onDeleted={() => {
            if (deletingGroupName === selectedGroup) onSelectGroup(null)
            setDeletingGroupName(null)
          }}
        />
      )}
      <AssetTypesDialog open={typesDialogOpen} onOpenChange={setTypesDialogOpen} />

      {!externalAddSloLink && mode === 'slo' && (
        <SloLinkDialog
          open={linkingGroupName !== null}
          onOpenChange={open => { if (!open) setLinkingGroupName(null) }}
          lockedGroupName={linkingGroupName ?? undefined}
        />
      )}
    </div>
  )
}

/**
 * Hook that fetches SLO link counts for all groups in slo mode.
 * In navigator mode, returns an empty map (no fetches).
 */
function useSloLinkCounts(): Map<string, number> {
  // For slo mode, we fetch links per selected group on demand in the parent.
  // For now, return empty map — the count will show 0 until we have a batch endpoint.
  // The SLO Registry page already fetches links for the selected group.
  return useMemo(() => new Map<string, number>(), [])
}
