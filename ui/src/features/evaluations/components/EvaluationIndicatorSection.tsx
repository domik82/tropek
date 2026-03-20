// ui/src/features/evaluations/components/EvaluationIndicatorSection.tsx
import { useTabState } from '../hooks/useTabState'
import { SLIBreakdownTable } from './SLIBreakdownTable'
import { MetricTrendBlock } from './MetricTrendBlock'
import { EvaluationTabs, tabLabel } from './EvaluationTabs'
import type { EvaluationDetail } from '../types'

interface Props {
  evaluation: EvaluationDetail
  onMetricClick?: (metric: string) => void
}

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export function EvaluationIndicatorSection({ evaluation: ev, onMetricClick }: Props) {
  const { availableGroups, counts, activeTab, setActiveTab, tabIndicators } =
    useTabState(ev.indicator_results)

  return (
    <>
      {/* SLI breakdown - tab bar + table */}
      <div id="sli-table" className="space-y-0 scroll-mt-4">
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
              setTimeout(() => scrollTo(`trend-${metric}`), 50)
            }
          }}
        />
      </div>

      {/* Trend charts */}
      <div className="space-y-4">
        <p className="text-xs text-slate-500">
          30-day trend for{' '}
          <strong className="text-slate-300">{activeTab === 'all' ? 'All' : tabLabel(activeTab)}</strong>{' '}
          metrics on <strong className="text-slate-300">{ev.asset_snapshot.name}</strong>.
          Dot colour reflects each metric's own pass/warn/fail result.
        </p>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {tabIndicators.map(ind => (
            <MetricTrendBlock key={ind.metric} evalId={ev.id} indicator={ind} />
          ))}
        </div>
      </div>
    </>
  )
}
