// ui/src/features/evaluations/components/actions/InvalidateForm.tsx
import { useState, useCallback } from 'react'
import { useInvalidateEvaluation } from '../../hooks'
import { Input } from '@/components/ui/input'
import { ActionFormShell } from './ActionFormShell'

const ACTION_DEF = {
  label: 'Invalidate',
  description: 'Discard this evaluation — it will not be used for scoring or baselines.',
  accentColor: '#8B949E',
  accentBorder: 'border-action-secondary-border/25',
  accentText: 'text-muted-foreground',
  confirmClasses: 'bg-action-secondary-bg hover:bg-action-secondary-bg/80',
}

interface Props {
  evaluationId: string
  onComplete: () => void
}

export function InvalidateForm({ evaluationId, onComplete }: Props) {
  const [reason, setReason] = useState('')
  const [author, setAuthor] = useState('')
  const invalidate = useInvalidateEvaluation(evaluationId)

  const canConfirm = !!reason.trim() && !!author.trim()

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
      <Input
        value={reason}
        onChange={e => setReason(e.target.value)}
        placeholder="Reason…"
      />
      <Input
        value={author}
        onChange={e => setAuthor(e.target.value)}
        placeholder="Author"
        autoComplete="name"
      />
    </ActionFormShell>
  )
}
