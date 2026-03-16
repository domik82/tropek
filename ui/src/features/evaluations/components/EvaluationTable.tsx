// src/features/evaluations/components/EvaluationTable.tsx
import type { RefObject } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR } from '@/lib/theme'
import type { ResultColours } from '@/lib/theme'
import { fmtDateTime } from '@/lib/format'
import { AnnotationCell } from './AnnotationCell'
import type { EvaluationSummary, ColumnDef } from '../types'

interface Props {
  evaluations: EvaluationSummary[]
  dynamicCols: ColumnDef[]
  visibleKeys: Set<string>
  allCols: ColumnDef[]
  open: boolean
  setOpen: (v: boolean) => void
  toggle: (key: string) => void
  pickerRef: RefObject<HTMLDivElement | null>
  onAssetSelect?: (name: string) => void
  /** When provided, clicking the evaluation name calls this instead of navigating to the detail page. */
  onEvalClick?: (ev: EvaluationSummary) => void
}

const STATIC_KEYS = new Set([
  'test', 'asset', 'arch', 'os', 'branch', 'build', 'triggered_by',
  'start', 'score', 'result', 'slo', 'annotations',
])

function cell(
  ev: EvaluationSummary,
  key: string,
  colours: ResultColours,
  onAssetSelect?: (name: string) => void,
  onEvalClick?: (ev: EvaluationSummary) => void,
) {
  switch (key) {
    case 'test':
      return (
        <td key="test" className="px-4 py-3">
          {onEvalClick ? (
            <button
              onClick={() => onEvalClick(ev)}
              className="text-slate-200 hover:text-indigo-300 hover:underline decoration-dotted underline-offset-2 font-medium cursor-pointer transition-colors"
            >
              {ev.name}
            </button>
          ) : (
            <Link to={`/evaluations/${ev.id}`} className="text-slate-200 hover:text-indigo-300 hover:underline decoration-dotted underline-offset-2 font-medium transition-colors">
              {ev.name}
            </Link>
          )}
        </td>
      )
    case 'asset':
      return (
        <td key="asset" className="px-4 py-3 font-mono text-sm">
          {onAssetSelect ? (
            <button
              onClick={() => onAssetSelect(ev.asset_snapshot.name)}
              className="text-slate-200 hover:text-indigo-300 hover:underline decoration-dotted underline-offset-2 cursor-pointer transition-colors"
            >
              {ev.asset_snapshot.name}
            </button>
          ) : (
            <span className="text-slate-200">{ev.asset_snapshot.name}</span>
          )}
        </td>
      )
    case 'arch':
      return <td key="arch" className="px-4 py-3 text-sm text-slate-400">{ev.asset_snapshot.tags?.['arch'] ?? '—'}</td>
    case 'os':
      return <td key="os" className="px-4 py-3 text-sm text-slate-400">{ev.asset_snapshot.tags?.['os'] ?? '—'}</td>
    case 'branch':
      return <td key="branch" className="px-4 py-3 text-sm text-slate-400">{ev.evaluation_metadata?.['branch'] ?? '—'}</td>
    case 'build':
      return <td key="build" className="px-4 py-3 text-sm text-slate-400">{ev.evaluation_metadata?.['build'] ?? '—'}</td>
    case 'triggered_by':
      return <td key="triggered_by" className="px-4 py-3 text-sm text-slate-400">{ev.evaluation_metadata?.['triggered_by'] ?? '—'}</td>
    case 'start':
      return <td key="start" className="px-4 py-3 text-sm text-slate-400 tabular-nums whitespace-nowrap">{fmtDateTime(ev.period_start)}</td>
    case 'score':
      return <td key="score" className="px-4 py-3 tabular-nums font-medium font-mono">{ev.score.toFixed(1)}%</td>
    case 'result':
      return (
        <td key="result" className="px-4 py-3">
          <Badge style={{ backgroundColor: colours[ev.result as keyof ResultColours] ?? colours.error, color: '#fff' }}>
            {ev.result.toUpperCase()}
          </Badge>
        </td>
      )
    case 'slo':
      return (
        <td key="slo" className="px-4 py-3 text-sm text-slate-400">
          {ev.slo_name ? `${ev.slo_name}${ev.slo_version != null ? ` v${ev.slo_version}` : ''}` : '—'}
        </td>
      )
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
  onAssetSelect, onEvalClick,
}: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]
  const visibleCols = allCols.filter(c => visibleKeys.has(c.key))

  return (
    <div className="relative overflow-x-auto rounded-lg border border-slate-700 bg-gray-900">
      <table className="w-full text-sm text-left">
        <thead className="text-xs uppercase text-slate-400 bg-gray-800 border-b border-slate-700">
          <tr>
            {visibleCols.map(col => (
              <th key={col.key} className="text-left px-4 py-3">{col.label}</th>
            ))}
            <th className="px-2 py-2 text-right sticky right-0 bg-gray-800 w-px" ref={pickerRef}>
              <button
                onClick={() => setOpen(!open)}
                className="text-xs normal-case text-slate-400 hover:text-slate-200 transition-colors"
              >
                Columns ▾
              </button>
              {open && (
                <div className="absolute right-2 top-10 z-10 bg-gray-800 border border-slate-700 rounded p-3 min-w-48 text-left normal-case shadow-lg">
                  {allCols.map(col => (
                    <label key={col.key} className="flex items-center gap-2 py-1 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={visibleKeys.has(col.key)}
                        disabled={col.required}
                        onChange={() => toggle(col.key)}
                      />
                      <span className="text-sm text-slate-300">{col.label}</span>
                    </label>
                  ))}
                </div>
              )}
            </th>
          </tr>
        </thead>
          <tbody>
            {evaluations.map((ev, idx) => (
              <tr
                key={ev.id}
                className={`border-b border-slate-800/60 last:border-0 transition-colors hover:bg-gray-700/50 ${
                  idx % 2 === 0 ? 'bg-gray-900' : 'bg-gray-800/50'
                }`}
              >
                {visibleCols.map(col =>
                  STATIC_KEYS.has(col.key)
                    ? cell(ev, col.key, colours, onAssetSelect, onEvalClick)
                    : (
                      <td key={col.key} className="px-4 py-3 text-sm text-slate-400">
                        {ev.asset_snapshot.tags?.[col.key] ?? ev.evaluation_metadata?.[col.key] ?? '—'}
                      </td>
                    )
                )}
                <td />
              </tr>
            ))}
          </tbody>
        </table>
    </div>
  )
}
