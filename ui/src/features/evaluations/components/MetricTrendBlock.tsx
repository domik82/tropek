// src/features/evaluations/components/MetricTrendBlock.tsx
import ReactECharts from 'echarts-for-react'
import { useCallback } from 'react'
import { Sheet } from 'lucide-react'
import { useTrend } from '../hooks'
import { STATUS_TEXT } from '@/lib/status'
import { useChartAreaClick } from '@/lib/useChartAreaClick'
import { useMetricTrendState, isRelativeCriteria } from '../hooks/useMetricTrendState'
import type { IndicatorResult } from '../types'

interface Props {
  assetName: string
  sloName: string
  /** Human-readable SLO label shown next to the metric title. Falls back to sloName. */
  sloDisplayName?: string
  /** Eval ID to highlight on the trend line (white ring + larger dot). */
  selectedEvalId?: string
  /**
   * Additional eval ids considered "selected" when highlighting trend dots.
   * Use this when the same column spans multiple SLOs (each with its own
   * slo_evaluation_id) so every SLO's chart highlights the same column.
   */
  selectedEvalIds?: ReadonlySet<string>
  indicator: IndicatorResult
  onEvalSelect?: (evalId: string) => void
  onScrollToTable?: () => void
  /**
   * DOM id for the trend block wrapper. Defaults to `trend-${indicator.metric}`.
   * Callers that render multiple trend blocks for the same metric (e.g. the
   * navigator, which groups by SLO) must pass a scope-qualified id to avoid
   * `getElementById` collisions that land scroll targets on the wrong block.
   */
  blockId?: string
}

function defaultScrollToTable() {
  document.getElementById('sli-table')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export function MetricTrendBlock({ assetName, sloName, sloDisplayName, selectedEvalId, selectedEvalIds, indicator, onEvalSelect, onScrollToTable, blockId }: Props) {
  const sloLabel = sloDisplayName ?? (sloName || null)
  const { data: trend, isLoading } = useTrend(assetName, sloName, indicator.metric)

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
  } = useMetricTrendState(trend, selectedEvalId ?? '', indicator, onEvalSelect, selectedEvalIds)

  return (
    <div id={blockId ?? `trend-${indicator.metric}`} className="bg-card border border-border rounded-xl p-4 scroll-mt-4">
      <div className="relative flex items-center justify-between mb-1 gap-2">
        <span className={`text-xs font-semibold uppercase ${STATUS_TEXT[indicator.status] ?? 'text-muted-foreground'}`}>
          {indicator.status}
        </span>
        {sloLabel && (
          <span
            className="absolute left-1/2 -translate-x-1/2 text-xs font-semibold uppercase tracking-wide truncate max-w-[60%] text-center"
            style={{ color: '#58a6ff' }}
            title={sloName ? `SLO: ${sloName}` : undefined}
          >
            {sloLabel}
          </span>
        )}
        <button
          onClick={onScrollToTable ?? defaultScrollToTable}
          className="text-[#58a6ff]/60 hover:text-[#58a6ff] transition-colors"
          title="Go to SLI table"
          aria-label="Go to SLI table"
        >
          <Sheet className="size-5" />
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
            <span className="text-xs font-semibold text-foreground truncate" title={indicator.metric}>
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
