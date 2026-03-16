// ui/src/pages/MetricExplorerPage.tsx
import { useState, useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useQueries } from '@tanstack/react-query'
import { evaluationKeys } from '@/lib/queryKeys'
import { useEvaluations, useEvaluationDetail } from '@/features/evaluations/hooks'
import { fetchTrend } from '@/features/evaluations/api'
import { useAssetEvaluations, useMetricHeatmap } from '@/features/navigator/hooks'
import { MetricLabelPanel } from '@/components/charts/MetricLabelPanel'
import { MultiSeriesChart } from '@/components/charts/MultiSeriesChart'
import type { MultiSeriesChartProps } from '@/components/charts/MultiSeriesChart'
import { buildColorMap } from '@/components/charts/colors'
import type { TrendPoint } from '@/features/evaluations/types'

// ── useEnabledTrends ──────────────────────────────────────────────────────────

function useEnabledTrends(
  evalId: string | undefined,
  enabledMetrics: string[],
): Map<string, TrendPoint[]> {
  const results = useQueries({
    queries: enabledMetrics.map(metric => ({
      queryKey: evaluationKeys.trend(evalId ?? '', metric),
      queryFn: () => fetchTrend(evalId!, metric),
      enabled: !!evalId,
      staleTime: Infinity,
    })),
  })

  const map = new Map<string, TrendPoint[]>()
  for (let i = 0; i < enabledMetrics.length; i++) {
    const data = results[i]?.data
    if (data) map.set(enabledMetrics[i], data)
  }
  return map
}

// ── ChartSection ─────────────────────────────────────────────────────────────

interface ChartSectionProps {
  title: string
  subtitle: string
  indicators: Array<{ metric: string; display_name: string; tab_group?: string }>
  colors: Map<string, string>
  enabled: Set<string>
  setEnabled: React.Dispatch<React.SetStateAction<Set<string>>>
  evalId: string | undefined
  dataKey: 'value' | 'score'
  yAxisMax?: number
  stacked?: boolean
}

type ChartType = 'line' | 'bar'

function ChartSection({
  title,
  subtitle,
  indicators,
  colors,
  enabled,
  setEnabled,
  evalId,
  dataKey,
  yAxisMax: yAxisMaxProp,
  stacked: stackedProp = false,
}: ChartSectionProps) {
  const [yMin, setYMin] = useState('')
  const [yMax, setYMax] = useState('')
  const [chartType, setChartType] = useState<ChartType>('line')

  const trendData = useEnabledTrends(evalId, [...enabled])

  const chartSeries = useMemo(() => {
    const result: MultiSeriesChartProps['series'] = []
    for (const [metric, points] of trendData) {
      const ind = indicators.find(i => i.metric === metric)
      if (!ind) continue
      result.push({
        metric,
        displayName: ind.display_name,
        color: colors.get(metric) ?? '#64748b',
        data: points.map(p => ({ timestamp: p.timestamp, value: p[dataKey] })),
      })
    }
    return result
  }, [trendData, indicators, colors, dataKey])

  function handleToggle(metric: string) {
    setEnabled(prev => {
      const next = new Set(prev)
      next.has(metric) ? next.delete(metric) : next.add(metric)
      return next
    })
  }

  function handleGroupAll(group: string) {
    const groupMetrics = indicators
      .filter(i => (i.tab_group ?? 'Other') === group)
      .map(i => i.metric)
    setEnabled(prev => {
      const next = new Set(prev)
      for (const m of groupMetrics) next.add(m)
      return next
    })
  }

  function handleGroupNone(group: string) {
    const groupMetrics = new Set(
      indicators
        .filter(i => (i.tab_group ?? 'Other') === group)
        .map(i => i.metric),
    )
    setEnabled(prev => {
      const next = new Set(prev)
      for (const m of groupMetrics) next.delete(m)
      return next
    })
  }

  return (
    <div className="flex flex-col border-b border-slate-700" style={{ minHeight: '50%' }}>
      {/* Section title bar */}
      <div className="px-4 py-2 border-b border-slate-700 shrink-0 flex items-center gap-4">
        <div>
          <span className="text-sm font-semibold text-slate-200">{title}</span>
          <span className="ml-2 text-xs text-slate-400">{subtitle}</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          {/* All / None */}
          <div className="flex items-center gap-1 text-xs">
            <button
              onClick={() => setEnabled(new Set(indicators.map(i => i.metric)))}
              className="text-slate-500 hover:text-slate-300"
            >
              All
            </button>
            <button
              onClick={() => setEnabled(new Set())}
              className="text-slate-500 hover:text-slate-300"
            >
              None
            </button>
          </div>
          {/* Y-axis range */}
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <label className="flex items-center gap-1">
              Y <input
                type="number" value={yMin} onChange={e => setYMin(e.target.value)}
                placeholder="min"
                className="w-14 px-1 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-300 text-xs"
              />
            </label>
            <label className="flex items-center gap-1">
              – <input
                type="number" value={yMax} onChange={e => setYMax(e.target.value)}
                placeholder="max"
                className="w-14 px-1 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-300 text-xs"
              />
            </label>
          </div>
          {/* Line / Bar toggle */}
          <div className="flex border border-slate-700 rounded overflow-hidden text-xs">
            <button
              onClick={() => setChartType('line')}
              className={`px-2 py-0.5 transition-colors ${chartType === 'line' ? 'bg-gray-800 text-slate-200' : 'text-slate-400 hover:bg-gray-800/50'}`}
            >
              Line
            </button>
            <button
              onClick={() => setChartType('bar')}
              className={`px-2 py-0.5 transition-colors ${chartType === 'bar' ? 'bg-gray-800 text-slate-200' : 'text-slate-400 hover:bg-gray-800/50'}`}
            >
              Bar
            </button>
          </div>
        </div>
      </div>

      {/* Label panel + chart */}
      <div className="flex flex-1 min-h-0">
        <div className="shrink-0 border-r border-slate-700 p-3 overflow-y-auto" style={{ width: 280 }}>
          <MetricLabelPanel
            indicators={indicators}
            colors={colors}
            enabled={enabled}
            onToggle={handleToggle}
            onGroupAll={handleGroupAll}
            onGroupNone={handleGroupNone}
          />
        </div>
        <div className="flex-1 min-w-0 p-3 flex flex-col">
          <div className="flex-1 min-h-0">
            <MultiSeriesChart
              series={chartSeries}
              yAxisMin={yMin !== '' ? parseFloat(yMin) : undefined}
              yAxisMax={yMax !== '' ? parseFloat(yMax) : yAxisMaxProp}
              chartType={chartType}
              stacked={stackedProp}
              height="100%"
            />
          </div>
        </div>
      </div>
    </div>
  )
}

// ── MetricExplorerPage ────────────────────────────────────────────────────────

export function MetricExplorerPage() {
  const [params] = useSearchParams()
  const groupName = params.get('group') ?? undefined
  const assetName = params.get('asset') ?? undefined

  const [valuesEnabled, setValuesEnabled] = useState<Set<string>>(new Set())
  const [scoresEnabled, setScoresEnabled] = useState<Set<string>>(new Set())

  const { data: groupEvals = [] } = useEvaluations(
    groupName ? { group_name: groupName } : {},
  )
  const { data: assetEvals = [] } = useAssetEvaluations(assetName)
  const { data: heatmapData } = useMetricHeatmap(assetName)

  // Pick the anchor eval for trend queries
  const evals = assetName ? assetEvals : groupEvals
  const latestEval = useMemo(
    () =>
      [...evals]
        .filter(e => !e.invalidated)
        .sort((a, b) => b.period_start.localeCompare(a.period_start))[0],
    [evals],
  )

  // For group view: load indicator list from the latest eval's detail
  const { data: latestDetail } = useEvaluationDetail(
    !assetName && latestEval ? latestEval.id : undefined,
  )

  // Build indicator list
  const allIndicators = useMemo(() => {
    if (heatmapData) {
      return heatmapData.metrics.map(m => ({
        metric: m.name,
        display_name: m.display_name,
        tab_group: m.tab_group,
      }))
    }
    if (latestDetail) {
      return latestDetail.indicator_results.map(r => ({
        metric: r.metric,
        display_name: r.display_name,
        tab_group: r.tab_group,
      }))
    }
    return []
  }, [heatmapData, latestDetail])

  const colorMap = useMemo(() => buildColorMap(allIndicators), [allIndicators])

  const backHref = assetName
    ? `/navigator?asset=${encodeURIComponent(assetName)}`
    : groupName
    ? `/navigator?group=${encodeURIComponent(groupName)}`
    : '/navigator'

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 49px)' }}>
      {/* Header bar */}
      <div className="px-6 py-3 border-b border-slate-700 flex items-center gap-3 shrink-0">
        <Link to={backHref} className="text-sm text-slate-400 hover:text-slate-200">
          ← Back
        </Link>
        <h1 className="text-lg font-semibold text-slate-100">Metric Explorer</h1>
        {(groupName || assetName) && (
          <span className="text-sm text-slate-400">— {assetName ?? groupName}</span>
        )}
      </div>

      {/* Two chart sections */}
      <div className="flex-1 overflow-y-auto">
        <ChartSection
          title="Values"
          subtitle="Raw metric values over time"
          indicators={allIndicators}
          colors={colorMap}
          enabled={valuesEnabled}
          setEnabled={setValuesEnabled}
          evalId={latestEval?.id}
          dataKey="value"
        />
        <ChartSection
          title="Scores"
          subtitle="Weighted contributions — stacks to 100% when all pass"
          indicators={allIndicators}
          colors={colorMap}
          enabled={scoresEnabled}
          setEnabled={setScoresEnabled}
          evalId={latestEval?.id}
          dataKey="score"
          yAxisMax={100}
          stacked
        />
      </div>
    </div>
  )
}
