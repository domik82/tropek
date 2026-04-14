// ui/src/components/charts/NoteIndicatorRow.tsx
import { useState, useRef, useCallback, useMemo } from 'react'
import { MessageSquareWarning, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { Annotation } from '@/features/evaluations/domain'
import { useColumnAnnotations } from '@/features/evaluations/hooks'

export interface SlotNote {
  evalId: string
  count: number
}

export interface ColumnPosition {
  x: number
  width: number
}

interface Props {
  /** Ordered list of column keys (same as HeatmapChart columns) */
  columns: string[]
  /** Map of column key → eval info for columns that have notes */
  notedColumns: Map<string, SlotNote>
  /** Pixel position and width for each column, computed from ECharts grid */
  columnPositions: ColumnPosition[]
  /** Called when user clicks an indicator */
  onIndicatorClick?: (slot: string) => void
}

/** Collapse grouped annotations (same noteGroupId) into a single summary line. */
function TooltipNoteList({ annotations }: { annotations: Annotation[] }) {
  const entries = useMemo(() => {
    const groups = new Map<string, { name: string; count: number }>()
    const standalone: Annotation[] = []
    for (const a of annotations) {
      if (a.noteGroupId) {
        const existing = groups.get(a.noteGroupId)
        if (existing) {
          existing.count++
        } else {
          groups.set(a.noteGroupId, { name: a.noteGroupName ?? 're-evaluation', count: 1 })
        }
      } else {
        standalone.push(a)
      }
    }
    return { groups: [...groups.values()], standalone }
  }, [annotations])

  return (
    <div className="space-y-1">
      {entries.groups.map((g, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <span className="text-[10px] bg-amber-900/40 text-amber-300 px-1 py-0.5 rounded shrink-0">
            re-eval
          </span>
          <span className="text-xs text-foreground/80 truncate">{g.name}</span>
          <span className="text-[10px] text-muted-foreground/60 shrink-0">({g.count})</span>
        </div>
      ))}
      {entries.standalone.map(a => (
        <div key={a.id}>
          <p className="text-xs text-foreground line-clamp-2">{a.content}</p>
          {a.author && (
            <p className="text-[10px] text-muted-foreground">— {a.author}</p>
          )}
        </div>
      ))}
    </div>
  )
}

function NoteIcon({ slot, info, x, width, onIndicatorClick }: {
  slot: string
  info: SlotNote
  x: number
  width: number
  onIndicatorClick?: (slot: string) => void
}) {
  const [open, setOpen] = useState(false)
  const hideTimer = useRef<ReturnType<typeof setTimeout>>(null)
  const { data: annotations, isFetching } = useColumnAnnotations(
    open ? info.evalId : undefined,
  )

  const count = annotations?.length ?? 0

  const show = useCallback(() => {
    if (hideTimer.current) clearTimeout(hideTimer.current)
    setOpen(true)
  }, [])

  const hide = useCallback(() => {
    hideTimer.current = setTimeout(() => setOpen(false), 150)
  }, [])

  // Scale icon size with column width, min 8px, max 14px
  const iconSize = Math.max(8, Math.min(14, width * 0.6))

  return (
    <div
      className="absolute flex justify-center"
      style={{ left: x, width, top: 0 }}
      onMouseEnter={show}
      onMouseLeave={hide}
    >
      <Button
        variant="ghost"
        size="icon-xs"
        onClick={() => onIndicatorClick?.(slot)}
        className="text-amber-400 hover:text-amber-300 relative"
        style={{ padding: 0, minWidth: 0, width: iconSize + 4, height: iconSize + 4 }}
      >
        <MessageSquareWarning style={{ width: iconSize, height: iconSize }} />
        {open && isFetching && (
          <Loader2 className="absolute -top-1 -right-1 text-amber-300 animate-spin" style={{ width: iconSize * 0.7, height: iconSize * 0.7 }} />
        )}
      </Button>
      {open && (
        <div className="absolute bottom-full mb-1.5 z-30 left-1/2 -translate-x-1/2 w-64 bg-popover border border-amber-700/40 rounded-lg shadow-xl p-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-amber-400 text-xs">⚑</span>
            <span className="text-[10px] text-muted-foreground">
              {annotations ? `${count} note${count !== 1 ? 's' : ''}` : 'Notes'}
            </span>
          </div>
          {annotations ? (
            <TooltipNoteList annotations={annotations} />
          ) : (
            <div className="flex items-center gap-1.5">
              <Loader2 className="w-3 h-3 text-amber-400 animate-spin" />
              <span className="text-[10px] text-muted-foreground">Loading notes…</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function NoteIndicatorRow({ columns, notedColumns, columnPositions, onIndicatorClick }: Props) {
  if (notedColumns.size === 0 || columnPositions.length === 0) return null

  return (
    <div className="relative" style={{ height: 20 }}>
      {columns.map((col, i) => {
        const info = notedColumns.get(col)
        const pos = columnPositions[i]
        if (!info || !pos) return null
        return (
          <NoteIcon
            key={i}
            slot={col}
            info={info}
            x={pos.x}
            width={pos.width}
            onIndicatorClick={onIndicatorClick}
          />
        )
      })}
    </div>
  )
}
