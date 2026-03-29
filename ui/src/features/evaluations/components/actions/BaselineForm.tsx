// ui/src/features/evaluations/components/actions/BaselineForm.tsx
import { useState, useCallback } from 'react'
import { usePinBaseline } from '../../hooks'
import { Input } from '@/components/ui/input'
import { ActionFormShell } from './ActionFormShell'

const ACTION_DEF = {
  label: 'Pin Baseline',
  description: 'Set this evaluation as the new baseline — future comparisons start from here.',
  accentColor: '#58A6FF',
  accentBorder: 'border-blue-500/25',
  accentText: 'text-blue-400',
  confirmClasses: 'bg-blue-600 hover:bg-blue-500',
}

interface Props {
  evaluationId: string
  onComplete: () => void
}

export function BaselineForm({ evaluationId, onComplete }: Props) {
  const [reason, setReason] = useState('')
  const [author, setAuthor] = useState('')
  const baseline = usePinBaseline(evaluationId)

  const canConfirm = !!reason.trim() && !!author.trim()

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
