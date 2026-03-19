// ui/src/components/charts/NoteIndicatorRow.tsx
import { useState } from 'react'
import { MessageSquareWarning } from 'lucide-react'

export interface NoteInfo {
  count: number
  content: string
  author: string | null
}

interface Props {
  /** Ordered list of column keys (same as HeatmapChart columns) */
  columns: string[]
  /** Map of column key → note info for columns that have notes */
  notedColumns: Map<string, NoteInfo>
  /** Called when user clicks an indicator */
  onIndicatorClick?: (slot: string) => void
}

export function NoteIndicatorRow({ columns, notedColumns, onIndicatorClick }: Props) {
  const [hoveredCol, setHoveredCol] = useState<string | null>(null)

  if (notedColumns.size === 0) return null

  return (
    <div className="flex items-center -mb-2" style={{ paddingLeft: 210, paddingRight: 20 }}>
      {columns.map(col => {
        const info = notedColumns.get(col)
        return (
          <div key={col} className="flex-1 flex justify-center relative">
            {info ? (
              <>
                <button
                  onClick={() => onIndicatorClick?.(col)}
                  onMouseEnter={() => setHoveredCol(col)}
                  onMouseLeave={() => setHoveredCol(null)}
                  className="text-amber-400 hover:text-amber-300 transition-colors"
                >
                  <MessageSquareWarning className="w-3.5 h-3.5" />
                </button>
                {hoveredCol === col && (
                  <div className="absolute bottom-full mb-1.5 z-30 w-56 bg-popover border border-border rounded-lg shadow-xl p-2.5 pointer-events-none"
                    style={{ left: '50%', transform: 'translateX(-50%)' }}
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="text-amber-400 text-xs">⚑</span>
                      <span className="text-[10px] text-muted-foreground">
                        {info.count} note{info.count !== 1 ? 's' : ''}
                      </span>
                    </div>
                    <p className="text-xs text-foreground/80 line-clamp-3">{info.content}</p>
                    {info.author && (
                      <p className="text-[10px] text-muted-foreground mt-1">— {info.author}</p>
                    )}
                  </div>
                )}
              </>
            ) : (
              <span className="w-3.5 h-3.5" />
            )}
          </div>
        )
      })}
    </div>
  )
}
