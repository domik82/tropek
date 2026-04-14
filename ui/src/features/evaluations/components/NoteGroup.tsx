// ui/src/features/evaluations/components/NoteGroup.tsx
import { useState } from 'react'
import { DeletionConfirmForm } from '@/components/DeletionConfirmForm'
import { useHideAnnotation } from '../hooks'
import type { Annotation } from '../domain'

interface Props {
  evalId: string
  annotations: Annotation[]
  compact?: boolean
}

export function NoteGroup({ evalId, annotations, compact }: Props) {
  const hideAnnotation = useHideAnnotation(evalId)
  const [hidingId, setHidingId] = useState<string | null>(null)
  const firstCreated = annotations[0].createdAt

  function handleHide(reason: string, author: string) {
    if (!hidingId) return
    hideAnnotation.mutate(
      { annotationId: hidingId, reason, author: author || undefined },
      { onSuccess: () => setHidingId(null) },
    )
  }

  const padding = compact ? 'px-3 py-1.5' : 'px-3 py-2'

  return (
    <div className={`bg-amber-950/15 border border-amber-700/25 rounded-md ${padding} text-sm`}>
      <div className="flex items-start gap-2">
        <span className="text-amber-400 text-xs leading-none mt-0.5">⚑</span>
        <span className="text-[10px] bg-amber-900/40 text-amber-300 px-1.5 py-0.5 rounded shrink-0">
          re-evaluation
        </span>
        <div className="flex-1 min-w-0 space-y-0.5">
          {annotations.map(a => (
            <div key={a.id} className="flex items-center gap-2 group">
              <span className="text-foreground/80 text-xs truncate flex-1">{a.content}</span>
              <button
                onClick={() => setHidingId(a.id)}
                className="text-muted-foreground/30 hover:text-action-destructive text-xs transition-colors shrink-0 opacity-0 group-hover:opacity-100"
                title="Delete note"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
        <span className="text-muted-foreground/60 text-[10px] shrink-0 ml-auto">
          {firstCreated.toISOString().slice(5, 16).replace('T', ' ')}
        </span>
      </div>

      {hidingId && (
        <div className="mt-2 ml-6">
          <DeletionConfirmForm
            title="Delete this note?"
            onConfirm={handleHide}
            onCancel={() => setHidingId(null)}
            confirmLabel="Delete note"
            pendingLabel="Deleting\u2026"
            isPending={hideAnnotation.isPending}
            requireReason
            requireAuthor
          />
        </div>
      )}
    </div>
  )
}
