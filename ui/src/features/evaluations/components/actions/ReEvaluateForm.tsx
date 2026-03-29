// ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx
import { useState, useCallback } from 'react'
import { useReEvaluate } from '../../hooks'
import { ActionFormShell } from './ActionFormShell'
import type { ReEvaluateResponse } from '../../types'

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
  const reEvaluate = useReEvaluate()

  const canConfirm = fromBaseline || !!fromDate

  const handleConfirm = useCallback(() => {
    if (!canConfirm) return
    reEvaluate.mutate(
      {
        asset_name: assetName,
        slo_name: sloName,
        ...(fromBaseline ? { from_baseline: true } : { from_date: new Date(fromDate).toISOString() }),
      },
      { onSuccess: (data) => setReEvalResult(data) },
    )
  }, [canConfirm, fromBaseline, fromDate, assetName, sloName, reEvaluate])

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
                  <span className="text-muted-foreground/60 mx-1">{'\u2192'}</span>
                  <span className={
                    r.new_result === 'pass' ? 'text-pass'
                      : r.new_result === 'warning' ? 'text-warning'
                        : 'text-fail'
                  }>
                    {r.new_result}
                  </span>
                </span>
                <span className="text-muted-foreground">
                  {r.old_score.toFixed(1)} {'\u2192'} {r.new_score.toFixed(1)}
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
      canConfirm={canConfirm}
      isPending={reEvaluate.isPending}
      confirmLabel={'\u25B6 Run'}
    >
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
          className="rounded border-border accent-[var(--entity-sli)]"
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
            className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground focus:outline-none focus:border-entity-sli"
          />
        </div>
      )}
    </ActionFormShell>
  )
}
