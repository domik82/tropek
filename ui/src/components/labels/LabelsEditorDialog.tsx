// ui/src/components/labels/LabelsEditorDialog.tsx
import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { LabelComboBox } from './LabelComboBox'
import { useTagKeys, useTagValues } from '@/features/assets/hooks'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  subtitle?: string
  labels: Record<string, string>
  onSave: (labels: Record<string, string>) => void
}

export function LabelsEditorDialog({ open, onOpenChange, title, subtitle, labels: initialLabels, onSave }: Props) {
  const [labels, setLabels] = useState<Record<string, string>>(initialLabels)
  const [newKey, setNewKey] = useState('')
  const [newValue, setNewValue] = useState('')

  // Sync internal state when dialog opens (useState ignores prop changes after mount)
  useEffect(() => {
    if (open) {
      setLabels(initialLabels)
      setNewKey('')
      setNewValue('')
    }
  }, [open, initialLabels])

  const { data: keysSuggestions = [], isLoading: keysLoading } = useTagKeys()
  const { data: valueSuggestions = [], isLoading: valuesLoading } = useTagValues(newKey || null)

  const handleAdd = () => {
    if (newKey && newValue) {
      setLabels(prev => ({ ...prev, [newKey]: newValue }))
      setNewKey('')
      setNewValue('')
    }
  }

  const handleRemove = (key: string) => {
    setLabels(prev => {
      const next = { ...prev }
      delete next[key]
      return next
    })
  }

  const handleDone = () => {
    onSave(labels)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Assigned labels */}
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-2">
              Assigned {Object.keys(labels).length}
            </label>
            {Object.entries(labels).length === 0 && (
              <p className="text-sm text-muted-foreground italic">No labels assigned</p>
            )}
            <div className="space-y-1.5">
              {Object.entries(labels).map(([key, value]) => (
                <div key={key} className="flex items-center gap-2">
                  <div className="flex-1 flex items-center gap-0 border border-border rounded overflow-hidden">
                    <span className="px-3 py-1.5 text-sm font-mono text-[#58A6FF] bg-card border-r border-border min-w-[80px]">
                      {key}
                    </span>
                    <span className="px-3 py-1.5 text-sm font-mono text-foreground bg-input flex-1">
                      {value}
                    </span>
                  </div>
                  <button
                    onClick={() => handleRemove(key)}
                    className="p-1 text-muted-foreground hover:text-[#F85149] transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Add new label */}
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-2">Add New Label</label>
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="text-[10px] text-muted-foreground mb-0.5 block">Key</label>
                <LabelComboBox
                  value={newKey}
                  onChange={setNewKey}
                  suggestions={keysSuggestions.map(k => ({ value: k.key, count: k.count }))}
                  placeholder="e.g. env"
                  isLoading={keysLoading}
                />
              </div>
              <div className="flex-1">
                <label className="text-[10px] text-muted-foreground mb-0.5 block">Value</label>
                <LabelComboBox
                  value={newValue}
                  onChange={setNewValue}
                  suggestions={(valueSuggestions ?? []).map(v => ({ value: v.value, count: v.count }))}
                  placeholder="e.g. production"
                  isLoading={valuesLoading}
                />
              </div>
            </div>
            <div className="flex items-center gap-2 mt-2">
              <button
                onClick={handleAdd}
                disabled={!newKey || !newValue}
                className="px-3 py-1.5 text-xs rounded border border-[#58A6FF] bg-[#0D2847] text-[#58A6FF] hover:bg-[#0D2847]/80 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                + Add
              </button>
              <span className="text-xs text-muted-foreground">Type or select from existing</span>
            </div>
          </div>
        </div>

        {/* Footer: Done button on the right */}
        <div className="flex justify-end pt-2 border-t border-border">
          <button
            onClick={handleDone}
            className="px-4 py-1.5 text-sm rounded border border-[#58A6FF] bg-[#0D2847] text-[#58A6FF] hover:bg-[#0D2847]/80 font-medium"
          >
            Done
          </button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
