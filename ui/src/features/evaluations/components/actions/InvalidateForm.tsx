import { useState, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { invalidateEvaluation } from '../../api'
import { ActionFormShell } from './ActionFormShell'
import { ReasonAuthorFields } from './ReasonAuthorFields'
import { useReasonAuthor } from './useReasonAuthor'
import { SloScopeField } from './slo-scope/SloScopeField'
import { SloScopeModal } from './slo-scope/SloScopeModal'
import { invalidateColumnQueries } from './invalidate-column-queries'
import type { SloScopeResult } from './slo-scope/types'

interface Props {
  scope: SloScopeResult
  columnEvalId: string
  onComplete: () => void
}

interface RowResult {
  sloName: string
  sloEvaluationId: string
  status: 'success' | 'failed'
  error?: string
}

const ACTION_DEF = {
  label: 'Invalidate',
  description: 'Discard this evaluation — it will not be used for scoring or baselines.',
  accentColor: 'var(--entity-group)',
  accentBorder: 'border-action-secondary-border/25',
  accentText: 'text-muted-foreground',
  confirmClasses: 'bg-action-secondary-bg hover:bg-action-secondary-bg/80',
}

export function InvalidateForm({ scope, columnEvalId, onComplete }: Props) {
  const { reason, setReason, author, setAuthor, canConfirm: reasonAuthorValid } = useReasonAuthor()
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
      }
    })

    const rowResults: RowResult[] = []
    await Promise.all(
      targets.map(async sloTarget => {
        try {
          await invalidateEvaluation(sloTarget.sloEvaluationId, reason)
          rowResults.push({
            sloName: sloTarget.sloName,
            sloEvaluationId: sloTarget.sloEvaluationId,
            status: 'success',
          })
        } catch (err) {
          rowResults.push({
            sloName: sloTarget.sloName,
            sloEvaluationId: sloTarget.sloEvaluationId,
            status: 'failed',
            error: err instanceof Error ? err.message : 'unknown error',
          })
        }
      }),
    )

    invalidateColumnQueries(
      queryClient,
      rowResults
        .filter(rowResult => rowResult.status === 'success')
        .map(rowResult => rowResult.sloEvaluationId),
    )
    setResults(rowResults)
    setSubmitting(false)
  }, [canConfirm, scope, reason, queryClient])

  if (results) {
    const successCount = results.filter(rowResult => rowResult.status === 'success').length
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
            {successCount} succeeded · {failedCount} failed
          </p>
          <ul className='max-h-48 overflow-y-auto space-y-1'>
            {results.map(rowResult => (
              <li
                key={rowResult.sloEvaluationId}
                className={`flex justify-between text-xs px-2 py-1 rounded ${
                  rowResult.status === 'success' ? 'bg-pass/10 text-pass' : 'bg-fail/10 text-fail'
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
      <ReasonAuthorFields
        reason={reason}
        onReasonChange={setReason}
        author={author}
        onAuthorChange={setAuthor}
      />
    </ActionFormShell>
  )
}
