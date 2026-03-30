// ui/src/features/evaluations/components/actions/BaselineForm.tsx
import { useCallback } from 'react'
import { usePinBaseline } from '../../hooks'
import { ActionFormShell } from './ActionFormShell'
import { ReasonAuthorFields } from './ReasonAuthorFields'
import { useReasonAuthor } from './useReasonAuthor'

const ACTION_DEF = {
  label: 'Pin Baseline',
  description: 'Set this evaluation as the new baseline — future comparisons start from here.',
  accentColor: 'var(--action-primary)',
  accentBorder: 'border-blue-500/25',
  accentText: 'text-blue-400',
  confirmClasses: 'bg-blue-600 hover:bg-blue-500',
}

interface Props {
  evaluationId: string
  onComplete: () => void
}

export function BaselineForm({ evaluationId, onComplete }: Props) {
  const { reason, setReason, author, setAuthor, canConfirm } = useReasonAuthor()
  const baseline = usePinBaseline(evaluationId)

  const handleConfirm = useCallback(() => {
    if (!canConfirm) return
    baseline.mutate({ reason, author }, { onSuccess: onComplete })
  }, [reason, author, canConfirm, baseline, onComplete])

  return (
    <ActionFormShell
      actionDef={ACTION_DEF}
      onClose={onComplete}
      onConfirm={handleConfirm}
      canConfirm={canConfirm}
      isPending={baseline.isPending}
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
