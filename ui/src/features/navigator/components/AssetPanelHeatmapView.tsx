// ui/src/features/navigator/components/AssetPanelHeatmapView.tsx
import { useRef, useCallback, useMemo } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { AssetHeatmap } from './AssetHeatmap'
import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
import { SLIBreakdownGrouped } from '@/features/evaluations/components/SLIBreakdownGrouped'
import type { SloBreakdownGroup } from '@/features/evaluations/components/SLIBreakdownGrouped'
import { ViewToggle } from '@/components/charts/ViewToggle'
import type { ViewMode } from '@/components/charts/ViewToggle'
import type { TimeSlotSelection } from './AssetHeatmap'
import type { MetricHeatmapResponse } from '../types'
import type { EvaluationDetail, SliMetadata } from '@/features/evaluations/types'

interface Props {
  assetName: string
  heatmapData: MetricHeatmapResponse | undefined
  allSlotEvals: EvaluationDetail[]
  effectiveEvalId: string | undefined
  notedSlots: Map<string, { evalId: string; count: number }>
  onEvalSelect: (evalId: string) => void
  onSlotSelect?: (slot: TimeSlotSelection) => void
  sliMetadata?: Record<string, SliMetadata>
  mode: ViewMode
  setMode: (m: ViewMode) => void
  explorerButton: React.ReactNode
  sloExpandState: Map<string, boolean>
  onSloToggle: (sloName: string) => void
  metricEvalMap?: Map<string, string>
}

export function AssetPanelHeatmapView({
  assetName, heatmapData, allSlotEvals, effectiveEvalId, notedSlots,
  onEvalSelect, onSlotSelect, mode, setMode, explorerButton,
  sliMetadata, metricEvalMap, sloExpandState, onSloToggle,
}: Props) {
  const sliTableRef = useRef<HTMLDivElement>(null)

  const handleScrollToTable = useCallback(() => {
    sliTableRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  // Build SloBreakdownGroup[] from heatmap groups joined with slot evals
  const breakdownGroups = useMemo((): SloBreakdownGroup[] => {
    if (!heatmapData) return []
    return heatmapData.groups.flatMap(g => {
      const sloEval = allSlotEvals.find(e => e.slo_name === g.slo_name)
      const indicators = sloEval?.indicator_results ?? []
      if (indicators.length === 0) return []
      const result = sloEval
        ? (sloEval.invalidated ? 'invalidated' : sloEval.result ?? 'none')
        : 'none'
      const score = Math.round(sloEval?.score ?? 0)
      const achieved_points = indicators.reduce((sum, ind) => sum + ind.score, 0)
      const total_points = indicators.reduce((sum, ind) => sum + ind.weight, 0)
      return [{
        slo_name: g.slo_name,
        slo_display_name: g.slo_display_name,
        indicators,
        score,
        result,
        achieved_points,
        total_points,
      }]
    })
  }, [heatmapData, allSlotEvals])

  // Build groups for trend chart sections
  const trendGroups = useMemo((): SloBreakdownGroup[] => {
    return breakdownGroups.filter(g => g.indicators.length > 0)
  }, [breakdownGroups])

  const resultColour = (result: string) =>
    result === 'pass' ? 'text-pass' :
    result === 'warning' ? 'text-warning' :
    result === 'fail' ? 'text-fail' :
    'text-muted-foreground'

  return (
    <>
      {/* Metric Heatmap with view toggle */}
      {heatmapData && (
        <div className="rounded-lg border border-border bg-surface-sunken p-4">
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
            onIndicatorClick={(metric) => {
              const el = document.getElementById(`trend-${metric}`)
              if (el) setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
            }}
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
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-t border border-border bg-surface-sunken hover:bg-state-hover-bg transition-colors text-left"
                >
                  {expanded ? (
                    <ChevronDown size={14} className="shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronRight size={14} className="shrink-0 text-muted-foreground" />
                  )}
                  <span
                    className="text-sm font-semibold flex-1 truncate"
                    style={{ color: '#58a6ff' }}
                  >
                    {label}
                  </span>
                  {g.result !== 'none' && (
                    <span className={`text-xs font-bold uppercase ${resultColour(g.result)}`}>
                      {g.result}
                    </span>
                  )}
                </button>
                {expanded && g.indicators.length > 0 && (
                  <div className="border border-t-0 border-border rounded-b p-4">
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                      {g.indicators.map(ind => (
                        <MetricTrendBlock
                          key={ind.metric}
                          evalId={metricEvalMap?.get(ind.metric) ?? effectiveEvalId ?? ''}
                          indicator={ind}
                          onEvalSelect={onEvalSelect}
                          onScrollToTable={handleScrollToTable}
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
