import { useState, useEffect } from 'react'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useCreateSli } from '@/features/slis/hooks'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import { tagsToRows, rowsToTags } from './tagUtils'
import type { TagRow } from './tagUtils'
import type { SliDefinition } from '@/features/slis/types'

const schema = z.object({
  name: z.string().min(1, 'Name is required'),
  display_name: z.string().optional(),
  adapter_type: z.string().min(1, 'Adapter type is required'),
  author: z.string().optional(),
  notes: z.string().optional(),
  indicators: z.array(z.object({
    name: z.string().min(1, 'Indicator name is required'),
    query: z.string().min(1, 'Query is required'),
  })).min(1, 'At least one indicator is required'),
})

type FormValues = z.infer<typeof schema>

interface SliFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  editFrom?: SliDefinition
  defaultAdapterType?: string
}

function indicatorsToRows(indicators: Record<string, string>): { name: string; query: string }[] {
  return Object.entries(indicators).map(([name, query]) => ({ name, query }))
}

function rowsToIndicators(rows: { name: string; query: string }[]): Record<string, string> {
  const result: Record<string, string> = {}
  for (const row of rows) {
    if (row.name.trim()) {
      result[row.name.trim()] = row.query
    }
  }
  return result
}

export function SliForm({ open, onOpenChange, editFrom, defaultAdapterType }: SliFormProps) {
  const isNewVersion = !!editFrom

  const { register, handleSubmit, control, formState: { errors }, reset } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: editFrom?.name ?? '',
      display_name: editFrom?.display_name ?? '',
      adapter_type: editFrom?.adapter_type ?? defaultAdapterType ?? '',
      author: editFrom?.author ?? '',
      notes: editFrom?.notes ?? '',
      indicators: editFrom?.indicators ? indicatorsToRows(editFrom.indicators) : [],
    },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'indicators' })

  const [tagRows, setTagRows] = useState<TagRow[]>(
    editFrom?.tags ? tagsToRows(editFrom.tags) : [],
  )

  // Reset form when editFrom changes
  useEffect(() => {
    if (editFrom) {
      reset({
        name: editFrom.name,
        display_name: editFrom.display_name ?? '',
        adapter_type: editFrom.adapter_type,
        author: editFrom.author ?? '',
        notes: editFrom.notes ?? '',
        indicators: indicatorsToRows(editFrom.indicators),
      })
      setTagRows(tagsToRows(editFrom.tags))
    }
  }, [editFrom, reset])

  const createMutation = useCreateSli()
  const isPending = createMutation.isPending

  if (!open) return null

  function onSubmit(values: FormValues) {
    const tags = rowsToTags(tagRows)
    createMutation.mutate(
      {
        name: values.name,
        display_name: values.display_name || undefined,
        adapter_type: values.adapter_type,
        indicators: rowsToIndicators(values.indicators),
        notes: values.notes || undefined,
        author: values.author || undefined,
        tags: Object.keys(tags).length > 0 ? tags : undefined,
      },
      { onSuccess: () => { reset(); onOpenChange(false) } },
    )
  }

  const title = isNewVersion ? `New Version of: ${editFrom!.name}` : 'New SLI'
  const submitLabel = isPending ? 'Saving…' : isNewVersion ? 'Create Version' : 'Create'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-lg bg-popover border border-border rounded-xl overflow-hidden shadow-xl"
        style={{ fontFamily: SANS_SERIF }}
      >
        {/* Accent strip */}
        <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.sli }} />

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-foreground">{title}</h2>
          <button
            type="button"
            aria-label="Close"
            className="text-muted-foreground hover:text-foreground"
            onClick={() => onOpenChange(false)}
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Form body (scrollable) */}
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="p-4 space-y-3 max-h-[70vh] overflow-y-auto">
            {/* Name */}
            <div>
              <label htmlFor="sli-name" className="block text-xs text-muted-foreground mb-1">
                Name
              </label>
              <Input
                id="sli-name"
                {...register('name')}
                disabled={isNewVersion}
                placeholder="my-sli"
              />
              {errors.name && (
                <p className="text-xs text-destructive-form-text mt-0.5">{errors.name.message}</p>
              )}
            </div>

            {/* Display Name */}
            <div>
              <label htmlFor="sli-display-name" className="block text-xs text-muted-foreground mb-1">
                Display Name
              </label>
              <Input id="sli-display-name" {...register('display_name')} placeholder="My SLI" />
            </div>

            {/* Adapter Type */}
            <div>
              <label htmlFor="sli-adapter-type" className="block text-xs text-muted-foreground mb-1">
                Adapter Type
              </label>
              <Input
                id="sli-adapter-type"
                {...register('adapter_type')}
                placeholder="prometheus"
              />
              {errors.adapter_type && (
                <p className="text-xs text-destructive-form-text mt-0.5">{errors.adapter_type.message}</p>
              )}
            </div>

            {/* Author */}
            <div>
              <label htmlFor="sli-author" className="block text-xs text-muted-foreground mb-1">
                Author
              </label>
              <Input id="sli-author" {...register('author')} placeholder="your-name" />
            </div>

            {/* Notes */}
            <div>
              <label htmlFor="sli-notes" className="block text-xs text-muted-foreground mb-1">
                Notes
              </label>
              <Input id="sli-notes" {...register('notes')} placeholder="Optional notes" />
            </div>

            {/* Indicators */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-muted-foreground">Indicators</span>
                <button
                  type="button"
                  aria-label="Add indicator"
                  onClick={() => append({ name: '', query: '' })}
                  className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary"
                >
                  <Plus className="size-3" /> Add indicator
                </button>
              </div>
              {errors.indicators?.root && (
                <p className="text-xs text-destructive-form-text mb-1">{errors.indicators.root.message}</p>
              )}
              <div className="space-y-1.5">
                {fields.map((field, i) => (
                  <div key={field.id} className="flex gap-1.5 items-center">
                    <Input
                      {...register(`indicators.${i}.name`)}
                      placeholder="metric_name"
                      className="w-1/3 font-mono text-xs"
                    />
                    <Input
                      {...register(`indicators.${i}.query`)}
                      placeholder="rate(metric[5m])"
                      className="flex-1 font-mono text-xs"
                    />
                    <button
                      type="button"
                      aria-label="remove indicator"
                      onClick={() => remove(i)}
                      className="text-muted-foreground hover:text-action-destructive"
                    >
                      <X className="size-3.5" />
                    </button>
                  </div>
                ))}
              </div>
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
              {submitLabel}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

function TagRowEditor({ rows, onChange }: { rows: TagRow[]; onChange: (rows: TagRow[]) => void }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-muted-foreground">Tags</span>
        <button
          type="button"
          onClick={() => onChange([...rows, { key: '', value: '' }])}
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
              onChange={e => onChange(rows.map((r, j) => (j === i ? { ...r, key: e.target.value } : r)))}
              placeholder="key"
              className="flex-1"
            />
            <Input
              value={row.value}
              onChange={e => onChange(rows.map((r, j) => (j === i ? { ...r, value: e.target.value } : r)))}
              placeholder="value"
              className="flex-1"
            />
            <button
              type="button"
              aria-label="remove tag"
              onClick={() => onChange(rows.filter((_, j) => j !== i))}
              className="text-muted-foreground hover:text-action-destructive"
            >
              <X className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
