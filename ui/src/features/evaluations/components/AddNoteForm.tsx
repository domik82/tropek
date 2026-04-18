// ui/src/features/evaluations/components/AddNoteForm.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAddRunAnnotation } from '../hooks'
import {
  useNoteCategories,
  paletteOf,
  DEFAULT_CATEGORY_PALETTE,
} from '@/features/note-categories'
import { SANS_SERIF } from '@/lib/fonts'

interface Props {
  runId: string
  onClose: () => void
}

export function AddNoteForm({ runId, onClose }: Props) {
  const addAnnotation = useAddRunAnnotation(runId)
  const { data: categories = [] } = useNoteCategories()
  const [content, setContent] = useState('')
  const [author, setAuthor] = useState('')
  const [categoryId, setCategoryId] = useState<string>('')

  const defaultId = categories.find(c => c.name === 'info')?.id ?? categories[0]?.id ?? ''
  const effectiveId = categoryId || defaultId
  const selected = categories.find(c => c.id === effectiveId)
  const palette = selected ? paletteOf(selected.color) : null

  function handleSave() {
    if (!content.trim() || !effectiveId) return
    addAnnotation.mutate(
      { content, author: author || undefined, categoryId: effectiveId },
      { onSuccess: () => { setContent(''); setAuthor(''); onClose() } },
    )
  }

  const accentBg = palette?.bg ?? DEFAULT_CATEGORY_PALETTE.bg
  const accentFg = palette?.fg ?? DEFAULT_CATEGORY_PALETTE.fg

  return (
    <div className="flex justify-end">
      <div className="w-full max-w-md border border-border rounded-xl bg-popover overflow-hidden">
        <div className="h-[3px]" style={{ background: accentBg }} />
        <div className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium"
              style={{ fontFamily: SANS_SERIF, color: accentFg }}>
              Add Note
            </p>
            <button onClick={onClose}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors">
              Cancel
            </button>
          </div>

          <Input
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="Note content..."
          />

          <div className="grid grid-cols-2 gap-2">
            <Input
              value={author}
              onChange={e => setAuthor(e.target.value)}
              placeholder="Author"
              autoComplete="name"
            />
            <select
              value={effectiveId}
              onChange={e => setCategoryId(e.target.value)}
              aria-label="Category"
              className="bg-surface-sunken border border-border rounded px-2 py-1 text-sm"
              style={{ background: accentBg, color: accentFg }}
            >
              {categories.map(c => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
          </div>

          <div className="flex justify-end">
            <Button
              size="xs"
              onClick={handleSave}
              disabled={!content.trim() || !effectiveId || addAnnotation.isPending}
              style={{ background: accentBg, color: accentFg }}
            >
              {addAnnotation.isPending ? 'Saving...' : 'Save note'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
