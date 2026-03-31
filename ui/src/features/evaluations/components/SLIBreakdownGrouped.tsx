// ui/src/features/evaluations/components/SLIBreakdownGrouped.tsx
import { ChevronDown, ChevronRight } from 'lucide-react'
import { SLIBreakdownTable } from './SLIBreakdownTable'
import type { IndicatorResult, SliMetadata } from '../types'

export interface SloBreakdownGroup {
  slo_name: string
  slo_display_name?: string
  indicators: IndicatorResult[]
  score: number           // 0–100
  result: string
  achieved_points: number
  total_points: number
}

interface Props {
  groups: SloBreakdownGroup[]
  expandState: Map<string, boolean>
  onToggle: (sloName: string) => void
  sliMetadata?: Record<string, SliMetadata>
  onIndicatorClick?: (metric: string, sloName: string) => void
}

export function SLIBreakdownGrouped({
  groups,
  expandState,
  onToggle,
  sliMetadata,
  onIndicatorClick,
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

            {/* Indicator rows — only when expanded and there are indicators */}
            {expanded && g.indicators.length > 0 && (
              <div className="border border-t-0 border-border rounded-b mb-2">
                <SLIBreakdownTable
                  indicators={g.indicators}
                  sliMetadata={sliMetadata}
                  onIndicatorClick={
                    onIndicatorClick
                      ? (metric) => onIndicatorClick(metric, g.slo_name)
                      : undefined
                  }
                />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
