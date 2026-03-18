// src/features/evaluations/components/ReEvaluateModal.tsx
import { useState } from 'react'
import { useReEvaluate } from '../hooks'
import type { ReEvaluateResponse } from '../types'

interface Props {
  assetName: string
  sloName: string
  defaultFromDate?: string
  onClose: () => void
}

export function ReEvaluateModal({ assetName, sloName, defaultFromDate, onClose }: Props) {
  const [fromDate, setFromDate] = useState(defaultFromDate ?? '')
  const [fromBaseline, setFromBaseline] = useState(false)
  const [result, setResult] = useState<ReEvaluateResponse | null>(null)

  const reEvaluate = useReEvaluate()

  function handleSubmit() {
    reEvaluate.mutate(
      {
        asset_name: assetName,
        slo_name: sloName,
        ...(fromBaseline
          ? { from_baseline: true }
          : { from_date: new Date(fromDate).toISOString() }),
      },
      {
        onSuccess: (data) => setResult(data),
      }
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-gray-800 border border-slate-700 rounded-xl p-6 w-full max-w-lg space-y-4">
        <h2 className="text-lg font-semibold text-slate-100">Run Re-evaluation</h2>
        {reEvaluate.isError && (
          <p className="text-sm text-red-400 bg-red-900/20 border border-red-700/30 rounded px-3 py-2">
            {reEvaluate.error instanceof Error ? reEvaluate.error.message : 'Request failed'}
          </p>
        )}
        <p className="text-sm text-slate-400">
          Re-score evaluations for <span className="text-slate-200">{assetName}</span>{' '}
          with SLO <span className="text-slate-200">{sloName}</span>
        </p>

        {result ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-300">
              {result.affected_evaluations} evaluation{result.affected_evaluations !== 1 ? 's' : ''}{' '}
              re-evaluated (SLO v{result.slo_version_used})
            </p>
            <div className="max-h-60 overflow-y-auto space-y-1">
              {result.results.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between text-xs px-3 py-2 bg-gray-900/60 rounded"
                >
                  <span className="text-slate-400">
                    {new Date(r.period_start).toLocaleDateString()}
                  </span>
                  <span>
                    <span className="text-slate-500">{r.old_result}</span>
                    <span className="text-slate-600 mx-1">&rarr;</span>
                    <span
                      className={
                        r.new_result === 'pass'
                          ? 'text-green-400'
                          : r.new_result === 'warning'
                            ? 'text-yellow-400'
                            : 'text-red-400'
                      }
                    >
                      {r.new_result}
                    </span>
                  </span>
                  <span className="text-slate-500">
                    {r.old_score.toFixed(1)} &rarr; {r.new_score.toFixed(1)}
                  </span>
                </div>
              ))}
            </div>
            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm rounded border border-slate-600 text-slate-300 hover:text-slate-100 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input
                  type="checkbox"
                  checked={fromBaseline}
                  onChange={(e) => setFromBaseline(e.target.checked)}
                  className="rounded border-slate-600"
                />
                Run from last baseline
              </label>

              {!fromBaseline && (
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Start date</label>
                  <input
                    type="datetime-local"
                    value={fromDate}
                    onChange={(e) => setFromDate(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-900 border border-slate-600 rounded text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                  />
                </div>
              )}
            </div>

            <div className="flex gap-2 justify-end pt-2">
              <button
                onClick={onClose}
                className="px-3 py-1.5 text-sm rounded border border-slate-600 text-slate-400 hover:text-slate-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={(!fromBaseline && !fromDate) || reEvaluate.isPending}
                className="px-3 py-1.5 text-sm font-medium rounded text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {reEvaluate.isPending ? 'Running...' : 'OK'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
