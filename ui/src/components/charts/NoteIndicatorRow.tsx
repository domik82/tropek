// ui/src/components/charts/NoteIndicatorRow.tsx
import { useState } from 'react'
import { MessageSquareWarning } from 'lucide-react'
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
  const [hovered, setHovered] = useState(false)
  const { data: ev } = useEvaluationDetail(hovered ? info.evalId : undefined)

  const latest = ev?.annotations?.[ev.annotations.length - 1]

  return (
    <>
      <button
        onClick={() => onIndicatorClick?.(slot)}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        className="text-amber-400 hover:text-amber-300 transition-colors p-1.5 -m-1.5"
      >
        <MessageSquareWarning className="w-3.5 h-3.5" />
      </button>
      {hovered && (
        <div className="absolute bottom-full mb-1.5 z-30 w-56 bg-popover border border-amber-700/40 rounded-lg shadow-xl p-2.5 pointer-events-none"
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
            <p className="text-[10px] text-muted-foreground italic">Loading…</p>
          )}
        </div>
      )}
    </>
  )
}

export function NoteIndicatorRow({ columns, notedColumns, onIndicatorClick }: Props) {
  if (notedColumns.size === 0) return null

  return (
    <div className="flex items-center -mb-2" style={{ paddingLeft: 210, paddingRight: 20 }}>
      {columns.map(col => {
        const info = notedColumns.get(col)
        return (
          <div key={col} className="flex-1 flex justify-center relative">
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
