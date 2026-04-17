import { useState } from 'react'
import {
  useNoteCategories,
  useCreateNoteCategory,
  useUpdateNoteCategory,
  useDeleteNoteCategory,
} from '../hooks'
import type { NoteCategory } from '../domain'
import { CategoryRow } from './CategoryRow'
import { CategoryForm } from './CategoryForm'

export function CategoryManagementPage() {
  const { data: categories = [], isLoading } = useNoteCategories()
  const createMut = useCreateNoteCategory()
  const updateMut = useUpdateNoteCategory()
  const deleteMut = useDeleteNoteCategory()

  const [editing, setEditing] = useState<NoteCategory | null>(null)
  const [creating, setCreating] = useState(false)

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Note categories</h1>
        <button
          className="text-xs px-2 py-1 border border-border rounded"
          onClick={() => setCreating(true)}
        >
          + Add category
        </button>
      </div>

      {creating && (
        <CategoryForm
          onSubmit={input => createMut.mutate(input, { onSuccess: () => setCreating(false) })}
          onCancel={() => setCreating(false)}
          busy={createMut.isPending}
        />
      )}

      {editing && (
        <CategoryForm
          initial={editing}
          disableName={editing.isSystem}
          onSubmit={input =>
            updateMut.mutate(
              { id: editing.id, patch: input },
              { onSuccess: () => setEditing(null) },
            )
          }
          onCancel={() => setEditing(null)}
          busy={updateMut.isPending}
        />
      )}

      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-muted-foreground">
            <th className="px-2 py-1">Name</th>
            <th className="px-2 py-1">Label</th>
            <th className="px-2 py-1">Color</th>
            <th className="px-2 py-1">On graph</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {categories.map(c => (
            <CategoryRow
              key={c.id}
              category={c}
              onToggleShow={v => updateMut.mutate({ id: c.id, patch: { showOnGraph: v } })}
              onEdit={() => setEditing(c)}
              onDelete={() => {
                if (confirm(`Delete '${c.name}'? Notes using it move to 'info'.`))
                  deleteMut.mutate(c.id)
              }}
              busy={updateMut.isPending || deleteMut.isPending}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
