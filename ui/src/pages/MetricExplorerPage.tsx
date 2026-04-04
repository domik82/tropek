// ui/src/pages/MetricExplorerPage.tsx
import { useState, useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useQueries } from '@tanstack/react-query'
import { evaluationKeys } from '@/lib/queryKeys'
import { useEvaluations, useEvaluationDetail, fetchTrend } from '@/features/evaluations'
import type { TrendPoint } from '@/features/evaluations'
import { useAssetEvaluations, useMetricHeatmap } from '@/features/navigator'
import { MetricLabelPanel } from '@/components/charts/MetricLabelPanel'
import { MultiSeriesChart } from '@/components/charts/MultiSeriesChart'
import type { MultiSeriesChartProps } from '@/components/charts/MultiSeriesChart'
import { buildColorMap } from '@/components/charts/colors'
import { TimeRangePicker } from '@/components/TimeRangePicker'
import { useTimeRange } from '@/lib/time-range-context'
import { Button } from '@/components/ui/button'

// ── useEnabledTrends ──────────────────────────────────────────────────────────

function useEnabledTrends(
  assetName: string | undefined,
  enabledKeys: string[],
  metricSloMap?: Map<string, string>,
  apiMetricMap?: Map<string, string>,
): Map<string, TrendPoint[]> {
  const { from, to } = useTimeRange()
  const dateRange = { from, ...(to ? { to } : {}) }
  const results = useQueries({
    queries: enabledKeys.map(key => {
      const sloName = metricSloMap?.get(key) ?? ''
      const apiMetric = apiMetricMap?.get(key) ?? key
      return {
        queryKey: evaluationKeys.trend(assetName ?? '', sloName, apiMetric, dateRange),
        queryFn: () => fetchTrend(assetName!, sloName, apiMetric, dateRange),
        enabled: !!assetName && !!sloName,
        staleTime: Infinity,
      }
    }),
  })

  const map = new Map<string, TrendPoint[]>()
  for (let i = 0; i < enabledKeys.length; i++) {
    const data = results[i]?.data
    if (data) map.set(enabledKeys[i], data)
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
  assetName: string | undefined
  metricSloMap?: Map<string, string>
  apiMetricMap?: Map<string, string>
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
  assetName,
  metricSloMap,
  apiMetricMap,
  dataKey,
  yAxisMax: yAxisMaxProp,
  stacked: stackedProp = false,
}: ChartSectionProps) {
  const [yMin, setYMin] = useState('')
  const [yMax, setYMax] = useState('')
  const [chartType, setChartType] = useState<ChartType>('line')

  const trendData = useEnabledTrends(assetName, [...enabled], metricSloMap, apiMetricMap)

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
      if (next.has(metric)) next.delete(metric); else next.add(metric)
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
    <div className="flex flex-col border-b border-border" style={{ minHeight: '50%' }}>
      {/* Section title bar */}
      <div className="px-4 py-2 border-b border-border shrink-0 flex items-center">
        <div className="shrink-0">
          <span className="text-sm font-semibold text-foreground">{title}</span>
          <span className="ml-2 text-xs text-muted-foreground">{subtitle}</span>
        </div>
        {/* All / None — centered between title and right controls */}
        <div className="flex-1 flex justify-center">
          <div className="flex items-center gap-1 text-xs">
            <Button
              variant="outline"
              size="xs"
              onClick={() => setEnabled(new Set(indicators.map(i => i.metric)))}
              className="text-muted-foreground hover:text-foreground"
            >
              All
            </Button>
            <Button
              variant="outline"
              size="xs"
              onClick={() => setEnabled(new Set())}
              className="text-muted-foreground hover:text-foreground"
            >
              None
            </Button>
          </div>
        </div>
        <div className="shrink-0 flex items-center gap-3">
          {/* Y-axis range */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <label className="flex items-center gap-1">
              Y <input
                type="number" value={yMin} onChange={e => setYMin(e.target.value)}
                placeholder="min"
                className="w-14 px-1 py-0.5 bg-surface-sunken border border-border rounded text-foreground text-xs"
              />
            </label>
            <label className="flex items-center gap-1">
              – <input
                type="number" value={yMax} onChange={e => setYMax(e.target.value)}
                placeholder="max"
                className="w-14 px-1 py-0.5 bg-surface-sunken border border-border rounded text-foreground text-xs"
              />
            </label>
          </div>
          {/* Line / Bar toggle */}
          <div className="flex border border-border rounded overflow-hidden text-xs">
            <Button
              variant="ghost"
              size="xs"
              onClick={() => setChartType('line')}
              className={`rounded-none ${chartType === 'line' ? 'bg-state-selected-bg text-foreground' : 'text-muted-foreground'}`}
            >
              Line
            </Button>
            <Button
              variant="ghost"
              size="xs"
              onClick={() => setChartType('bar')}
              className={`rounded-none ${chartType === 'bar' ? 'bg-state-selected-bg text-foreground' : 'text-muted-foreground'}`}
            >
              Bar
            </Button>
          </div>
        </div>
      </div>

      {/* Label panel + chart */}
      <div className="flex flex-1 min-h-0">
        <div className="shrink-0 border-r border-border p-3 overflow-y-auto" style={{ width: 280 }}>
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

  // Build indicator list — use composite key (slo\0metric) when multiple SLOs
  const multiSlo = (heatmapData?.groups.length ?? 0) > 1

  const allIndicators = useMemo(() => {
    if (heatmapData) {
      return heatmapData.groups.flatMap(g => {
        const sloLabel = g.slo_display_name ?? g.slo_name
        return g.metrics
          .filter(m => m.name !== '__score__')
          .map(m => ({
            metric: multiSlo ? `${g.slo_name}\0${m.name}` : m.name,
            display_name: multiSlo ? `${sloLabel} / ${m.display_name}` : m.display_name,
            tab_group: multiSlo ? sloLabel : undefined,
          }))
      })
    }
    if (latestDetail) {
      return latestDetail.indicator_results.map(r => ({
        metric: r.metric,
        display_name: r.display_name,
        tab_group: r.tab_group,
      }))
    }
    return []
  }, [heatmapData, latestDetail, multiSlo])

  // Map composite key → API metric name (strips the slo prefix)
  const apiMetricMap = useMemo((): Map<string, string> | undefined => {
    if (!multiSlo || !heatmapData) return undefined
    const m = new Map<string, string>()
    for (const g of heatmapData.groups) {
      for (const metric of g.metrics) m.set(`${g.slo_name}\0${metric.name}`, metric.name)
    }
    return m
  }, [heatmapData, multiSlo])

  // Map composite key → SLO name for trend queries
  const metricSloMap = useMemo((): Map<string, string> | undefined => {
    if (!heatmapData) return undefined
    const m = new Map<string, string>()
    for (const g of heatmapData.groups) {
      const prefix = multiSlo ? `${g.slo_name}\0` : ''
      for (const metric of g.metrics) m.set(`${prefix}${metric.name}`, g.slo_name)
    }
    return m.size > 0 ? m : undefined
  }, [heatmapData, multiSlo])

  const colorMap = useMemo(() => buildColorMap(allIndicators), [allIndicators])

  const backHref = assetName
    ? `/navigator?asset=${encodeURIComponent(assetName)}`
    : groupName
    ? `/navigator?group=${encodeURIComponent(groupName)}`
    : '/navigator'

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 49px)' }}>
      {/* Header bar */}
      <div className="px-6 py-3 border-b border-border flex items-center gap-3 shrink-0">
        <Link to={backHref} className="text-sm text-muted-foreground hover:text-foreground">
          ← Back
        </Link>
        <h1 className="text-lg font-semibold text-foreground">Metric Explorer</h1>
        {(groupName || assetName) && (
          <span className="text-sm text-muted-foreground">— {assetName ?? groupName}</span>
        )}
        <div className="ml-auto">
          <TimeRangePicker />
        </div>
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
          assetName={assetName}
          metricSloMap={metricSloMap}
          apiMetricMap={apiMetricMap}
          dataKey="value"
        />
        <ChartSection
          title="Scores"
          subtitle="Weighted contributions — stacks to 100% when all pass"
          indicators={allIndicators}
          colors={colorMap}
          enabled={scoresEnabled}
          setEnabled={setScoresEnabled}
          assetName={assetName}
          metricSloMap={metricSloMap}
          apiMetricMap={apiMetricMap}
          dataKey="score"
          yAxisMax={100}
          stacked
        />
      </div>
    </div>
  )
}
