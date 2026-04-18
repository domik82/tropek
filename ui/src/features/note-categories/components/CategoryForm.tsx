import { useState } from 'react'
import { PALETTE_OPTIONS, paletteOf } from '../palette'
import type { CategoryColor, NoteCategory, NoteCategoryInput } from '../domain'

interface Props {
  initial?: NoteCategory
  disableName?: boolean
  onSubmit: (input: NoteCategoryInput) => void
  onCancel: () => void
  busy?: boolean
}

export function CategoryForm({ initial, disableName, onSubmit, onCancel, busy }: Props) {
  const [name, setName] = useState(initial?.name ?? '')
  const [label, setLabel] = useState(initial?.label ?? '')
  const [color, setColor] = useState<CategoryColor>(initial?.color ?? 'sky')
  const [showOnGraph, setShowOnGraph] = useState(initial?.showOnGraph ?? true)
  const [error, setError] = useState<string | null>(null)

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!/^[a-z][a-z0-9-]*$/.test(name)) {
      setError('name must be lowercase-hyphenated')
      return
    }
    if (label.length === 0 || label.length > 12) {
      setError('label must be 1–12 chars')
      return
    }
    setError(null)
    onSubmit({ name, label, color, showOnGraph })
  }

  return (
    <form onSubmit={submit} className="bg-popover border border-border rounded-md p-3 space-y-2">
      <label className="block text-xs">
        Name
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          disabled={disableName || busy}
          className="w-full bg-surface-sunken border border-border rounded px-2 py-1 text-sm"
        />
      </label>
      <label className="block text-xs">
        Label (≤12 chars)
        <input
          value={label}
          maxLength={12}
          onChange={e => setLabel(e.target.value)}
          className="w-full bg-surface-sunken border border-border rounded px-2 py-1 text-sm"
        />
      </label>
      <div className="text-xs">
        Color
        <div className="flex gap-1 mt-1">
          {PALETTE_OPTIONS.map(c => {
            const p = paletteOf(c)
            return (
              <button
                type="button"
                key={c}
                onClick={() => setColor(c)}
                className={`px-2 py-0.5 rounded ${c === color ? 'ring-2 ring-primary' : ''}`}
                style={{ background: p.bg, color: p.fg }}
              >
                {c}
              </button>
            )
          })}
        </div>
      </div>
      <label className="block text-xs">
        <input
          type="checkbox"
          checked={showOnGraph}
          onChange={e => setShowOnGraph(e.target.checked)}
          className="mr-1"
        />
        Show on chart
      </label>
      {error && <p className="text-xs text-action-destructive">{error}</p>}
      <div className="flex gap-2 justify-end">
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="text-xs text-muted-foreground"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={busy}
          className="text-xs px-2 py-1 bg-primary text-primary-foreground rounded"
        >
          Save
        </button>
      </div>
    </form>
  )
}
