// src/features/evaluations/components/MetricTrendBlock.tsx
import ReactECharts from 'echarts-for-react'
import { useCallback, useState, useRef, useEffect } from 'react'
import { Sheet, Tags } from 'lucide-react'
import { useTrend } from '../hooks'
import { STATUS_TEXT } from '@/lib/status'
import { useChartAreaClick } from '@/lib/useChartAreaClick'
import { useMetricTrendState } from '../hooks/useMetricTrendState'
import type { IndicatorResult } from '../types'

interface Props {
  assetName: string
  sloName: string
  sloDisplayName?: string
  selectedEvalId?: string
  selectedEvalIds?: ReadonlySet<string>
  selectedPeriodStart?: string
  indicator: IndicatorResult
  onEvalSelect?: (evalId: string) => void
  onScrollToTable?: () => void
  blockId?: string
}

function defaultScrollToTable() {
  document.getElementById('sli-table')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function TargetDropdown({ targets }: { targets: ReturnType<typeof useMetricTrendState>['targets'] }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  if (targets.length === 0) return null

  const activeCount = targets.filter(t => t.visible).length

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        className={`p-1 rounded border transition-colors ${
          activeCount > 0
            ? 'border-primary/40 text-primary'
            : 'border-border text-muted-foreground/60'
        }`}
        title="Toggle threshold lines"
      >
        <Tags className="size-3.5" />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 bg-popover border border-border rounded-lg shadow-lg py-1 min-w-[180px]">
          {targets.map(t => {
            const dotColor = t.level === 'pass'
              ? 'bg-pass'
              : t.level === 'warn'
                ? 'bg-warning'
                : 'bg-[#58a6ff]'
            return (
              <label
                key={t.key}
                className="flex items-center gap-2 px-3 py-1.5 hover:bg-muted/50 cursor-pointer text-xs"
              >
                <input
                  type="checkbox"
                  checked={t.visible}
                  onChange={t.toggle}
                  className="rounded border-border"
                />
                <span className={`size-2 rounded-full ${dotColor} shrink-0`} />
                <span className="text-foreground font-mono">{t.criteria}</span>
              </label>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function MetricTrendBlock({
  assetName,
  sloName,
  sloDisplayName,
  selectedEvalId,
  selectedEvalIds,
  selectedPeriodStart,
  indicator,
  onEvalSelect,
  onScrollToTable,
  blockId,
}: Props) {
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
    targets,
    chartOption,
  } = useMetricTrendState(trend, selectedEvalId ?? '', indicator, onEvalSelect, selectedEvalIds, selectedPeriodStart)

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
              <TargetDropdown targets={targets} />
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
