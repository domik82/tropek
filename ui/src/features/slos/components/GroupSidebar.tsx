import { useState } from 'react'
import { GroupTreeRenderer } from '@/components/GroupTreeRenderer'
import { useGroupTree } from '../hooks'
import type { AssetGroup } from '@/features/assets/types'

interface Props {
  selectedGroup: string | null
  onSelectGroup: (name: string | null) => void
  onCreateGroup: () => void
  onEditGroup: (name: string) => void
  onDeleteGroup: (name: string) => void
  onAddSloLink: (groupName: string) => void
}

export function GroupSidebar({
  selectedGroup, onSelectGroup, onCreateGroup,
  onEditGroup, onDeleteGroup, onAddSloLink,
}: Props) {
  const { data: tree, isLoading } = useGroupTree()
  const [filterQuery, setFilterQuery] = useState('')

  if (isLoading || !tree) {
    return (
      <div className="w-[180px] shrink-0 border-r border-border bg-card/50 p-3">
        <p className="text-muted-foreground text-xs">Loading…</p>
      </div>
    )
  }

  return (
    <div className="w-[180px] shrink-0 border-r border-border bg-card/50 flex flex-col">
      <div className="px-3 py-2.5 border-b border-border flex items-center justify-between">
        <span className="text-sm font-semibold text-foreground">Asset Groups</span>
        <button
          onClick={onCreateGroup}
          className="text-xs px-2 py-0.5 border border-primary/40 text-primary rounded hover:bg-primary/10 transition-colors"
        >
          + New
        </button>
      </div>
      <div className="px-3 py-2">
        <input
          type="text"
          placeholder="Filter groups…"
          value={filterQuery}
          onChange={e => setFilterQuery(e.target.value)}
          className="w-full bg-input border border-border rounded px-2 py-1 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
        />
      </div>
      <div className="flex-1 overflow-y-auto px-1 py-1">
        <div
          className={`flex items-center justify-between px-2 py-1.5 rounded cursor-pointer text-xs transition-colors ${
            selectedGroup === null
              ? 'bg-primary/15 border-l-2 border-primary font-medium'
              : 'hover:bg-muted/50'
          }`}
          onClick={() => onSelectGroup(null)}
        >
          <span>All SLOs</span>
        </div>
        {tree.top_level.map(group => (
          <GroupTreeRenderer
            key={group.id}
            group={group}
            tree={tree}
            filterQuery={filterQuery}
            selectedGroup={selectedGroup}
            onSelect={(name) => onSelectGroup(name)}
            renderNode={(g) => (
              <div
                className="flex items-center justify-between px-1 py-1.5 text-xs group"
              >
                <span className="truncate">{g.display_name ?? g.name}</span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={e => { e.stopPropagation(); onEditGroup(g.name) }}
                    className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-foreground transition-opacity text-[10px]"
                    title="Edit"
                  >
                    ✎
                  </button>
                  <button
                    onClick={e => { e.stopPropagation(); onDeleteGroup(g.name) }}
                    className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-opacity text-[10px]"
                    title="Delete"
                  >
                    ✕
                  </button>
                  <button
                    onClick={e => { e.stopPropagation(); onAddSloLink(g.name) }}
                    className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-primary transition-opacity text-[10px]"
                    title="Link SLO"
                  >
                    +
                  </button>
                </div>
              </div>
            )}
          />
        ))}
        <div
          className={`flex items-center justify-between px-2 py-1.5 rounded cursor-pointer text-xs mt-2 border-t border-border pt-2 transition-colors ${
            selectedGroup === '__ungrouped__'
              ? 'bg-primary/15 border-l-2 border-primary font-medium'
              : 'hover:bg-muted/50 text-muted-foreground italic'
          }`}
          onClick={() => onSelectGroup('__ungrouped__')}
        >
          <span>Ungrouped</span>
        </div>
      </div>
    </div>
  )
}
