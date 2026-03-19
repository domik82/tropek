// ui/src/components/charts/NoteIndicatorRow.tsx
import { MessageSquareWarning } from 'lucide-react'

interface Props {
  /** Ordered list of column keys (same as HeatmapChart columns) */
  columns: string[]
  /** Set of column keys that have notes */
  notedColumns: Set<string>
  /** Called when user clicks an indicator */
  onIndicatorClick?: (slot: string) => void
}

export function NoteIndicatorRow({ columns, notedColumns, onIndicatorClick }: Props) {
  if (notedColumns.size === 0) return null

  return (
    <div className="flex items-center" style={{ paddingLeft: 210, paddingRight: 20 }}>
      {columns.map(col => (
        <div key={col} className="flex-1 flex justify-center">
          {notedColumns.has(col) ? (
            <button
              onClick={() => onIndicatorClick?.(col)}
              className="text-amber-400 hover:text-amber-300 transition-colors"
              title="This evaluation has notes"
            >
              <MessageSquareWarning className="w-3.5 h-3.5" />
            </button>
          ) : (
            <span className="w-3.5 h-3.5" />
          )}
        </div>
      ))}
    </div>
  )
}
