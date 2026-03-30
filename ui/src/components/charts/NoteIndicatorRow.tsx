// ui/src/components/charts/NoteIndicatorRow.tsx
import { useState, useRef, useCallback } from 'react'
import { MessageSquareWarning, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useEvaluationDetail } from '@/features/evaluations/hooks'

export interface SlotNote {
  evalId: string
  count: number
}

interface Props {
  /** Ordered list of column keys (same as HeatmapChart columns) */
  columns: string[]
  /** Map of column key → eval info for columns that have notes */
  notedColumns: Map<string, SlotNote>
  /** Called when user clicks an indicator */
  onIndicatorClick?: (slot: string) => void
}

function NoteIcon({ slot, info, onIndicatorClick }: { slot: string; info: SlotNote; onIndicatorClick?: (slot: string) => void }) {
  const [open, setOpen] = useState(false)
  const hideTimer = useRef<ReturnType<typeof setTimeout>>(null)
  const { data: ev, isFetching } = useEvaluationDetail(open ? info.evalId : undefined)

  const latest = ev?.annotations?.[ev.annotations.length - 1]

  const show = useCallback(() => {
    if (hideTimer.current) clearTimeout(hideTimer.current)
    setOpen(true)
  }, [])

  const hide = useCallback(() => {
    hideTimer.current = setTimeout(() => setOpen(false), 150)
  }, [])

  return (
    <div onMouseEnter={show} onMouseLeave={hide}>
      <Button
        variant="ghost"
        size="icon-xs"
        onClick={() => onIndicatorClick?.(slot)}
        className="text-amber-400 hover:text-amber-300 relative -m-1.5"
      >
        <MessageSquareWarning className="w-3.5 h-3.5" />
        {open && isFetching && (
          <Loader2 className="w-2.5 h-2.5 absolute -top-1 -right-1 text-amber-300 animate-spin" />
        )}
      </Button>
      {open && (
        <div className="absolute bottom-full mb-1.5 z-30 w-56 bg-popover border border-amber-700/40 rounded-lg shadow-xl p-2.5"
          style={{ left: '50%', transform: 'translateX(-50%)' }}
        >
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-amber-400 text-xs">⚑</span>
            <span className="text-[10px] text-muted-foreground">
              {info.count} note{info.count !== 1 ? 's' : ''}
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

export function NoteIndicatorRow({ columns, notedColumns, onIndicatorClick }: Props) {
  if (notedColumns.size === 0) return null

  return (
    <div className="flex items-center -mb-2" style={{ paddingLeft: 210, paddingRight: 20 }}>
      {columns.map((col, i) => {
        const info = notedColumns.get(col)
        return (
          <div key={i} className="flex-1 flex justify-center relative">
            {info ? (
              <NoteIcon slot={col} info={info} onIndicatorClick={onIndicatorClick} />
            ) : (
              <span className="w-3.5 h-3.5" />
            )}
          </div>
        )
      })}
    </div>
  )
}
