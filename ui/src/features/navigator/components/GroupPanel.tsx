// ui/src/features/navigator/components/GroupPanel.tsx
import { useState, useMemo } from 'react'
import { useAssetGroups, useAssets } from '@/features/assets/hooks'
import { useSlos } from '@/features/slos/hooks'
import { useEvaluations, useDynamicColumns, useColumnVisibility } from '@/features/evaluations/hooks'
import { EvaluationHeatmap } from '@/features/evaluations/components/EvaluationHeatmap'
import { EvaluationTable } from '@/features/evaluations/components/EvaluationTable'
import { EvaluationHeader } from '@/features/evaluations/components/EvaluationHeader'
import { TruncationWarning } from '@/features/evaluations/components/TruncationWarning'
import { TimeRangePicker } from '@/components/TimeRangePicker'
import { EvaluationNameFilter } from './EvaluationNameFilter'
import { useEvaluationNames } from '../hooks'
import { GroupScoreChart } from './GroupScoreChart'
import { ViewToggle } from '@/components/charts/ViewToggle'
import type { ViewMode } from '@/components/charts/ViewToggle'

interface Props {
  groupName: string
  onSelectAsset: (name: string, evalId?: string) => void
}

function prettyGroupName(name: string) {
  return name.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export function GroupPanel({ groupName, onSelectAsset }: Props) {
  const [mode, setMode] = useState<ViewMode>('heatmap')
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedNames, setSelectedNames] = useState<string[] | undefined>(undefined)

  const { data: tree } = useAssetGroups()
  const group = tree?.all_groups.find(g => g.name === groupName)
  const groupLabel = group?.display_name ?? prettyGroupName(groupName)

  const { data: evalNames = [] } = useEvaluationNames(undefined, groupName)

  const { data: evals = [], isLoading, truncated, total } = useEvaluations({
    group_name: groupName,
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
    for (const s of slos ?? []) if (s.display_name) m.set(s.name, s.display_name)
    return m
  }, [slos])

  const dynamicCols = useDynamicColumns(evals)
  const colVis = useColumnVisibility(dynamicCols)
  const tableEvals = selectedDate
    ? evals.filter(e => e.period_start === selectedDate)
    : evals

  return (
    <div className="p-6 space-y-4">
      {/* Header card — group name only */}
      <EvaluationHeader
        title={groupLabel}
        subtitle={evals.length > 0 ? `${evals.length} evaluations` : undefined}
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

      {/* Content */}
      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {!isLoading && evals.length === 0 && (
        <p className="text-sm text-muted-foreground">No evaluations found for this group.</p>
      )}

      {!isLoading && evals.length > 0 && mode === 'heatmap' && (
        <>
          <div className="rounded-lg border border-border bg-surface-sunken p-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Evaluation Heatmap</h2>
              <ViewToggle mode={mode} setMode={setMode} />
            </div>
            <EvaluationHeatmap
              evaluations={evals}
              selectedDate={selectedDate}
              onDateSelect={setSelectedDate}
              assetDisplayNames={assetDisplayNames}
              onAssetSelect={(assetName) => {
                const match = selectedDate
                  ? evals.find(e => e.asset_snapshot.name === assetName && e.period_start === selectedDate)
                  : undefined
                onSelectAsset(assetName, match?.id)
              }}
            />
          </div>
          <EvaluationTable evaluations={tableEvals} {...colVis} onAssetSelect={onSelectAsset} onEvalClick={ev => onSelectAsset(ev.asset_snapshot.name, ev.id)} assetDisplayNames={assetDisplayNames} sloDisplayNames={sloDisplayNames} />
        </>
      )}

      {!isLoading && evals.length > 0 && mode === 'chart' && (
        <>
          <div className="flex justify-end">
            <ViewToggle mode={mode} setMode={setMode} />
          </div>
          <div className="rounded-lg border border-border bg-surface-sunken p-4">
            <GroupScoreChart evaluations={evals} assetDisplayNames={assetDisplayNames} />
          </div>
        </>
      )}
    </div>
  )
}
