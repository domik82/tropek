// ui/src/features/evaluations/components/EvaluationIndicatorSection.tsx
import { useRef, useCallback } from 'react'
import { useTabState } from '../hooks/useTabState'
import { SLIBreakdownTable } from './SLIBreakdownTable'
import { MetricTrendBlock } from './MetricTrendBlock'
import { EvaluationTabs, tabLabel } from './EvaluationTabs'
import { ChartViewControls } from '@/components/charts/ChartViewControls'
import { useChartPreferences } from '@/lib/chart-preferences-context'
import type { EvaluationDetail } from '../domain'

interface Props {
  evaluation: EvaluationDetail
  onMetricClick?: (metric: string) => void
  /** Fallback display name for the asset (when snapshot lacks display_name). */
  assetDisplayName?: string
  /** Human-readable SLO name passed through to each trend block. */
  sloDisplayName?: string
}

export function EvaluationIndicatorSection({ evaluation: ev, onMetricClick, assetDisplayName, sloDisplayName }: Props) {
  const { availableGroups, counts, activeTab, setActiveTab, tabIndicators } =
    useTabState(ev.indicators)

  const { columns } = useChartPreferences()

  const sliMetadata = ev.sliMetadata

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
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">SLI Breakdown</h2>
        </div>

        <EvaluationTabs
          availableGroups={availableGroups}
          allCount={ev.indicators.length}
          counts={counts}
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

        <SLIBreakdownTable
          indicators={tabIndicators}
          sliMetadata={sliMetadata}
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
        <div className="flex items-start justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            30-day trend for{' '}
            <strong className="text-foreground">{activeTab === 'all' ? 'All' : tabLabel(activeTab)}</strong>{' '}
            metrics on <strong className="text-foreground">{ev.assetSnapshot.displayName ?? assetDisplayName ?? ev.assetSnapshot.name}</strong>.
            Dot colour reflects each metric's own pass/warn/fail result.
          </p>
          <ChartViewControls />
        </div>
        <div className={columns === 1 ? 'grid grid-cols-1 gap-4' : 'grid grid-cols-1 xl:grid-cols-2 gap-4'}>
          {tabIndicators.map(ind => (
            <MetricTrendBlock
              key={ind.metric}
              assetName={ev.assetSnapshot.name}
              sloName={ev.sloName ?? ''}
              sloDisplayName={sloDisplayName}
              selectedEvalId={ev.id}
              indicator={ind}
              onScrollToTable={handleScrollToTable}
            />
          ))}
        </div>
      </div>
    </>
  )
}
