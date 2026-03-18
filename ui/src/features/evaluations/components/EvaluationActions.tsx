// src/features/evaluations/components/EvaluationActions.tsx
import { useState, useEffect, useRef } from 'react'
import { useInvalidateEvaluation, useOverrideStatus, usePinBaseline } from '../hooks'

export type ActionKind = 'invalidate' | 'override' | 'baseline' | 're-evaluate'

interface ActionDef {
  kind: ActionKind
  label: string
  description: string
  borderColor: string
  bgColor: string
  confirmBg: string
  confirmHoverBg: string
  dotColor: string
  textColor: string
  focusBorder: string
}

const INVALIDATE: ActionDef = {
  kind: 'invalidate',
  label: 'Invalidate',
  description: 'Discard this evaluation — it will not be used for scoring or baselines.',
  borderColor: 'border-slate-600/40',
  bgColor: 'bg-gray-800',
  confirmBg: 'bg-slate-600',
  confirmHoverBg: 'hover:bg-slate-500',
  dotColor: 'bg-slate-400',
  textColor: 'text-slate-300',
  focusBorder: 'focus:border-slate-400',
}

const OVERRIDE_TO_PASS: ActionDef = {
  kind: 'override',
  label: 'Mark as Successful',
  description: 'Override the failed result — SLOs false-flagged this evaluation.',
  borderColor: 'border-green-700/40',
  bgColor: 'bg-green-950/40',
  confirmBg: 'bg-green-600',
  confirmHoverBg: 'hover:bg-green-500',
  dotColor: 'bg-green-400',
  textColor: 'text-green-300',
  focusBorder: 'focus:border-green-500',
}

const OVERRIDE_TO_FAIL: ActionDef = {
  kind: 'override',
  label: 'Mark as Failure',
  description: 'Override the passed result — SLOs missed an issue in this evaluation.',
  borderColor: 'border-red-700/40',
  bgColor: 'bg-red-950/40',
  confirmBg: 'bg-red-600',
  confirmHoverBg: 'hover:bg-red-500',
  dotColor: 'bg-red-400',
  textColor: 'text-red-300',
  focusBorder: 'focus:border-red-500',
}

const BASELINE: ActionDef = {
  kind: 'baseline',
  label: 'Pin Baseline',
  description: 'Set this evaluation as the new baseline — future comparisons start from here.',
  borderColor: 'border-blue-700/40',
  bgColor: 'bg-blue-950/40',
  confirmBg: 'bg-blue-600',
  confirmHoverBg: 'hover:bg-blue-500',
  dotColor: 'bg-blue-400',
  textColor: 'text-blue-300',
  focusBorder: 'focus:border-blue-500',
}

const RE_EVALUATE: ActionDef = {
  kind: 're-evaluate',
  label: 'Run Evaluations',
  description: 'Re-score all evaluations from stored data with current SLO thresholds.',
  borderColor: 'border-purple-700/40',
  bgColor: 'bg-purple-950/40',
  confirmBg: 'bg-purple-600',
  confirmHoverBg: 'hover:bg-purple-500',
  dotColor: 'bg-purple-400',
  textColor: 'text-purple-300',
  focusBorder: 'focus:border-purple-500',
}

function getActions(currentResult: string): ActionDef[] {
  return [
    INVALIDATE,
    currentResult === 'pass' ? OVERRIDE_TO_FAIL : OVERRIDE_TO_PASS,
    BASELINE,
    RE_EVALUATE,
  ]
}

// ── Dropdown button (goes in EvaluationHeader actions slot) ──

interface ButtonProps {
  currentResult: string
  invalidated: boolean
  activeAction: ActionKind | null
  onSelectAction: (kind: ActionKind) => void
}

export function EvaluationActionsButton({ currentResult, invalidated, activeAction, onSelectAction }: ButtonProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    if (menuOpen) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [menuOpen])

  if (invalidated) {
    return <span className="text-xs text-slate-500 italic">invalidated</span>
  }

  const actions = getActions(currentResult)

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setMenuOpen(v => !v)}
        className={`px-3 py-1.5 text-sm font-medium rounded border transition-colors ${
          activeAction
            ? 'border-slate-500 text-slate-100 bg-slate-800'
            : 'border-slate-600 text-slate-300 hover:text-slate-100 hover:border-slate-400'
        }`}
      >
        Actions ▾
      </button>

      {menuOpen && (
        <div className="absolute right-0 top-full mt-1 z-20 min-w-52 bg-gray-800 border border-slate-700 rounded-lg shadow-xl overflow-hidden">
          {actions.map(action => (
            <button
              key={action.kind}
              onClick={() => { onSelectAction(action.kind); setMenuOpen(false) }}
              className={`flex items-center gap-2.5 w-full text-left px-4 py-2.5 text-sm transition-colors hover:bg-gray-700/60 ${action.textColor}`}
            >
              <span className={`w-2 h-2 rounded-full ${action.dotColor} shrink-0`} />
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Action form (rendered below EvaluationHeader by the parent) ──

interface FormProps {
  evalId: string
  currentResult: string
  activeAction: ActionKind
  onClose: () => void
}

export function EvaluationActionForm({ evalId, currentResult, activeAction, onClose }: FormProps) {
  const [reason, setReason] = useState('')
  const [author, setAuthor] = useState('')

  const invalidate = useInvalidateEvaluation(evalId)
  const override = useOverrideStatus(evalId)
  const baseline = usePinBaseline(evalId)

  const isPending = invalidate.isPending || override.isPending || baseline.isPending
  const actions = getActions(currentResult)
  const actionDef = actions.find(a => a.kind === activeAction)!

  function handleConfirm() {
    if (!reason.trim() || !author.trim()) return

    const onSuccess = () => onClose()

    if (activeAction === 'invalidate') {
      invalidate.mutate(reason, { onSuccess })
    } else if (activeAction === 'override') {
      const newResult = currentResult === 'pass' ? 'fail' : 'pass'
      override.mutate({ new_result: newResult, reason, author }, { onSuccess })
    } else if (activeAction === 'baseline') {
      baseline.mutate({ reason, author }, { onSuccess })
    }
  }

  return (
    <div className={`${actionDef.bgColor} border ${actionDef.borderColor} rounded-xl p-4 space-y-3`}>
      <div>
        <p className={`text-sm font-medium ${actionDef.textColor}`}>
          {actionDef.label}
        </p>
        <p className="text-xs text-slate-500 mt-0.5">{actionDef.description}</p>
      </div>
      <textarea
        value={reason}
        onChange={e => setReason(e.target.value)}
        placeholder="Reason…"
        rows={3}
        className={`w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-sm text-gray-200 placeholder-gray-500 focus:outline-none ${actionDef.focusBorder} resize-none`}
      />
      <input
        value={author}
        onChange={e => setAuthor(e.target.value)}
        placeholder="Author"
        className={`w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-sm text-gray-200 placeholder-gray-500 focus:outline-none ${actionDef.focusBorder}`}
      />
      <div className="flex gap-2 justify-end">
        <button
          onClick={onClose}
          className="px-3 py-1.5 text-xs rounded border border-slate-600 text-slate-400 hover:text-slate-200 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleConfirm}
          disabled={!reason.trim() || !author.trim() || isPending}
          className={`px-3 py-1.5 text-xs font-medium rounded text-white ${actionDef.confirmBg} ${actionDef.confirmHoverBg} disabled:opacity-40 disabled:cursor-not-allowed transition-colors`}
        >
          {isPending ? 'Saving…' : 'Confirm'}
        </button>
      </div>
    </div>
  )
}
