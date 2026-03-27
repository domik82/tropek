// ui/src/features/evaluations/components/EvaluationIndicatorSection.tsx
import { useRef, useCallback } from 'react'
import { useTabState } from '../hooks/useTabState'
import { SLIBreakdownTable } from './SLIBreakdownTable'
import { MetricTrendBlock } from './MetricTrendBlock'
import { EvaluationTabs, tabLabel } from './EvaluationTabs'
import type { EvaluationDetail } from '../types'

interface Props {
  evaluation: EvaluationDetail
  onMetricClick?: (metric: string) => void
  /** Fallback display name for the asset (when snapshot lacks display_name). */
  assetDisplayName?: string
}

export function EvaluationIndicatorSection({ evaluation: ev, onMetricClick, assetDisplayName }: Props) {
  const { availableGroups, counts, activeTab, setActiveTab, tabIndicators } =
    useTabState(ev.indicator_results)

  const sliTableRef = useRef<HTMLDivElement>(null)

  const scrollToTrend = useCallback((metric: string) => {
    // Trend blocks are rendered as siblings — use id-based scroll
    // since refs cannot span dynamic list items
    const el = document.getElementById(`trend-${metric}`)
    if (el) {
      setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
    }
  }, [])

  const handleScrollToTable = useCallback(() => {
    sliTableRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  return (
    <>
      {/* SLI breakdown - tab bar + table */}
      <div ref={sliTableRef} id="sli-table" className="space-y-0 scroll-mt-4">
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
            if (onMetricClick) {
              onMetricClick(metric)
            } else {
              scrollToTrend(metric)
            }
          }}
        />
      </div>

      {/* Trend charts */}
      <div className="space-y-4">
        <p className="text-xs text-slate-500">
          30-day trend for{' '}
          <strong className="text-slate-300">{activeTab === 'all' ? 'All' : tabLabel(activeTab)}</strong>{' '}
          metrics on <strong className="text-slate-300">{ev.asset_snapshot.display_name ?? assetDisplayName ?? ev.asset_snapshot.name}</strong>.
          Dot colour reflects each metric's own pass/warn/fail result.
        </p>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {tabIndicators.map(ind => (
            <MetricTrendBlock
              key={ind.metric}
              evalId={ev.id}
              indicator={ind}
              onScrollToTable={handleScrollToTable}
            />
          ))}
        </div>
      </div>
    </>
  )
}
