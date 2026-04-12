// ui/src/features/assets/components/AssetCreateDialog.tsx
import { useState } from 'react'
import { FieldLabel } from '@/components/ui/field-label'
import { Input } from '@/components/ui/input'
import { FormDialog } from '@/components/ui/form-dialog'
import { LabelChips } from '@/components/labels/LabelChips'
import { LabelsEditorDialog } from '@/components/labels/LabelsEditorDialog'
import { GroupTreeSelector } from './GroupTreeSelector'
import { isValidEntityName, ENTITY_NAME_HINT } from '@/lib/validation'
import { useAssetTypes, useCreateAsset, useAddGroupMember, useAssetGroups } from '../hooks'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AssetCreateDialog({ open, onOpenChange }: Props) {
  const { data: types = [] } = useAssetTypes()
  const { data: tree } = useAssetGroups()
  const createAsset = useCreateAsset()
  const addGroupMember = useAddGroupMember()

  const [name, setName] = useState('')
  const [typeName, setTypeName] = useState('')
  const [labels, setLabels] = useState<Record<string, string>>({})
  const [groupName, setGroupName] = useState<string | null>(null)
  const [weight, setWeight] = useState('1.0')
  const [labelsEditorOpen, setLabelsEditorOpen] = useState(false)

  const effectiveType = typeName || types.find(t => t.isDefault)?.name || types[0]?.name || ''
  const isValid = isValidEntityName(name) && !!effectiveType

  const handleCreate = async () => {
    const asset = await createAsset.mutateAsync({
      name,
      type_name: effectiveType,
      tags: Object.keys(labels).length > 0 ? labels : undefined,
    })
    if (groupName && asset) {
      await addGroupMember.mutateAsync({
        groupName,
        assetId: asset.id,
        weight: parseFloat(weight) || 1.0,
      })
    }
    setName('')
    setTypeName('')
    setLabels({})
    setGroupName(null)
    setWeight('1.0')
    onOpenChange(false)
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Add Asset"
      submitLabel="Add"
      pendingLabel="Adding…"
      onSubmit={() => void handleCreate()}
      canSubmit={isValid}
      isPending={createAsset.isPending}
    >
      <div>
        <FieldLabel required>Asset Name</FieldLabel>
        <Input
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="linux-cache-01"
          className="font-mono"
        />
        {name && !isValid && (
          <p className="text-xs text-destructive mt-1">{ENTITY_NAME_HINT}</p>
        )}
      </div>
      <div>
        <FieldLabel required>Type</FieldLabel>
        <select
          value={effectiveType}
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
      <div>
        <FieldLabel>Add to Group</FieldLabel>
        {tree && (
          <GroupTreeSelector tree={tree} value={groupName} onChange={setGroupName} />
        )}
      </div>
      {groupName && (
        <div>
          <FieldLabel>Weight</FieldLabel>
          <Input
            type="number"
            value={weight}
            onChange={e => setWeight(e.target.value)}
            step="0.1"
            min="0"
            className="w-24 font-mono"
          />
        </div>
      )}
      <LabelsEditorDialog
        open={labelsEditorOpen}
        onOpenChange={setLabelsEditorOpen}
        title="Edit Labels"
        subtitle={name || 'New asset'}
        labels={labels}
        onSave={setLabels}
      />
    </FormDialog>
  )
}
