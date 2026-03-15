// ui/src/features/navigator/components/AssetPanel.tsx
import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAssetEvaluations, useMetricHeatmap } from '../hooks'
import { AssetHeatmap } from './AssetHeatmap'
import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
import { EvaluationTable } from '@/features/evaluations/components/EvaluationTable'
import { useColumnVisibility } from '@/features/evaluations/hooks'
import type { IndicatorResult } from '@/features/evaluations/types'

type ViewMode = 'heatmap' | 'chart'

interface Props {
  assetName: string
}

export function AssetPanel({ assetName }: Props) {
  const [mode, setMode] = useState<ViewMode>('heatmap')
  const [metricGroupFilter, setMetricGroupFilter] = useState<string>('all')
  const navigate = useNavigate()

  const { data: evals = [], isLoading: evalsLoading } = useAssetEvaluations(assetName)
  const { data: heatmapData, isLoading: heatmapLoading } = useMetricHeatmap(assetName)

  // Latest non-invalidated evaluation for trend charts
  const latestEval = useMemo(() => {
    return [...evals]
      .filter(e => !e.invalidated)
      .sort((a, b) => b.period_start.localeCompare(a.period_start))[0]
  }, [evals])

  const latestScore = latestEval ? Math.round(latestEval.score) : null

  // Build indicator stubs for MetricTrendBlock from heatmap metric list
  const allIndicators = useMemo((): IndicatorResult[] => {
    if (!heatmapData) return []
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
  }, [heatmapData])

  // Unique tab_group values from the metric list
  const metricGroups = useMemo(
    () => Array.from(new Set(allIndicators.map(i => i.tab_group).filter(Boolean) as string[])),
    [allIndicators]
  )

  // Chart mode: filter by selected group; heatmap mode: show first 8 metrics
  const visibleIndicators = mode === 'chart'
    ? (metricGroupFilter === 'all' ? allIndicators : allIndicators.filter(i => i.tab_group === metricGroupFilter))
    : allIndicators.slice(0, 8)

  const colVis = useColumnVisibility([])
  const isLoading = evalsLoading || heatmapLoading

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold font-mono">{assetName}</h2>
          {evals.length > 0 && (
            <p className="text-xs text-muted-foreground mt-0.5">{evals.length} evaluations</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {latestScore != null && (
            <span className="text-2xl font-bold tabular-nums text-foreground">{latestScore}%</span>
          )}
          <div className="flex border border-border rounded overflow-hidden text-xs">
            <button
              onClick={() => setMode('heatmap')}
              className={`px-3 py-1.5 transition-colors ${mode === 'heatmap' ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted/50'}`}
            >
              Heatmap
            </button>
            <button
              onClick={() => setMode('chart')}
              className={`px-3 py-1.5 transition-colors ${mode === 'chart' ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted/50'}`}
            >
              Charts
            </button>
          </div>
          <button
            onClick={() => navigate(`/explorer?asset=${encodeURIComponent(assetName)}`)}
            className="p-1.5 rounded border border-border text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            title="Open Metric Explorer"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <rect x="1" y="9" width="3" height="6" rx="0.5"/>
              <rect x="6" y="5" width="3" height="10" rx="0.5"/>
              <rect x="11" y="2" width="3" height="13" rx="0.5"/>
            </svg>
          </button>
        </div>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {/* Heatmap mode: overview grid + first 8 trend charts */}
      {!isLoading && heatmapData && mode === 'heatmap' && (
        <>
          <div className="rounded-lg border border-border bg-card p-4">
            <AssetHeatmap data={heatmapData} />
          </div>
          {latestEval && visibleIndicators.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Metric Trends — {assetName} (first 8 metrics)
              </h3>
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {visibleIndicators.map(ind => (
                  <MetricTrendBlock key={ind.metric} evalId={latestEval.id} indicator={ind} />
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Chart mode: metric group filter + all filtered trend charts, no heatmap */}
      {!isLoading && mode === 'chart' && latestEval && (
        <div className="space-y-4">
          {/* Metric group filter */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setMetricGroupFilter('all')}
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                metricGroupFilter === 'all' ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              All ({allIndicators.length})
            </button>
            {metricGroups.map(g => (
              <button
                key={g}
                onClick={() => setMetricGroupFilter(g)}
                className={`px-3 py-1.5 rounded text-sm transition-colors ${
                  metricGroupFilter === g ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {g} ({allIndicators.filter(i => i.tab_group === g).length})
              </button>
            ))}
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {visibleIndicators.map(ind => (
              <MetricTrendBlock key={ind.metric} evalId={latestEval.id} indicator={ind} />
            ))}
          </div>
        </div>
      )}

      {/* Score table — always shown at the bottom */}
      {!isLoading && evals.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
            Evaluation History
          </h3>
          <EvaluationTable evaluations={evals} dynamicCols={[]} {...colVis} />
        </div>
      )}
    </div>
  )
}
