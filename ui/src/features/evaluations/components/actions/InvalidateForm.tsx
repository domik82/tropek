// ui/src/features/evaluations/components/actions/InvalidateForm.tsx
import { useCallback } from 'react'
import { useInvalidateEvaluation } from '../../hooks'
import { ActionFormShell } from './ActionFormShell'
import { ReasonAuthorFields } from './ReasonAuthorFields'
import { useReasonAuthor } from './useReasonAuthor'

const ACTION_DEF = {
  label: 'Invalidate',
  description: 'Discard this evaluation — it will not be used for scoring or baselines.',
  accentColor: 'var(--entity-group)',
  accentBorder: 'border-action-secondary-border/25',
  accentText: 'text-muted-foreground',
  confirmClasses: 'bg-action-secondary-bg hover:bg-action-secondary-bg/80',
}

interface Props {
  evaluationId: string
  onComplete: () => void
}

export function InvalidateForm({ evaluationId, onComplete }: Props) {
  const { reason, setReason, author, setAuthor, canConfirm } = useReasonAuthor()
  const invalidate = useInvalidateEvaluation(evaluationId)

  const handleConfirm = useCallback(() => {
    if (!canConfirm) return
    invalidate.mutate({ note: reason, author }, { onSuccess: onComplete })
  }, [reason, author, canConfirm, invalidate, onComplete])

  return (
    <ActionFormShell
      actionDef={ACTION_DEF}
      onClose={onComplete}
      onConfirm={handleConfirm}
      canConfirm={canConfirm}
      isPending={invalidate.isPending}
    >
      <ReasonAuthorFields
        reason={reason}
        onReasonChange={setReason}
        author={author}
        onAuthorChange={setAuthor}
      />
    </ActionFormShell>
  )
}
