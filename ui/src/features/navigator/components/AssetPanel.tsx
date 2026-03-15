// ui/src/features/navigator/components/AssetPanel.tsx
import { useState, useMemo } from 'react'
import { useAssetEvaluations, useMetricHeatmap } from '../hooks'
import { useEvaluationDetail, useInvalidateEvaluation } from '@/features/evaluations/hooks'
import { AssetHeatmap } from './AssetHeatmap'
import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
import { SLIBreakdownTable } from '@/features/evaluations/components/SLIBreakdownTable'
import { EvaluationTabs, tabLabel } from '@/features/evaluations/components/EvaluationTabs'
import { AnnotationForm } from '@/features/evaluations/components/AnnotationForm'
import { ResultBadge } from '@/features/evaluations/components/ResultBadge'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR } from '@/lib/theme'

type ViewMode = 'heatmap' | 'chart'

interface Props {
  assetName: string
}

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export function AssetPanel({ assetName }: Props) {
  const [mode, setMode] = useState<ViewMode>('heatmap')
  const [selectedEvalId, setSelectedEvalId] = useState<string | undefined>(undefined)
  const [activeTab, setActiveTab] = useState('all')
  const [metricGroupFilter, setMetricGroupFilter] = useState<string>('all')
  const [showInvalidateForm, setShowInvalidateForm] = useState(false)
  const [pendingReason, setPendingReason] = useState('')

  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]

  const { data: evals = [], isLoading: evalsLoading } = useAssetEvaluations(assetName)
  const { data: heatmapData, isLoading: heatmapLoading } = useMetricHeatmap(assetName)

  // Default selection: latest non-invalidated eval, or latest if all invalidated
  const defaultEvalId = useMemo(() => {
    if (!evals.length) return undefined
    const sorted = [...evals].sort((a, b) => b.period_start.localeCompare(a.period_start))
    return (sorted.find(e => !e.invalidated) ?? sorted[0]).id
  }, [evals])

  // Use explicit selection if set, otherwise fall back to default
  const effectiveEvalId = selectedEvalId ?? defaultEvalId

  const { data: ev } = useEvaluationDetail(effectiveEvalId)
  const invalidate = useInvalidateEvaluation(effectiveEvalId ?? '')

  // SLI tab groups from detail
  const availableGroups = useMemo(() =>
    [...new Set(ev?.indicator_results.map(i => i.tab_group).filter(Boolean) as string[])],
    [ev],
  )

  const counts = useMemo(() =>
    Object.fromEntries(
      availableGroups.map(g => [g, ev?.indicator_results.filter(i => i.tab_group === g).length ?? 0]),
    ),
    [ev, availableGroups],
  )

  const resolvedTab = ['all', ...availableGroups].includes(activeTab) ? activeTab : 'all'

  const tabIndicators = useMemo(
    () => resolvedTab === 'all'
      ? (ev?.indicator_results ?? [])
      : (ev?.indicator_results.filter(ind => ind.tab_group === resolvedTab) ?? []),
    [ev, resolvedTab],
  )

  // All indicators for chart mode (from heatmap metric list — stubs for MetricTrendBlock)
  const allIndicators = useMemo(() => {
    if (!heatmapData) return []
    return heatmapData.metrics.map(m => ({
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

  const isLoading = evalsLoading || heatmapLoading
  const displayResult = ev ? (ev.invalidated ? 'invalidated' : ev.result) : undefined
  const score = ev ? Math.round(ev.score) : undefined

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold font-mono">{assetName}</h2>
          <span
            className="text-2xl font-bold tabular-nums"
            style={{ color: score != null ? (colours[ev!.result as keyof typeof colours] ?? colours.error) : undefined }}
          >
            {score != null ? `${score}%` : '—'}
          </span>
          {displayResult && <ResultBadge result={displayResult} />}
        </div>
        <div className="flex items-center gap-2">
          {/* Invalidate button */}
          {ev && !ev.invalidated && (
            <button
              onClick={() => setShowInvalidateForm(v => !v)}
              className="px-3 py-1 text-xs font-medium rounded border border-red-700/60 text-red-400 bg-red-900/20 hover:bg-red-900/40 transition-colors"
            >
              Invalidate
            </button>
          )}
          {ev?.invalidated && (
            <span className="text-xs text-muted-foreground italic">invalidated</span>
          )}
          {/* View toggle */}
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
        </div>
      </div>

      {/* Inline invalidate form */}
      {showInvalidateForm && ev && !ev.invalidated && (
        <div className="rounded-lg border border-red-800/40 bg-card p-4 space-y-3">
          <p className="text-sm font-medium text-red-300">Reason for invalidation</p>
          <textarea
            value={pendingReason}
            onChange={e => setPendingReason(e.target.value)}
            placeholder="Describe why this evaluation result should be discarded…"
            rows={3}
            className="w-full px-3 py-2 bg-muted border border-border rounded text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-red-500 resize-none"
          />
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => { setShowInvalidateForm(false); setPendingReason('') }}
              className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:text-foreground transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                invalidate.mutate(pendingReason, {
                  onSuccess: () => { setShowInvalidateForm(false); setPendingReason('') },
                })
              }}
              disabled={!pendingReason.trim() || invalidate.isPending}
              className="px-3 py-1.5 text-xs font-medium rounded bg-red-700 text-white hover:bg-red-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {invalidate.isPending ? 'Invalidating…' : 'Confirm invalidation'}
            </button>
          </div>
        </div>
      )}

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {/* ── Heatmap mode ── */}
      {!isLoading && mode === 'heatmap' && (
        <>
          {/* Notes */}
          {effectiveEvalId && (
            <AnnotationForm evalId={effectiveEvalId} annotations={ev?.annotations ?? []} />
          )}

          {/* Metric Heatmap */}
          {heatmapData && (
            <div className="rounded-lg border border-border bg-card p-4">
              <AssetHeatmap
                data={heatmapData}
                selectedEvalId={effectiveEvalId}
                onEvalSelect={setSelectedEvalId}
              />
            </div>
          )}

          {/* SLI Breakdown */}
          {ev && (
            <div id="sli-table" className="space-y-0 scroll-mt-4">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">SLI Breakdown</h2>
              </div>
              <EvaluationTabs
                availableGroups={availableGroups}
                allCount={ev.indicator_results.length}
                counts={counts}
                activeTab={resolvedTab}
                onTabChange={setActiveTab}
              />
              <SLIBreakdownTable
                indicators={tabIndicators}
                onIndicatorClick={(metric, tabGroup) => {
                  if (resolvedTab !== 'all') setActiveTab(tabGroup)
                  setTimeout(() => scrollTo(`trend-${metric}`), 50)
                }}
              />
            </div>
          )}

          {/* Metric Trend Charts */}
          {effectiveEvalId && tabIndicators.length > 0 && (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                30-day trend for{' '}
                <strong className="text-foreground">{resolvedTab === 'all' ? 'All' : tabLabel(resolvedTab)}</strong>{' '}
                metrics on <strong className="text-foreground">{assetName}</strong>.
              </p>
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {tabIndicators.map(ind => (
                  <MetricTrendBlock key={ind.metric} evalId={effectiveEvalId} indicator={ind} />
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Charts mode ── */}
      {!isLoading && mode === 'chart' && effectiveEvalId && (
        <div className="space-y-4">
          {/* Metric group filter tabs */}
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
            {chartIndicators.map(ind => (
              <MetricTrendBlock key={ind.metric} evalId={effectiveEvalId} indicator={ind} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
