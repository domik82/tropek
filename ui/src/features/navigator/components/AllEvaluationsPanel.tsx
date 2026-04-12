// ui/src/features/navigator/components/AllEvaluationsPanel.tsx
import { useState, useMemo } from 'react'
import { useAssets } from '@/features/assets/hooks'
import { useSlos } from '@/features/slos/hooks'
import { useEvaluations, useDynamicColumns, useColumnVisibility } from '@/features/evaluations/hooks'
import { EvaluationHeatmap } from '@/features/evaluations/components/EvaluationHeatmap'
import { EvaluationTable } from '@/features/evaluations/components/EvaluationTable'
import { EvaluationHeader } from '@/features/evaluations/components/EvaluationHeader'
import { TruncationWarning } from '@/features/evaluations/components/TruncationWarning'
import { EvaluationNameFilter } from './EvaluationNameFilter'
import { useEvaluationNames } from '../hooks'
import { TimeRangePicker } from '@/components/TimeRangePicker'

interface Props {
  onSelectAsset: (name: string, evalId?: string) => void
}

export function AllEvaluationsPanel({ onSelectAsset }: Props) {
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedNames, setSelectedNames] = useState<string[] | undefined>(undefined)

  const { data: evalNames = [] } = useEvaluationNames()

  const { data: evals = [], isLoading, truncated, total } = useEvaluations({
    evaluation_name: selectedNames,
  })

  // Live display name lookups — fallback for evaluations whose snapshot lacks display_name
  const { data: assets } = useAssets()
  const { data: slos } = useSlos()
  const assetDisplayNames = useMemo(() => {
    const m = new Map<string, string>()
    for (const a of assets ?? []) if (a.display_name) m.set(a.name, a.display_name)
    return m
  }, [assets])
  const sloDisplayNames = useMemo(() => {
    const m = new Map<string, string>()
    for (const s of slos ?? []) if (s.displayName) m.set(s.name, s.displayName)
    return m
  }, [slos])

  const dynamicCols = useDynamicColumns(evals)
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
        toolbar={<TimeRangePicker />}
      />

      {evalNames.length >= 1 && (
        <EvaluationNameFilter
          names={evalNames}
          selected={selectedNames}
          onChange={setSelectedNames}
        />
      )}

      {truncated && <TruncationWarning total={total} />}

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {!isLoading && evals.length === 0 && (
        <p className="text-sm text-muted-foreground">No evaluations found.</p>
      )}

      {!isLoading && evals.length > 0 && (
        <>
          <div className="rounded-lg border border-border bg-surface-sunken p-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Evaluation Heatmap</h2>
            </div>
            <EvaluationHeatmap
              evaluations={evals}
              selectedDate={selectedDate}
              onDateSelect={setSelectedDate}
              onAssetSelect={onSelectAsset}
              assetDisplayNames={assetDisplayNames}
            />
          </div>
          <EvaluationTable
            evaluations={tableEvals}
            {...colVis}
            onAssetSelect={onSelectAsset}
            onEvalClick={ev => onSelectAsset(ev.asset_snapshot.name, ev.id)}
            assetDisplayNames={assetDisplayNames}
            sloDisplayNames={sloDisplayNames}
          />
        </>
      )}
    </div>
  )
}
