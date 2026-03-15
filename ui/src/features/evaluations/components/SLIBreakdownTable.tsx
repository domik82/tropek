// src/features/evaluations/components/SLIBreakdownTable.tsx
import { useState } from 'react'
import { fmt } from '@/lib/format'
import type { IndicatorResult } from '../types'

const STATUS_TEXT: Record<string, string> = {
  pass:    'text-pass',
  warning: 'text-warning',
  fail:    'text-fail',
}

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
    <div className="overflow-x-auto rounded-lg border border-slate-700 bg-gray-900">
      <table className="w-full text-sm text-left">
        <thead className="text-xs uppercase text-slate-400 bg-gray-800 border-b border-slate-700">
          <tr>
            <th className="px-2 py-3 text-center w-6 text-cyan-500/70" title="Key SLI">◆</th>
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
            const zebraBase = idx % 2 === 0 ? 'bg-gray-900' : 'bg-gray-800/50'
            const rowBg = isSelected ? 'bg-gray-600/40' : zebraBase
            const rowHover = isSelected ? 'hover:bg-gray-600/50' : 'hover:bg-gray-700/50'
            const rowRing = isSelected ? 'ring-1 ring-inset ring-slate-400/60' : ''
            return (
            <tr
              key={ind.metric}
              onClick={() => handleRowClick(ind.metric, ind.tab_group ?? 'summary')}
              className={`transition-colors group border-b border-slate-800/60 last:border-0 cursor-pointer ${rowBg} ${rowHover} ${rowRing}`}
            >
              <td className="px-2 py-3 text-center">
                {ind.key_sli && (
                  <span className="text-cyan-400 text-xs leading-none" title="Key SLI">◆</span>
                )}
              </td>
              <td className="px-4 py-3 font-medium whitespace-nowrap">
                {onIndicatorClick ? (
                  <button
                    className="text-left group/name"
                    title={`${ind.metric} — click to go to trend chart`}
                  >
                    <span className="flex items-center gap-1">
                      <span className="text-slate-200 group-hover/name:text-indigo-300 transition-colors underline decoration-dotted underline-offset-2 decoration-slate-600 group-hover/name:decoration-indigo-400">
                        {ind.display_name || ind.metric}
                      </span>
                      <span className="text-slate-600 group-hover/name:text-indigo-500 text-xs">↓</span>
                    </span>
                  </button>
                ) : (
                  <span className="text-slate-200" title={ind.metric}>
                    {ind.display_name || ind.metric}
                  </span>
                )}
              </td>
              <td className="px-4 py-3 text-right font-mono">{fmt(ind.value)}</td>
              <td className="px-4 py-3 text-right font-mono text-slate-400">{fmt(ind.compared_value)}</td>
              <td className="px-4 py-3 text-right font-mono">
                {ind.change_relative_pct != null ? (
                  <span className={STATUS_TEXT[ind.status] ?? 'text-slate-300'}>
                    {fmtPct(ind.change_relative_pct)}
                  </span>
                ) : '—'}
              </td>
              <td className="px-4 py-3 text-right text-slate-400">{ind.weight}</td>
              <td className="px-4 py-3 text-right font-mono">{fmt(ind.score)}</td>
              <td className={`px-4 py-3 font-semibold uppercase text-xs ${STATUS_TEXT[ind.status] ?? ''}`}>
                {ind.status}
              </td>
              <td className="px-4 py-3 text-xs text-slate-400">
                {ind.pass_targets?.map((t, i) => (
                  <div key={i} className={`font-mono ${t.violated ? 'text-red-400' : ''}`}>
                    {t.criteria}{t.violated && ' ✗'}
                  </div>
                ))}
              </td>
              <td className="px-4 py-3 text-xs text-slate-500">
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
