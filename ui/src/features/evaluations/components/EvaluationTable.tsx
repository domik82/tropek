// src/features/evaluations/components/EvaluationTable.tsx
import type { RefObject } from 'react'
import { Link } from 'react-router-dom'
import { ResultBadge } from './ResultBadge'
import { fmtDateTime } from '@/lib/format'
import { AnnotationCell } from './AnnotationCell'
import { DataTable, DataTableHeader, dataTableRowClass } from '@/components/ui/data-table'
import type { Evaluation } from '../domain'
import type { ColumnDef } from '../ui-types'

interface Props {
  evaluations: Evaluation[]
  visibleKeys: Set<string>
  allCols: ColumnDef[]
  open: boolean
  setOpen: (v: boolean) => void
  toggle: (key: string) => void
  pickerRef: RefObject<HTMLTableCellElement | null>
  onAssetSelect?: (name: string) => void
  /** When provided, clicking the evaluation name calls this instead of navigating to the detail page. */
  onEvalClick?: (ev: Evaluation) => void
  /** Fallback lookup for asset display names (for evaluations created before snapshot included display_name). */
  assetDisplayNames?: Map<string, string>
  /** Fallback lookup for SLO display names. */
  sloDisplayNames?: Map<string, string>
}

const STATIC_KEYS = new Set([
  'test', 'asset', 'start', 'score', 'result', 'slo', 'annotations',
])

function cell(
  ev: Evaluation,
  key: string,
  onAssetSelect?: (name: string) => void,
  onEvalClick?: (ev: Evaluation) => void,
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
              {ev.evaluationName}
            </button>
          ) : (
            <Link to={`/evaluations/${ev.id}`} className="text-foreground hover:text-link-hover hover:underline decoration-dotted underline-offset-2 font-medium transition-colors">
              {ev.evaluationName}
            </Link>
          )}
        </td>
      )
    case 'asset': {
      const assetLabel = ev.assetSnapshot.displayName
        ?? assetDisplayNames?.get(ev.assetSnapshot.name)
        ?? ev.assetSnapshot.name
      const hasDisplayName = assetLabel !== ev.assetSnapshot.name
      return (
        <td key="asset" className="px-4 py-3 text-sm">
          {onAssetSelect ? (
            <button
              onClick={() => onAssetSelect(ev.assetSnapshot.name)}
              className="text-foreground hover:text-link-hover hover:underline decoration-dotted underline-offset-2 cursor-pointer transition-colors"
            >
              {assetLabel}
            </button>
          ) : (
            <span className="text-foreground">{assetLabel}</span>
          )}
          {hasDisplayName && (
            <span className="block text-xs text-muted-foreground font-mono">{ev.assetSnapshot.name}</span>
          )}
        </td>
      )
    }
    case 'start':
      return <td key="start" className="px-4 py-3 text-sm text-muted-foreground tabular-nums whitespace-nowrap">{fmtDateTime(ev.period.from)}</td>
    case 'score':
      return <td key="score" className="px-4 py-3 tabular-nums font-medium font-mono">{ev.score != null ? `${ev.score.toFixed(1)}%` : '—'}</td>
    case 'result':
      return (
        <td key="result" className="px-4 py-3">
          <ResultBadge result={ev.outcome} />
        </td>
      )
    case 'slo': {
      const sloLabel = (ev.sloName && sloDisplayNames?.get(ev.sloName)) ?? ev.sloName
      return (
        <td key="slo" className="px-4 py-3 text-sm text-muted-foreground">
          {sloLabel ? `${sloLabel}${ev.sloVersion != null ? ` v${ev.sloVersion}` : ''}` : '—'}
        </td>
      )
    }
    case 'annotations':
      return (
        <td key="annotations" className="px-4 py-3">
          {/* AnnotationCell still uses the old Annotation shape (Task 14). Cast through never to bridge until that batch lands. */}
          <AnnotationCell annotation={(ev.latestAnnotation ?? undefined) as never} count={ev.annotationCount} />
        </td>
      )
    default:
      return null
  }
}

export function EvaluationTable({
  evaluations,
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
                    {ev.assetSnapshot.tags?.[col.key] ?? ev.variables?.[col.key] ?? '—'}
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
