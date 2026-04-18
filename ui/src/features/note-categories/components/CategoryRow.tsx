import { Lock, Pencil, Trash2 } from 'lucide-react'
import { paletteOf } from '../palette'
import type { NoteCategory } from '../domain'

interface Props {
  category: NoteCategory
  onToggleShow: (showOnGraph: boolean) => void
  onEdit: () => void
  onDelete: () => void
  busy?: boolean
}

export function CategoryRow({ category, onToggleShow, onEdit, onDelete, busy }: Props) {
  const p = paletteOf(category.color)
  return (
    <tr className="border-b border-border">
      <td className="px-2 py-1.5">
        <span className="inline-flex items-center gap-1.5">
          {category.name}
          {category.isSystem && <Lock className="size-3 text-muted-foreground" />}
        </span>
      </td>
      <td className="px-2 py-1.5">
        <span
          className="inline-block px-2 py-0.5 rounded text-xs"
          style={{ background: p.bg, color: p.fg }}
        >
          {category.label}
        </span>
      </td>
      <td className="px-2 py-1.5">{category.color}</td>
      <td className="px-2 py-1.5">
        <input
          type="checkbox"
          checked={category.showOnGraph}
          onChange={e => onToggleShow(e.target.checked)}
          disabled={busy}
          aria-label={`Show ${category.name} on graph`}
        />
      </td>
      <td className="px-2 py-1.5 text-right">
        <button
          onClick={onEdit}
          disabled={busy}
          className="text-muted-foreground hover:text-foreground mr-2"
          aria-label={`Edit ${category.name}`}
        >
          <Pencil className="size-4" />
        </button>
        <button
          onClick={onDelete}
          disabled={busy || category.isSystem}
          className="text-muted-foreground hover:text-action-destructive disabled:opacity-30"
          aria-label={`Delete ${category.name}`}
        >
          <Trash2 className="size-4" />
        </button>
      </td>
    </tr>
  )
}
