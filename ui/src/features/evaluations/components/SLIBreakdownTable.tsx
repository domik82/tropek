// src/features/evaluations/components/SLIBreakdownTable.tsx
import { fmt } from '@/lib/format'
import type { IndicatorResult } from '../types'

const STATUS_TEXT: Record<string, string> = {
  pass:    'text-[#7dc540]',
  warning: 'text-[#e6be00]',
  fail:    'text-[#dc172a]',
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
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-700">
      <table className="w-full text-sm text-left">
        <thead className="text-xs uppercase text-slate-400 bg-slate-800/60 border-b border-slate-700">
          <tr>
            <th className="px-2 py-3 text-center w-6 text-cyan-500/70" title="Key SLI">◆</th>
            <th className="px-4 py-3">Indicator</th>
            <th className="px-4 py-3 text-right">Value</th>
            <th className="px-4 py-3 text-right">Baseline</th>
            <th className="px-4 py-3 text-right">Δ</th>
            <th className="px-4 py-3 text-right">Weight</th>
            <th className="px-4 py-3 text-right">Score</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Criteria</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {indicators.map(ind => (
            <tr key={ind.metric} className="hover:bg-slate-800/40 transition-colors group">
              <td className="px-2 py-3 text-center">
                {ind.key_sli && (
                  <span className="text-cyan-400 text-xs leading-none" title="Key SLI">◆</span>
                )}
              </td>
              <td className="px-4 py-3 font-medium whitespace-nowrap">
                {onIndicatorClick ? (
                  <button
                    onClick={() => onIndicatorClick(ind.metric, ind.tab_group ?? 'summary')}
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
              <td className="px-4 py-3 text-xs text-slate-400 space-y-1">
                {ind.pass_targets?.map((t, i) => (
                  <div key={i} className={t.violated ? 'text-red-400' : ''}>
                    pass: {t.criteria}{t.violated && ' ✗'}
                  </div>
                ))}
                {ind.warning_targets?.map((t, i) => (
                  <div key={i} className="text-slate-500">
                    warn: {t.criteria}
                  </div>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
