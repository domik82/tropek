// ui/src/features/evaluations/components/actions/ActionFormShell.tsx

interface ActionDef {
  label: string
  description: string
  accentColor: string
  accentBorder: string
  accentText: string
  confirmClasses: string
}

interface Props {
  actionDef: ActionDef
  onClose: () => void
  onConfirm: () => void
  canConfirm: boolean
  isPending: boolean
  confirmLabel?: string
  hideButtons?: boolean
  children: React.ReactNode
}

export function ActionFormShell({
  actionDef, onClose, onConfirm, canConfirm, isPending,
  confirmLabel = 'Confirm', hideButtons = false, children,
}: Props) {
  return (
    <div className="flex justify-end">
      <div className={`w-full max-w-md border ${actionDef.accentBorder} rounded-xl bg-popover overflow-hidden`}>
        <div className="h-[3px]" style={{ backgroundColor: actionDef.accentColor, opacity: 0.7 }} />
        <div className="p-4 space-y-3">
          <div>
            <p className={`text-sm font-medium ${actionDef.accentText}`}>
              {actionDef.label}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">{actionDef.description}</p>
          </div>

          {children}

          {!hideButtons && (
            <div className="flex gap-2 justify-end">
              <button
                onClick={onClose}
                className="px-3 py-1.5 text-xs rounded-md border border-border text-muted-foreground hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={onConfirm}
                disabled={!canConfirm || isPending}
                className={`px-3 py-1.5 text-xs font-medium rounded-md text-white ${actionDef.confirmClasses} disabled:opacity-40 disabled:cursor-not-allowed transition-colors`}
              >
                {isPending ? 'Saving\u2026' : confirmLabel}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
