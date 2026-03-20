// ui/src/features/evaluations/components/AddNoteForm.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAddAnnotation } from '../hooks'

interface Props {
  evalId: string
  onClose: () => void
}

export function AddNoteForm({ evalId, onClose }: Props) {
  const addAnnotation = useAddAnnotation(evalId)
  const [content, setContent] = useState('')
  const [author, setAuthor] = useState('')
  const [category, setCategory] = useState('')

  function handleSave() {
    if (!content.trim()) return
    addAnnotation.mutate(
      { content, author: author || undefined, category: category || undefined },
      { onSuccess: () => { setContent(''); setAuthor(''); setCategory(''); onClose() } },
    )
  }

  return (
    <div className="flex justify-end">
      <div className="w-full max-w-md border border-amber-700/40 rounded-xl bg-popover overflow-hidden">
        {/* Amber accent strip */}
        <div className="h-[3px] bg-amber-500" />
        <div className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-amber-400"
              style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}>
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
            />
            <Input
              value={category}
              onChange={e => setCategory(e.target.value)}
              placeholder="Category"
            />
          </div>

          <div className="flex justify-end">
            <Button
              size="xs"
              onClick={handleSave}
              disabled={!content.trim() || addAnnotation.isPending}
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
