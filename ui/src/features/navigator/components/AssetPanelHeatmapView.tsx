// ui/src/features/navigator/components/AssetPanelHeatmapView.tsx
import { useRef, useCallback } from 'react'
import { AssetHeatmap } from './AssetHeatmap'
import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
import { SLIBreakdownTable } from '@/features/evaluations/components/SLIBreakdownTable'
import { EvaluationTabs, tabLabel } from '@/features/evaluations/components/EvaluationTabs'
import { ViewToggle } from '@/components/charts/ViewToggle'
import type { ViewMode } from '@/components/charts/ViewToggle'
import type { MetricHeatmapResponse } from '../types'
import type { EvaluationDetail, IndicatorResult } from '@/features/evaluations/types'

interface Props {
  assetName: string
  heatmapData: MetricHeatmapResponse | undefined
  ev: EvaluationDetail | undefined
  effectiveEvalId: string | undefined
  notedSlots: Map<string, { evalId: string; count: number }>
  onEvalSelect: (evalId: string) => void
  mode: ViewMode
  setMode: (m: ViewMode) => void
  explorerButton: React.ReactNode
  // Tab state
  availableGroups: string[]
  counts: Record<string, number>
  activeTab: string
  setActiveTab: (tab: string) => void
  tabIndicators: IndicatorResult[]
}

export function AssetPanelHeatmapView({
  assetName, heatmapData, ev, effectiveEvalId, notedSlots,
  onEvalSelect, mode, setMode, explorerButton,
  availableGroups, counts, activeTab, setActiveTab, tabIndicators,
}: Props) {
  const sliTableRef = useRef<HTMLDivElement>(null)

  const handleScrollToTable = useCallback(() => {
    sliTableRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  return (
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
            onEvalSelect={onEvalSelect}
            notedSlots={notedSlots}
          />
        </div>
      )}

      {/* SLI Breakdown */}
      {ev && (
        <div ref={sliTableRef} className="space-y-0 scroll-mt-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">SLI Breakdown</h2>
          </div>
          <EvaluationTabs
            availableGroups={availableGroups}
            allCount={ev.indicator_results.length}
            counts={counts}
            activeTab={activeTab}
            onTabChange={setActiveTab}
          />
          <SLIBreakdownTable
            indicators={tabIndicators}
            onIndicatorClick={(metric, tabGroup) => {
              if (activeTab !== 'all') setActiveTab(tabGroup)
              // Trend blocks are dynamic list items — use id-based scroll
              const el = document.getElementById(`trend-${metric}`)
              if (el) setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
            }}
          />
        </div>
      )}

      {/* Metric Trend Charts */}
      {effectiveEvalId && tabIndicators.length > 0 && (
        <div className="space-y-4">
          <p className="text-xs text-slate-500">
            30-day trend for{' '}
            <strong className="text-slate-300">{activeTab === 'all' ? 'All' : tabLabel(activeTab)}</strong>{' '}
            metrics on <strong className="text-slate-300">{assetName}</strong>.
          </p>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {tabIndicators.map(ind => (
              <MetricTrendBlock
                key={ind.metric}
                evalId={effectiveEvalId}
                indicator={ind}
                onEvalSelect={onEvalSelect}
                onScrollToTable={handleScrollToTable}
              />
            ))}
          </div>
        </div>
      )}
    </>
  )
}
