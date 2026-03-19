// ui/src/features/evaluations/components/AnnotationForm.tsx
import { useState, useImperativeHandle, forwardRef } from 'react'
import type { Annotation } from '../types'
import { NoteEntry } from './NoteEntry'
import { AddNoteForm } from './AddNoteForm'

export interface AnnotationSectionHandle {
  openForm: () => void
}

interface Props {
  evalId: string
  annotations: Annotation[]
}

export const AnnotationSection = forwardRef<AnnotationSectionHandle, Props>(
  function AnnotationSection({ evalId, annotations }, ref) {
    const [showForm, setShowForm] = useState(false)
    const [viewMode, setViewMode] = useState<'compact' | 'expanded'>('expanded')

    useImperativeHandle(ref, () => ({
      openForm: () => setShowForm(true),
    }))

    return (
      <div className="space-y-2">
        {/* Header row — always visible */}
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide"
            style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}>
            Notes
            <span className="normal-case font-normal ml-1 text-muted-foreground/60">
              ({annotations.length})
            </span>
          </h2>

          <div className="flex items-center gap-3">
            {/* View mode toggle */}
            {annotations.length > 0 && (
              <div className="flex items-center gap-1 text-[10px]"
                style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}>
                <button
                  onClick={() => setViewMode('compact')}
                  className={viewMode === 'compact' ? 'text-amber-400 font-semibold' : 'text-muted-foreground/50 hover:text-muted-foreground'}
                >
                  compact
                </button>
                <span className="text-muted-foreground/30">/</span>
                <button
                  onClick={() => setViewMode('expanded')}
                  className={viewMode === 'expanded' ? 'text-amber-400 font-semibold' : 'text-muted-foreground/50 hover:text-muted-foreground'}
                >
                  expanded
                </button>
              </div>
            )}

            {/* + Note button */}
            <button
              onClick={() => setShowForm(v => !v)}
              className="px-2 py-1 text-[10px] font-medium rounded border border-amber-700/50 text-amber-400 hover:border-amber-500 hover:text-amber-300 transition-colors"
              style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
            >
              {showForm ? 'Cancel' : '+ Note'}
            </button>
          </div>
        </div>

        {/* Add note form */}
        {showForm && (
          <AddNoteForm evalId={evalId} onClose={() => setShowForm(false)} />
        )}

        {/* Note entries */}
        {annotations.map(a => (
          <NoteEntry key={a.id} annotation={a} compact={viewMode === 'compact'} />
        ))}

        {annotations.length === 0 && !showForm && (
          <p className="text-xs text-muted-foreground/40">No notes yet.</p>
        )}
      </div>
    )
  }
)

// Re-export for backwards compatibility during transition
export { AnnotationSection as AnnotationForm }
