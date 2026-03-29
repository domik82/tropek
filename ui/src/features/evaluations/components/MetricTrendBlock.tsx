// src/features/evaluations/components/MetricTrendBlock.tsx
import ReactECharts from 'echarts-for-react'
import { useCallback } from 'react'
import { useTrend } from '../hooks'
import { STATUS_TEXT } from '@/lib/status'
import { useChartAreaClick } from '@/lib/useChartAreaClick'
import { useMetricTrendState, isRelativeCriteria } from '../hooks/useMetricTrendState'
import type { IndicatorResult } from '../types'

interface Props {
  evalId: string
  indicator: IndicatorResult
  onEvalSelect?: (evalId: string) => void
  onScrollToTable?: () => void
}

function defaultScrollToTable() {
  document.getElementById('sli-table')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export function MetricTrendBlock({ evalId, indicator, onEvalSelect, onScrollToTable }: Props) {
  const { data: trend, isLoading } = useTrend(evalId, indicator.metric)

  const handleClickIndex = useCallback(
    (idx: number) => {
      const pt = (trend ?? [])[idx]
      if (pt && onEvalSelect) onEvalSelect(pt.eval_id)
    },
    [trend, onEvalSelect],
  )

  const { chartRef, onContainerClick } = useChartAreaClick(
    onEvalSelect ? handleClickIndex : undefined,
    (trend ?? []).length,
  )

  const {
    yMin, yMax, setYMin, setYMax,
    showPass, showWarn, togglePass, toggleWarn,
    chartOption,
    passTarget, warnTarget, passCriteria, warnCriteria,
  } = useMetricTrendState(trend, evalId, indicator, onEvalSelect)

  return (
    <div id={`trend-${indicator.metric}`} className="bg-card border border-border rounded-xl p-4 scroll-mt-4">
      <div className="flex items-center justify-between mb-1">
        <span className={`text-xs font-semibold uppercase ${STATUS_TEXT[indicator.status] ?? 'text-muted-foreground'}`}>
          {indicator.status}
        </span>
        <button
          onClick={onScrollToTable ?? defaultScrollToTable}
          className="text-sm font-medium text-foreground hover:text-link-hover transition-colors"
          title="Back to SLI table"
          aria-label="Back to SLI table"
        >
          ↑ top
        </button>
      </div>

      {isLoading ? (
        <div>
          <div className="text-xs text-muted-foreground mb-2">{indicator.display_name}</div>
          <div className="h-[200px] flex items-center justify-center text-muted-foreground/60 text-xs">loading…</div>
        </div>
      ) : (
        <div>
          <div className="flex items-center gap-3 mb-1">
            <span className="text-xs font-semibold text-foreground" title={indicator.metric}>
              {indicator.display_name || indicator.metric}
            </span>
            <div className="flex items-center gap-1 ml-auto text-xs">
              {(passTarget?.target_value != null || isRelativeCriteria(passCriteria)) && (
                <button
                  onClick={togglePass}
                  className={`px-2 py-0.5 rounded border text-[10px] font-medium transition-colors ${
                    showPass
                      ? 'border-pass/50 text-pass bg-pass/10'
                      : 'border-border text-muted-foreground/60 bg-transparent'
                  }`}
                >
                  pass {passCriteria ?? passTarget?.target_value}
                </button>
              )}
              {(warnTarget?.target_value != null || isRelativeCriteria(warnCriteria)) && (
                <button
                  onClick={toggleWarn}
                  className={`px-2 py-0.5 rounded border text-[10px] font-medium transition-colors ${
                    showWarn
                      ? 'border-warning/50 text-warning bg-warning/10'
                      : 'border-border text-muted-foreground/60 bg-transparent'
                  }`}
                >
                  warn {warnCriteria ?? warnTarget?.target_value}
                </button>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <label className="flex items-center gap-1">
                Y <input
                  type="number" value={yMin} onChange={e => setYMin(e.target.value)}
                  placeholder="min" className="w-14 px-1 py-0.5 bg-surface-sunken border border-border rounded text-foreground"
                />
              </label>
              <label className="flex items-center gap-1">
                – <input
                  type="number" value={yMax} onChange={e => setYMax(e.target.value)}
                  placeholder="max" className="w-14 px-1 py-0.5 bg-surface-sunken border border-border rounded text-foreground"
                />
              </label>
            </div>
          </div>
          <div onClick={onContainerClick} style={{ cursor: onEvalSelect ? 'crosshair' : undefined }}>
            <ReactECharts
              ref={chartRef}
              option={chartOption}
              style={{ height: 200 }}
              opts={{ renderer: 'svg' }}
              notMerge
            />
          </div>
        </div>
      )}
    </div>
  )
}
