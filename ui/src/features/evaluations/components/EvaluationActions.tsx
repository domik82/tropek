import { useState, useEffect, useRef } from 'react'
import { MoreVertical, MessageSquareWarning } from 'lucide-react'
import type { ActionKind } from '../ui-types'

interface ActionDef {
  kind: ActionKind
  label: string
  description: string
  accentColor: string
  accentBorder: string
  accentText: string
  confirmClasses: string
}

interface MenuAction extends ActionDef {
  disabled?: boolean
  disabledReason?: string
}

const INVALIDATE: ActionDef = {
  kind: 'invalidate',
  label: 'Invalidate',
  description: 'Discard selected SLO evaluations — they will not be used for scoring or baselines.',
  accentColor: 'var(--entity-group)',
  accentBorder: 'border-action-secondary-border/25',
  accentText: 'text-muted-foreground',
  confirmClasses: 'bg-action-secondary-bg hover:bg-action-secondary-bg/80',
}

const OVERRIDE: ActionDef = {
  kind: 'override',
  label: 'Override result',
  description: 'Change the result for selected SLOs (pass / warning / fail).',
  accentColor: 'var(--action-primary)',
  accentBorder: 'border-blue-500/25',
  accentText: 'text-blue-400',
  confirmClasses: 'bg-blue-600 hover:bg-blue-500',
}

const BASELINE: ActionDef = {
  kind: 'baseline',
  label: 'Pin Baseline',
  description: 'Set selected SLO evaluations as the new baseline.',
  accentColor: 'var(--action-primary)',
  accentBorder: 'border-blue-500/25',
  accentText: 'text-blue-400',
  confirmClasses: 'bg-blue-600 hover:bg-blue-500',
}

const RE_EVALUATE: ActionDef = {
  kind: 're-evaluate',
  label: 'Run Evaluations',
  description: 'Re-score selected SLO evaluations from stored data with current thresholds.',
  accentColor: 'var(--entity-sli)',
  accentBorder: 'border-entity-sli/25',
  accentText: 'text-entity-sli',
  confirmClasses: 'bg-entity-sli hover:bg-entity-sli/80',
}

const RESTORE: ActionDef = {
  kind: 'restore',
  label: 'Restore',
  description: 'Un-invalidate selected SLO evaluations — bring them back into scoring and baselines.',
  accentColor: 'var(--status-pass)',
  accentBorder: 'border-green-500/25',
  accentText: 'text-green-400',
  confirmClasses: 'bg-green-600 hover:bg-green-500',
}

interface AvailabilityFlags {
  allRowsInvalidated: boolean
  noRowsInvalidated: boolean
}

function getActions({ allRowsInvalidated, noRowsInvalidated }: AvailabilityFlags): MenuAction[] {
  const actions: MenuAction[] = [
    {
      ...INVALIDATE,
      disabled: allRowsInvalidated,
      disabledReason: allRowsInvalidated ? 'all SLOs in this column are already invalidated' : undefined,
    },
    OVERRIDE,
    BASELINE,
    RE_EVALUATE,
  ]
  if (!noRowsInvalidated) {
    actions.push(RESTORE)
  }
  return actions
}

interface ButtonProps {
  currentResult: string
  allRowsInvalidated: boolean
  noRowsInvalidated: boolean
  activeAction: ActionKind | null
  onSelectAction: (kind: ActionKind) => void
  onAddNote?: () => void
}

export function EvaluationActionsButton({
  allRowsInvalidated,
  noRowsInvalidated,
  activeAction,
  onSelectAction,
  onAddNote,
}: ButtonProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [menuOpen])

  const actions = getActions({ allRowsInvalidated, noRowsInvalidated })

  return (
    <div className='relative' ref={menuRef}>
      <button
        onClick={() => setMenuOpen(open => !open)}
        aria-label='Evaluation actions'
        aria-expanded={menuOpen}
        aria-haspopup='true'
        className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors ${
          activeAction
            ? 'bg-primary/15 border-primary/40 text-primary'
            : 'bg-primary/10 border-primary/30 text-primary hover:bg-primary/20'
        }`}
      >
        <MoreVertical className='w-3.5 h-3.5' />
        Actions
      </button>

      {menuOpen && (
        <div
          className='absolute right-0 top-full mt-1 z-20 min-w-[280px] bg-popover border border-border rounded-xl shadow-xl overflow-hidden py-2'
          role='menu'
        >
          {onAddNote && (
            <>
              <button
                onClick={() => {
                  onAddNote()
                  setMenuOpen(false)
                }}
                className='flex items-start gap-3 w-full text-left px-3 py-2.5 transition-colors hover:bg-amber-500/10 group'
                role='menuitem'
                aria-label='Add note to this evaluation'
              >
                <div
                  className='w-[3px] rounded-full shrink-0 mt-0.5'
                  style={{ backgroundColor: 'var(--indicator-note)', height: 36 }}
                />
                <div className='min-w-0'>
                  <div className='text-[13px] font-medium text-amber-400'>Add Note</div>
                  <div className='text-[11px] text-muted-foreground mt-0.5'>Annotate this evaluation</div>
                </div>
              </button>
              <div className='mx-3 my-1 border-t border-border' />
            </>
          )}
          {actions.map(action => (
            <button
              key={action.kind}
              onClick={() => {
                if (action.disabled) return
                onSelectAction(action.kind)
                setMenuOpen(false)
              }}
              aria-disabled={action.disabled || undefined}
              className={`flex items-start gap-3 w-full text-left px-3 py-2.5 transition-colors ${
                action.disabled ? 'opacity-40 cursor-not-allowed' : 'hover:bg-accent group'
              }`}
              role='menuitem'
              aria-label={action.label}
              title={action.disabledReason ?? action.description}
            >
              <div
                className='w-[3px] rounded-full shrink-0 mt-0.5'
                style={{ backgroundColor: action.accentColor, height: 36 }}
              />
              <div className='min-w-0'>
                <div className='text-[13px] font-medium text-popover-foreground'>{action.label}</div>
                <div className='text-[11px] text-muted-foreground mt-0.5'>
                  {action.disabledReason ?? action.description}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function NoteIconButton({ onClick, annotationCount }: { onClick: () => void; annotationCount: number }) {
  return (
    <button
      onClick={onClick}
      className='relative p-2 rounded-lg border border-amber-700/40 text-amber-400 hover:bg-amber-500/10 hover:border-amber-500/50 transition-colors'
      title='Add note'
      aria-label={`Add note (${annotationCount} existing)`}
    >
      <MessageSquareWarning className='w-4 h-4' />
      {annotationCount > 0 && (
        <span className='absolute -top-1 -right-1 w-4 h-4 rounded-full bg-amber-500 text-[9px] font-bold text-black flex items-center justify-center'>
          {annotationCount > 9 ? '9+' : annotationCount}
        </span>
      )}
    </button>
  )
}
