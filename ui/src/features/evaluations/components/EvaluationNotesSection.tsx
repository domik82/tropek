// ui/src/features/evaluations/components/EvaluationNotesSection.tsx
import { useRef, forwardRef, useImperativeHandle } from 'react'
import { AnnotationSection, type AnnotationSectionHandle } from './AnnotationForm'
import type { Annotation } from '../types'

interface Props {
  evaluationId: string
  annotations: Annotation[]
}

export interface EvaluationNotesSectionHandle {
  openFormAndScroll: () => void
}

export const EvaluationNotesSection = forwardRef<EvaluationNotesSectionHandle, Props>(
  function EvaluationNotesSection({ evaluationId, annotations }, ref) {
    const notesRef = useRef<AnnotationSectionHandle>(null)
    const sectionRef = useRef<HTMLDivElement>(null)

    useImperativeHandle(ref, () => ({
      openFormAndScroll: () => {
        notesRef.current?.openForm()
        sectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      },
    }))

    return (
      <div ref={sectionRef}>
        <AnnotationSection ref={notesRef} evalId={evaluationId} annotations={annotations} />
      </div>
    )
  },
)

/**
 * Returns a ref to attach to EvaluationNotesSection and a handler
 * that opens the form + scrolls into view.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useNotesActions() {
  const notesSectionRef = useRef<EvaluationNotesSectionHandle>(null)

  function handleAddNote() {
    notesSectionRef.current?.openFormAndScroll()
  }

  return { notesSectionRef, handleAddNote }
}
