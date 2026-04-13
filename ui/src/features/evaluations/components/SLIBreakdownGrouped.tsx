// ui/src/features/evaluations/components/SLIBreakdownGrouped.tsx
import { useState, useCallback } from 'react'
import { ChevronDown, ChevronRight, Copy, Check, Grid3X3 } from 'lucide-react'
import { SLIBreakdownTable } from './SLIBreakdownTable'
import type { Indicator, SliMetadata } from '../domain'

export interface SloBreakdownGroup {
  slo_name: string
  slo_display_name?: string
  indicators: Indicator[]
  score: number           // 0–100
  result: string
  achieved_points: number
  total_points: number
  slo_version?: number | null
  sli_version?: number | null
}

function CopySloButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }, [text])

  return (
    <span
      role="button"
      tabIndex={0}
      onClick={handleCopy}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') handleCopy(e as unknown as React.MouseEvent) }}
      className="text-muted-foreground/60 hover:text-link-hover transition-colors shrink-0"
      title="Copy SLO name"
      aria-label={`Copy ${text}`}
    >
      {copied
        ? <Check className="size-5 text-pass" />
        : <Copy className="size-5" />
      }
    </span>
  )
}

interface Props {
  groups: SloBreakdownGroup[]
  expandState: Map<string, boolean>
  onToggle: (sloName: string) => void
  sliMetadata?: Record<string, SliMetadata>
  onIndicatorClick?: (metric: string, sloName: string) => void
  onScrollToHeatmap?: () => void
  /**
   * Builder for the DOM id prefix applied to each SLO group's rows.
   * Receives the SLO name and must return a string suffixed so that the
   * full row id is `${builder(sloName)}${metric}`. When omitted, rows get
   * no id (used by the eval detail page, which has a single flat trend list).
   */
  rowIdPrefixBuilder?: (sloName: string) => string
}

export function SLIBreakdownGrouped({
  groups,
  expandState,
  onToggle,
  sliMetadata,
  onIndicatorClick,
  onScrollToHeatmap,
  rowIdPrefixBuilder,
}: Props) {
  return (
    <div className="space-y-1">
      {groups.map(g => {
        const expanded = expandState.get(g.slo_name) ?? false
        const label = g.slo_display_name ?? g.slo_name
        const resultColour =
          g.result === 'pass' ? 'text-pass' :
          g.result === 'warning' ? 'text-warning' :
          g.result === 'fail' ? 'text-fail' :
          'text-muted-foreground'

        return (
          <div key={g.slo_name}>
            {/* SLO section header */}
            <button
              type="button"
              onClick={() => onToggle(g.slo_name)}
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
              <CopySloButton text={g.slo_name} />
              {(g.slo_version != null || g.sli_version != null) && (
                <span className="text-xs text-muted-foreground/70 tabular-nums shrink-0">
                  [
                  {g.slo_version != null && `SLO v${g.slo_version}`}
                  {g.slo_version != null && g.sli_version != null && ' '}
                  {g.sli_version != null && `SLI v${g.sli_version}`}
                  ]
                </span>
              )}
              {onScrollToHeatmap && (
                <span
                  role="button"
                  tabIndex={0}
                  onClick={e => { e.stopPropagation(); onScrollToHeatmap() }}
                  onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); onScrollToHeatmap() } }}
                  className="absolute left-1/2 -translate-x-1/2 inset-y-0 flex items-center px-6 text-pass/60 hover:text-pass transition-colors"
                  title="Go to heatmap"
                  aria-label="Go to heatmap"
                >
                  <Grid3X3 className="size-5" />
                </span>
              )}
              <span className="flex-1" />
              {g.total_points > 0 && (
                <span className="text-xs text-muted-foreground tabular-nums">
                  {g.achieved_points}/{g.total_points}pts
                </span>
              )}
              {g.result !== 'none' && (
                <span className={`text-xs font-bold uppercase ${resultColour}`}>
                  {g.result}
                </span>
              )}
            </button>

            {/* Indicator rows — hidden when collapsed to preserve DOM */}
            {g.indicators.length > 0 && (
              <div className={`border border-t-0 border-border rounded-b mb-2 ${expanded ? '' : 'hidden'}`}>
                <SLIBreakdownTable
                  indicators={g.indicators}
                  sliMetadata={sliMetadata}
                  onIndicatorClick={
                    onIndicatorClick
                      ? (metric) => onIndicatorClick(metric, g.slo_name)
                      : undefined
                  }
                  rowIdPrefix={rowIdPrefixBuilder?.(g.slo_name)}
                />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
