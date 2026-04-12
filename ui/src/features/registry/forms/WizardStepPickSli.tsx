import { useState, useEffect, useRef } from 'react'
import { SearchableComboBox } from '@/components/shared/SearchableComboBox'
import { useSliDefinitions, useSliTagKeys, useSliTagValues } from '@/features/slis'

export interface PickSliData {
  sliName: string
  sliVersion: number | null
  indicators: Record<string, string>
}

interface WizardStepPickSliProps {
  data: PickSliData
  onChange: (data: PickSliData) => void
  /** Indicator names from editSlo objectives — used to auto-select matching SLI */
  editIndicatorNames?: string[]
}

function TagChips({
  selectedTags,
  onToggle,
}: {
  selectedTags: Record<string, string>
  onToggle: (key: string, value: string) => void
}) {
  const { data: tagKeys } = useSliTagKeys()
  const [expandedKey, setExpandedKey] = useState<string | null>(null)
  const { data: tagValues } = useSliTagValues(expandedKey ?? '')

  if (!tagKeys?.length) return null

  return (
    <div className="space-y-1.5">
      <label className="block text-xs text-muted-foreground">Filter by tags</label>
      <div className="flex flex-wrap gap-1.5">
        {tagKeys.map(({ key }) => {
          const activeValue = selectedTags[key]
          const isExpanded = expandedKey === key

          if (activeValue) {
            return (
              <button
                key={key}
                type="button"
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-primary/15 text-primary transition-colors hover:bg-primary/25"
                onClick={() => onToggle(key, activeValue)}
              >
                {key}: {activeValue}
                <span className="text-[9px] opacity-60">&times;</span>
              </button>
            )
          }

          return (
            <div key={key} className="relative">
              <button
                type="button"
                className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-muted text-muted-foreground transition-colors hover:text-foreground"
                onClick={() => setExpandedKey(isExpanded ? null : key)}
              >
                {key}
              </button>
              {isExpanded && tagValues && (
                <div className="absolute top-full left-0 mt-1 z-10 bg-popover border border-border rounded shadow-md p-1 min-w-[100px]">
                  {tagValues.map(({ value }) => (
                    <button
                      key={value}
                      type="button"
                      className="block w-full text-left px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded"
                      onClick={() => {
                        onToggle(key, value)
                        setExpandedKey(null)
                      }}
                    >
                      {value}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function WizardStepPickSli({ data, onChange, editIndicatorNames }: WizardStepPickSliProps) {
  const [selectedTags, setSelectedTags] = useState<Record<string, string>>({})
  const { data: sliDefs } = useSliDefinitions()
  const autoSelectedRef = useRef(false)

  // Auto-select SLI definition whose indicator keys overlap with edit objectives
  useEffect(() => {
    if (autoSelectedRef.current || !editIndicatorNames?.length || !sliDefs?.length) return
    if (data.sliName) return // already selected

    const editSet = new Set(editIndicatorNames)
    const match = sliDefs.find((sli) => {
      const keys = Object.keys(sli.indicators)
      return keys.length > 0 && keys.some((k) => editSet.has(k))
    })
    if (match) {
      autoSelectedRef.current = true
      onChange({
        ...data,
        sliName: match.name,
        sliVersion: match.version,
        indicators: match.indicators,
      })
    }
  }, [sliDefs, editIndicatorNames, data, onChange])

  const filteredSlis = (sliDefs ?? []).filter((sli) => {
    return Object.entries(selectedTags).every(
      ([key, val]) => sli.tags?.[key] === val,
    )
  })

  const sliItems = filteredSlis.map((sli) => ({
    value: sli.name,
    label: sli.displayName ?? sli.name,
    badge: sli.adapterType,
  }))

  function handleTagToggle(key: string, value: string) {
    setSelectedTags((prev) => {
      const next = { ...prev }
      if (next[key] === value) {
        delete next[key]
      } else {
        next[key] = value
      }
      return next
    })
  }

  function handleSliSelect(sliName: string) {
    const sli = sliDefs?.find((s) => s.name === sliName)
    onChange({
      ...data,
      sliName,
      sliVersion: sli?.version ?? null,
      indicators: sli?.indicators ?? {},
    })
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-[10px] font-bold">2</span>
        <h3 className="text-sm font-semibold text-foreground">Pick SLI</h3>
      </div>

      <TagChips selectedTags={selectedTags} onToggle={handleTagToggle} />

      <div>
        <label className="block text-xs text-muted-foreground mb-1">
          SLI Definition
          {Object.keys(selectedTags).length > 0 && (
            <span className="ml-1 text-[10px] opacity-60 normal-case">
              — {filteredSlis.length} match{filteredSlis.length !== 1 ? 'es' : ''}
            </span>
          )}
        </label>
        <SearchableComboBox
          value={data.sliName}
          items={sliItems}
          onSelect={handleSliSelect}
          placeholder="Select SLI definition..."
        />
      </div>
    </div>
  )
}
