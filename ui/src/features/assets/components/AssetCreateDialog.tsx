// ui/src/features/assets/components/AssetCreateDialog.tsx
import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import { FieldLabel } from '@/components/ui/field-label'
import { LabelChips } from '@/components/labels/LabelChips'
import { LabelsEditorDialog } from '@/components/labels/LabelsEditorDialog'
import { GroupTreeSelector } from './GroupTreeSelector'
import { useAssetTypes, useCreateAsset, useAddGroupMember, useAssetGroups } from '../hooks'
import { SANS_SERIF } from '@/lib/fonts'

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

  // Auto-select default type when types load
  const effectiveType = typeName || types.find(t => t.is_default)?.name || types[0]?.name || ''

  const isValid = name.length > 0 && /^[a-z0-9-]+$/.test(name) && effectiveType

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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent style={{ fontFamily: SANS_SERIF }}>
        <DialogHeader>
          <DialogTitle>Add Asset</DialogTitle>
        </DialogHeader>

        <div className="space-y-3 py-2">
          {/* Name */}
          <div>
            <FieldLabel required>Asset Name</FieldLabel>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="linux-cache-01"
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
            />
            {name && !isValid && (
              <p className="text-xs text-destructive mt-1">lowercase letters, numbers, hyphens only</p>
            )}
          </div>

          {/* Type */}
          <div>
            <FieldLabel required>Type</FieldLabel>
            <select
              value={effectiveType}
              onChange={e => setTypeName(e.target.value)}
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50"
            >
              {types.map(t => (
                <option key={t.name} value={t.name}>
                  {t.name}{t.is_default ? ' (default)' : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Labels */}
          <div>
            <FieldLabel>Labels</FieldLabel>
            <LabelChips
              labels={labels}
              onEdit={() => setLabelsEditorOpen(true)}
            />
          </div>

          {/* Group */}
          <div>
            <FieldLabel>Add to Group</FieldLabel>
            {tree && (
              <GroupTreeSelector
                tree={tree}
                value={groupName}
                onChange={setGroupName}
              />
            )}
          </div>

          {/* Weight (only show when group selected) */}
          {groupName && (
            <div>
              <FieldLabel>Weight</FieldLabel>
              <input
                type="number"
                value={weight}
                onChange={e => setWeight(e.target.value)}
                step="0.1"
                min="0"
                className="w-24 bg-input border border-border rounded px-3 py-2 text-sm font-mono text-foreground focus:outline-none focus:border-primary/50"
              />
            </div>
          )}
        </div>

        <DialogFooter>
          <button
            onClick={() => onOpenChange(false)}
            className="px-3 py-1.5 text-sm rounded bg-action-secondary-bg border border-action-secondary-border text-white hover:bg-action-secondary-bg/80 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => void handleCreate()}
            disabled={!isValid || createAsset.isPending}
            className="px-3 py-1.5 text-sm rounded bg-action-primary-bg border border-action-primary-border text-action-primary hover:bg-action-primary-hover transition-colors disabled:opacity-40"
          >
            {createAsset.isPending ? 'Adding…' : 'Add'}
          </button>
        </DialogFooter>

        <LabelsEditorDialog
          open={labelsEditorOpen}
          onOpenChange={setLabelsEditorOpen}
          title="Edit Labels"
          subtitle={name || 'New asset'}
          labels={labels}
          onSave={setLabels}
        />
      </DialogContent>
    </Dialog>
  )
}
