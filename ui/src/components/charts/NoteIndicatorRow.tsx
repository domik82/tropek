// ui/src/components/charts/NoteIndicatorRow.tsx
import { useState, useRef, useCallback } from 'react'
import { MessageSquareWarning, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
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

  const latest = annotations?.[annotations.length - 1]
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
        <div className="absolute bottom-full mb-1.5 z-30 left-1/2 -translate-x-1/2 w-56 bg-popover border border-amber-700/40 rounded-lg shadow-xl p-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-amber-400 text-xs">⚑</span>
            <span className="text-[10px] text-muted-foreground">
              {annotations ? `${count} note${count !== 1 ? 's' : ''}` : 'Notes'}
            </span>
          </div>
          {latest ? (
            <>
              <p className="text-xs text-foreground line-clamp-3">{latest.content}</p>
              {latest.author && (
                <p className="text-[10px] text-muted-foreground mt-1">— {latest.author}</p>
              )}
            </>
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
