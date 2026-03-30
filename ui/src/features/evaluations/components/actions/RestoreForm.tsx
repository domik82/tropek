// ui/src/features/evaluations/components/actions/RestoreForm.tsx
import { useCallback } from 'react'
import { useRestoreEvaluation } from '../../hooks'
import { ActionFormShell } from './ActionFormShell'

const ACTION_DEF = {
  label: 'Restore',
  description: 'Un-invalidate this evaluation — bring it back into scoring and baselines.',
  accentColor: 'var(--status-pass)',
  accentBorder: 'border-green-500/25',
  accentText: 'text-green-400',
  confirmClasses: 'bg-green-600 hover:bg-green-500',
}

interface Props {
  evaluationId: string
  onComplete: () => void
}

export function RestoreForm({ evaluationId, onComplete }: Props) {
  const restore = useRestoreEvaluation(evaluationId)

  const handleConfirm = useCallback(() => {
    restore.mutate(undefined, { onSuccess: onComplete })
  }, [restore, onComplete])

  return (
    <ActionFormShell
      actionDef={ACTION_DEF}
      onClose={onComplete}
      onConfirm={handleConfirm}
      canConfirm
      isPending={restore.isPending}
    >
      <p className="text-sm text-muted-foreground">
        This will restore the evaluation to its original result and include it in scoring and baselines again.
      </p>
    </ActionFormShell>
  )
}
