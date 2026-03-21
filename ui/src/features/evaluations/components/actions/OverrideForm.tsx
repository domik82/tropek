// ui/src/features/evaluations/components/actions/OverrideForm.tsx
import { useState, useCallback } from 'react'
import { useOverrideStatus } from '../../hooks'
import { ActionFormShell } from './ActionFormShell'

interface Props {
  evaluationId: string
  currentResult: string
  onComplete: () => void
}

export function OverrideForm({ evaluationId, currentResult, onComplete }: Props) {
  const [reason, setReason] = useState('')
  const [author, setAuthor] = useState('')
  const override = useOverrideStatus(evaluationId)

  const isOverrideToFail = currentResult === 'pass'
  const actionDef = isOverrideToFail
    ? {
        label: 'Mark as Failure',
        description: 'Override the passed result — SLOs missed an issue in this evaluation.',
        accentColor: '#F85149',
        accentBorder: 'border-red-500/25',
        accentText: 'text-red-400',
        confirmClasses: 'bg-red-600 hover:bg-red-500',
      }
    : {
        label: 'Mark as Successful',
        description: 'Override the failed result — SLOs false-flagged this evaluation.',
        accentColor: '#22C55E',
        accentBorder: 'border-green-500/25',
        accentText: 'text-green-400',
        confirmClasses: 'bg-green-600 hover:bg-green-500',
      }

  const canConfirm = !!reason.trim() && !!author.trim()

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
