// ui/src/features/assets/components/GroupTreeSelector.tsx
import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import type { AssetGroup, AssetGroupTree } from '../domain'
import { SANS_SERIF } from '@/lib/fonts'

interface Props {
  tree: AssetGroupTree
  value: string | null
  onChange: (name: string | null) => void
  excludeName?: string
}

function findSubgroups(group: AssetGroup, allGroups: AssetGroup[]): AssetGroup[] {
  return group.subgroups
    .map(s => allGroups.find(g => g.id === s.groupId))
    .filter((g): g is AssetGroup => g !== undefined)
}

function GroupNode({
  group, allGroups, depth, value, onChange, expandedSet, onToggle, excludeName,
}: {
  group: AssetGroup
  allGroups: AssetGroup[]
  depth: number
  value: string | null
  onChange: (name: string | null) => void
  expandedSet: Set<string>
  onToggle: (name: string) => void
  excludeName?: string
}) {
  if (group.name === excludeName) return null

  const children = findSubgroups(group, allGroups)
  const hasChildren = children.length > 0
  const isExpanded = expandedSet.has(group.name)
  const isSelected = value === group.name

  return (
    <>
      <button
        type="button"
        className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-sm transition-colors rounded-sm ${
          isSelected
            ? 'bg-primary/15 border-l-2 border-primary text-primary font-medium'
            : 'hover:bg-muted/50 text-foreground'
        }`}
        style={{ paddingLeft: depth * 16 + 8 }}
        onClick={() => onChange(group.name)}
      >
        {hasChildren ? (
          <span
            className="shrink-0 cursor-pointer"
            onClick={e => { e.stopPropagation(); onToggle(group.name) }}
          >
            {isExpanded
              ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
              : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />}
          </span>
        ) : (
          <span className="w-3.5 shrink-0" />
        )}
        <span>{group.displayName ?? group.name}</span>
      </button>
      {isExpanded && children.map(child => (
        <GroupNode
          key={child.id}
          group={child}
          allGroups={allGroups}
          depth={depth + 1}
          value={value}
          onChange={onChange}
          expandedSet={expandedSet}
          onToggle={onToggle}
          excludeName={excludeName}
        />
      ))}
    </>
  )
}

export function GroupTreeSelector({ tree, value, onChange, excludeName }: Props) {
  const [expandedSet, setExpandedSet] = useState<Set<string>>(() => {
    return new Set(tree.allGroups.map(g => g.name))
  })

  const onToggle = (name: string) => {
    setExpandedSet(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  return (
    <div
      className="border border-border rounded-md bg-input max-h-[200px] overflow-y-auto py-1"
      style={{ fontFamily: SANS_SERIF }}
    >
      <button
        type="button"
        className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-sm transition-colors rounded-sm ${
          value === null
            ? 'bg-primary/15 border-l-2 border-primary text-primary font-medium'
            : 'hover:bg-muted/50 text-foreground'
        }`}
        onClick={() => onChange(null)}
      >
        <span className="w-3.5 shrink-0" />
        <span className={`${value === null ? '' : 'text-muted-foreground'}`}>
          None (top level)
        </span>
      </button>

      {tree.topLevel.map(group => (
        <GroupNode
          key={group.id}
          group={group}
          allGroups={tree.allGroups}
          depth={0}
          value={value}
          onChange={onChange}
          expandedSet={expandedSet}
          onToggle={onToggle}
          excludeName={excludeName}
        />
      ))}
    </div>
  )
}
