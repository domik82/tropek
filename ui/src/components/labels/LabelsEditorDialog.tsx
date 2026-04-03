// ui/src/components/labels/LabelsEditorDialog.tsx
import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { FieldLabel } from '@/components/ui/field-label'
import { LabelComboBox } from './LabelComboBox'
import { useTagKeys, useTagValues } from '@/features/assets'
import { SANS_SERIF } from '@/lib/fonts'

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
  /* eslint-disable react-hooks/set-state-in-effect -- intentional reset on dialog open */
  useEffect(() => {
    if (open) {
      setLabels(initialLabels)
      setNewKey('')
      setNewValue('')
    }
  }, [open, initialLabels])
  /* eslint-enable react-hooks/set-state-in-effect */

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
      <DialogContent style={{ fontFamily: SANS_SERIF }}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Assigned labels */}
          <div>
            <FieldLabel className="mb-2">Assigned {Object.keys(labels).length}</FieldLabel>
            {Object.entries(labels).length === 0 && (
              <p className="text-sm text-muted-foreground italic">No labels assigned</p>
            )}
            <div className="space-y-1.5">
              {Object.entries(labels).map(([key, value]) => (
                <div key={key} className="flex items-center gap-2">
                  <div className="flex-1 flex items-center gap-0 border border-border rounded overflow-hidden">
                    <span className="px-3 py-1.5 text-sm font-mono text-label-key bg-card border-r border-border min-w-[80px]">
                      {key}
                    </span>
                    <span className="px-3 py-1.5 text-sm font-mono text-foreground bg-input flex-1">
                      {value}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => handleRemove(key)}
                    className="text-muted-foreground hover:text-action-destructive"
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              ))}
            </div>
          </div>

          {/* Add new label */}
          <div>
            <FieldLabel className="mb-2">Add New Label</FieldLabel>
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
              <Button
                variant="default"
                size="sm"
                onClick={handleAdd}
                disabled={!newKey || !newValue}
              >
                + Add
              </Button>
              <span className="text-xs text-muted-foreground">Type or select from existing</span>
            </div>
          </div>
        </div>

        {/* Footer: Done button on the right */}
        <div className="flex justify-end pt-2 border-t border-border">
          <Button variant="default" size="sm" onClick={handleDone}>
            Done
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
