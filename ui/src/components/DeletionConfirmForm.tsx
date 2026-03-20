import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface DeletionConfirmFormProps {
  title: string
  onConfirm: (reason: string, author: string) => void
  onCancel: () => void
  confirmLabel?: string
  pendingLabel?: string
  isPending?: boolean
  requireReason?: boolean
  requireAuthor?: boolean
}

export function DeletionConfirmForm({
  title,
  onConfirm,
  onCancel,
  confirmLabel = 'Confirm',
  pendingLabel = 'Saving\u2026',
  isPending = false,
  requireReason = true,
  requireAuthor = false,
}: DeletionConfirmFormProps) {
  const [reason, setReason] = useState('')
  const [author, setAuthor] = useState('')

  const canConfirm = (!requireReason || reason.trim().length > 0)
    && (!requireAuthor || author.trim().length > 0)

  function handleConfirm() {
    if (!canConfirm || isPending) return
    onConfirm(reason, author)
  }

  return (
    <div className="border border-red-700/40 rounded-md bg-red-950/20 overflow-hidden">
      <div className="h-[3px] bg-red-500" />
      <div className="p-3 space-y-2">
        <p
          className="text-xs font-medium text-red-400"
          style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
        >
          {title}
        </p>
        {requireReason && (
          <Input
            value={reason}
            onChange={e => setReason(e.target.value)}
            placeholder={"Reason\u2026"}
          />
        )}
        {requireAuthor && (
          <Input
            value={author}
            onChange={e => setAuthor(e.target.value)}
            placeholder="Your name"
          />
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="xs" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            size="xs"
            onClick={handleConfirm}
            disabled={!canConfirm || isPending}
            className="bg-red-600 text-white hover:bg-red-500"
          >
            {isPending ? pendingLabel : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
