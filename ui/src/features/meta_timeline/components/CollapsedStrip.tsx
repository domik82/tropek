import { ChevronDown, ChevronRight } from 'lucide-react'

interface CollapsedStripProps {
  itemCount: number
  expanded: boolean
  onToggle: () => void
}

export function CollapsedStrip({ itemCount, expanded, onToggle }: CollapsedStripProps) {
  const itemsText =
    itemCount === 0 ? 'no items tracked'
    : itemCount === 1 ? '1 item tracked'
    : `${itemCount} items tracked`

  return (
    <button
      type="button"
      onClick={onToggle}
      className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded transition-colors"
      aria-expanded={expanded}
      style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
    >
      {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      <span className="font-medium">Asset meta</span>
      <span>·</span>
      <span>{itemsText}</span>
      {!expanded && (
        <span className="ml-auto text-xs opacity-60">
          click to investigate changes over time
        </span>
      )}
    </button>
  )
}
