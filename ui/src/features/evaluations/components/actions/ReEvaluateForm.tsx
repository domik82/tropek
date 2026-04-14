// ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx
import { useState, useCallback } from 'react'
import { useReEvaluate } from '../../hooks'
import { PinConflictError } from '../../api'
import { Input } from '@/components/ui/input'
import { ActionFormShell } from './ActionFormShell'
import type { ReEvaluateMode, ReEvaluateResponse, PinConflictInfo } from '../../domain'

const ACTION_DEF = {
  label: 'Run Evaluations',
  description: 'Re-score all evaluations from stored data with current SLO thresholds.',
  accentColor: 'var(--entity-sli)',
  accentBorder: 'border-entity-sli/25',
  accentText: 'text-entity-sli',
  confirmClasses: 'bg-entity-sli hover:bg-entity-sli/80',
}

interface Props {
  evaluationId: string
  assetName: string
  sloName: string
  defaultFromDate?: string
  onComplete: () => void
}

export function ReEvaluateForm({ assetName, sloName, defaultFromDate, onComplete }: Props) {
  const [fromDate, setFromDate] = useState(defaultFromDate ?? '')
  const [fromBaseline, setFromBaseline] = useState(false)
  const [reEvalResult, setReEvalResult] = useState<ReEvaluateResponse | null>(null)
  const [pinConflict, setPinConflict] = useState<PinConflictInfo | null>(null)
  const reEvaluate = useReEvaluate()

  const canConfirm = fromBaseline || !!fromDate

  const submitReEval = useCallback(
    (pinStrategy?: 'skip_to_pin' | 'ignore_pin') => {
      setPinConflict(null)
      const mode: ReEvaluateMode = fromBaseline
        ? { kind: 'baseline' }
        : { kind: 'date', fromDate: new Date(fromDate).toISOString() }
      reEvaluate.mutate(
        {
          assetName,
          sloName,
          mode,
          sloVersion: null,
          dryRun: false,
          pinStrategy: pinStrategy ?? null,
        },
        {
          onSuccess: (data) => setReEvalResult(data),
          onError: (err) => {
            if (err instanceof PinConflictError) {
              setPinConflict({ pinDate: err.pinDate, pinEvaluationId: err.pinEvaluationId })
            }
          },
        },
      )
    },
    [fromBaseline, fromDate, assetName, sloName, reEvaluate],
  )

  const handleConfirm = useCallback(() => {
    if (!canConfirm) return
    submitReEval()
  }, [canConfirm, submitReEval])

  // Results view
  if (reEvalResult) {
    return (
      <ActionFormShell
        actionDef={ACTION_DEF}
        onClose={onComplete}
        onConfirm={onComplete}
        canConfirm={false}
        isPending={false}
        hideButtons
      >
        <div className="space-y-2">
          <p className="text-sm text-foreground">
            {reEvalResult.affectedEvaluations} evaluation{reEvalResult.affectedEvaluations !== 1 ? 's' : ''}{' '}
            re-evaluated{reEvalResult.sloVersionUsed != null ? ` (SLO v${reEvalResult.sloVersionUsed})` : ''}
          </p>
          <div className="max-h-48 overflow-y-auto space-y-1">
            {reEvalResult.results.map((r) => (
              <div key={r.id} className="flex items-center justify-between text-xs px-3 py-1.5 bg-muted/50 rounded">
                <span className="text-muted-foreground">
                  {new Date(r.period.from).toLocaleDateString()}
                </span>
                <span>
                  <span className="text-muted-foreground">{r.oldOutcome}</span>
                  <span className="text-muted-foreground/60 mx-1">{'\u2192'}</span>
                  <span className={
                    r.newOutcome === 'pass' ? 'text-pass'
                      : r.newOutcome === 'warning' ? 'text-warning'
                        : 'text-fail'
                  }>
                    {r.newOutcome}
                  </span>
                </span>
                <span className="text-muted-foreground">
                  {r.oldScore.toFixed(1)} {'\u2192'} {r.newScore.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
          <div className="flex justify-end">
            <button
              onClick={onComplete}
              className="px-3 py-1.5 text-xs rounded-md border border-border text-muted-foreground hover:text-foreground transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </ActionFormShell>
    )
  }

  return (
    <ActionFormShell
      actionDef={ACTION_DEF}
      onClose={onComplete}
      onConfirm={handleConfirm}
      canConfirm={canConfirm && !pinConflict}
      isPending={reEvaluate.isPending}
      confirmLabel={'\u25B6 Run'}
    >
      {/* Pin conflict dialog */}
      {pinConflict && (
        <div className="text-xs border border-warning/30 bg-warning/5 rounded px-3 py-2 space-y-2">
          <p className="text-warning">
            Start date is before the baseline pin at{' '}
            <span className="text-foreground">{new Date(pinConflict.pinDate).toLocaleString()}</span>
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => submitReEval('skip_to_pin')}
              className="px-2 py-1 rounded border border-border text-muted-foreground hover:text-foreground transition-colors"
            >
              Start from pin
            </button>
            <button
              onClick={() => submitReEval('ignore_pin')}
              className="px-2 py-1 rounded border border-border text-muted-foreground hover:text-foreground transition-colors"
            >
              Ignore pin
            </button>
          </div>
        </div>
      )}
      {/* Generic error (non-conflict) */}
      {reEvaluate.isError && !pinConflict && (
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
          onChange={(e) => { setFromBaseline(e.target.checked); setPinConflict(null) }}
          className="rounded border-border accent-[var(--entity-sli)]"
        />
        Run from last baseline
      </label>
      {!fromBaseline && (
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Start date</label>
          <Input
            type="datetime-local"
            value={fromDate}
            onChange={(e) => { setFromDate(e.target.value); setPinConflict(null) }}
          />
        </div>
      )}
    </ActionFormShell>
  )
}
