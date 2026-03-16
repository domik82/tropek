// ui/src/features/navigator/components/AllEvaluationsPanel.tsx
import { useState, useMemo } from 'react'
import { useEvaluations, useColumnVisibility } from '@/features/evaluations/hooks'
import { EvaluationHeatmap } from '@/features/evaluations/components/EvaluationHeatmap'
import { EvaluationTable } from '@/features/evaluations/components/EvaluationTable'
import { EvaluationHeader } from '@/features/evaluations/components/EvaluationHeader'
import type { ColumnDef } from '@/features/evaluations/types'

interface Props {
  onSelectAsset: (name: string) => void
}

export function AllEvaluationsPanel({ onSelectAsset }: Props) {
  const [selectedDate, setSelectedDate] = useState<string | null>(null)

  const { data: evals = [], isLoading } = useEvaluations({})

  const dynamicCols: ColumnDef[] = Array.from(
    new Set(evals.flatMap(e => Object.keys(e.asset_snapshot.tags ?? {})))
  )
    .filter(k => !['os', 'arch', 'lab'].includes(k))
    .map(key => ({ key, label: key, required: false }))

  const colVis = useColumnVisibility(dynamicCols)
  const tableEvals = selectedDate
    ? evals.filter(e => e.period_start === selectedDate)
    : evals

  const dateRange = useMemo(() => {
    if (!evals.length) return null
    const dates = evals.map(e => e.period_start).sort()
    return Math.round(
      (new Date(dates[dates.length - 1]).getTime() - new Date(dates[0]).getTime()) /
      (1000 * 60 * 60 * 24)
    ) + 1
  }, [evals])

  return (
    <div className="p-6 space-y-4">
      <EvaluationHeader
        title="All Evaluations"
        subtitle={evals.length > 0 && dateRange != null
          ? `${evals.length} runs · ${dateRange} days`
          : undefined}
      />

      {isLoading && <p className="text-sm text-slate-400">Loading…</p>}
      {!isLoading && evals.length === 0 && (
        <p className="text-sm text-slate-400">No evaluations found.</p>
      )}

      {!isLoading && evals.length > 0 && (
        <>
          <div className="rounded-lg border border-slate-700 bg-gray-900 p-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Evaluation Heatmap</h2>
            </div>
            <EvaluationHeatmap
              evaluations={evals}
              selectedDate={selectedDate}
              onDateSelect={setSelectedDate}
              onAssetSelect={onSelectAsset}
            />
          </div>
          <EvaluationTable
            evaluations={tableEvals}
            dynamicCols={dynamicCols}
            {...colVis}
            onAssetSelect={onSelectAsset}
            onEvalClick={ev => onSelectAsset(ev.asset_snapshot.name)}
          />
        </>
      )}
    </div>
  )
}
