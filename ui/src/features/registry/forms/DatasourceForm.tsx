import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useCreateDatasource, useUpdateDatasource } from '@/features/datasources/hooks'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import { tagsToRows, rowsToTags } from './tagUtils'
import type { TagRow } from './tagUtils'
import type { DataSource } from '@/features/datasources/types'

const createSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  display_name: z.string().optional(),
  adapter_type: z.string().min(1, 'Adapter type is required'),
  adapter_url: z.string().min(1, 'Adapter URL is required'),
  token: z.string().optional(),
})

const editSchema = z.object({
  display_name: z.string().optional(),
  adapter_url: z.string().min(1, 'Adapter URL is required'),
  token: z.string().optional(),
})

type CreateValues = z.infer<typeof createSchema>
type EditValues = z.infer<typeof editSchema>

interface DatasourceFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  editFrom?: DataSource
}

export function DatasourceForm({ open, onOpenChange, editFrom }: DatasourceFormProps) {
  const isEdit = !!editFrom

  const createForm = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: '', display_name: '', adapter_type: '', adapter_url: '', token: '' },
  })

  const editForm = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      display_name: editFrom?.display_name ?? '',
      adapter_url: editFrom?.adapter_url ?? '',
      token: '',
    },
  })

  const form = isEdit ? editForm : createForm
  const { register, handleSubmit, formState: { errors }, reset } = form

  // Reset form when editFrom changes
  useEffect(() => {
    if (editFrom) {
      editForm.reset({
        display_name: editFrom.display_name ?? '',
        adapter_url: editFrom.adapter_url,
        token: '',
      })
      setTagRows(tagsToRows(editFrom.tags))
    }
  }, [editFrom]) // eslint-disable-line react-hooks/exhaustive-deps

  const [tagRows, setTagRows] = useTagRows(editFrom?.tags ? tagsToRows(editFrom.tags) : [])

  const createMutation = useCreateDatasource()
  const updateMutation = useUpdateDatasource()
  const isPending = createMutation.isPending || updateMutation.isPending

  if (!open) return null

  function onSubmit(values: CreateValues | EditValues) {
    const tags = rowsToTags(tagRows)
    const tagsPayload = Object.keys(tags).length > 0 ? tags : undefined

    if (isEdit) {
      const v = values as EditValues
      const payload: Parameters<typeof updateMutation.mutate>[0] = {
        name: editFrom!.name,
        adapter_url: v.adapter_url || undefined,
        display_name: v.display_name || undefined,
        tags: tagsPayload,
      }
      if (v.token?.trim()) {
        payload.token = v.token
      }
      updateMutation.mutate(payload, {
        onSuccess: () => { reset(); onOpenChange(false) },
      })
    } else {
      const v = values as CreateValues
      createMutation.mutate(
        {
          name: v.name,
          display_name: v.display_name || undefined,
          adapter_type: v.adapter_type,
          adapter_url: v.adapter_url,
          token: v.token || undefined,
          tags: tagsPayload,
        },
        { onSuccess: () => { reset(); onOpenChange(false) } },
      )
    }
  }

  const fieldErrors = isEdit
    ? (errors as typeof editForm.formState.errors)
    : (errors as typeof createForm.formState.errors)

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
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="p-4 space-y-3">
            {/* Name (create only) */}
            {!isEdit && (
              <div>
                <label htmlFor="ds-name" className="block text-xs text-muted-foreground mb-1">
                  Name
                </label>
                <Input id="ds-name" {...(createForm.register('name'))} placeholder="my-datasource" />
                {'name' in fieldErrors && fieldErrors.name && (
                  <p className="text-xs text-red-400 mt-0.5">{fieldErrors.name.message}</p>
                )}
              </div>
            )}
            {isEdit && (
              <div>
                <label htmlFor="ds-name" className="block text-xs text-muted-foreground mb-1">
                  Name
                </label>
                <Input id="ds-name" value={editFrom!.name} disabled />
              </div>
            )}

            {/* Display Name */}
            <div>
              <label htmlFor="ds-display-name" className="block text-xs text-muted-foreground mb-1">
                Display Name
              </label>
              <Input id="ds-display-name" {...register('display_name')} placeholder="My Datasource" />
            </div>

            {/* Adapter Type (create only) */}
            {!isEdit && (
              <div>
                <label htmlFor="ds-adapter-type" className="block text-xs text-muted-foreground mb-1">
                  Adapter Type
                </label>
                <Input id="ds-adapter-type" {...createForm.register('adapter_type')} placeholder="prometheus" />
                {'adapter_type' in fieldErrors && fieldErrors.adapter_type && (
                  <p className="text-xs text-red-400 mt-0.5">{fieldErrors.adapter_type.message}</p>
                )}
              </div>
            )}
            {isEdit && (
              <div>
                <label htmlFor="ds-adapter-type" className="block text-xs text-muted-foreground mb-1">
                  Adapter Type
                </label>
                <Input id="ds-adapter-type" value={editFrom!.adapter_type} disabled />
              </div>
            )}

            {/* Adapter URL */}
            <div>
              <label htmlFor="ds-adapter-url" className="block text-xs text-muted-foreground mb-1">
                Adapter URL
              </label>
              <Input id="ds-adapter-url" {...register('adapter_url')} placeholder="http://adapter:8081" />
              {fieldErrors.adapter_url && (
                <p className="text-xs text-red-400 mt-0.5">{fieldErrors.adapter_url.message}</p>
              )}
            </div>

            {/* Token */}
            <div>
              <label htmlFor="ds-token" className="block text-xs text-muted-foreground mb-1">
                Token
              </label>
              <Input
                id="ds-token"
                type="password"
                {...register('token')}
                placeholder={isEdit ? '••••••••' : 'Bearer token (optional)'}
              />
            </div>

            {/* Tags */}
            <TagRowEditor rows={tagRows} onChange={setTagRows} />
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-2 px-4 py-3 border-t border-border bg-muted/20">
            <Button size="xs" variant="outline" type="button" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button size="xs" type="submit" disabled={isPending}>
              {isPending ? 'Saving…' : isEdit ? 'Save' : 'Create'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

function useTagRows(initial: TagRow[]): [TagRow[], (rows: TagRow[]) => void] {
  const [rows, setRows] = useState<TagRow[]>(initial)
  return [rows, setRows]
}

function TagRowEditor({ rows, onChange }: { rows: TagRow[]; onChange: (rows: TagRow[]) => void }) {
  function handleAdd() {
    onChange([...rows, { key: '', value: '' }])
  }

  function handleRemove(index: number) {
    onChange(rows.filter((_, i) => i !== index))
  }

  function handleChange(index: number, field: 'key' | 'value', val: string) {
    onChange(rows.map((row, i) => (i === index ? { ...row, [field]: val } : row)))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-muted-foreground">Tags</span>
        <button
          type="button"
          onClick={handleAdd}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary"
        >
          <Plus className="size-3" /> Add
        </button>
      </div>
      <div className="space-y-1.5">
        {rows.map((row, i) => (
          <div key={i} className="flex gap-1.5 items-center">
            <Input
              value={row.key}
              onChange={e => handleChange(i, 'key', e.target.value)}
              placeholder="key"
              className="flex-1"
            />
            <Input
              value={row.value}
              onChange={e => handleChange(i, 'value', e.target.value)}
              placeholder="value"
              className="flex-1"
            />
            <button
              type="button"
              aria-label="remove tag"
              onClick={() => handleRemove(i)}
              className="text-muted-foreground hover:text-red-400"
            >
              <X className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

