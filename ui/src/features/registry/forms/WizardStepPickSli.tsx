import { useEffect, useRef } from 'react'
import { SearchableComboBox } from '@/components/shared/SearchableComboBox'
import { useDatasources } from '@/features/datasources/hooks'
import { useSliDefinitions } from '@/features/slis/hooks'

export interface PickSliData {
  datasource: string
  sliName: string
  indicators: Record<string, string>
}

interface WizardStepPickSliProps {
  data: PickSliData
  onChange: (data: PickSliData) => void
  /** Indicator names from editSlo objectives — used to auto-select matching SLI */
  editIndicatorNames?: string[]
}

export function WizardStepPickSli({ data, onChange, editIndicatorNames }: WizardStepPickSliProps) {
  const { data: datasources } = useDatasources()
  const selectedDs = datasources?.find((ds) => ds.name === data.datasource)
  const { data: sliDefs } = useSliDefinitions(selectedDs?.adapter_type)
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
      onChange({ ...data, sliName: match.name, indicators: match.indicators })
    }
  }, [sliDefs, editIndicatorNames, data, onChange])

  const dsItems = (datasources ?? []).map((ds) => ({
    value: ds.name,
    label: ds.display_name ?? ds.name,
    badge: ds.adapter_type,
  }))

  const sliItems = (sliDefs ?? []).map((sli) => ({
    value: sli.name,
    label: sli.display_name ?? sli.name,
    badge: sli.adapter_type,
  }))

  function handleDatasourceSelect(dsName: string) {
    onChange({ ...data, datasource: dsName, sliName: '', indicators: {} })
  }

  function handleSliSelect(sliName: string) {
    const sli = sliDefs?.find((s) => s.name === sliName)
    onChange({
      ...data,
      sliName,
      indicators: sli?.indicators ?? {},
    })
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-[10px] font-bold">2</span>
        <h3 className="text-sm font-semibold text-foreground">Pick SLI</h3>
      </div>

      <div>
        <label className="block text-xs text-muted-foreground mb-1">Datasource</label>
        <SearchableComboBox
          value={data.datasource}
          items={dsItems}
          onSelect={handleDatasourceSelect}
          placeholder="Select datasource..."
        />
      </div>

      <div>
        <label className="block text-xs text-muted-foreground mb-1">
          SLI Definition
          {selectedDs && (
            <span className="ml-1 text-[10px] opacity-60 normal-case">— filtered to {selectedDs.adapter_type}</span>
          )}
        </label>
        {data.datasource ? (
          <SearchableComboBox
            value={data.sliName}
            items={sliItems}
            onSelect={handleSliSelect}
            placeholder="Select SLI definition..."
          />
        ) : (
          <div className="rounded border border-border bg-popover px-3 py-2 text-sm text-muted-foreground opacity-60">
            Select a datasource first
          </div>
        )}
      </div>
    </div>
  )
}
