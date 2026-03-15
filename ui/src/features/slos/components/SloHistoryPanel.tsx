// src/features/slos/components/SloHistoryPanel.tsx
import { useState } from 'react'
import { useSloVersions } from '../hooks'

interface Props {
  name: string
}

export function SloHistoryPanel({ name }: Props) {
  const { data: versions, isLoading, isError } = useSloVersions(name, true)
  const [expandedYaml, setExpandedYaml] = useState<number | null>(null)

  if (isLoading) return <p className="text-slate-500 text-sm py-2">Loading history…</p>
  if (isError || !versions) return <p className="text-red-400 text-sm py-2">Failed to load history.</p>
  if (versions.length === 0) return <p className="text-slate-600 text-sm py-2">No version history found.</p>

  return (
    <div className="space-y-2">
      {versions.map(v => (
        <div key={v.version} className="border border-slate-700 rounded-lg overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-3 bg-slate-800/40">
            <span className="text-slate-300 font-mono text-sm font-semibold">v{v.version}</span>
            {v.active
              ? <span className="text-xs bg-[#7dc540]/20 text-[#7dc540] border border-[#7dc540]/30 px-1.5 py-0.5 rounded-full">active</span>
              : <span className="text-xs bg-slate-700/40 text-slate-500 border border-slate-600/40 px-1.5 py-0.5 rounded-full">inactive</span>
            }
            {v.author && <span className="text-xs text-slate-500">{v.author}</span>}
            {v.notes && <span className="text-xs text-slate-600 italic truncate max-w-xs">{v.notes}</span>}
            <span className="ml-auto text-xs text-slate-600">{v.created_at.slice(0, 16).replace('T', ' ')}</span>
            {v.slo_yaml && (
              <button
                onClick={() => setExpandedYaml(prev => prev === v.version ? null : v.version)}
                className="text-xs text-slate-400 hover:text-slate-200 transition-colors shrink-0"
              >
                {expandedYaml === v.version ? 'Hide YAML ▲' : 'View YAML ▼'}
              </button>
            )}
          </div>
          {expandedYaml === v.version && v.slo_yaml && (
            <pre className="px-4 py-3 bg-slate-900/80 text-xs font-mono text-slate-300 overflow-x-auto whitespace-pre-wrap border-t border-slate-700">
              {v.slo_yaml}
            </pre>
          )}
        </div>
      ))}
    </div>
  )
}
