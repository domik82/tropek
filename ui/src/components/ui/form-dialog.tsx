import { type ReactNode } from 'react'
import {
  Dialog, DialogClose, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from './dialog'
import { Button } from './button'
import { SANS_SERIF } from '@/lib/fonts'

interface FormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: ReactNode
  submitLabel: string
  pendingLabel?: string
  onSubmit: () => void
  canSubmit: boolean
  isPending: boolean
  children: ReactNode
}

export function FormDialog({
  open,
  onOpenChange,
  title,
  submitLabel,
  pendingLabel = 'Saving…',
  onSubmit,
  canSubmit,
  isPending,
  children,
}: FormDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent style={{ fontFamily: SANS_SERIF }}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">{children}</div>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" size="sm" />}>Cancel</DialogClose>
          <Button size="sm" onClick={onSubmit} disabled={!canSubmit || isPending}>
            {isPending ? pendingLabel : submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
