// ui/src/features/evaluations/components/EvaluationNotesSection.tsx
import { useRef } from 'react'
import { AnnotationSection, type AnnotationSectionHandle } from './AnnotationForm'
import type { Annotation } from '../types'

interface Props {
  evaluationId: string
  annotations: Annotation[]
}

export interface EvaluationNotesSectionHandle {
  openFormAndScroll: () => void
}

export function EvaluationNotesSection({ evaluationId, annotations }: Props) {
  const notesRef = useRef<AnnotationSectionHandle>(null)

  return (
    <div id="notes-section">
      <AnnotationSection ref={notesRef} evalId={evaluationId} annotations={annotations} />
    </div>
  )
}

/**
 * Convenience hook-like pattern: returns a ref to attach to EvaluationNotesSection
 * and a handler that opens the form + scrolls to the notes section.
 */
export function useNotesActions() {
  const notesRef = useRef<AnnotationSectionHandle>(null)

  function handleAddNote() {
    notesRef.current?.openForm()
    document.getElementById('notes-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return { notesRef, handleAddNote }
}
