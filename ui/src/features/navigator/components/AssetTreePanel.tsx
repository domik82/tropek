// ui/src/features/navigator/components/AssetTreePanel.tsx
import { useState } from 'react'
import { useAssetGroups } from '@/features/assets/hooks'
import type { AssetGroup, AssetGroupTree } from '@/features/assets/types'
import { countLeafMembers } from './treeUtils'

export { countLeafMembers }

interface Props {
  selectedGroup?: string
  selectedAsset?: string
  onSelectGroup: (name: string) => void
  onSelectAsset: (name: string) => void
  onClearSelection: () => void
}

interface NodeProps {
  group: AssetGroup
  tree: AssetGroupTree
  depth: number
  filter: string
  selectedGroup?: string
  selectedAsset?: string
  onSelectGroup: (name: string) => void
  onSelectAsset: (name: string) => void
}

function TreeNode({ group, tree, depth, filter, selectedGroup, selectedAsset, onSelectGroup, onSelectAsset }: NodeProps) {
  const [open, setOpen] = useState(depth === 0)

  const subgroups = group.subgroups
    .map(sg => tree.all_groups.find(g => g.id === sg.group_id))
    .filter(Boolean) as AssetGroup[]

  const filteredMembers = filter
    ? group.members.filter(m => m.asset_name.toLowerCase().includes(filter.toLowerCase()))
    : group.members

  const isGroupSelected = selectedGroup === group.name
  const indent = depth * 12

  return (
    <div>
      <button
        className={`flex items-center w-full text-left py-1.5 text-sm gap-1 hover:bg-slate-800/50 transition-colors ${
          isGroupSelected ? 'bg-slate-800 text-slate-100 font-medium' : 'text-slate-300'
        }`}
        style={{ paddingLeft: `${indent + 12}px`, paddingRight: '12px' }}
        onClick={() => {
          setOpen(v => !v)
          onSelectGroup(group.name)
        }}
      >
        <span className="text-xs w-3 shrink-0 text-slate-500">{open ? '▾' : '▸'}</span>
        <span className="truncate">{group.display_name ?? group.name}</span>
        {(() => {
          const leafCount = countLeafMembers(group, tree)
          return leafCount > 0 ? (
            <span className="text-xs text-slate-500 ml-auto shrink-0">{leafCount}</span>
          ) : null
        })()}
      </button>

      {open && (
        <div>
          {subgroups.map(sg => (
            <TreeNode
              key={sg.id}
              group={sg}
              tree={tree}
              depth={depth + 1}
              filter={filter}
              selectedGroup={selectedGroup}
              selectedAsset={selectedAsset}
              onSelectGroup={onSelectGroup}
              onSelectAsset={onSelectAsset}
            />
          ))}
          {filteredMembers.map(m => {
            const isAssetSelected = selectedAsset === m.asset_name
            return (
              <button
                key={m.asset_id}
                className={`flex items-center w-full text-left py-1 text-sm transition-colors hover:bg-slate-800/50 ${
                  isAssetSelected ? 'bg-slate-800 text-slate-100 font-medium' : 'text-slate-300'
                }`}
                style={{ paddingLeft: `${indent + 28}px`, paddingRight: '12px' }}
                onClick={() => onSelectAsset(m.asset_name)}
              >
                <span className="font-mono truncate">{m.asset_name}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function AssetTreePanel({ selectedGroup, selectedAsset, onSelectGroup, onSelectAsset, onClearSelection }: Props) {
  const { data: tree, isLoading } = useAssetGroups()
  const [filter, setFilter] = useState('')

  return (
    <div className="flex flex-col h-full bg-gray-900">
      <div className="p-3 border-b border-slate-700">
        <input
          type="text"
          placeholder="Filter…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          className="w-full px-2 py-1.5 text-sm rounded border border-slate-700 bg-gray-800 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-slate-500"
        />
      </div>
      <div className="flex-1 overflow-y-auto py-2">
        {isLoading && <p className="px-3 py-2 text-xs text-slate-500">Loading…</p>}
        {!isLoading && (
          <button
            className={`flex items-center w-full text-left py-1.5 text-sm gap-1 hover:bg-slate-800/50 transition-colors ${
              !selectedGroup && !selectedAsset ? 'bg-slate-800 text-slate-100 font-medium' : 'text-slate-300'
            }`}
            style={{ paddingLeft: '12px', paddingRight: '12px' }}
            onClick={onClearSelection}
          >
            All
          </button>
        )}
        {tree?.top_level.map(group => (
          <TreeNode
            key={group.id}
            group={group}
            tree={tree}
            depth={0}
            filter={filter}
            selectedGroup={selectedGroup}
            selectedAsset={selectedAsset}
            onSelectGroup={onSelectGroup}
            onSelectAsset={onSelectAsset}
          />
        ))}
      </div>
    </div>
  )
}
