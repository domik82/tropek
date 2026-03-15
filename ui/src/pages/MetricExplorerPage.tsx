// ui/src/pages/MetricExplorerPage.tsx
import { useState, useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useEvaluations } from '@/features/evaluations/hooks'
import { useAssetEvaluations, useMetricHeatmap } from '@/features/navigator/hooks'
import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
import { METRICS } from '@/mocks/generate'
import type { IndicatorResult } from '@/features/evaluations/types'
import type { MetricHeatmapResponse } from '@/features/navigator/types'

function buildIndicatorStubsFromHeatmap(heatmapData: MetricHeatmapResponse): IndicatorResult[] {
  return heatmapData.metrics.map(m => ({
    metric: m.name,
    display_name: m.display_name,
    tab_group: m.tab_group,
    value: 0,
    compared_value: null,
    change_absolute: null,
    change_relative_pct: null,
    aggregation: 'avg',
    status: 'pass' as const,
    score: 0,
    weight: 1,
    key_sli: false,
    pass_targets: null,
    warning_targets: null,
  }))
}

// Fallback for group view (no per-asset heatmap): use the full METRICS catalogue
function buildIndicatorStubsFromCatalogue(): IndicatorResult[] {
  return METRICS.map(m => ({
    metric: m.name,
    display_name: m.display_name,
    tab_group: m.tab_group,
    value: 0,
    compared_value: null,
    change_absolute: null,
    change_relative_pct: null,
    aggregation: 'avg',
    status: 'pass' as const,
    score: 0,
    weight: m.weight,
    key_sli: m.key_sli,
    pass_targets: null,
    warning_targets: null,
  }))
}

export function MetricExplorerPage() {
  const [params] = useSearchParams()
  const groupName = params.get('group') ?? undefined
  const assetName = params.get('asset') ?? undefined
  const [metricGroupFilter, setMetricGroupFilter] = useState<string>('all')

  const { data: groupEvals = [] } = useEvaluations(
    groupName ? { group_name: groupName } : {},
  )
  const { data: assetEvals = [] } = useAssetEvaluations(assetName)
  const { data: heatmapData } = useMetricHeatmap(assetName)

  // Pick the anchor eval for trend charts
  const evals = assetName ? assetEvals : groupEvals
  const latestEval = useMemo(() =>
    [...evals]
      .filter(e => !e.invalidated)
      .sort((a, b) => b.period_start.localeCompare(a.period_start))[0],
    [evals]
  )

  // Use asset heatmap metric list when available (accurate per-asset metrics),
  // fall back to the full METRICS catalogue for group view
  const allIndicators = useMemo(
    () => heatmapData ? buildIndicatorStubsFromHeatmap(heatmapData) : buildIndicatorStubsFromCatalogue(),
    [heatmapData],
  )
  const metricGroups = useMemo(
    () => Array.from(new Set(allIndicators.map(i => i.tab_group).filter(Boolean))),
    [allIndicators],
  )

  const visibleIndicators = metricGroupFilter === 'all'
    ? allIndicators
    : allIndicators.filter(i => i.tab_group === metricGroupFilter)

  const backHref = assetName
    ? `/navigator?asset=${encodeURIComponent(assetName)}`
    : groupName
    ? `/navigator?group=${encodeURIComponent(groupName)}`
    : '/navigator'

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <Link to={backHref} className="text-sm text-muted-foreground hover:text-foreground">
          ← Back
        </Link>
        <h1 className="text-xl font-semibold">Metric Explorer</h1>
        {(groupName || assetName) && (
          <span className="text-sm text-muted-foreground">
            — {assetName ?? groupName}
          </span>
        )}
      </div>

      {/* Metric group filter tabs */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setMetricGroupFilter('all')}
          className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
            metricGroupFilter === 'all' ? 'bg-muted text-foreground' : 'bg-background text-muted-foreground hover:text-foreground'
          }`}
        >
          All ({allIndicators.length})
        </button>
        {metricGroups.map(g => (
          <button
            key={g}
            onClick={() => setMetricGroupFilter(g!)}
            className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
              metricGroupFilter === g ? 'bg-muted text-foreground' : 'bg-background text-muted-foreground hover:text-foreground'
            }`}
          >
            {g} ({allIndicators.filter(i => i.tab_group === g).length})
          </button>
        ))}
      </div>

      {!latestEval && (
        <p className="text-sm text-muted-foreground">
          Select a group or asset from the Navigator to load metric trends.
        </p>
      )}

      {latestEval && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {visibleIndicators.map(ind => (
            <MetricTrendBlock key={ind.metric} evalId={latestEval.id} indicator={ind} />
          ))}
        </div>
      )}
    </div>
  )
}
