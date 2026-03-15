// src/features/slos/components/SloObjectiveTable.tsx
import { useMemo } from 'react'
import { parseSloYaml } from '@/lib/parseSloYaml'
import type { SloDefinition } from '../types'

interface Props {
  slo: SloDefinition
}

export function SloObjectiveTable({ slo }: Props) {
  const { objectives, sliQueryMap, scoreThresholds } = useMemo(() => {
    const sliQueryMap: Record<string, string> = {}

    if (slo.slo_yaml) {
      const parsed = parseSloYaml(slo.slo_yaml)
      if (parsed) {
        const scoreThresholds = parsed.spec.total_score.pass || parsed.spec.total_score.warning
          ? {
              total_pass: parsed.spec.total_score.pass
                ? parseFloat(parsed.spec.total_score.pass) : undefined,
              total_warning: parsed.spec.total_score.warning
                ? parseFloat(parsed.spec.total_score.warning) : undefined,
              comparison: parsed.spec.comparison.compare_with,
            }
          : undefined
        return { objectives: parsed.spec.objectives, sliQueryMap, scoreThresholds }
      }
    }

    return { objectives: [], sliQueryMap, scoreThresholds: undefined }
  }, [slo])

  if (objectives.length === 0) {
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
              <th className="px-3 py-2">SLI Query</th>
              <th className="px-3 py-2 text-center">Pass</th>
              <th className="px-3 py-2 text-center">Warning</th>
              <th className="px-3 py-2 text-center w-16">Weight</th>
              <th className="px-3 py-2 text-center w-24">Group</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {objectives.map(obj => (
              <tr key={obj.sli_name} className="hover:bg-slate-800/40 transition-colors">
                <td className="px-2 py-2 text-center">
                  {obj.key_sli
                    ? <span className="text-cyan-400 text-xs" title="Key SLI">◆</span>
                    : <span className="text-slate-700">—</span>
                  }
                </td>
                <td className="px-3 py-2">
                  <div className="font-mono text-xs text-[#7dc540]">{obj.sli_name}</div>
                  {obj.display_name && obj.display_name !== obj.sli_name && (
                    <div className="text-xs text-slate-400">{obj.display_name}</div>
                  )}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-slate-400 max-w-xs truncate" title={sliQueryMap[obj.sli_name]}>
                  {sliQueryMap[obj.sli_name] ?? '—'}
                </td>
                <td className="px-3 py-2 text-center text-xs text-[#7dc540]">
                  {obj.pass.join(', ') || '—'}
                </td>
                <td className="px-3 py-2 text-center text-xs text-[#e6be00]">
                  {obj.warning.join(', ') || '—'}
                </td>
                <td className="px-3 py-2 text-center text-slate-400">{obj.weight}</td>
                <td className="px-3 py-2 text-center">
                  {obj.tab_group
                    ? <span className="text-xs bg-slate-700/60 text-slate-300 px-1.5 py-0.5 rounded">{obj.tab_group}</span>
                    : <span className="text-slate-600">—</span>
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {scoreThresholds && (
        <div className="mt-3 flex flex-wrap gap-6 text-sm text-slate-400">
          {scoreThresholds.total_pass != null && (
            <span>Total pass: <strong className="text-[#7dc540]">{scoreThresholds.total_pass}%</strong></span>
          )}
          {scoreThresholds.total_warning != null && (
            <span>Total warning: <strong className="text-[#e6be00]">{scoreThresholds.total_warning}%</strong></span>
          )}
          {scoreThresholds.comparison && (
            <span>Comparison: <strong className="text-slate-300">{scoreThresholds.comparison}</strong></span>
          )}
        </div>
      )}
    </div>
  )
}
