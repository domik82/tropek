import { useState, type ReactNode } from 'react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import type { AssetGroup, AssetGroupTree } from '@/features/assets'

interface GroupTreeRendererProps {
  group: AssetGroup
  tree: AssetGroupTree
  filterQuery: string
  renderNode: (group: AssetGroup, isOpen: boolean) => ReactNode
  renderLeaves?: (group: AssetGroup) => ReactNode
  onSelect?: (groupName: string) => void
  selectedGroup?: string | null
  forceExpanded?: boolean
  indent?: number
}

export function GroupTreeRenderer({
  group, tree, filterQuery, renderNode, renderLeaves,
  onSelect, selectedGroup, forceExpanded, indent = 0,
}: GroupTreeRendererProps) {
  const [open, setOpen] = useState(false)
  const isOpen = forceExpanded !== undefined ? forceExpanded : open

  const subGroups = group.subgroups
    .map(sg => tree.all_groups.find(g => g.id === sg.group_id))
    .filter(Boolean) as AssetGroup[]

  const matchesFilter = !filterQuery
    || (group.display_name ?? group.name).toLowerCase().includes(filterQuery.toLowerCase())

  const hasMatchingChildren = subGroups.some(sg =>
    (sg.display_name ?? sg.name).toLowerCase().includes(filterQuery.toLowerCase())
  )

  if (filterQuery && !matchesFilter && !hasMatchingChildren) return null

  const isSelected = selectedGroup === group.name

  return (
    <div style={{ paddingLeft: indent > 0 ? `${indent * 16}px` : undefined }}>
      <Collapsible open={isOpen} onOpenChange={forceExpanded === undefined ? setOpen : undefined}>
        <div
          className={`flex items-center cursor-pointer rounded transition-colors ${
            isSelected ? 'bg-primary/15 border-l-2 border-primary' : 'hover:bg-muted/50'
          }`}
          onClick={() => onSelect?.(group.name)}
        >
          {subGroups.length > 0 ? (
            <CollapsibleTrigger
              className="px-1 py-1 text-muted-foreground text-xs shrink-0"
              onClick={e => e.stopPropagation()}
            >
              {isOpen ? '▾' : '▸'}
            </CollapsibleTrigger>
          ) : (
            <span className="px-1 py-1 text-xs w-4 shrink-0" />
          )}
          <div className="flex-1 min-w-0">{renderNode(group, isOpen)}</div>
        </div>
        <CollapsibleContent>
          {renderLeaves?.(group)}
          {subGroups.map(sg => (
            <GroupTreeRenderer
              key={sg.id}
              group={sg}
              tree={tree}
              filterQuery={filterQuery}
              renderNode={renderNode}
              renderLeaves={renderLeaves}
              onSelect={onSelect}
              selectedGroup={selectedGroup}
              forceExpanded={forceExpanded}
              indent={indent + 1}
            />
          ))}
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
