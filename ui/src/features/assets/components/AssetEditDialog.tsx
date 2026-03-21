import { useState, useEffect } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
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

  useEffect(() => {
    if (asset) {
      setDisplayName(asset.display_name ?? '')
      setTypeName(asset.type_name)
      setLabels(asset.tags ?? {})
    }
  }, [asset])

  const handleSave = () => {
    if (!assetName) return
    updateAsset.mutate({
      name: assetName,
      display_name: displayName || undefined,
      type_name: typeName,
      tags: labels,
    }, {
      onSuccess: () => onOpenChange(false),
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}>
        <DialogHeader>
          <DialogTitle>Edit Asset — <span className="font-mono text-primary">{assetName}</span></DialogTitle>
        </DialogHeader>

        <div className="space-y-3 py-2">
          {/* Display name */}
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">Display Name</label>
            <input
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder={assetName ?? ''}
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
            />
          </div>

          {/* Type */}
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">Type</label>
            <select
              value={typeName}
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
            <label className="text-xs uppercase text-muted-foreground block mb-1">Labels</label>
            <LabelChips
              labels={labels}
              onEdit={() => setLabelsEditorOpen(true)}
            />
          </div>
        </div>

        <DialogFooter>
          <button
            onClick={() => onOpenChange(false)}
            className="px-3 py-1.5 text-sm rounded bg-[#1A1F2E] border border-[#9CA3AF] text-white hover:bg-[#1A1F2E]/80 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={updateAsset.isPending}
            className="px-3 py-1.5 text-sm rounded bg-[#0D2847] border border-[#58A6FF] text-[#58A6FF] hover:bg-[#0D2847]/80 transition-colors disabled:opacity-40"
          >
            {updateAsset.isPending ? 'Saving…' : 'Save'}
          </button>
        </DialogFooter>

        <LabelsEditorDialog
          open={labelsEditorOpen}
          onOpenChange={setLabelsEditorOpen}
          title="Edit Labels"
          subtitle={assetName ?? ''}
          labels={labels}
          onSave={setLabels}
        />
      </DialogContent>
    </Dialog>
  )
}
