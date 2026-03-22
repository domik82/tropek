import { useState } from 'react'
import { Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useCreateDatasource, useUpdateDatasource } from '@/features/datasources/hooks'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import type { DataSource } from '@/features/datasources/types'

interface DatasourceFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  editFrom?: DataSource
}

interface TagRow {
  key: string
  value: string
}

function tagsToRows(tags: Record<string, string>): TagRow[] {
  return Object.entries(tags).map(([key, value]) => ({ key, value }))
}

function rowsToTags(rows: TagRow[]): Record<string, string> {
  const result: Record<string, string> = {}
  for (const row of rows) {
    if (row.key.trim()) {
      result[row.key.trim()] = row.value
    }
  }
  return result
}

export function DatasourceForm({ open, onOpenChange, editFrom }: DatasourceFormProps) {
  const isEdit = !!editFrom

  const [name, setName] = useState(editFrom?.name ?? '')
  const [displayName, setDisplayName] = useState(editFrom?.display_name ?? '')
  const [adapterType, setAdapterType] = useState(editFrom?.adapter_type ?? '')
  const [adapterUrl, setAdapterUrl] = useState(editFrom?.adapter_url ?? '')
  const [token, setToken] = useState('')
  const [tagRows, setTagRows] = useState<TagRow[]>(
    editFrom?.tags ? tagsToRows(editFrom.tags) : []
  )

  const createMutation = useCreateDatasource()
  const updateMutation = useUpdateDatasource()

  const isPending = createMutation.isPending || updateMutation.isPending

  if (!open) return null

  function handleAddTag() {
    setTagRows(prev => [...prev, { key: '', value: '' }])
  }

  function handleRemoveTag(index: number) {
    setTagRows(prev => prev.filter((_, i) => i !== index))
  }

  function handleTagChange(index: number, field: 'key' | 'value', val: string) {
    setTagRows(prev => prev.map((row, i) => i === index ? { ...row, [field]: val } : row))
  }

  function handleSubmit() {
    const tags = rowsToTags(tagRows)

    if (isEdit) {
      const payload: Parameters<typeof updateMutation.mutate>[0] = {
        name: editFrom!.name,
        adapter_url: adapterUrl || undefined,
        display_name: displayName || undefined,
        tags: Object.keys(tags).length > 0 ? tags : undefined,
      }
      if (token.trim()) {
        payload.token = token
      }
      updateMutation.mutate(payload, {
        onSuccess: () => onOpenChange(false),
      })
    } else {
      createMutation.mutate(
        {
          name,
          display_name: displayName || undefined,
          adapter_type: adapterType,
          adapter_url: adapterUrl,
          token: token || undefined,
          tags: Object.keys(tags).length > 0 ? tags : undefined,
        },
        {
          onSuccess: () => onOpenChange(false),
        }
      )
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-md bg-popover border border-border rounded-xl overflow-hidden shadow-xl"
        style={{ fontFamily: SANS_SERIF }}
      >
        {/* Accent strip */}
        <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.ds }} />

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-foreground">
            {isEdit ? `Edit Datasource: ${editFrom!.name}` : 'New Datasource'}
          </h2>
          <button
            type="button"
            aria-label="Close"
            className="text-muted-foreground hover:text-foreground"
            onClick={() => onOpenChange(false)}
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Form body */}
        <div className="p-4 space-y-3">
          {/* Name */}
          <div>
            <label htmlFor="ds-name" className="block text-xs text-muted-foreground mb-1">
              Name
            </label>
            <Input
              id="ds-name"
              value={name}
              onChange={e => setName(e.target.value)}
              disabled={isEdit}
              placeholder="my-datasource"
            />
          </div>

          {/* Display Name */}
          <div>
            <label htmlFor="ds-display-name" className="block text-xs text-muted-foreground mb-1">
              Display Name
            </label>
            <Input
              id="ds-display-name"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder="My Datasource"
            />
          </div>

          {/* Adapter Type */}
          <div>
            <label htmlFor="ds-adapter-type" className="block text-xs text-muted-foreground mb-1">
              Adapter Type
            </label>
            <Input
              id="ds-adapter-type"
              value={adapterType}
              onChange={e => setAdapterType(e.target.value)}
              disabled={isEdit}
              placeholder="prometheus"
            />
          </div>

          {/* Adapter URL */}
          <div>
            <label htmlFor="ds-adapter-url" className="block text-xs text-muted-foreground mb-1">
              Adapter URL
            </label>
            <Input
              id="ds-adapter-url"
              value={adapterUrl}
              onChange={e => setAdapterUrl(e.target.value)}
              placeholder="http://adapter:8081"
            />
          </div>

          {/* Token */}
          <div>
            <label htmlFor="ds-token" className="block text-xs text-muted-foreground mb-1">
              Token
            </label>
            <Input
              id="ds-token"
              type="password"
              value={token}
              onChange={e => setToken(e.target.value)}
              placeholder={isEdit ? '••••••••' : 'Bearer token (optional)'}
            />
          </div>

          {/* Tags */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground">Tags</span>
              <button
                type="button"
                onClick={handleAddTag}
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary"
              >
                <Plus className="size-3" /> Add
              </button>
            </div>
            <div className="space-y-1.5">
              {tagRows.map((row, i) => (
                <div key={i} className="flex gap-1.5 items-center">
                  <Input
                    value={row.key}
                    onChange={e => handleTagChange(i, 'key', e.target.value)}
                    placeholder="key"
                    className="flex-1"
                  />
                  <Input
                    value={row.value}
                    onChange={e => handleTagChange(i, 'value', e.target.value)}
                    placeholder="value"
                    className="flex-1"
                  />
                  <button
                    type="button"
                    aria-label="remove tag"
                    onClick={() => handleRemoveTag(i)}
                    className="text-muted-foreground hover:text-red-400"
                  >
                    <X className="size-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-4 py-3 border-t border-border bg-muted/20">
          <Button size="xs" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            size="xs"
            onClick={handleSubmit}
            disabled={isPending || (!isEdit && (!name.trim() || !adapterType.trim() || !adapterUrl.trim()))}
            style={{ backgroundColor: ENTITY_COLORS.ds, color: '#fff' }}
          >
            {isPending ? 'Saving…' : isEdit ? 'Save' : 'Create'}
          </Button>
        </div>
      </div>
    </div>
  )
}
