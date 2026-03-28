// ui/src/features/navigator/components/AssetPanelChartView.tsx
import { useState, useMemo } from 'react'
import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
import { ViewToggle } from '@/components/charts/ViewToggle'
import type { ViewMode } from '@/components/charts/ViewToggle'
import { AssetScoreChart } from './AssetScoreChart'
import { MetricGroupFilter } from './MetricGroupFilter'
import type { EvaluationSummary, IndicatorResult } from '@/features/evaluations/types'
import type { MetricHeatmapResponse } from '../types'

interface Props {
  effectiveEvalId: string | undefined
  evals: EvaluationSummary[]
  heatmapData: MetricHeatmapResponse | undefined
  onEvalSelect: (evalId: string) => void
  mode: ViewMode
  setMode: (m: ViewMode) => void
  explorerButton: React.ReactNode
}

export function AssetPanelChartView({
  effectiveEvalId, evals, heatmapData,
  onEvalSelect, mode, setMode, explorerButton,
}: Props) {
  const [metricGroupFilter, setMetricGroupFilter] = useState<string>('all')

  const allIndicators: IndicatorResult[] = useMemo(() => {
    if (!heatmapData) return []
    return heatmapData.metrics.filter(m => m.name !== '__score__').map(m => ({
      metric: m.name,
      display_name: m.display_name,
      tab_group: m.tab_group,
      value: 0,
      compared_value: null,
      change_absolute: null,
      change_relative_pct: null,
      aggregation: 'avg' as const,
      status: 'pass' as const,
      score: 0,
      weight: 1,
      key_sli: false,
      pass_targets: null,
      warning_targets: null,
    }))
  }, [heatmapData])

  const metricGroups = useMemo(
    () => Array.from(new Set(allIndicators.map(i => i.tab_group).filter(Boolean) as string[])),
    [allIndicators],
  )

  const chartIndicators = metricGroupFilter === 'all'
    ? allIndicators
    : allIndicators.filter(i => i.tab_group === metricGroupFilter)

  return (
    <>
      {/* Toggle + explorer */}
      <div className="flex justify-end">
        <div className="flex items-center gap-3">
          <ViewToggle mode={mode} setMode={setMode} />
          {explorerButton}
        </div>
      </div>

      {/* Score over time */}
      <div className="rounded-lg border border-slate-700 bg-gray-900 p-4">
        <AssetScoreChart evaluations={evals} selectedEvalId={effectiveEvalId} onEvalSelect={onEvalSelect} />
      </div>

      {effectiveEvalId && (
        <div className="space-y-4">
          <MetricGroupFilter
            allIndicators={allIndicators}
            metricGroups={metricGroups}
            activeFilter={metricGroupFilter}
            onFilterChange={setMetricGroupFilter}
          />

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {chartIndicators.map(ind => (
              <MetricTrendBlock key={ind.metric} evalId={effectiveEvalId} indicator={ind} onEvalSelect={onEvalSelect} />
            ))}
          </div>
        </div>
      )}
    </>
  )
}
