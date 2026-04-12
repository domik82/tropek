import { useState, useEffect } from 'react'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useCreateSli } from '@/features/slis'
import { AggregatedModeFields } from './AggregatedModeFields'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import { tagsToRows, rowsToTags } from './tagUtils'
import type { TagRow } from './tagUtils'
import type { Sli, SliCreateInput } from '@/features/slis'

const rawSchema = z.object({
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

const aggregatedSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  display_name: z.string().optional(),
  adapter_type: z.string().min(1, 'Adapter type is required'),
  author: z.string().optional(),
  notes: z.string().optional(),
  indicators: z.array(z.object({
    name: z.string(),
    query: z.string(),
  })),
})

type FormValues = z.infer<typeof rawSchema>

interface SliFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  editFrom?: Sli
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
  const initialMode = editFrom?.mode ?? 'raw'

  const [mode, setMode] = useState<'raw' | 'aggregated'>(initialMode)
  const [queryTemplate, setQueryTemplate] = useState(editFrom?.queryTemplate ?? '')
  const [interval, setInterval] = useState(editFrom?.interval ?? '1m')
  const [methods, setMethods] = useState<string[]>(editFrom?.methods ?? [])

  const schema = mode === 'raw' ? rawSchema : aggregatedSchema

  const { register, handleSubmit, control, formState: { errors }, reset } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: editFrom?.name ?? '',
      display_name: editFrom?.displayName ?? '',
      adapter_type: editFrom?.adapterType ?? defaultAdapterType ?? '',
      author: editFrom?.author ?? '',
      notes: editFrom?.notes ?? '',
      indicators: editFrom?.indicators ? indicatorsToRows(editFrom.indicators) : [],
    },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'indicators' })

  const [tagRows, setTagRows] = useState<TagRow[]>(
    editFrom?.tags ? tagsToRows(editFrom.tags) : [],
  )

  /* eslint-disable react-hooks/set-state-in-effect -- intentional reset on prop change */
  useEffect(() => {
    if (editFrom) {
      reset({
        name: editFrom.name,
        display_name: editFrom.displayName ?? '',
        adapter_type: editFrom.adapterType,
        author: editFrom.author ?? '',
        notes: editFrom.notes ?? '',
        indicators: indicatorsToRows(editFrom.indicators),
      })
      setMode(editFrom.mode ?? 'raw')
      setQueryTemplate(editFrom.queryTemplate ?? '')
      setInterval(editFrom.interval ?? '1m')
      setMethods(editFrom.methods ?? [])
      setTagRows(tagsToRows(editFrom.tags))
    }
  }, [editFrom, reset])
  /* eslint-enable react-hooks/set-state-in-effect */

  const createMutation = useCreateSli()
  const isPending = createMutation.isPending

  if (!open) return null

  function onSubmit(values: FormValues) {
    const tags = rowsToTags(tagRows)
    const base = {
      name: values.name,
      display_name: values.display_name || undefined,
      adapter_type: values.adapter_type,
      notes: values.notes || undefined,
      author: values.author || undefined,
      tags,
    }

    if (mode === 'raw') {
      const payload: SliCreateInput = {
        ...base,
        mode: 'raw',
        indicators: rowsToIndicators(values.indicators),
      }
      createMutation.mutate(payload, {
        onSuccess: () => { reset(); onOpenChange(false) },
      })
    } else {
      const payload: SliCreateInput = {
        ...base,
        mode: 'aggregated',
        indicators: {},
        query_template: queryTemplate,
        interval,
        // Aggregation methods come from a free-form string-state checkbox group;
        // backend constrains to AggregationMethod literals.
        methods: methods as SliCreateInput['methods'],
      }
      createMutation.mutate(payload, {
        onSuccess: () => { reset(); onOpenChange(false) },
      })
    }
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

            {/* Mode toggle */}
            <div>
              <span className="block text-xs text-muted-foreground mb-1">Mode</span>
              <div className="flex gap-4">
                <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
                  <input
                    type="radio"
                    name="sli-mode"
                    value="raw"
                    checked={mode === 'raw'}
                    onChange={() => setMode('raw')}
                  />
                  <span className="text-foreground">Raw</span>
                </label>
                <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
                  <input
                    type="radio"
                    name="sli-mode"
                    value="aggregated"
                    checked={mode === 'aggregated'}
                    onChange={() => setMode('aggregated')}
                  />
                  <span className="text-foreground">Aggregated</span>
                </label>
              </div>
            </div>

            {/* Mode-specific fields */}
            {mode === 'raw' ? (
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
            ) : (
              <AggregatedModeFields
                queryTemplate={queryTemplate}
                interval={interval}
                methods={methods}
                onQueryTemplateChange={setQueryTemplate}
                onIntervalChange={setInterval}
                onMethodsChange={setMethods}
              />
            )}

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
