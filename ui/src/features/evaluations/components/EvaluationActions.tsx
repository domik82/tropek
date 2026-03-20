import { useState, useEffect, useRef, useCallback } from 'react'
import { MoreVertical, MessageSquareWarning } from 'lucide-react'
import { useInvalidateEvaluation, useOverrideStatus, usePinBaseline, useReEvaluate } from '../hooks'
import type { ReEvaluateResponse } from '../types'

export type ActionKind = 'invalidate' | 'override' | 'baseline' | 're-evaluate'

interface ActionDef {
  kind: ActionKind
  label: string
  description: string
  accentColor: string        // hex — used for accent strip, title text, confirm bg
  accentBorder: string       // Tailwind border class for card outline
  accentText: string         // Tailwind text class for title
  confirmClasses: string     // Tailwind classes for confirm button bg + hover
}

const INVALIDATE: ActionDef = {
  kind: 'invalidate',
  label: 'Invalidate',
  description: 'Discard this evaluation — it will not be used for scoring or baselines.',
  accentColor: '#8B949E',
  accentBorder: 'border-slate-500/25',
  accentText: 'text-slate-400',
  confirmClasses: 'bg-slate-500 hover:bg-slate-400',
}

const OVERRIDE_TO_PASS: ActionDef = {
  kind: 'override',
  label: 'Mark as Successful',
  description: 'Override the failed result — SLOs false-flagged this evaluation.',
  accentColor: '#22C55E',
  accentBorder: 'border-green-500/25',
  accentText: 'text-green-400',
  confirmClasses: 'bg-green-600 hover:bg-green-500',
}

const OVERRIDE_TO_FAIL: ActionDef = {
  kind: 'override',
  label: 'Mark as Failure',
  description: 'Override the passed result — SLOs missed an issue in this evaluation.',
  accentColor: '#F85149',
  accentBorder: 'border-red-500/25',
  accentText: 'text-red-400',
  confirmClasses: 'bg-red-600 hover:bg-red-500',
}

const BASELINE: ActionDef = {
  kind: 'baseline',
  label: 'Pin Baseline',
  description: 'Set this evaluation as the new baseline — future comparisons start from here.',
  accentColor: '#58A6FF',
  accentBorder: 'border-blue-500/25',
  accentText: 'text-blue-400',
  confirmClasses: 'bg-blue-600 hover:bg-blue-500',
}

const RE_EVALUATE: ActionDef = {
  kind: 're-evaluate',
  label: 'Run Evaluations',
  description: 'Re-score all evaluations from stored data with current SLO thresholds.',
  accentColor: '#A371F7',
  accentBorder: 'border-purple-500/25',
  accentText: 'text-purple-400',
  confirmClasses: 'bg-purple-600 hover:bg-purple-500',
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
  onAddNote?: () => void
}

export function EvaluationActionsButton({ currentResult, invalidated, activeAction, onSelectAction, onAddNote }: ButtonProps) {
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

  if (invalidated) {
    return <span className="text-xs text-muted-foreground italic">invalidated</span>
  }

  const actions = getActions(currentResult)

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setMenuOpen(v => !v)}
        aria-label="Evaluation actions"
        aria-expanded={menuOpen}
        aria-haspopup="true"
        className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors ${
          activeAction
            ? 'bg-primary/15 border-primary/40 text-primary'
            : 'bg-primary/10 border-primary/30 text-primary hover:bg-primary/20'
        }`}
      >
        <MoreVertical className="w-3.5 h-3.5" />
        Actions
      </button>

      {menuOpen && (
        <div className="absolute right-0 top-full mt-1 z-20 min-w-[280px] bg-popover border border-border rounded-xl shadow-xl overflow-hidden py-2" role="menu">
          {/* Add Note — first item */}
          {onAddNote && (
            <>
              <button
                onClick={() => { onAddNote(); setMenuOpen(false) }}
                className="flex items-start gap-3 w-full text-left px-3 py-2.5 transition-colors hover:bg-amber-500/10 group"
                role="menuitem"
                aria-label="Add note to this evaluation"
              >
                <div
                  className="w-[3px] rounded-full shrink-0 mt-0.5"
                  style={{ backgroundColor: '#F59E0B', height: 36 }}
                />
                <div className="min-w-0">
                  <div className="text-[13px] font-medium text-amber-400">Add Note</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">Annotate this evaluation</div>
                </div>
              </button>
              <div className="mx-3 my-1 border-t border-border" />
            </>
          )}
          {actions.map(action => (
            <button
              key={action.kind}
              onClick={() => { onSelectAction(action.kind); setMenuOpen(false) }}
              className="flex items-start gap-3 w-full text-left px-3 py-2.5 transition-colors hover:bg-accent group"
              role="menuitem"
              aria-label={action.description}
            >
              <div
                className="w-[3px] rounded-full shrink-0 mt-0.5"
                style={{ backgroundColor: action.accentColor, height: 36 }}
              />
              <div className="min-w-0">
                <div className={`text-[13px] font-medium text-popover-foreground`}>
                  {action.label}
                </div>
                <div className="text-[11px] text-muted-foreground mt-0.5">
                  {action.description}
                </div>
              </div>
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
  /** Required for re-evaluate action */
  assetName?: string
  sloName?: string
  defaultFromDate?: string
}

export function EvaluationActionForm({
  evalId, currentResult, activeAction, onClose,
  assetName, sloName, defaultFromDate,
}: FormProps) {
  const [reason, setReason] = useState('')
  const [author, setAuthor] = useState('')
  const [fromDate, setFromDate] = useState(defaultFromDate ?? '')
  const [fromBaseline, setFromBaseline] = useState(false)
  const [reEvalResult, setReEvalResult] = useState<ReEvaluateResponse | null>(null)

  const invalidate = useInvalidateEvaluation(evalId)
  const override = useOverrideStatus(evalId)
  const baseline = usePinBaseline(evalId)
  const reEvaluate = useReEvaluate()

  const isPending = invalidate.isPending || override.isPending || baseline.isPending || reEvaluate.isPending
  const isReEval = activeAction === 're-evaluate'
  const actions = getActions(currentResult)
  const actionDef = actions.find(a => a.kind === activeAction)!

  const handleConfirm = useCallback(() => {
    const onSuccess = () => onClose()

    if (activeAction === 'invalidate') {
      if (!reason.trim() || !author.trim()) return
      invalidate.mutate({ note: reason, author }, { onSuccess })
    } else if (activeAction === 'override') {
      if (!reason.trim() || !author.trim()) return
      const newResult = currentResult === 'pass' ? 'fail' : 'pass'
      override.mutate({ new_result: newResult, reason, author }, { onSuccess })
    } else if (activeAction === 'baseline') {
      if (!reason.trim() || !author.trim()) return
      baseline.mutate({ reason, author }, { onSuccess })
    } else if (activeAction === 're-evaluate') {
      if (!fromBaseline && !fromDate) return
      reEvaluate.mutate(
        {
          asset_name: assetName ?? '',
          slo_name: sloName ?? '',
          ...(fromBaseline ? { from_baseline: true } : { from_date: new Date(fromDate).toISOString() }),
        },
        { onSuccess: (data) => setReEvalResult(data) }
      )
    }
  }, [activeAction, reason, author, currentResult, fromBaseline, fromDate, assetName, sloName,
      invalidate, override, baseline, reEvaluate, onClose])

  const needsAuthor = activeAction === 'invalidate' || activeAction === 'override' || activeAction === 'baseline'
  const canConfirm = isReEval
    ? (fromBaseline || !!fromDate)
    : (!!reason.trim() && (!needsAuthor || !!author.trim()))

  return (
    <div className="flex justify-end">
      <div className={`w-full max-w-md border ${actionDef.accentBorder} rounded-xl bg-popover overflow-hidden`}>
        {/* Accent strip */}
        <div className="h-[3px]" style={{ backgroundColor: actionDef.accentColor, opacity: 0.7 }} />

        <div className="p-4 space-y-3">
          {/* Title + description */}
          <div>
            <p className={`text-sm font-medium ${actionDef.accentText}`}>
              {actionDef.label}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">{actionDef.description}</p>
          </div>

          {/* Re-evaluate results view */}
          {isReEval && reEvalResult && (
            <div className="space-y-2">
              <p className="text-sm text-foreground">
                {reEvalResult.affected_evaluations} evaluation{reEvalResult.affected_evaluations !== 1 ? 's' : ''}{' '}
                re-evaluated (SLO v{reEvalResult.slo_version_used})
              </p>
              <div className="max-h-48 overflow-y-auto space-y-1">
                {reEvalResult.results.map((r) => (
                  <div key={r.id} className="flex items-center justify-between text-xs px-3 py-1.5 bg-muted/50 rounded">
                    <span className="text-muted-foreground">
                      {new Date(r.period_start).toLocaleDateString()}
                    </span>
                    <span>
                      <span className="text-muted-foreground">{r.old_result}</span>
                      <span className="text-muted-foreground/60 mx-1">→</span>
                      <span className={
                        r.new_result === 'pass' ? 'text-pass'
                          : r.new_result === 'warning' ? 'text-warning'
                            : 'text-fail'
                      }>
                        {r.new_result}
                      </span>
                    </span>
                    <span className="text-muted-foreground">
                      {r.old_score.toFixed(1)} → {r.new_score.toFixed(1)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex justify-end">
                <button
                  onClick={onClose}
                  className="px-3 py-1.5 text-xs rounded-md border border-border text-muted-foreground hover:text-foreground transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          )}

          {/* Re-evaluate input form (checkbox + date) */}
          {isReEval && !reEvalResult && (
            <div className="space-y-3">
              {reEvaluate.isError && (
                <p className="text-xs text-fail bg-fail/10 border border-fail/20 rounded px-3 py-2">
                  {reEvaluate.error instanceof Error ? reEvaluate.error.message : 'Request failed'}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                Re-score <span className="text-foreground">{assetName}</span>{' '}
                with SLO <span className="text-foreground">{sloName}</span>
              </p>
              <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={fromBaseline}
                  onChange={(e) => setFromBaseline(e.target.checked)}
                  className="rounded border-border accent-purple-500"
                />
                Run from last baseline
              </label>
              {!fromBaseline && (
                <div>
                  <label className="block text-xs text-muted-foreground mb-1">Start date</label>
                  <input
                    type="datetime-local"
                    value={fromDate}
                    onChange={(e) => setFromDate(e.target.value)}
                    className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground focus:outline-none focus:border-purple-500"
                  />
                </div>
              )}
            </div>
          )}

          {/* Reason + author form (invalidate shows reason only; override/baseline show both) */}
          {!isReEval && (
            <>
              <input
                value={reason}
                onChange={e => setReason(e.target.value)}
                placeholder="Reason…"
                className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none"
              />
              {needsAuthor && (
                <input
                  value={author}
                  onChange={e => setAuthor(e.target.value)}
                  placeholder="Author"
                  autoComplete="name"
                  className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none"
                />
              )}
            </>
          )}

          {/* Buttons (hidden when showing re-eval results) */}
          {!(isReEval && reEvalResult) && (
            <div className="flex gap-2 justify-end">
              <button
                onClick={onClose}
                className="px-3 py-1.5 text-xs rounded-md border border-border text-muted-foreground hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                disabled={!canConfirm || isPending}
                className={`px-3 py-1.5 text-xs font-medium rounded-md text-white ${actionDef.confirmClasses} disabled:opacity-40 disabled:cursor-not-allowed transition-colors`}
              >
                {isPending
                  ? 'Saving…'
                  : isReEval
                    ? '▶ Run'
                    : 'Confirm'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function NoteIconButton({ onClick, annotationCount }: { onClick: () => void; annotationCount: number }) {
  return (
    <button
      onClick={onClick}
      className="relative p-2 rounded-lg border border-amber-700/40 text-amber-400 hover:bg-amber-500/10 hover:border-amber-500/50 transition-colors"
      title="Add note"
      aria-label={`Add note (${annotationCount} existing)`}
    >
      <MessageSquareWarning className="w-4 h-4" />
      {annotationCount > 0 && (
        <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-amber-500 text-[9px] font-bold text-black flex items-center justify-center">
          {annotationCount > 9 ? '9+' : annotationCount}
        </span>
      )}
    </button>
  )
}
