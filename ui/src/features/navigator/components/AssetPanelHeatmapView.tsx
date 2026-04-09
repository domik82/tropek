// ui/src/features/navigator/components/AssetPanelHeatmapView.tsx
import { useRef, useCallback, useMemo } from 'react'
import { ChevronDown, ChevronRight, Grid3X3 } from 'lucide-react'
import { AssetHeatmap } from './AssetHeatmap'
import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
import { SLIBreakdownGrouped } from '@/features/evaluations/components/SLIBreakdownGrouped'
import type { SloBreakdownGroup } from '@/features/evaluations/components/SLIBreakdownGrouped'
import { ViewToggle } from '@/components/charts/ViewToggle'
import type { ViewMode } from '@/components/charts/ViewToggle'
import type { TimeSlotSelection } from './AssetHeatmap'
import type { MetricHeatmapResponse } from '../types'
import type { SliMetadata } from '@/features/evaluations/types'

interface Props {
  assetName: string
  heatmapData: MetricHeatmapResponse | undefined
  selectedColumnEvalId: string | undefined
  effectiveEvalId: string | undefined
  /** All slo_evaluation_ids in the currently selected column, one per SLO. */
  selectedColumnSloEvalIds: ReadonlySet<string>
  notedSlots: Map<string, { evalId: string; count: number }>
  onEvalSelect: (evalId: string) => void
  onSlotSelect?: (slot: TimeSlotSelection) => void
  mode: ViewMode
  setMode: (m: ViewMode) => void
  explorerButton: React.ReactNode
  sloExpandState: Map<string, boolean>
  onSloToggle: (sloName: string) => void
}

export function AssetPanelHeatmapView({
  assetName, heatmapData, selectedColumnEvalId, effectiveEvalId,
  selectedColumnSloEvalIds, notedSlots,
  onEvalSelect, onSlotSelect, mode, setMode, explorerButton,
  sloExpandState, onSloToggle,
}: Props) {
  const sliTableRef = useRef<HTMLDivElement>(null)
  const heatmapRef = useRef<HTMLDivElement>(null)

  // Scope-qualified id builders. Same metric may appear in multiple SLOs
  // (e.g. "http.response_time" under a latency SLO and a throughput SLO),
  // so DOM ids must include the SLO name to avoid getElementById collisions
  // that silently scroll to the first match (= top of the section).
  const rowIdPrefixFor = useCallback((sloName: string) => `row-${sloName}::`, [])
  const trendIdFor = useCallback(
    (sloName: string, metric: string) => `trend-${sloName}::${metric}`,
    [],
  )

  const handleScrollToHeatmap = useCallback(() => {
    heatmapRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  // Scroll to a specific SLI row, expanding the owning SLO group first.
  // Falls back to the section root when the row id is missing (shouldn't
  // happen in practice — defensive only).
  const scrollToRow = useCallback((sloName: string, metric: string) => {
    const expanded = sloExpandState.get(sloName) ?? false
    if (!expanded) onSloToggle(sloName)
    requestAnimationFrame(() => {
      const el = document.getElementById(`${rowIdPrefixFor(sloName)}${metric}`)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      else sliTableRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }, [sloExpandState, onSloToggle, rowIdPrefixFor])

  // Scroll to a specific trend chart, expanding the owning SLO group first.
  const scrollToTrend = useCallback((sloName: string, metric: string) => {
    const expanded = sloExpandState.get(sloName) ?? false
    if (!expanded) onSloToggle(sloName)
    requestAnimationFrame(() => {
      const el = document.getElementById(trendIdFor(sloName, metric))
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }, [sloExpandState, onSloToggle, trendIdFor])

  const handleHeatmapMetricClick = useCallback(
    (metricName: string, sloName: string) => scrollToRow(sloName, metricName),
    [scrollToRow],
  )

  // Reverse lookup: slo_evaluation_id → parent column + period_start. Used to
  // promote a trend-dot click into a full-column selection so every SLO's
  // trend chart and the heatmap column light up together.
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

  const columnSloEvalIdsByColumn = useMemo((): Map<string, string[]> => {
    if (!heatmapData) return new Map()
    const m = new Map<string, string[]>()
    for (const group of heatmapData.groups) {
      for (const cell of group.cells) {
        const ids = m.get(cell.evaluation_id) ?? []
        if (!ids.includes(cell.slo_evaluation_id)) ids.push(cell.slo_evaluation_id)
        m.set(cell.evaluation_id, ids)
      }
    }
    return m
  }, [heatmapData])

  const handleTrendClick = useCallback((evalId: string) => {
    const col = sloEvalIdToColumn.get(evalId)
    if (!col || !onSlotSelect) { onEvalSelect(evalId); return }
    const evalIds = columnSloEvalIdsByColumn.get(col.columnEvalId) ?? [evalId]
    onSlotSelect({ periodStart: col.periodStart, evalIds, columnEvalId: col.columnEvalId })
  }, [sloEvalIdToColumn, columnSloEvalIdsByColumn, onEvalSelect, onSlotSelect])

  // Build SloBreakdownGroup[] directly from enriched heatmap cells — no detail fetch needed.
  const breakdownGroups = useMemo((): SloBreakdownGroup[] => {
    if (!heatmapData || !selectedColumnEvalId) return []
    return heatmapData.groups.map(g => {
      const summary = g.summary.find(s => s.evaluation_id === selectedColumnEvalId)
      const indicators = g.cells
        .filter(c => c.evaluation_id === selectedColumnEvalId)
        .map(c => ({
          metric: c.metric,
          display_name: c.display_name,
          value: c.value ?? 0,
          compared_value: c.compared_value ?? null,
          change_absolute: null,
          change_relative_pct: c.change_relative_pct ?? null,
          aggregation: c.aggregation ?? '',
          status: c.result as 'pass' | 'warning' | 'fail',
          score: c.score,
          weight: c.weight ?? 1,
          key_sli: c.key_sli ?? false,
          pass_targets: c.pass_targets ?? null,
          warning_targets: c.warning_targets ?? null,
          tab_group: c.tab_group ?? undefined,
        }))
      const result = summary?.invalidated
        ? 'invalidated'
        : (summary?.result ?? 'none')
      return {
        slo_name: g.slo_name,
        slo_display_name: g.slo_display_name,
        indicators,
        score: Math.round(summary?.score ?? 0),
        result,
        achieved_points: indicators.reduce((sum, ind) => sum + ind.score, 0),
        total_points: indicators.reduce((sum, ind) => sum + ind.weight, 0),
      }
    })
  }, [heatmapData, selectedColumnEvalId])

  // Build sliMetadata from heatmap summary cells
  const sliMetadata = useMemo((): Record<string, SliMetadata> | undefined => {
    if (!heatmapData || !selectedColumnEvalId) return undefined
    const meta: Record<string, SliMetadata> = {}
    for (const g of heatmapData.groups) {
      const summary = g.summary.find(s => s.evaluation_id === selectedColumnEvalId)
      if (summary?.sli_metadata) Object.assign(meta, summary.sli_metadata)
    }
    return Object.keys(meta).length > 0 ? meta : undefined
  }, [heatmapData, selectedColumnEvalId])

  // Trend chart sections use all breakdown groups — headers always visible
  const trendGroups = breakdownGroups

  const resultColour = (result: string) =>
    result === 'pass' ? 'text-pass' :
    result === 'warning' ? 'text-warning' :
    result === 'fail' ? 'text-fail' :
    'text-muted-foreground'

  return (
    <>
      {/* Metric Heatmap with view toggle */}
      {heatmapData && (
        <div ref={heatmapRef} className="rounded-lg border border-border bg-surface-sunken p-4 scroll-mt-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Metric Heatmap</h2>
            <div className="flex items-center gap-3">
              <ViewToggle mode={mode} setMode={setMode} />
              {explorerButton}
            </div>
          </div>
          <AssetHeatmap
            data={heatmapData}
            selectedEvalId={effectiveEvalId}
            onEvalSelect={onEvalSelect}
            onSlotSelect={onSlotSelect}
            onMetricClick={handleHeatmapMetricClick}
            notedSlots={notedSlots}
            expandState={sloExpandState}
            onSloToggle={onSloToggle}
          />
        </div>
      )}

      {/* SLI Breakdown — grouped by SLO */}
      {breakdownGroups.length > 0 && (
        <div ref={sliTableRef} className="space-y-0 scroll-mt-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">SLI Breakdown</h2>
          </div>
          <SLIBreakdownGrouped
            groups={breakdownGroups}
            expandState={sloExpandState}
            onToggle={onSloToggle}
            sliMetadata={sliMetadata}
            onScrollToHeatmap={handleScrollToHeatmap}
            onIndicatorClick={(metric, sloName) => scrollToTrend(sloName, metric)}
            rowIdPrefixBuilder={rowIdPrefixFor}
          />
        </div>
      )}

      {/* Metric Trend Charts — SLO-grouped */}
      {trendGroups.length > 0 && (
        <div className="space-y-4">
          <p className="text-xs text-muted-foreground">
            30-day trend for <strong className="text-foreground">{assetName}</strong>.
          </p>
          {trendGroups.map(g => {
            const expanded = sloExpandState.get(g.slo_name) ?? false
            const label = g.slo_display_name ?? g.slo_name
            return (
              <div key={g.slo_name}>
                <button
                  type="button"
                  onClick={() => onSloToggle(g.slo_name)}
                  className="relative w-full flex items-center gap-2 px-3 py-2 rounded-t border border-border bg-surface-sunken hover:bg-state-hover-bg transition-colors text-left"
                >
                  {expanded ? (
                    <ChevronDown size={14} className="shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronRight size={14} className="shrink-0 text-muted-foreground" />
                  )}
                  <span
                    className="text-sm font-semibold truncate"
                    style={{ color: '#58a6ff' }}
                  >
                    {label}
                  </span>
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={e => { e.stopPropagation(); handleScrollToHeatmap() }}
                    onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); handleScrollToHeatmap() } }}
                    className="absolute left-1/2 -translate-x-1/2 inset-y-0 flex items-center px-6 text-pass/60 hover:text-pass transition-colors"
                    title="Go to heatmap"
                    aria-label="Go to heatmap"
                  >
                    <Grid3X3 className="size-5" />
                  </span>
                  <span className="flex-1" />
                  {g.result !== 'none' && (
                    <span className={`text-xs font-bold uppercase ${resultColour(g.result)}`}>
                      {g.result}
                    </span>
                  )}
                </button>
                {g.indicators.length > 0 && expanded && (
                  <div className="border border-t-0 border-border rounded-b p-4">
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                      {g.indicators.map(ind => (
                        <MetricTrendBlock
                          key={ind.metric}
                          assetName={assetName}
                          sloName={g.slo_name}
                          sloDisplayName={g.slo_display_name}
                          selectedEvalId={effectiveEvalId}
                          selectedEvalIds={selectedColumnSloEvalIds}
                          indicator={ind}
                          onEvalSelect={handleTrendClick}
                          blockId={trendIdFor(g.slo_name, ind.metric)}
                          onScrollToTable={() => scrollToRow(g.slo_name, ind.metric)}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </>
  )
}
