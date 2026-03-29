import { useState } from 'react'
import { TreeNode } from '@/components/tree'
import { getEntityIcon, getAssetTypeIcon } from '@/components/tree'
import { NODE_TYPE_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import type { TreeNode as TreeNodeData, SelectedNode } from './types'

interface Props {
  nodes: TreeNodeData[]
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
      style={{ fontFamily: SANS_SERIF }}
    >
      {nodes.map(node => (
        <RegistryNodeRow
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

function getIconForNode(node: TreeNodeData) {
  if (node.type === 'asset') return getAssetTypeIcon(node.assetTypeName ?? 'vm')
  return getEntityIcon(node.type)
}

function getColorForNode(node: TreeNodeData) {
  return NODE_TYPE_COLORS[node.type] ?? '#c9d1d9'
}

function getBadgeForNode(node: TreeNodeData): { type: 'count' | 'version'; value: string | number } | undefined {
  if (!node.badge) return undefined
  if (node.badge.startsWith('v')) return { type: 'version', value: node.badge }
  return { type: 'count', value: node.badge }
}

function RegistryNodeRow({
  node, depth, expanded, onToggle, selected, onSelect, parentGroupName,
}: {
  node: TreeNodeData
  depth: number
  expanded: Set<string>
  onToggle: (id: string) => void
  selected: SelectedNode | null
  onSelect: (node: SelectedNode) => void
  parentGroupName?: string
}) {
  const hasChildren = node.children && node.children.length > 0
  const isExpanded = expanded.has(node.id)
  const isSelected = selected?.type === node.type && selected?.name === node.name
  const color = getColorForNode(node)
  const groupContext = node.type === 'group' ? node.name : parentGroupName

  return (
    <>
      <TreeNode
        testId={`node-${node.id}`}
        icon={getIconForNode(node)}
        iconColor={color}
        label={node.displayName ?? node.name}
        depth={depth}
        isExpandable={!!hasChildren}
        isExpanded={isExpanded}
        isSelected={isSelected}
        selectionColor={color}
        isGroup={node.type === 'group'}
        badge={getBadgeForNode(node)}
        onClick={() => onSelect({ type: node.type, name: node.name, groupName: groupContext })}
        onToggle={() => onToggle(node.id)}
      />
      {hasChildren && isExpanded && node.children!.map(child => (
        <RegistryNodeRow
          key={child.id}
          node={child}
          depth={depth + 1}
          expanded={expanded}
          onToggle={onToggle}
          selected={selected}
          onSelect={onSelect}
          parentGroupName={groupContext}
        />
      ))}
    </>
  )
}
