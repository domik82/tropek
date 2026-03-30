import { useState } from 'react'
import { Search, X, Plus } from 'lucide-react'
import type { TagFilter } from '@/features/registry'
import { SANS_SERIF } from '@/lib/fonts'

interface TagKeySuggestion {
  key: string
  count: number
}

interface TagValueSuggestion {
  value: string
  count: number
}

interface TagFilterBarProps {
  search: string
  onSearchChange: (s: string) => void
  tags: TagFilter[]
  onTagsChange: (tags: TagFilter[]) => void
  tagKeySuggestions: TagKeySuggestion[]
  tagValueSuggestions: TagValueSuggestion[]
  onTagKeySelected: (key: string) => void
  isLoadingKeys: boolean
  isLoadingValues: boolean
  hideSearch?: boolean
}

type AddFlowStep = 'idle' | 'pick-key' | 'pick-value'

export function TagFilterBar({
  search,
  onSearchChange,
  tags,
  onTagsChange,
  tagKeySuggestions,
  tagValueSuggestions,
  onTagKeySelected,
  isLoadingKeys,
  isLoadingValues,
  hideSearch = false,
}: TagFilterBarProps) {
  const [addStep, setAddStep] = useState<AddFlowStep>('idle')
  const [selectedKey, setSelectedKey] = useState<string>('')

  function handleRemoveTag(index: number) {
    onTagsChange(tags.filter((_, i) => i !== index))
  }

  function handleStartAdd() {
    setAddStep('pick-key')
  }

  function handleKeySelect(key: string) {
    setSelectedKey(key)
    onTagKeySelected(key)
    setAddStep('pick-value')
  }

  function handleValueSelect(value: string) {
    const already = tags.some(t => t.key === selectedKey && t.value === value)
    if (!already) {
      onTagsChange([...tags, { key: selectedKey, value }])
    }
    setAddStep('idle')
    setSelectedKey('')
  }

  function handleCancel() {
    setAddStep('idle')
    setSelectedKey('')
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') {
      handleCancel()
    }
  }

  return (
    <div style={{ fontFamily: SANS_SERIF }} className="flex flex-col gap-2" onKeyDown={handleKeyDown}>
      {/* Search input */}
      {!hideSearch && (
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Filter..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-sm bg-popover border border-border rounded-md
                       placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      )}

      {/* Active tag pills */}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.map((tag, index) => (
            <span
              key={`${tag.key}:${tag.value}`}
              className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full
                         bg-primary/15 text-primary border border-primary/30"
            >
              <span className="font-semibold">{tag.key}</span>
              <span className="text-muted-foreground">:</span>
              <span>{tag.value}</span>
              <button
                type="button"
                aria-label="remove tag"
                onClick={() => handleRemoveTag(index)}
                className="ml-0.5 hover:text-primary/80 cursor-pointer"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Add tag flow */}
      {addStep === 'idle' && (
        <button
          type="button"
          onClick={handleStartAdd}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground
                     hover:text-primary cursor-pointer self-start"
        >
          <Plus className="h-3.5 w-3.5" />
          Add tag filter
        </button>
      )}

      {addStep === 'pick-key' && (
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Select tag key:</span>
          {isLoadingKeys ? (
            <span className="text-xs text-muted-foreground">Loading...</span>
          ) : (
            <div className="flex flex-wrap gap-1">
              {tagKeySuggestions.map((s) => (
                <button
                  key={s.key}
                  type="button"
                  onClick={() => handleKeySelect(s.key)}
                  className="px-2 py-0.5 text-xs rounded border border-border bg-popover
                             hover:border-primary hover:text-primary cursor-pointer"
                >
                  {s.key}
                  <span className="ml-1 text-muted-foreground">({s.count})</span>
                </button>
              ))}
              <button
                type="button"
                onClick={handleCancel}
                className="px-2 py-0.5 text-xs text-muted-foreground hover:text-primary cursor-pointer"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      )}

      {addStep === 'pick-value' && (
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">
            Select value for <span className="font-semibold text-primary">{selectedKey}</span>:
          </span>
          {isLoadingValues ? (
            <span className="text-xs text-muted-foreground">Loading...</span>
          ) : (
            <div className="flex flex-wrap gap-1">
              {tagValueSuggestions.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  onClick={() => handleValueSelect(s.value)}
                  className="px-2 py-0.5 text-xs rounded border border-border bg-popover
                             hover:border-primary hover:text-primary cursor-pointer"
                >
                  {s.value}
                  <span className="ml-1 text-muted-foreground">({s.count})</span>
                </button>
              ))}
              <button
                type="button"
                onClick={handleCancel}
                className="px-2 py-0.5 text-xs text-muted-foreground hover:text-primary cursor-pointer"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
