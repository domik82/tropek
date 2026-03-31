// src/features/slos/components/SloObjectiveTable.tsx
import { DataTable, DataTableHeader, dataTableRowClass } from '@/components/ui/data-table'
import type { SloDefinition } from '../types'

interface Props {
  slo: SloDefinition
}

export function SloObjectiveTable({ slo }: Props) {
  if (slo.objectives.length === 0) {
    return <p className="text-xs text-muted-foreground italic">No objectives defined.</p>
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
          {slo.objectives.map((obj, idx) => (
            <tr key={obj.sli} className={dataTableRowClass(idx)}>
              <td className="px-2 py-2 text-center">
                {obj.key_sli
                  ? <span className="text-indicator-key-sli text-xs" title="Key SLI">◆</span>
                  : <span className="text-muted-foreground/40">—</span>
                }
              </td>
              <td className="px-3 py-2">
                <div className="font-mono text-xs text-pass">{obj.sli}</div>
                {obj.display_name && obj.display_name !== obj.sli && (
                  <div className="text-xs text-muted-foreground">{obj.display_name}</div>
                )}
              </td>
              <td className="px-3 py-2 text-center text-xs text-pass">
                {obj.pass_threshold.join(', ') || '—'}
              </td>
              <td className="px-3 py-2 text-center text-xs text-warning">
                {obj.warning_threshold.join(', ') || '—'}
              </td>
              <td className="px-3 py-2 text-center text-muted-foreground">{obj.weight}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>

      <div className="mt-3 flex flex-wrap gap-6 text-sm text-muted-foreground">
        <span>Total pass: <strong className="text-pass">{slo.total_score_pass_threshold}%</strong></span>
        <span>Total warning: <strong className="text-warning">{slo.total_score_warning_threshold}%</strong></span>
        {slo.comparable_from_version != null && (
          <span>Comparable from: <strong className="text-link">v{slo.comparable_from_version}</strong></span>
        )}
      </div>
    </div>
  )
}
