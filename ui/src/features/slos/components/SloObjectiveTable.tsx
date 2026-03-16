// src/features/slos/components/SloObjectiveTable.tsx
import type { SloDefinition } from '../types'

interface Props {
  slo: SloDefinition
}

export function SloObjectiveTable({ slo }: Props) {
  if (slo.objectives.length === 0) {
    return <p className="text-xs text-slate-500 italic">No objectives defined.</p>
  }

  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-slate-700">
        <table className="w-full text-sm text-left">
          <thead className="text-xs uppercase text-slate-400 bg-slate-800/60 border-b border-slate-700">
            <tr>
              <th className="px-2 py-2 text-center w-6 text-cyan-500/70" title="Key SLI">◆</th>
              <th className="px-3 py-2">Indicator</th>
              <th className="px-3 py-2 text-center">Pass</th>
              <th className="px-3 py-2 text-center">Warning</th>
              <th className="px-3 py-2 text-center w-16">Weight</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {slo.objectives.map(obj => (
              <tr key={obj.sli} className="hover:bg-slate-800/40 transition-colors">
                <td className="px-2 py-2 text-center">
                  {obj.key_sli
                    ? <span className="text-cyan-400 text-xs" title="Key SLI">◆</span>
                    : <span className="text-slate-700">—</span>
                  }
                </td>
                <td className="px-3 py-2">
                  <div className="font-mono text-xs text-[#7dc540]">{obj.sli}</div>
                  {obj.display_name && obj.display_name !== obj.sli && (
                    <div className="text-xs text-slate-400">{obj.display_name}</div>
                  )}
                </td>
                <td className="px-3 py-2 text-center text-xs text-[#7dc540]">
                  {obj.pass_criteria.join(', ') || '—'}
                </td>
                <td className="px-3 py-2 text-center text-xs text-[#e6be00]">
                  {obj.warning_criteria.join(', ') || '—'}
                </td>
                <td className="px-3 py-2 text-center text-slate-400">{obj.weight}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex flex-wrap gap-6 text-sm text-slate-400">
        <span>Total pass: <strong className="text-[#7dc540]">{slo.total_score_pass_pct}%</strong></span>
        <span>Total warning: <strong className="text-[#e6be00]">{slo.total_score_warning_pct}%</strong></span>
      </div>
    </div>
  )
}
