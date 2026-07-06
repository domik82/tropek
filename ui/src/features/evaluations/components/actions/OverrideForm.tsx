import { useState, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { overrideStatusMany } from '../../api'
import { ActionFormShell } from './ActionFormShell'
import { ReasonAuthorFields } from './ReasonAuthorFields'
import { useReasonAuthor } from './useReasonAuthor'
import { SloScopeField } from './slo-scope/SloScopeField'
import { SloScopeModal } from './slo-scope/SloScopeModal'
import { invalidateColumnQueries } from './invalidate-column-queries'
import { runBatch, type BatchTarget } from './run-batch'
import type { SloScopeResult } from './slo-scope/types'

type Outcome = 'pass' | 'warning' | 'fail'

interface Props {
  scope: SloScopeResult
  columnEvalId: string
  onComplete: () => void
}

interface RowResult {
  sloName: string
  sloEvaluationId: string
  status: 'success' | 'skipped' | 'failed'
  error?: string
}

const ACTION_DEF = {
  label: 'Override result',
  description: 'Override the current result for selected SLOs.',
  accentColor: 'var(--action-destructive)',
  accentBorder: 'border-action-destructive-border/25',
  accentText: 'text-action-destructive',
  confirmClasses: 'bg-action-destructive-confirm hover:bg-action-destructive-confirm/80',
}

export function OverrideForm({ scope, columnEvalId, onComplete }: Props) {
  const { reason, setReason, author, setAuthor, canConfirm: reasonAuthorValid } = useReasonAuthor()
  const [target, setTarget] = useState<Outcome>('pass')
  const [pickerOpen, setPickerOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [results, setResults] = useState<RowResult[] | null>(null)
  const queryClient = useQueryClient()

  const canConfirm = reasonAuthorValid && scope.selected.size > 0 && !submitting
  void columnEvalId // reserved for future cache-scoping logic

  const handleConfirm = useCallback(async () => {
    if (!canConfirm) return
    setSubmitting(true)

    const targets = [...scope.selected].map(sloName => {
      const option = scope.availableSlos.find(slo => slo.sloName === sloName)
      return {
        sloName,
        sloEvaluationId: option?.sloEvaluationId ?? '',
        currentResult: option?.currentResult,
      }
    })

    // Rows already at the target result are skipped client-side; the rest go
    // through one batch call.
    const skipped: RowResult[] = []
    const toApply: BatchTarget[] = []
    for (const sloTarget of targets) {
      if (sloTarget.currentResult === target) {
        skipped.push({
          sloName: sloTarget.sloName,
          sloEvaluationId: sloTarget.sloEvaluationId,
          status: 'skipped',
        })
      } else {
        toApply.push({ sloName: sloTarget.sloName, sloEvaluationId: sloTarget.sloEvaluationId })
      }
    }

    // When every selected SLO is already at the target, there is nothing to
    // apply — skip the request entirely rather than PATCH an empty id list.
    const applied =
      toApply.length > 0
        ? await runBatch(toApply, ids => overrideStatusMany(ids, { outcome: target, reason, author }))
        : []
    const rowResults: RowResult[] = [...skipped, ...applied]

    invalidateColumnQueries(
      queryClient,
      rowResults
        .filter(rowResult => rowResult.status === 'success')
        .map(rowResult => rowResult.sloEvaluationId),
    )
    setResults(rowResults)
    setSubmitting(false)
  }, [canConfirm, scope, target, reason, author, queryClient])

  if (results) {
    const successCount = results.filter(rowResult => rowResult.status === 'success').length
    const skippedCount = results.filter(rowResult => rowResult.status === 'skipped').length
    const failedCount = results.filter(rowResult => rowResult.status === 'failed').length
    const failedNames = results
      .filter(rowResult => rowResult.status === 'failed')
      .map(rowResult => rowResult.sloName)

    return (
      <ActionFormShell
        actionDef={ACTION_DEF}
        onClose={onComplete}
        onConfirm={onComplete}
        canConfirm={false}
        isPending={false}
        hideButtons
      >
        <div className='space-y-2'>
          <p className='text-xs text-muted-foreground'>
            {successCount} succeeded · {failedCount} failed · {skippedCount} skipped
          </p>
          <ul className='max-h-48 overflow-y-auto space-y-1'>
            {results.map(rowResult => (
              <li
                key={rowResult.sloEvaluationId}
                className={`flex justify-between text-xs px-2 py-1 rounded ${
                  rowResult.status === 'success'
                    ? 'bg-pass/10 text-pass'
                    : rowResult.status === 'skipped'
                      ? 'bg-muted/20 text-muted-foreground'
                      : 'bg-fail/10 text-fail'
                }`}
              >
                <span>{rowResult.sloName}</span>
                <span>{rowResult.status === 'failed' ? rowResult.error : rowResult.status}</span>
              </li>
            ))}
          </ul>
          <div className='flex justify-end gap-2 pt-2'>
            {failedCount > 0 && (
              <button
                type='button'
                onClick={() => {
                  scope.setSelected(new Set(failedNames))
                  setResults(null)
                }}
                className='px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:text-foreground'
              >
                Retry failed
              </button>
            )}
            <button
              type='button'
              onClick={onComplete}
              className='px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground'
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
      isPending={submitting}
    >
      <SloScopeField scope={scope} onOpenPicker={() => setPickerOpen(true)} />
      <SloScopeModal
        open={pickerOpen}
        availableSlos={scope.availableSlos}
        initialSelected={scope.selected}
        onConfirm={next => {
          scope.setSelected(next)
          setPickerOpen(false)
        }}
        onCancel={() => setPickerOpen(false)}
      />
      <fieldset className='space-y-1'>
        <legend className='text-xs text-muted-foreground mb-1'>Set result to</legend>
        <div className='flex gap-3'>
          {(['pass', 'warning', 'fail'] as const).map(option => (
            <label key={option} className='flex items-center gap-1.5 text-xs text-foreground'>
              <input
                type='radio'
                name='override-target'
                value={option}
                checked={target === option}
                onChange={() => setTarget(option)}
                className='accent-primary'
              />
              {option}
            </label>
          ))}
        </div>
      </fieldset>
      <ReasonAuthorFields
        reason={reason}
        onReasonChange={setReason}
        author={author}
        onAuthorChange={setAuthor}
      />
    </ActionFormShell>
  )
}
