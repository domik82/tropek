import { useCallback, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { pinBaseline } from '../../api'
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
  label: 'Pin Baseline',
  description: 'Set the selected evaluations as the new baseline — future comparisons start from here.',
  accentColor: 'var(--action-primary)',
  accentBorder: 'border-blue-500/25',
  accentText: 'text-blue-400',
  confirmClasses: 'bg-blue-600 hover:bg-blue-500',
}

const COUNT_WARNING_THRESHOLD = 5

export function BaselineForm({ scope, columnEvalId, onComplete }: Props) {
  const { reason, setReason, author, setAuthor, canConfirm: reasonAuthorValid } = useReasonAuthor()
  const [pickerOpen, setPickerOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [results, setResults] = useState<RowResult[] | null>(null)
  const queryClient = useQueryClient()

  const canConfirm = reasonAuthorValid && scope.selected.size > 0 && !submitting
  void columnEvalId

  const handleConfirm = useCallback(async () => {
    if (!canConfirm) return
    setSubmitting(true)

    const targets = [...scope.selected].map(sloName => {
      const option = scope.availableSlos.find(s => s.sloName === sloName)
      return {
        sloName,
        sloEvaluationId: option?.sloEvaluationId ?? '',
      }
    })

    const rowResults: RowResult[] = []
    await Promise.all(
      targets.map(async target => {
        try {
          await pinBaseline(target.sloEvaluationId, { reason, author })
          rowResults.push({ sloName: target.sloName, sloEvaluationId: target.sloEvaluationId, status: 'success' })
        } catch (err) {
          rowResults.push({
            sloName: target.sloName,
            sloEvaluationId: target.sloEvaluationId,
            status: 'failed',
            error: err instanceof Error ? err.message : 'unknown error',
          })
        }
      }),
    )

    invalidateColumnQueries(
      queryClient,
      rowResults.filter(rowResult => rowResult.status === 'success').map(rowResult => rowResult.sloEvaluationId),
    )
    setResults(rowResults)
    setSubmitting(false)
  }, [canConfirm, scope, reason, author, queryClient])

  if (results) {
    const successCount = results.filter(rowResult => rowResult.status === 'success').length
    const failedCount = results.filter(rowResult => rowResult.status === 'failed').length
    const failedNames = results.filter(rowResult => rowResult.status === 'failed').map(rowResult => rowResult.sloName)

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
      {scope.selected.size > COUNT_WARNING_THRESHOLD && (
        <p className='text-xs text-warning'>
          This will create {scope.selected.size} baseline pins.
        </p>
      )}
    </ActionFormShell>
  )
}
