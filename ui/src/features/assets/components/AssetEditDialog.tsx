import { useState, useEffect } from 'react'
import { FieldLabel } from '@/components/ui/field-label'
import { Input } from '@/components/ui/input'
import { FormDialog } from '@/components/ui/form-dialog'
import { LabelChips } from '@/components/labels/LabelChips'
import { LabelsEditorDialog } from '@/components/labels/LabelsEditorDialog'
import { useAsset, useAssetTypes, useUpdateAsset } from '../hooks'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  assetName: string | null
}

export function AssetEditDialog({ open, onOpenChange, assetName }: Props) {
  const { data: asset } = useAsset(assetName)
  const { data: types = [] } = useAssetTypes()
  const updateAsset = useUpdateAsset()

  const [displayName, setDisplayName] = useState('')
  const [typeName, setTypeName] = useState('')
  const [labels, setLabels] = useState<Record<string, string>>({})
  const [labelsEditorOpen, setLabelsEditorOpen] = useState(false)

  /* eslint-disable react-hooks/set-state-in-effect -- intentional reset on prop change */
  useEffect(() => {
    if (asset) {
      setDisplayName(asset.displayName ?? '')
      setTypeName(asset.typeName)
      setLabels(asset.tags ?? {})
    }
  }, [asset])
  /* eslint-enable react-hooks/set-state-in-effect */

  const handleSave = () => {
    if (!assetName) return
    updateAsset.mutate(
      { name: assetName, display_name: displayName || undefined, type_name: typeName, tags: labels },
      { onSuccess: () => onOpenChange(false) },
    )
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={onOpenChange}
      title={<>Edit Asset — <span className="font-mono text-primary">{assetName}</span></>}
      submitLabel="Save"
      onSubmit={handleSave}
      canSubmit={true}
      isPending={updateAsset.isPending}
    >
      <div>
        <FieldLabel>Display Name</FieldLabel>
        <Input
          value={displayName}
          onChange={e => setDisplayName(e.target.value)}
          placeholder={assetName ?? ''}
        />
      </div>
      <div>
        <FieldLabel>Type</FieldLabel>
        <select
          value={typeName}
          onChange={e => setTypeName(e.target.value)}
          className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50"
        >
          {types.map(t => (
            <option key={t.name} value={t.name}>
              {t.name}{t.isDefault ? ' (default)' : ''}
            </option>
          ))}
        </select>
      </div>
      <div>
        <FieldLabel>Labels</FieldLabel>
        <LabelChips labels={labels} onEdit={() => setLabelsEditorOpen(true)} />
      </div>
      <LabelsEditorDialog
        open={labelsEditorOpen}
        onOpenChange={setLabelsEditorOpen}
        title="Edit Labels"
        subtitle={assetName ?? ''}
        labels={labels}
        onSave={setLabels}
      />
    </FormDialog>
  )
}
