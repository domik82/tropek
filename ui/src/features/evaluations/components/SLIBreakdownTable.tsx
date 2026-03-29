// src/features/evaluations/components/SLIBreakdownTable.tsx
import { useState } from 'react'
import { fmt } from '@/lib/format'
import { STATUS_TEXT } from '@/lib/status'
import type { IndicatorResult } from '../types'

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}%`
}

interface Props {
  indicators: IndicatorResult[]
  onIndicatorClick?: (metric: string, tabGroup: string) => void
}

export function SLIBreakdownTable({ indicators, onIndicatorClick }: Props) {
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null)

  function handleRowClick(metric: string, tabGroup: string) {
    setSelectedMetric(metric)
    onIndicatorClick?.(metric, tabGroup)
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-table-row-bg">
      <table className="w-full text-sm text-left">
        <thead className="text-xs uppercase text-muted-foreground bg-table-header-bg border-b border-border">
          <tr>
            <th className="px-2 py-3 text-center w-6 text-indicator-key-sli" title="Key SLI">◆</th>
            <th className="px-4 py-3">Indicator</th>
            <th className="px-4 py-3 text-right">Value</th>
            <th className="px-4 py-3 text-right">Baseline</th>
            <th className="px-4 py-3 text-right">Δ</th>
            <th className="px-4 py-3 text-right">Weight</th>
            <th className="px-4 py-3 text-right">Score</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Pass criteria</th>
            <th className="px-4 py-3">Warn criteria</th>
          </tr>
        </thead>
        <tbody>
          {indicators.map((ind, idx) => {
            const isSelected = ind.metric === selectedMetric
            const zebraBase = idx % 2 === 0 ? 'bg-table-row-bg' : 'bg-table-row-alt'
            const rowBg = isSelected ? 'bg-table-row-selected' : zebraBase
            const rowHover = isSelected ? 'hover:bg-table-row-selected' : 'hover:bg-table-row-hover'
            const rowRing = isSelected ? 'ring-1 ring-inset ring-muted-foreground/60' : ''
            return (
            <tr
              key={ind.metric}
              onClick={() => handleRowClick(ind.metric, ind.tab_group ?? 'summary')}
              className={`transition-colors group border-b border-border/60 last:border-0 cursor-pointer ${rowBg} ${rowHover} ${rowRing}`}
            >
              <td className="px-2 py-3 text-center">
                {ind.key_sli && (
                  <span className="text-indicator-key-sli text-xs leading-none" title="Key SLI">◆</span>
                )}
              </td>
              <td className="px-4 py-3 font-medium whitespace-nowrap">
                {onIndicatorClick ? (
                  <button
                    className="text-left group/name"
                    title={`${ind.metric} — click to go to trend chart`}
                  >
                    <span className="flex items-center gap-1">
                      <span className="text-foreground group-hover/name:text-link-hover transition-colors underline decoration-dotted underline-offset-2 decoration-muted-foreground/60 group-hover/name:decoration-link-hover">
                        {ind.display_name || ind.metric}
                      </span>
                      <span className="text-muted-foreground/60 group-hover/name:text-link-hover text-xs">↓</span>
                    </span>
                  </button>
                ) : (
                  <span className="text-foreground" title={ind.metric}>
                    {ind.display_name || ind.metric}
                  </span>
                )}
              </td>
              <td className="px-4 py-3 text-right font-mono">{fmt(ind.value)}</td>
              <td className="px-4 py-3 text-right font-mono text-muted-foreground">{fmt(ind.compared_value)}</td>
              <td className="px-4 py-3 text-right font-mono">
                {ind.change_relative_pct != null ? (
                  <span className={STATUS_TEXT[ind.status] ?? 'text-foreground'}>
                    {fmtPct(ind.change_relative_pct)}
                  </span>
                ) : '—'}
              </td>
              <td className="px-4 py-3 text-right text-muted-foreground">{ind.weight}</td>
              <td className="px-4 py-3 text-right font-mono">{fmt(ind.score)}</td>
              <td className={`px-4 py-3 font-semibold uppercase text-xs ${STATUS_TEXT[ind.status] ?? ''}`}>
                {ind.status}
              </td>
              <td className="px-4 py-3 text-xs text-muted-foreground">
                {ind.pass_targets?.map((t, i) => (
                  <div key={i} className={`font-mono ${t.violated ? 'text-destructive-form-text' : ''}`}>
                    {t.criteria}{t.violated && ' ✗'}
                  </div>
                ))}
              </td>
              <td className="px-4 py-3 text-xs text-muted-foreground">
                {ind.warning_targets?.map((t, i) => (
                  <div key={i} className="font-mono">{t.criteria}</div>
                ))}
              </td>
            </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
