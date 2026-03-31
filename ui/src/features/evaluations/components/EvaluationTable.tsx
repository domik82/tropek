// src/features/evaluations/components/EvaluationTable.tsx
import type { RefObject } from 'react'
import { Link } from 'react-router-dom'
import { ResultBadge } from './ResultBadge'
import { fmtDateTime } from '@/lib/format'
import { AnnotationCell } from './AnnotationCell'
import { DataTable, DataTableHeader, dataTableRowClass } from '@/components/ui/data-table'
import type { EvaluationSummary, ColumnDef } from '../types'

interface Props {
  evaluations: EvaluationSummary[]
  dynamicCols: ColumnDef[]
  visibleKeys: Set<string>
  allCols: ColumnDef[]
  open: boolean
  setOpen: (v: boolean) => void
  toggle: (key: string) => void
  pickerRef: RefObject<HTMLTableCellElement | null>
  onAssetSelect?: (name: string) => void
  /** When provided, clicking the evaluation name calls this instead of navigating to the detail page. */
  onEvalClick?: (ev: EvaluationSummary) => void
  /** Fallback lookup for asset display names (for evaluations created before snapshot included display_name). */
  assetDisplayNames?: Map<string, string>
  /** Fallback lookup for SLO display names. */
  sloDisplayNames?: Map<string, string>
}

const STATIC_KEYS = new Set([
  'test', 'asset', 'start', 'score', 'result', 'slo', 'annotations',
])

function cell(
  ev: EvaluationSummary,
  key: string,
  onAssetSelect?: (name: string) => void,
  onEvalClick?: (ev: EvaluationSummary) => void,
  assetDisplayNames?: Map<string, string>,
  sloDisplayNames?: Map<string, string>,
) {
  switch (key) {
    case 'test':
      return (
        <td key="test" className="px-4 py-3">
          {onEvalClick ? (
            <button
              onClick={() => onEvalClick(ev)}
              className="text-foreground hover:text-link-hover hover:underline decoration-dotted underline-offset-2 font-medium cursor-pointer transition-colors"
            >
              {ev.evaluation_name}
            </button>
          ) : (
            <Link to={`/evaluations/${ev.id}`} className="text-foreground hover:text-link-hover hover:underline decoration-dotted underline-offset-2 font-medium transition-colors">
              {ev.evaluation_name}
            </Link>
          )}
        </td>
      )
    case 'asset': {
      const assetLabel = ev.asset_snapshot.display_name
        ?? assetDisplayNames?.get(ev.asset_snapshot.name)
        ?? ev.asset_snapshot.name
      const hasDisplayName = assetLabel !== ev.asset_snapshot.name
      return (
        <td key="asset" className="px-4 py-3 text-sm">
          {onAssetSelect ? (
            <button
              onClick={() => onAssetSelect(ev.asset_snapshot.name)}
              className="text-foreground hover:text-link-hover hover:underline decoration-dotted underline-offset-2 cursor-pointer transition-colors"
            >
              {assetLabel}
            </button>
          ) : (
            <span className="text-foreground">{assetLabel}</span>
          )}
          {hasDisplayName && (
            <span className="block text-xs text-muted-foreground font-mono">{ev.asset_snapshot.name}</span>
          )}
        </td>
      )
    }
    case 'start':
      return <td key="start" className="px-4 py-3 text-sm text-muted-foreground tabular-nums whitespace-nowrap">{fmtDateTime(ev.period_start)}</td>
    case 'score':
      return <td key="score" className="px-4 py-3 tabular-nums font-medium font-mono">{ev.score.toFixed(1)}%</td>
    case 'result':
      return (
        <td key="result" className="px-4 py-3">
          <ResultBadge result={ev.result} />
        </td>
      )
    case 'slo': {
      const sloLabel = (ev.slo_name && sloDisplayNames?.get(ev.slo_name)) ?? ev.slo_name
      return (
        <td key="slo" className="px-4 py-3 text-sm text-muted-foreground">
          {sloLabel ? `${sloLabel}${ev.slo_version != null ? ` v${ev.slo_version}` : ''}` : '—'}
        </td>
      )
    }
    case 'annotations':
      return (
        <td key="annotations" className="px-4 py-3">
          <AnnotationCell annotation={ev.latest_annotation} count={ev.annotation_count} />
        </td>
      )
    default:
      return null
  }
}

export function EvaluationTable({
  evaluations, dynamicCols: _dynamicCols,
  visibleKeys, allCols, open, setOpen, toggle, pickerRef,
  onAssetSelect, onEvalClick, assetDisplayNames, sloDisplayNames,
}: Props) {
  const visibleCols = allCols.filter(c => visibleKeys.has(c.key))

  return (
    <DataTable className="relative bg-table-row-bg">
      <DataTableHeader>
        <tr>
          {visibleCols.map(col => (
            <th key={col.key} className="text-left px-4 py-3">{col.label}</th>
          ))}
          <th className="px-2 py-2 text-right sticky right-0 bg-table-header-bg w-px" ref={pickerRef}>
            <button
              onClick={() => setOpen(!open)}
              className="text-xs normal-case text-muted-foreground hover:text-foreground transition-colors"
            >
              Columns ▾
            </button>
            {open && (
              <div className="absolute right-2 top-10 z-10 bg-table-header-bg border border-border rounded p-3 min-w-48 text-left normal-case shadow-lg">
                {allCols.map(col => (
                  <label key={col.key} className="flex items-center gap-2 py-1 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={visibleKeys.has(col.key)}
                      disabled={col.required}
                      onChange={() => toggle(col.key)}
                    />
                    <span className="text-sm text-foreground">{col.label}</span>
                  </label>
                ))}
              </div>
            )}
          </th>
        </tr>
      </DataTableHeader>
      <tbody>
        {evaluations.map((ev, idx) => (
          <tr key={ev.id} className={dataTableRowClass(idx)}>
            {visibleCols.map(col =>
              STATIC_KEYS.has(col.key)
                ? cell(ev, col.key, onAssetSelect, onEvalClick, assetDisplayNames, sloDisplayNames)
                : (
                  <td key={col.key} className="px-4 py-3 text-sm text-muted-foreground">
                    {ev.asset_snapshot.tags?.[col.key] ?? ev.evaluation_metadata?.[col.key] ?? '—'}
                  </td>
                )
            )}
            <td />
          </tr>
        ))}
      </tbody>
    </DataTable>
  )
}
