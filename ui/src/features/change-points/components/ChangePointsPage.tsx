import { useState, useCallback } from 'react'
import { Diamond, Check, EyeOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  useChangePoints,
  useTriageChangePoint,
  useBulkTriageChangePoints,
} from '../hooks'
import type {
  ChangePoint,
  ChangePointFilters,
  ChangePointStatus,
  ChangePointDirection,
} from '../domain'

const STATUS_OPTIONS: Array<{ value: ChangePointStatus | ''; label: string }> = [
  { value: '', label: 'All statuses' },
  { value: 'unprocessed', label: 'Unprocessed' },
  { value: 'acknowledged', label: 'Acknowledged' },
  { value: 'hidden', label: 'Hidden' },
]

const DIRECTION_OPTIONS: Array<{ value: ChangePointDirection | ''; label: string }> = [
  { value: '', label: 'All directions' },
  { value: 'regression', label: 'Regression' },
  { value: 'improvement', label: 'Improvement' },
]

function formatPct(pct: number): string {
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(1)}%`
}

function formatDate(date: Date): string {
  return date.toISOString().slice(0, 16).replace('T', ' ')
}

function StatusBadge({ status }: { status: ChangePointStatus }) {
  const styles: Record<ChangePointStatus, string> = {
    unprocessed: 'bg-yellow-900/30 text-yellow-400 border-yellow-800',
    acknowledged: 'bg-green-900/30 text-green-400 border-green-800',
    hidden: 'bg-zinc-800/50 text-zinc-500 border-zinc-700',
  }
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs border ${styles[status]}`}>
      {status}
    </span>
  )
}

function DirectionIndicator({ direction }: { direction: ChangePointDirection }) {
  const color = direction === 'regression' ? 'text-red-400' : 'text-green-400'
  return (
    <span className={`flex items-center gap-1 ${color}`}>
      <Diamond className="w-3 h-3" fill="currentColor" />
      {direction}
    </span>
  )
}

export function ChangePointsPage() {
  const [statusFilter, setStatusFilter] = useState<ChangePointStatus | ''>('unprocessed')
  const [directionFilter, setDirectionFilter] = useState<ChangePointDirection | ''>('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [triageNote, setTriageNote] = useState('')

  const filters: ChangePointFilters = {
    status: statusFilter || undefined,
    direction: directionFilter || undefined,
    limit: 100,
  }

  const { data: changePoints, isLoading, error } = useChangePoints(filters)
  const triageMutation = useTriageChangePoint()
  const bulkTriageMutation = useBulkTriageChangePoints()

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleSelectAll = useCallback(() => {
    if (!changePoints) return
    setSelectedIds(prev =>
      prev.size === changePoints.length
        ? new Set()
        : new Set(changePoints.map(cp => cp.id)),
    )
  }, [changePoints])

  const handleTriage = useCallback(
    (id: string, status: 'acknowledged' | 'hidden') => {
      triageMutation.mutate({ id, input: { status } })
    },
    [triageMutation],
  )

  const handleBulkTriage = useCallback(
    (status: 'acknowledged' | 'hidden') => {
      if (selectedIds.size === 0) return
      bulkTriageMutation.mutate(
        {
          ids: [...selectedIds],
          status,
          triageNote: triageNote || undefined,
        },
        { onSuccess: () => { setSelectedIds(new Set()); setTriageNote('') } },
      )
    },
    [selectedIds, triageNote, bulkTriageMutation],
  )

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1
          className="text-xl font-semibold"
          style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
        >
          Change Points
        </h1>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value as ChangePointStatus | '')}
          className="bg-popover border border-border rounded px-3 py-1.5 text-sm text-foreground"
        >
          {STATUS_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <select
          value={directionFilter}
          onChange={e => setDirectionFilter(e.target.value as ChangePointDirection | '')}
          className="bg-popover border border-border rounded px-3 py-1.5 text-sm text-foreground"
        >
          {DIRECTION_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        {selectedIds.size > 0 && (
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-sm text-muted-foreground">
              {selectedIds.size} selected
            </span>
            <input
              type="text"
              placeholder="Triage note (optional)"
              value={triageNote}
              onChange={e => setTriageNote(e.target.value)}
              className="bg-popover border border-border rounded px-2 py-1 text-sm w-48"
            />
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleBulkTriage('acknowledged')}
              disabled={bulkTriageMutation.isPending}
            >
              <Check className="w-3 h-3 mr-1" />
              Acknowledge
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleBulkTriage('hidden')}
              disabled={bulkTriageMutation.isPending}
            >
              <EyeOff className="w-3 h-3 mr-1" />
              Hide
            </Button>
          </div>
        )}
      </div>

      {/* Table */}
      {isLoading && <p className="text-muted-foreground text-sm">Loading...</p>}
      {error && <p className="text-red-400 text-sm">Failed to load change points</p>}
      {changePoints && changePoints.length === 0 && (
        <p className="text-muted-foreground text-sm py-8 text-center">No change points found</p>
      )}
      {changePoints && changePoints.length > 0 && (
        <div className="border border-border rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-popover/50">
                <th className="px-3 py-2 text-left w-8">
                  <input
                    type="checkbox"
                    checked={selectedIds.size === changePoints.length}
                    onChange={toggleSelectAll}
                    className="rounded"
                  />
                </th>
                <th className="px-3 py-2 text-left text-muted-foreground font-medium">Status</th>
                <th className="px-3 py-2 text-left text-muted-foreground font-medium">Direction</th>
                <th className="px-3 py-2 text-left text-muted-foreground font-medium">Metric</th>
                <th className="px-3 py-2 text-left text-muted-foreground font-medium">SLO</th>
                <th className="px-3 py-2 text-right text-muted-foreground font-medium">Magnitude</th>
                <th className="px-3 py-2 text-left text-muted-foreground font-medium">Detected</th>
                <th className="px-3 py-2 text-left text-muted-foreground font-medium">Triage</th>
                <th className="px-3 py-2 text-right text-muted-foreground font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {changePoints.map(cp => (
                <ChangePointRow
                  key={cp.id}
                  changePoint={cp}
                  selected={selectedIds.has(cp.id)}
                  onToggleSelect={toggleSelect}
                  onTriage={handleTriage}
                  isPending={triageMutation.isPending}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function ChangePointRow({
  changePoint,
  selected,
  onToggleSelect,
  onTriage,
  isPending,
}: {
  changePoint: ChangePoint
  selected: boolean
  onToggleSelect: (id: string) => void
  onTriage: (id: string, status: 'acknowledged' | 'hidden') => void
  isPending: boolean
}) {
  return (
    <tr className="border-b border-border last:border-b-0 hover:bg-popover/30 transition-colors">
      <td className="px-3 py-2">
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggleSelect(changePoint.id)}
          className="rounded"
        />
      </td>
      <td className="px-3 py-2">
        <StatusBadge status={changePoint.status} />
      </td>
      <td className="px-3 py-2">
        <DirectionIndicator direction={changePoint.direction} />
      </td>
      <td className="px-3 py-2 font-mono text-xs">{changePoint.metricName}</td>
      <td className="px-3 py-2 font-mono text-xs">{changePoint.sloName}</td>
      <td className="px-3 py-2 text-right tabular-nums">
        <span className={changePoint.direction === 'regression' ? 'text-red-400' : 'text-green-400'}>
          {formatPct(changePoint.changeRelativePct)}
        </span>
        <span className="text-muted-foreground ml-1 text-xs">
          ({changePoint.changeAbsolute.toFixed(2)})
        </span>
      </td>
      <td className="px-3 py-2 text-xs text-muted-foreground tabular-nums">
        {formatDate(changePoint.createdAt)}
      </td>
      <td className="px-3 py-2 text-xs">
        {changePoint.triageAuthor && (
          <span className="text-muted-foreground">{changePoint.triageAuthor}</span>
        )}
        {changePoint.triageNote && (
          <span className="text-muted-foreground ml-1" title={changePoint.triageNote}>
            — {changePoint.triageNote.length > 30
              ? `${changePoint.triageNote.slice(0, 30)}...`
              : changePoint.triageNote}
          </span>
        )}
      </td>
      <td className="px-3 py-2 text-right">
        {changePoint.status === 'unprocessed' && (
          <div className="flex items-center justify-end gap-1">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onTriage(changePoint.id, 'acknowledged')}
              disabled={isPending}
              title="Acknowledge"
            >
              <Check className="w-3.5 h-3.5" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onTriage(changePoint.id, 'hidden')}
              disabled={isPending}
              title="Hide (false positive)"
            >
              <EyeOff className="w-3.5 h-3.5" />
            </Button>
          </div>
        )}
      </td>
    </tr>
  )
}
