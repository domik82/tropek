// src/features/slos/components/SloHistoryPanel.tsx
import { useState } from 'react'
import { useSloVersions } from '../hooks'
import { SloObjectiveTable } from './SloObjectiveTable'

interface Props {
  name: string
}

export function SloHistoryPanel({ name }: Props) {
  const { data: versions, isLoading, isError } = useSloVersions(name, true)
  const [expanded, setExpanded] = useState<number | null>(null)

  if (isLoading) return <p className="text-muted-foreground text-sm py-2">Loading history…</p>
  if (isError || !versions) return <p className="text-destructive-form-text text-sm py-2">Failed to load history.</p>
  if (versions.length === 0) return <p className="text-muted-foreground/60 text-sm py-2">No version history found.</p>

  return (
    <div className="space-y-2">
      {versions.map(v => (
        <div key={v.version} className="border border-border rounded-lg overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-3 bg-surface-sunken/40">
            <span className="text-foreground font-mono text-sm font-semibold">v{v.version}</span>
            {v.active
              ? <span className="text-xs bg-pass/20 text-pass border border-pass/30 px-1.5 py-0.5 rounded-full">active</span>
              : <span className="text-xs bg-surface-sunken/40 text-muted-foreground border border-border/40 px-1.5 py-0.5 rounded-full">inactive</span>
            }
            {v.comparable_from_version != null && (
              <span className="text-xs bg-primary/20 text-link border border-primary/30 px-1.5 py-0.5 rounded-full">
                comparable from v{v.comparable_from_version}
              </span>
            )}
            {v.author && <span className="text-xs text-muted-foreground">{v.author}</span>}
            {v.notes && <span className="text-xs text-muted-foreground/60 italic truncate max-w-xs">{v.notes}</span>}
            <span className="ml-auto text-xs text-muted-foreground/60">{v.created_at.slice(0, 16).replace('T', ' ')}</span>
            <button
              onClick={() => setExpanded(prev => prev === v.version ? null : v.version)}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors shrink-0"
            >
              {expanded === v.version ? 'Hide ▲' : 'Details ▼'}
            </button>
          </div>
          {expanded === v.version && (
            <div className="px-4 py-3 border-t border-border">
              <SloObjectiveTable slo={v} />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
