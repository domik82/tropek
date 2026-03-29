// ui/src/components/labels/LabelChips.tsx
import { useState } from 'react'

interface Props {
  labels: Record<string, string>
  maxVisible?: number
  size?: 'normal' | 'small'
  onEdit?: () => void
}

export function LabelChips({ labels, maxVisible = 3, size = 'normal', onEdit }: Props) {
  const [expanded, setExpanded] = useState(false)
  const entries = Object.entries(labels)

  if (entries.length === 0) {
    return (
      <span className="text-muted-foreground text-sm italic">
        No labels
        {onEdit && (
          <button
            onClick={onEdit}
            className="ml-2 px-2 py-0.5 text-xs rounded border border-action-primary-border bg-action-primary-bg text-action-primary hover:bg-action-primary-hover"
          >
            + Add Labels
          </button>
        )}
      </span>
    )
  }

  const visible = expanded ? entries : entries.slice(0, maxVisible)
  const remaining = entries.length - maxVisible

  const chipClass = size === 'small'
    ? 'text-[10px] px-1.5 py-0.5'
    : 'text-[11px] px-2 py-0.5'

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {visible.map(([key, value]) => (
        <span
          key={key}
          className={`inline-flex items-center gap-0.5 bg-card border border-border rounded font-mono ${chipClass}`}
        >
          <span className="text-label-key">{key}</span>
          <span className="text-muted-foreground">=</span>
          <span className="text-foreground">{value}</span>
        </span>
      ))}

      {!expanded && remaining > 0 && (
        <button
          onClick={() => setExpanded(true)}
          className={`inline-flex items-center rounded-full border border-action-primary-border bg-action-primary-bg text-action-primary cursor-pointer hover:bg-action-primary-hover ${chipClass}`}
        >
          +{remaining} more
        </button>
      )}

      {expanded && entries.length > maxVisible && (
        <button
          onClick={() => setExpanded(false)}
          className="text-link text-xs cursor-pointer hover:underline"
        >
          show less
        </button>
      )}

      {onEdit && (
        <button
          onClick={onEdit}
          className={`inline-flex items-center rounded border border-action-primary-border bg-action-primary-bg text-action-primary cursor-pointer hover:bg-action-primary-hover ${chipClass}`}
        >
          Edit Labels
        </button>
      )}
    </div>
  )
}
