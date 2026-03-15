// src/features/assets/components/AssetGroupCard.tsx
import { useState } from 'react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { DEFAULT_OS_COLOUR_MAP } from '@/lib/theme'
import type { AssetGroup, AssetGroupTree } from '../types'

interface Props {
  group: AssetGroup
  tree: AssetGroupTree
  filterQuery: string
  colourMap: Record<string, string>
  forceExpanded?: boolean
}

function OsDot({ os, colourMap }: { os?: string; colourMap: Record<string, string> }) {
  const colour = (os && (colourMap[os] ?? DEFAULT_OS_COLOUR_MAP[os])) ?? '#888'
  return (
    <span
      className="inline-block w-2.5 h-2.5 rounded-full mr-2 flex-shrink-0"
      style={{ backgroundColor: colour }}
    />
  )
}

export function AssetGroupCard({ group, tree, filterQuery, colourMap, forceExpanded }: Props) {
  const [open, setOpen] = useState(false)
  const isOpen = forceExpanded !== undefined ? forceExpanded : open

  const filteredMembers = filterQuery
    ? group.members.filter(m => m.asset_name.toLowerCase().includes(filterQuery.toLowerCase()))
    : group.members

  const subGroups = group.subgroups
    .map(sg => tree.all_groups.find(g => g.id === sg.group_id))
    .filter(Boolean) as AssetGroup[]

  const hasContent = filteredMembers.length > 0 || subGroups.length > 0

  if (!hasContent && filterQuery) return null

  return (
    <div className="border border-gray-700 rounded-lg mb-3">
      <Collapsible open={isOpen} onOpenChange={forceExpanded === undefined ? setOpen : undefined}>
        <CollapsibleTrigger className="flex items-center justify-between w-full px-4 py-3 text-left hover:bg-gray-800/50 rounded-t-lg">
          <div>
            <span className="font-semibold">{group.display_name ?? group.name}</span>
            <span className="text-xs text-gray-500 ml-2">({group.members.length} assets)</span>
          </div>
          <span className="text-gray-500">{isOpen ? '▼' : '▶'}</span>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="px-4 pb-3">
            {filteredMembers.map(member => (
              <div key={member.asset_id} className="flex items-center py-1 text-sm text-gray-300">
                <OsDot os={member.asset_name.split('-')[0]} colourMap={colourMap} />
                <span className="font-mono">{member.asset_name}</span>
                <span className="text-gray-500 ml-auto text-xs">weight {member.weight}</span>
              </div>
            ))}
            {subGroups.map(sg => (
              <div key={sg.id} className="ml-4 mt-2">
                <AssetGroupCard
                  group={sg}
                  tree={tree}
                  filterQuery={filterQuery}
                  colourMap={colourMap}
                  forceExpanded={forceExpanded}
                />
              </div>
            ))}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
