// ui/src/features/navigator/components/AssetPanelChartView.tsx
import { useState, useMemo, useCallback } from 'react'
import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
import { ViewToggle } from '@/components/charts/ViewToggle'
import type { ViewMode } from '@/components/charts/ViewToggle'
import { AssetScoreChart } from './AssetScoreChart'
import { MetricGroupFilter } from './MetricGroupFilter'
import type { Evaluation, Indicator } from '@/features/evaluations'
import type { GroupedMetricHeatmapResponseDto } from '../mappers'
import type { TimeSlotSelection } from './AssetHeatmap'

interface Props {
  assetName: string
  effectiveEvalId: string | undefined
  /** All slo_evaluation_ids in the currently selected column, one per SLO. */
  selectedColumnSloEvalIds: ReadonlySet<string>
  /**
   * period_start of the currently selected column — passed to trend charts so
   * SLOs without a cell in the clicked parent run can still fall back to
   * highlighting the matching timestamp.
   */
  selectedPeriodStart: string | undefined
  evals: Evaluation[]
  heatmapData: GroupedMetricHeatmapResponseDto | undefined
  onEvalSelect: (evalId: string) => void
  onSlotSelect: (slot: TimeSlotSelection) => void
  mode: ViewMode
  setMode: (m: ViewMode) => void
  explorerButton: React.ReactNode
}

export function AssetPanelChartView({
  assetName, effectiveEvalId, selectedColumnSloEvalIds, selectedPeriodStart,
  evals, heatmapData,
  onEvalSelect, onSlotSelect,
  mode, setMode, explorerButton,
}: Props) {
  const [metricGroupFilter, setMetricGroupFilter] = useState<string>('all')

  // One point per EvaluationRun using the composite (aggregated) score.
  // Without this, evals has N entries per run (one per SLO), producing N× too many points.
  const scoreChartEvals = useMemo((): Evaluation[] => {
    if (!heatmapData || heatmapData.composite.length === 0) return evals
    return heatmapData.composite.map(cell => {
      const rep = evals.find(e => e.period.from === cell.period_start)
      const outcome: Evaluation['outcome'] = (() => {
        const raw = cell.result
        if (raw === 'pass' || raw === 'warning' || raw === 'fail' || raw === 'error' || raw === 'invalidated') {
          return raw
        }
        return 'error'
      })()
      return {
        ...(rep ?? {} as Evaluation),
        id: rep?.id ?? cell.evaluation_id,
        period: { from: cell.period_start, to: rep?.period.to ?? cell.period_start },
        outcome,
        score: cell.score,
        invalidated: false,
      }
    })
  }, [heatmapData, evals])

  // period_start → all slo_evaluation_ids for that column (across all SLO groups)
  const slotEvalIds = useMemo((): Map<string, string[]> => {
    if (!heatmapData) return new Map()
    const m = new Map<string, string[]>()
    for (const group of heatmapData.groups) {
      for (const cell of group.cells) {
        const ids = m.get(cell.period_start) ?? []
        if (!ids.includes(cell.slo_evaluation_id)) ids.push(cell.slo_evaluation_id)
        m.set(cell.period_start, ids)
      }
    }
    return m
  }, [heatmapData])

  // period_start → parent evaluation_id (column key) for the first cell in that column
  const slotColumnEvalId = useMemo((): Map<string, string> => {
    if (!heatmapData) return new Map()
    const m = new Map<string, string>()
    for (const group of heatmapData.groups) {
      for (const cell of group.cells) {
        if (!m.has(cell.period_start)) m.set(cell.period_start, cell.evaluation_id)
      }
    }
    return m
  }, [heatmapData])

  // Reverse lookup: slo_evaluation_id → parent evaluation_id + period_start.
  // Lets a trend-chart click select the whole heatmap column (all sibling SLOs).
  const sloEvalIdToColumn = useMemo((): Map<string, { columnEvalId: string; periodStart: string }> => {
    if (!heatmapData) return new Map()
    const m = new Map<string, { columnEvalId: string; periodStart: string }>()
    for (const group of heatmapData.groups) {
      for (const cell of group.cells) {
        if (!m.has(cell.slo_evaluation_id)) {
          m.set(cell.slo_evaluation_id, {
            columnEvalId: cell.evaluation_id,
            periodStart: cell.period_start,
          })
        }
      }
    }
    return m
  }, [heatmapData])

  // Score chart click → full slot selection (all SLOs for that column)
  function handleScoreChartClick(evalId: string) {
    const entry = scoreChartEvals.find(e => e.id === evalId)
    if (!entry) { onEvalSelect(evalId); return }
    const evalIds = slotEvalIds.get(entry.period.from) ?? [evalId]
    const columnEvalId = slotColumnEvalId.get(entry.period.from)
    onSlotSelect({ periodStart: entry.period.from, evalIds, columnEvalId })
  }

  // Trend chart click → same full-slot selection so every SLO's chart and
  // the heatmap column all light up together, not just the clicked SLO.
  const handleTrendClick = useCallback((evalId: string) => {
    const col = sloEvalIdToColumn.get(evalId)
    if (!col) { onEvalSelect(evalId); return }
    const evalIds = slotEvalIds.get(col.periodStart) ?? [evalId]
    onSlotSelect({ periodStart: col.periodStart, evalIds, columnEvalId: col.columnEvalId })
  }, [sloEvalIdToColumn, slotEvalIds, onEvalSelect, onSlotSelect])

  const metricSloMap = useMemo((): Map<string, string> => {
    if (!heatmapData) return new Map()
    const m = new Map<string, string>()
    for (const g of heatmapData.groups) {
      for (const metric of g.metrics) m.set(metric.name, g.slo_name)
    }
    return m
  }, [heatmapData])

  const metricSloDisplayMap = useMemo((): Map<string, string> => {
    if (!heatmapData) return new Map()
    const m = new Map<string, string>()
    for (const g of heatmapData.groups) {
      const label = g.slo_display_name ?? g.slo_name
      for (const metric of g.metrics) m.set(metric.name, label)
    }
    return m
  }, [heatmapData])

  const allIndicators: Indicator[] = useMemo(() => {
    if (!heatmapData) return []
    const allMetrics = heatmapData.groups.flatMap(g => g.metrics)
    return allMetrics.filter(m => m.name !== '__score__').map(m => ({
      metric: m.name,
      displayName: m.display_name,
      tabGroup: null,
      value: 0,
      comparedValue: null,
      changeAbsolute: null,
      changeRelativePct: null,
      aggregation: 'avg',
      status: 'pass' as const,
      score: 0,
      weight: 1,
      keySli: false,
      passTargets: [],
      warningTargets: [],
    }))
  }, [heatmapData])

  const metricGroups = useMemo(
    () => Array.from(new Set(allIndicators.map(i => i.tabGroup).filter(Boolean) as string[])),
    [allIndicators],
  )

  const chartIndicators = metricGroupFilter === 'all'
    ? allIndicators
    : allIndicators.filter(i => i.tabGroup === metricGroupFilter)

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
      <div className="rounded-lg border border-border bg-surface-sunken p-4">
        <AssetScoreChart evaluations={scoreChartEvals} selectedEvalId={effectiveEvalId} onEvalSelect={handleScoreChartClick} />
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
              <MetricTrendBlock key={ind.metric} assetName={assetName} sloName={metricSloMap.get(ind.metric) ?? ''} sloDisplayName={metricSloDisplayMap.get(ind.metric)} selectedEvalId={effectiveEvalId} selectedEvalIds={selectedColumnSloEvalIds} selectedPeriodStart={selectedPeriodStart} indicator={ind} onEvalSelect={handleTrendClick} />
            ))}
          </div>
        </div>
      )}
    </>
  )
}
