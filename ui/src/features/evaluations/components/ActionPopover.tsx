import { useEffect, type ReactNode } from 'react'

interface Props {
  open: boolean
  onClose: () => void
  children: ReactNode
}

export function ActionPopover({ open, onClose, children }: Props) {
  useEffect(() => {
    if (!open) return
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className='absolute right-0 top-full mt-2 z-30 w-[380px] bg-popover border border-border rounded-xl shadow-xl p-4'
      role='dialog'
      aria-modal='false'
    >
      {children}
    </div>
  )
}
