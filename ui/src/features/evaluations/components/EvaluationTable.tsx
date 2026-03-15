// src/features/evaluations/components/EvaluationTable.tsx
import type { RefObject } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { RESULT_COLOUR } from '../constants'
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
}

const STATIC_KEYS = new Set([
  'test', 'asset', 'arch', 'os', 'branch', 'build', 'triggered_by',
  'start', 'score', 'result', 'slo', 'annotations',
])

function cell(ev: EvaluationSummary, key: string) {
  switch (key) {
    case 'test':
      return (
        <td key="test" className="px-3 py-2">
          <Link to={`/evaluations/${ev.id}`} className="text-teal-400 hover:underline font-medium">
            {ev.name}
          </Link>
        </td>
      )
    case 'asset':
      return <td key="asset" className="px-3 py-2 font-mono text-xs">{ev.asset_snapshot.name}</td>
    case 'arch':
      return <td key="arch" className="px-3 py-2 text-xs text-gray-300">{ev.asset_snapshot.tags?.['arch'] ?? '—'}</td>
    case 'os':
      return <td key="os" className="px-3 py-2 text-xs text-gray-300">{ev.asset_snapshot.tags?.['os'] ?? '—'}</td>
    case 'branch':
      return <td key="branch" className="px-3 py-2 text-xs text-gray-300">{ev.evaluation_metadata?.['branch'] ?? '—'}</td>
    case 'build':
      return <td key="build" className="px-3 py-2 text-xs text-gray-300">{ev.evaluation_metadata?.['build'] ?? '—'}</td>
    case 'triggered_by':
      return <td key="triggered_by" className="px-3 py-2 text-xs text-gray-300">{ev.evaluation_metadata?.['triggered_by'] ?? '—'}</td>
    case 'start':
      return <td key="start" className="px-3 py-2 text-xs text-gray-300 tabular-nums whitespace-nowrap">{fmtDateTime(ev.period_start)}</td>
    case 'score':
      return <td key="score" className="px-3 py-2 tabular-nums font-medium">{ev.score.toFixed(1)}%</td>
    case 'result':
      return (
        <td key="result" className="px-3 py-2">
          <Badge style={{ backgroundColor: RESULT_COLOUR[ev.result] ?? '#888', color: '#fff' }}>
            {ev.result.toUpperCase()}
          </Badge>
        </td>
      )
    case 'slo':
      return (
        <td key="slo" className="px-3 py-2 text-xs text-teal-400">
          {ev.slo_name ? `${ev.slo_name}${ev.slo_version != null ? ` v${ev.slo_version}` : ''}` : '—'}
        </td>
      )
    case 'annotations':
      return (
        <td key="annotations" className="px-3 py-2">
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
}: Props) {
  const visibleCols = allCols.filter(c => visibleKeys.has(c.key))

  return (
    <div className="relative">
      <div className="flex justify-end mb-2" ref={pickerRef}>
        <Button variant="outline" size="sm" onClick={() => setOpen(!open)}>
          Columns ▾
        </Button>
        {open && (
          <div className="absolute right-0 top-8 z-10 bg-gray-800 border border-gray-600 rounded p-3 min-w-48">
            {allCols.map(col => (
              <label key={col.key} className="flex items-center gap-2 py-1 cursor-pointer">
                <input
                  type="checkbox"
                  checked={visibleKeys.has(col.key)}
                  disabled={col.required}
                  onChange={() => toggle(col.key)}
                />
                <span className="text-sm">{col.label}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-gray-400 text-xs uppercase border-b border-gray-700">
              {visibleCols.map(col => (
                <th key={col.key} className="text-left px-3 py-2">{col.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {evaluations.map(ev => (
              <tr key={ev.id} className="border-b border-gray-800 hover:bg-gray-800/40">
                {visibleCols.map(col =>
                  STATIC_KEYS.has(col.key)
                    ? cell(ev, col.key)
                    : (
                      <td key={col.key} className="px-3 py-2 text-xs text-gray-400">
                        {ev.asset_snapshot.tags?.[col.key] ?? ev.evaluation_metadata?.[col.key] ?? '—'}
                      </td>
                    )
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
