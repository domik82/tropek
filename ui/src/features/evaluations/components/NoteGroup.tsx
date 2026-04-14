// ui/src/features/evaluations/components/NoteGroup.tsx
import { useState } from 'react'
import { NoteEntry } from './NoteEntry'
import type { Annotation } from '../domain'

interface Props {
  evalId: string
  groupName: string
  annotations: Annotation[]
  compact?: boolean
}

export function NoteGroup({ evalId, groupName, annotations, compact }: Props) {
  const [expanded, setExpanded] = useState(false)

  if (compact && !expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full bg-amber-950/15 border border-amber-700/20 rounded px-3 py-1.5 text-sm flex items-center gap-2 hover:border-amber-700/40 transition-colors text-left"
      >
        <span className="text-amber-400 text-xs leading-none">⚑</span>
        <span className="text-[10px] bg-amber-900/40 text-amber-300 px-1.5 py-0.5 rounded shrink-0">
          re-evaluation
        </span>
        <span className="text-foreground/70 text-xs truncate flex-1">{groupName}</span>
        <span className="text-muted-foreground/50 text-[10px] shrink-0">
          {annotations.length} note{annotations.length !== 1 ? 's' : ''}
        </span>
        <span className="text-muted-foreground text-[10px] shrink-0">
          {annotations[0].createdAt.toISOString().slice(5, 16).replace('T', ' ')}
        </span>
      </button>
    )
  }

  return (
    <div className="bg-amber-950/15 border border-amber-700/20 rounded-md overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-3 py-2 flex items-center gap-2 text-left hover:bg-amber-950/25 transition-colors"
      >
        <span className="text-amber-400 text-xs leading-none">⚑</span>
        <span className="text-[10px] bg-amber-900/40 text-amber-300 px-1.5 py-0.5 rounded shrink-0">
          re-evaluation
        </span>
        <span className="text-foreground/85 text-xs flex-1">{groupName}</span>
        <span className="text-muted-foreground/50 text-[10px] shrink-0">
          {annotations.length} note{annotations.length !== 1 ? 's' : ''}
        </span>
        <span className="text-muted-foreground/60 text-[10px] shrink-0">
          {expanded ? '▾' : '▸'}
        </span>
      </button>
      {expanded && (
        <div className="px-3 pb-2 space-y-1">
          {annotations.map(a => (
            <NoteEntry key={a.id} evalId={evalId} annotation={a} compact={compact} />
          ))}
        </div>
      )}
    </div>
  )
}
