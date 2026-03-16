// ui/src/features/navigator/components/AssetPanel.tsx
import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAssetEvaluations, useMetricHeatmap } from '../hooks'
import { useEvaluationDetail } from '@/features/evaluations/hooks'
import { AssetHeatmap } from './AssetHeatmap'
import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
import { SLIBreakdownTable } from '@/features/evaluations/components/SLIBreakdownTable'
import { EvaluationTabs, tabLabel } from '@/features/evaluations/components/EvaluationTabs'
import { EvaluationHeader } from '@/features/evaluations/components/EvaluationHeader'
import { AnnotationForm } from '@/features/evaluations/components/AnnotationForm'
import { EvaluationActionsButton, EvaluationActionForm } from '@/features/evaluations/components/EvaluationActions'
import type { ActionKind } from '@/features/evaluations/components/EvaluationActions'
import { ViewToggle } from '@/components/charts/ViewToggle'
import type { ViewMode } from '@/components/charts/ViewToggle'
import { AssetScoreChart } from './AssetScoreChart'

interface Props {
  assetName: string
  initialEvalId?: string
}

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export function AssetPanel({ assetName, initialEvalId }: Props) {
  const [mode, setMode] = useState<ViewMode>('heatmap')
  const [selectedEvalId, setSelectedEvalId] = useState<string | undefined>(initialEvalId)
  const [activeTab, setActiveTab] = useState('all')
  const [activeAction, setActiveAction] = useState<ActionKind | null>(null)
  const [metricGroupFilter, setMetricGroupFilter] = useState<string>('all')
  const navigate = useNavigate()

  const explorerButton = (
    <button
      onClick={() => navigate(`/explorer?asset=${encodeURIComponent(assetName)}`)}
      className="p-1.5 rounded border border-slate-600 text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors"
      title="Open Metric Explorer"
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
        <rect x="1" y="9" width="3" height="6" rx="0.5"/>
        <rect x="6" y="5" width="3" height="10" rx="0.5"/>
        <rect x="11" y="2" width="3" height="13" rx="0.5"/>
      </svg>
    </button>
  )

  const { data: evals = [], isLoading: evalsLoading } = useAssetEvaluations(assetName)
  const { data: heatmapData, isLoading: heatmapLoading } = useMetricHeatmap(assetName)

  const defaultEvalId = useMemo(() => {
    if (!evals.length) return undefined
    const sorted = [...evals].sort((a, b) => b.period_start.localeCompare(a.period_start))
    return (sorted.find(e => !e.invalidated) ?? sorted[0]).id
  }, [evals])

  const effectiveEvalId = selectedEvalId ?? defaultEvalId

  const { data: ev } = useEvaluationDetail(effectiveEvalId)

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
      {/* Header card */}
      <EvaluationHeader
        title={assetName}
        titleMono
        result={displayResult}
        score={score}
        metadata={ev ? (
          <>
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-400">
              <span>Asset: <span className="text-slate-200">{ev.asset_snapshot.name}</span></span>
              {Object.entries(ev.asset_snapshot.tags ?? {}).map(([k, v]) => (
                <span key={k} className="text-slate-500 text-xs">{k}: {v as string}</span>
              ))}
              <span className="text-xs">
                {ev.period_start.slice(0, 16).replace('T', ' ')} → {ev.period_end.slice(11, 16)}
              </span>
            </div>
            <div className="mt-1 text-xs text-slate-500">
              SLO: {ev.slo_name ?? '—'}{ev.slo_version != null && ` v${ev.slo_version}`}
              {ev.adapter_used && ` · adapter: ${ev.adapter_used}`}
              {ev.asset_snapshot.build_ref && ` · build: ${ev.asset_snapshot.build_ref}`}
            </div>
          </>
        ) : undefined}
        actions={effectiveEvalId && ev ? (
          <EvaluationActionsButton
            currentResult={ev.result}
            invalidated={ev.invalidated}
            activeAction={activeAction}
            onSelectAction={setActiveAction}
          />
        ) : undefined}
      />

      {/* Action form */}
      {activeAction && effectiveEvalId && ev && !ev.invalidated && (
        <EvaluationActionForm
          evalId={effectiveEvalId}
          currentResult={ev.result}
          activeAction={activeAction}
          onClose={() => setActiveAction(null)}
        />
      )}

      {isLoading && <p className="text-sm text-slate-400">Loading…</p>}

      {/* Notes — shown when a single evaluation is selected */}
      {!isLoading && effectiveEvalId && ev && (
        <AnnotationForm evalId={effectiveEvalId} annotations={ev.annotations ?? []} />
      )}

      {/* ── Heatmap mode ── */}
      {!isLoading && mode === 'heatmap' && (
        <>
          {/* Metric Heatmap with view toggle */}
          {heatmapData && (
            <div className="rounded-lg border border-slate-700 bg-gray-900 p-4">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Metric Heatmap</h2>
                <div className="flex items-center gap-3">
                  <ViewToggle mode={mode} setMode={setMode} />
                  {explorerButton}
                </div>
              </div>
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
                <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">SLI Breakdown</h2>
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
              <p className="text-xs text-slate-500">
                30-day trend for{' '}
                <strong className="text-slate-300">{resolvedTab === 'all' ? 'All' : tabLabel(resolvedTab)}</strong>{' '}
                metrics on <strong className="text-slate-300">{assetName}</strong>.
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
      {!isLoading && mode === 'chart' && (
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
            <AssetScoreChart evaluations={evals} selectedEvalId={effectiveEvalId} />
          </div>

          {effectiveEvalId && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => setMetricGroupFilter('all')}
                  className={`px-3 py-1.5 rounded text-sm transition-colors ${
                    metricGroupFilter === 'all' ? 'bg-gray-800 text-slate-200' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  All ({allIndicators.length})
                </button>
                {metricGroups.map(g => (
                  <button
                    key={g}
                    onClick={() => setMetricGroupFilter(g)}
                    className={`px-3 py-1.5 rounded text-sm transition-colors ${
                      metricGroupFilter === g ? 'bg-gray-800 text-slate-200' : 'text-slate-400 hover:text-slate-200'
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
        </>
      )}
    </div>
  )
}
