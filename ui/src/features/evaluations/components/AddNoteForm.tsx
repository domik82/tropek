// ui/src/features/evaluations/components/AddNoteForm.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAddRunAnnotation } from '../hooks'
import { useNoteCategories, paletteOf } from '@/features/note-categories'
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

  return (
    <div className="flex justify-end">
      <div className="w-full max-w-md border border-amber-700/40 rounded-xl bg-popover overflow-hidden">
        <div className="h-[3px] bg-amber-500" />
        <div className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-amber-400"
              style={{ fontFamily: SANS_SERIF }}>
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
              style={palette ? { background: palette.bg, color: palette.fg } : undefined}
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
              className="bg-amber-500 text-black hover:bg-amber-400"
            >
              {addAnnotation.isPending ? 'Saving...' : 'Save note'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
