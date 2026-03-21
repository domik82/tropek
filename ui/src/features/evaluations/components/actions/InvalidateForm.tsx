// ui/src/features/evaluations/components/actions/InvalidateForm.tsx
import { useState, useCallback } from 'react'
import { useInvalidateEvaluation } from '../../hooks'
import { ActionFormShell } from './ActionFormShell'

const ACTION_DEF = {
  label: 'Invalidate',
  description: 'Discard this evaluation — it will not be used for scoring or baselines.',
  accentColor: '#8B949E',
  accentBorder: 'border-slate-500/25',
  accentText: 'text-slate-400',
  confirmClasses: 'bg-slate-500 hover:bg-slate-400',
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
      <input
        value={reason}
        onChange={e => setReason(e.target.value)}
        placeholder="Reason…"
        className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none"
      />
      <input
        value={author}
        onChange={e => setAuthor(e.target.value)}
        placeholder="Author"
        autoComplete="name"
        className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none"
      />
    </ActionFormShell>
  )
}
