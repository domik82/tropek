// src/features/slos/components/SloObjectiveTable.tsx
import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { DataTable, DataTableHeader, dataTableRowClass } from '@/components/ui/data-table'
import type { Slo } from '../domain'

const VARIABLE_COLOR = 'var(--chip-var-key)'

function highlightVariables(query: string): React.ReactNode {
  const parts = query.split(/(\$[a-zA-Z_][a-zA-Z0-9_]*)/)
  return parts.map((part, i) => {
    if (/^\$[a-zA-Z_][a-zA-Z0-9_]*$/.test(part)) {
      return (
        <span key={i} style={{ color: VARIABLE_COLOR }}>
          {part}
        </span>
      )
    }
    return part
  })
}

interface Props {
  slo: Slo
  /** metric_name → query_string map from the linked SLI definition */
  indicators?: Record<string, string>
}

export function SloObjectiveTable({ slo, indicators }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  if (slo.objectives.length === 0) {
    return <p className="text-xs text-muted-foreground italic">No objectives defined.</p>
  }

  function toggleExpand(sli: string) {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(sli)) next.delete(sli)
      else next.add(sli)
      return next
    })
  }

  return (
    <div>
      <DataTable>
        <DataTableHeader>
          <tr>
            <th className="px-2 py-2 text-center w-6 text-indicator-key-sli" title="Key SLI">◆</th>
            <th className="px-3 py-2">Indicator</th>
            <th className="px-3 py-2 text-center">Pass</th>
            <th className="px-3 py-2 text-center">Warning</th>
            <th className="px-3 py-2 text-center w-16">Weight</th>
          </tr>
        </DataTableHeader>
        <tbody className="divide-y divide-border">
          {slo.objectives.map((obj, idx) => {
            const query = indicators?.[obj.sli]
            const isExpanded = expanded.has(obj.sli)

            return (
              <tr key={obj.sli} className={dataTableRowClass(idx)}>
                <td className="px-2 py-2 text-center align-top">
                  {obj.keySli
                    ? <span className="text-indicator-key-sli text-xs" title="Key SLI">◆</span>
                    : <span className="text-muted-foreground/40">—</span>
                  }
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1">
                    {query && (
                      <button
                        type="button"
                        onClick={() => toggleExpand(obj.sli)}
                        className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <ChevronRight
                          className={`size-3.5 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                        />
                      </button>
                    )}
                    <div className="font-mono text-xs text-pass">{obj.sli}</div>
                  </div>
                  {obj.displayName && obj.displayName !== obj.sli && (
                    <div className="text-xs text-muted-foreground ml-[18px]">{obj.displayName}</div>
                  )}
                  {query && isExpanded && (
                    <div className="mt-1.5 ml-[18px] px-2 py-1.5 rounded bg-muted/40 border border-border/60 font-mono text-xs text-muted-foreground break-all">
                      {highlightVariables(query)}
                    </div>
                  )}
                </td>
                <td className="px-3 py-2 text-center text-xs text-pass align-top">
                  {obj.passThreshold.join(', ') || '—'}
                </td>
                <td className="px-3 py-2 text-center text-xs text-warning align-top">
                  {obj.warningThreshold.join(', ') || '—'}
                </td>
                <td className="px-3 py-2 text-center text-muted-foreground align-top">{obj.weight}</td>
              </tr>
            )
          })}
        </tbody>
      </DataTable>

      <div className="mt-3 flex flex-wrap gap-6 text-sm text-muted-foreground">
        <span>Total pass: <strong className="text-pass">{slo.totalScorePassThreshold}%</strong></span>
        <span>Total warning: <strong className="text-warning">{slo.totalScoreWarningThreshold}%</strong></span>
        {slo.comparableFromVersion != null && (
          <span>Comparable from: <strong className="text-link">v{slo.comparableFromVersion}</strong></span>
        )}
      </div>
    </div>
  )
}
