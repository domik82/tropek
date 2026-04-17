// ui/src/features/evaluations/components/AnnotationForm.tsx
import { useState, useImperativeHandle, forwardRef, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Settings2 } from 'lucide-react'
import type { Annotation } from '../domain'
import { NoteEntry } from './NoteEntry'
import { NoteGroup } from './NoteGroup'
import { AddNoteForm } from './AddNoteForm'
import { SANS_SERIF } from '@/lib/fonts'

interface GroupedEntry {
  kind: 'group'
  groupId: string
  groupName: string
  annotations: Annotation[]
  firstCreatedAt: Date
}

interface StandaloneEntry {
  kind: 'standalone'
  annotation: Annotation
}

type NoteListEntry = GroupedEntry | StandaloneEntry

function buildNoteList(annotations: Annotation[]): NoteListEntry[] {
  const groups = new Map<string, { name: string; items: Annotation[] }>()
  const entries: NoteListEntry[] = []
  const groupInsertOrder: string[] = []

  for (const annotation of annotations) {
    if (annotation.noteGroupId) {
      const existing = groups.get(annotation.noteGroupId)
      if (existing) {
        existing.items.push(annotation)
      } else {
        groups.set(annotation.noteGroupId, {
          name: annotation.noteGroupName ?? 're-evaluation',
          items: [annotation],
        })
        groupInsertOrder.push(annotation.noteGroupId)
      }
    }
  }

  let groupIndex = 0
  for (const annotation of annotations) {
    if (annotation.noteGroupId) {
      // Insert the group entry at the position of its first annotation
      if (groupIndex < groupInsertOrder.length && groupInsertOrder[groupIndex] === annotation.noteGroupId) {
        const group = groups.get(annotation.noteGroupId)!
        entries.push({
          kind: 'group',
          groupId: annotation.noteGroupId,
          groupName: group.name,
          annotations: group.items,
          firstCreatedAt: group.items[0].createdAt,
        })
        groupIndex++
      }
      // Skip subsequent annotations in the same group (already included above)
    } else {
      entries.push({ kind: 'standalone', annotation })
    }
  }

  return entries
}

export interface AnnotationSectionHandle {
  openForm: () => void
}

interface Props {
  runId: string
  annotations: Annotation[]
}

export const AnnotationSection = forwardRef<AnnotationSectionHandle, Props>(
  function AnnotationSection({ runId, annotations }, ref) {
    const [showForm, setShowForm] = useState(false)
    const [viewMode, setViewMode] = useState<'compact' | 'expanded'>('compact')

    const noteList = useMemo(() => buildNoteList(annotations), [annotations])

    useImperativeHandle(ref, () => ({
      openForm: () => setShowForm(true),
    }))

    return (
      <div className="space-y-2">
        {/* Header row — always visible */}
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide"
            style={{ fontFamily: SANS_SERIF }}>
            Notes
            <span className="normal-case font-normal ml-1 text-muted-foreground/60">
              ({annotations.length})
            </span>
          </h2>

          <div className="flex items-center gap-3">
            {/* View mode toggle */}
            {annotations.length > 0 && (
              <div className="flex items-center gap-1 text-[10px]"
                style={{ fontFamily: SANS_SERIF }}>
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

            {/* Gear link to category management */}
            <Link
              to="/settings/note-categories"
              title="Manage categories"
              className="text-muted-foreground/60 hover:text-muted-foreground text-xs"
              aria-label="Manage categories"
            >
              <Settings2 className="size-3.5" />
            </Link>

            {/* + Note button */}
            <button
              onClick={() => setShowForm(v => !v)}
              className="px-2 py-1 text-[10px] font-medium rounded border border-amber-700/50 text-amber-400 hover:border-amber-500 hover:text-amber-300 transition-colors"
              style={{ fontFamily: SANS_SERIF }}
            >
              {showForm ? 'Cancel' : '+ Note'}
            </button>
          </div>
        </div>

        {/* Add note form */}
        {showForm && (
          <AddNoteForm runId={runId} onClose={() => setShowForm(false)} />
        )}

        {/* Note entries — grouped and standalone */}
        {noteList.map(entry =>
          entry.kind === 'group' ? (
            <NoteGroup
              key={entry.groupId}
              runId={runId}
              annotations={entry.annotations}
              compact={viewMode === 'compact'}
            />
          ) : (
            <NoteEntry
              key={entry.annotation.id}
              runId={runId}
              annotation={entry.annotation}
              compact={viewMode === 'compact'}
            />
          ),
        )}

        {annotations.length === 0 && !showForm && (
          <p className="text-xs text-muted-foreground/40">No notes yet.</p>
        )}
      </div>
    )
  }
)

// Re-export for backwards compatibility during transition
export { AnnotationSection as AnnotationForm }
