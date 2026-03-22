import { useState } from 'react'
import { Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useCreateSli } from '@/features/slis/hooks'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import type { SliDefinition } from '@/features/slis/types'

interface SliFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  editFrom?: SliDefinition
  defaultAdapterType?: string
}

interface IndicatorRow {
  name: string
  query: string
}

interface TagRow {
  key: string
  value: string
}

function indicatorsToRows(indicators: Record<string, string>): IndicatorRow[] {
  return Object.entries(indicators).map(([name, query]) => ({ name, query }))
}

function rowsToIndicators(rows: IndicatorRow[]): Record<string, string> {
  const result: Record<string, string> = {}
  for (const row of rows) {
    if (row.name.trim()) {
      result[row.name.trim()] = row.query
    }
  }
  return result
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

export function SliForm({ open, onOpenChange, editFrom, defaultAdapterType }: SliFormProps) {
  const isNewVersion = !!editFrom

  const [name, setName] = useState(editFrom?.name ?? '')
  const [displayName, setDisplayName] = useState(editFrom?.display_name ?? '')
  const [adapterType, setAdapterType] = useState(
    editFrom?.adapter_type ?? defaultAdapterType ?? ''
  )
  const [author, setAuthor] = useState(editFrom?.author ?? '')
  const [notes, setNotes] = useState(editFrom?.notes ?? '')
  const [indicatorRows, setIndicatorRows] = useState<IndicatorRow[]>(
    editFrom?.indicators ? indicatorsToRows(editFrom.indicators) : []
  )
  const [tagRows, setTagRows] = useState<TagRow[]>(
    editFrom?.tags ? tagsToRows(editFrom.tags) : []
  )

  const createMutation = useCreateSli()

  const isPending = createMutation.isPending

  if (!open) return null

  function handleAddIndicator() {
    setIndicatorRows(prev => [...prev, { name: '', query: '' }])
  }

  function handleRemoveIndicator(index: number) {
    setIndicatorRows(prev => prev.filter((_, i) => i !== index))
  }

  function handleIndicatorChange(index: number, field: 'name' | 'query', val: string) {
    setIndicatorRows(prev =>
      prev.map((row, i) => (i === index ? { ...row, [field]: val } : row))
    )
  }

  function handleAddTag() {
    setTagRows(prev => [...prev, { key: '', value: '' }])
  }

  function handleRemoveTag(index: number) {
    setTagRows(prev => prev.filter((_, i) => i !== index))
  }

  function handleTagChange(index: number, field: 'key' | 'value', val: string) {
    setTagRows(prev =>
      prev.map((row, i) => (i === index ? { ...row, [field]: val } : row))
    )
  }

  function handleSubmit() {
    const indicators = rowsToIndicators(indicatorRows)
    const tags = rowsToTags(tagRows)

    createMutation.mutate(
      {
        name,
        display_name: displayName || undefined,
        adapter_type: adapterType,
        indicators,
        notes: notes || undefined,
        author: author || undefined,
        tags: Object.keys(tags).length > 0 ? tags : undefined,
      },
      {
        onSuccess: () => onOpenChange(false),
      }
    )
  }

  const title = isNewVersion ? `New Version of: ${editFrom!.name}` : 'New SLI'
  const submitLabel = isPending ? 'Saving…' : isNewVersion ? 'Create Version' : 'Create'
  const canSubmit = !isPending && !!name.trim() && !!adapterType.trim()

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
        <div className="p-4 space-y-3 max-h-[70vh] overflow-y-auto">
          {/* Name */}
          <div>
            <label htmlFor="sli-name" className="block text-xs text-muted-foreground mb-1">
              Name
            </label>
            <Input
              id="sli-name"
              value={name}
              onChange={e => setName(e.target.value)}
              disabled={isNewVersion}
              placeholder="my-sli"
            />
          </div>

          {/* Display Name */}
          <div>
            <label htmlFor="sli-display-name" className="block text-xs text-muted-foreground mb-1">
              Display Name
            </label>
            <Input
              id="sli-display-name"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder="My SLI"
            />
          </div>

          {/* Adapter Type */}
          <div>
            <label htmlFor="sli-adapter-type" className="block text-xs text-muted-foreground mb-1">
              Adapter Type
            </label>
            <Input
              id="sli-adapter-type"
              value={adapterType}
              onChange={e => setAdapterType(e.target.value)}
              placeholder="prometheus"
            />
          </div>

          {/* Author */}
          <div>
            <label htmlFor="sli-author" className="block text-xs text-muted-foreground mb-1">
              Author
            </label>
            <Input
              id="sli-author"
              value={author}
              onChange={e => setAuthor(e.target.value)}
              placeholder="your-name"
            />
          </div>

          {/* Notes */}
          <div>
            <label htmlFor="sli-notes" className="block text-xs text-muted-foreground mb-1">
              Notes
            </label>
            <Input
              id="sli-notes"
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Optional notes"
            />
          </div>

          {/* Indicators */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground">Indicators</span>
              <button
                type="button"
                aria-label="Add indicator"
                onClick={handleAddIndicator}
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary"
              >
                <Plus className="size-3" /> Add indicator
              </button>
            </div>
            <div className="space-y-1.5">
              {indicatorRows.map((row, i) => (
                <div key={i} className="flex gap-1.5 items-center">
                  <Input
                    value={row.name}
                    onChange={e => handleIndicatorChange(i, 'name', e.target.value)}
                    placeholder="metric_name"
                    className="w-1/3 font-mono text-xs"
                  />
                  <Input
                    value={row.query}
                    onChange={e => handleIndicatorChange(i, 'query', e.target.value)}
                    placeholder="rate(metric[5m])"
                    className="flex-1 font-mono text-xs"
                  />
                  <button
                    type="button"
                    aria-label="remove indicator"
                    onClick={() => handleRemoveIndicator(i)}
                    className="text-muted-foreground hover:text-red-400"
                  >
                    <X className="size-3.5" />
                  </button>
                </div>
              ))}
            </div>
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
            disabled={!canSubmit}
            style={{ backgroundColor: ENTITY_COLORS.sli, color: '#fff' }}
          >
            {submitLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
