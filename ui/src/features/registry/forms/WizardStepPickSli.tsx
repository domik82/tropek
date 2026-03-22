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
}

export function WizardStepPickSli({ data, onChange }: WizardStepPickSliProps) {
  const { data: datasources } = useDatasources()
  const selectedDs = datasources?.find((ds) => ds.name === data.datasource)
  const { data: sliDefs } = useSliDefinitions(selectedDs?.adapter_type)

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
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        Step 2 — Pick SLI
      </h3>

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
        <label className="block text-xs text-muted-foreground mb-1">SLI Definition</label>
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
