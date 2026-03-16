// src/features/assets/components/AssetGroupCard.tsx
import { GroupTreeRenderer } from '@/components/GroupTreeRenderer'
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
  return (
    <div className="border border-slate-700 rounded-lg mb-3 bg-gray-900">
      <GroupTreeRenderer
        group={group}
        tree={tree}
        filterQuery={filterQuery}
        forceExpanded={forceExpanded}
        renderNode={(g, _isOpen) => (
          <div className="flex items-center justify-between px-3 py-2.5">
            <div>
              <span className="font-semibold text-slate-200">{g.display_name ?? g.name}</span>
              <span className="text-xs text-slate-500 ml-2">({g.members.length} assets)</span>
            </div>
          </div>
        )}
        renderLeaves={(g) => {
          const members = filterQuery
            ? g.members.filter(m => m.asset_name.toLowerCase().includes(filterQuery.toLowerCase()))
            : g.members
          return (
            <div className="px-4 pb-3">
              {members.map(member => (
                <div key={member.asset_id} className="flex items-center py-1 text-sm text-slate-300">
                  <OsDot os={member.asset_name.split('-')[0]} colourMap={colourMap} />
                  <span className="font-mono">{member.asset_name}</span>
                  <span className="text-slate-500 ml-auto text-xs">weight {member.weight}</span>
                </div>
              ))}
            </div>
          )
        }}
      />
    </div>
  )
}
