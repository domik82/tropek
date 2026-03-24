import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { NODE_TYPE_COLORS } from '@/lib/entity-colors'
import type { TreeNode, SelectedNode } from './types'

interface Props {
  nodes: TreeNode[]
  selected: SelectedNode | null
  onSelect: (node: SelectedNode) => void
}

export function RegistryTree({ nodes, selected, onSelect }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const toggle = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div
      className="flex-1 overflow-y-auto py-1"
      style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
    >
      {nodes.map(node => (
        <TreeNodeRow
          key={node.id}
          node={node}
          depth={0}
          expanded={expanded}
          onToggle={toggle}
          selected={selected}
          onSelect={onSelect}
        />
      ))}
      {nodes.length === 0 && (
        <div className="px-4 py-3 text-xs text-muted-foreground italic">No items</div>
      )}
    </div>
  )
}

function TreeNodeRow({
  node,
  depth,
  expanded,
  onToggle,
  selected,
  onSelect,
}: {
  node: TreeNode
  depth: number
  expanded: Set<string>
  onToggle: (id: string) => void
  selected: SelectedNode | null
  onSelect: (node: SelectedNode) => void
}) {
  const hasChildren = node.children && node.children.length > 0
  const isExpanded = expanded.has(node.id)
  const isSelected = selected?.type === node.type && selected?.name === node.name
  const color = NODE_TYPE_COLORS[node.type] ?? '#c9d1d9'

  return (
    <>
      <div
        data-testid={`node-${node.id}`}
        data-selected={isSelected ? 'true' : 'false'}
        className="flex items-center gap-1 px-2 py-1 cursor-pointer transition-colors hover:bg-accent/50"
        style={{
          paddingLeft: `${8 + depth * 16}px`,
          ...(isSelected ? { backgroundColor: `${color}12`, borderLeft: `2px solid ${color}` } : {}),
        }}
      >
        {hasChildren ? (
          <button
            data-testid={`toggle-${node.id}`}
            aria-expanded={isExpanded}
            aria-label={`Toggle ${node.name}`}
            onClick={e => {
              e.stopPropagation()
              onToggle(node.id)
            }}
            className="shrink-0 p-0.5 text-muted-foreground hover:text-foreground"
          >
            {isExpanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
          </button>
        ) : (
          <span className="shrink-0 w-4" />
        )}

        <button
          onClick={() => onSelect({ type: node.type, name: node.name, groupName: node.groupName })}
          className="flex-1 text-left text-xs truncate"
          style={{ color }}
        >
          {node.displayName ?? node.name}
        </button>

        {node.badge && (
          <span className="shrink-0 text-[10px] text-muted-foreground">{node.badge}</span>
        )}
      </div>

      {hasChildren &&
        isExpanded &&
        node.children!.map(child => (
          <TreeNodeRow
            key={child.id}
            node={child}
            depth={depth + 1}
            expanded={expanded}
            onToggle={onToggle}
            selected={selected}
            onSelect={onSelect}
          />
        ))}
    </>
  )
}
