// ui/src/features/evaluations/components/actions/OverrideForm.tsx
import { useCallback } from 'react'
import { useOverrideStatus } from '../../hooks'
import { ActionFormShell } from './ActionFormShell'
import { ReasonAuthorFields } from './ReasonAuthorFields'
import { useReasonAuthor } from './useReasonAuthor'

interface Props {
  evaluationId: string
  currentResult: string
  onComplete: () => void
}

export function OverrideForm({ evaluationId, currentResult, onComplete }: Props) {
  const { reason, setReason, author, setAuthor, canConfirm } = useReasonAuthor()
  const override = useOverrideStatus(evaluationId)

  const isOverrideToFail = currentResult === 'pass'
  const actionDef = isOverrideToFail
    ? {
        label: 'Mark as Failure',
        description: 'Override the passed result — SLOs missed an issue in this evaluation.',
        accentColor: 'var(--action-destructive)',
        accentBorder: 'border-action-destructive-border/25',
        accentText: 'text-action-destructive',
        confirmClasses: 'bg-action-destructive-confirm hover:bg-action-destructive-confirm/80',
      }
    : {
        label: 'Mark as Successful',
        description: 'Override the failed result — SLOs false-flagged this evaluation.',
        accentColor: 'var(--status-pass)',
        accentBorder: 'border-green-500/25',
        accentText: 'text-green-400',
        confirmClasses: 'bg-green-600 hover:bg-green-500',
      }

  const handleConfirm = useCallback(() => {
    if (!canConfirm) return
    const newResult = currentResult === 'pass' ? 'fail' : 'pass'
    override.mutate({ new_result: newResult, reason, author }, { onSuccess: onComplete })
  }, [reason, author, currentResult, canConfirm, override, onComplete])

  return (
    <ActionFormShell
      actionDef={actionDef}
      onClose={onComplete}
      onConfirm={handleConfirm}
      canConfirm={canConfirm}
      isPending={override.isPending}
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
