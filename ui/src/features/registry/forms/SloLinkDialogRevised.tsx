import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SearchableComboBox } from '@/components/shared/SearchableComboBox'
import { useDatasources } from '@/features/datasources/hooks'
import { useSliDefinitions } from '@/features/slis/hooks'
import {
  useGroupTree, useSlos,
  useCreateGroupSloLink, useGroupSloLinks,
} from '@/features/slos/hooks'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  lockedSloName?: string
  lockedGroupName?: string
}

export function SloLinkDialogRevised({
  open, onOpenChange, lockedSloName, lockedGroupName,
}: Props) {
  const [datasource, setDatasource] = useState('')
  const [sliName, setSliName] = useState('')
  const [groupName, setGroupName] = useState(lockedGroupName ?? '')
  const [sloName, setSloName] = useState(lockedSloName ?? '')

  const { data: datasources } = useDatasources()
  const selectedDs = datasources?.find(d => d.name === datasource)
  const { data: slis } = useSliDefinitions(selectedDs?.adapter_type)
  const { data: tree } = useGroupTree()
  const { data: slos } = useSlos()
  const { data: existingLinks } = useGroupSloLinks(groupName || lockedGroupName || '')
  const createLink = useCreateGroupSloLink()

  useEffect(() => {
    if (lockedGroupName) setGroupName(lockedGroupName)
    if (lockedSloName) setSloName(lockedSloName)
  }, [lockedGroupName, lockedSloName])

  // Reset SLI when datasource changes
  useEffect(() => { setSliName('') }, [datasource])

  // Reset all when dialog opens
  useEffect(() => {
    if (open) {
      setDatasource('')
      setSliName('')
      if (!lockedGroupName) setGroupName('')
      if (!lockedSloName) setSloName('')
    }
  }, [open, lockedGroupName, lockedSloName])

  const isDuplicate = existingLinks?.some(l => l.slo_name === sloName) ?? false
  const isValid = datasource && sliName && groupName && sloName && !isDuplicate

  const handleLink = async () => {
    const targetGroup = lockedGroupName ?? groupName
    await createLink.mutateAsync({
      groupName: targetGroup,
      slo_name: sloName,
      sli_name: sliName,
      data_source_name: datasource,
    })
    onOpenChange(false)
  }

  if (!open) return null

  const dsItems = (datasources ?? []).map(ds => ({
    value: ds.name,
    label: ds.display_name ?? ds.name,
    badge: ds.adapter_type,
  }))

  const sliItems = (slis ?? [])
    .filter(s => s.active)
    .map(s => ({
      value: s.name,
      label: s.display_name ?? s.name,
    }))

  const sloItems = (slos ?? [])
    .filter(s => s.active)
    .map(s => ({
      value: s.name,
      label: s.display_name ?? s.name,
    }))

  const groupItems = (tree?.all_groups ?? []).map(g => ({
    value: g.name,
    label: g.display_name ?? g.name,
  }))

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-md bg-popover border border-border rounded-xl overflow-hidden shadow-xl"
        style={{ fontFamily: SANS_SERIF }}
      >
        {/* Accent strip */}
        <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.slo }} />

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-foreground">
            Link SLO to Asset Group
          </h2>
          <button
            type="button"
            aria-label="Close"
            className="text-muted-foreground hover:text-foreground"
            onClick={() => onOpenChange(false)}
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 space-y-3">
          {/* Step 1: Datasource */}
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Datasource</label>
            <SearchableComboBox
              value={datasource}
              items={dsItems}
              onSelect={setDatasource}
              placeholder="Select datasource..."
            />
          </div>

          {/* Step 2: SLI (disabled until DS selected) */}
          <div>
            <label className="block text-xs text-muted-foreground mb-1">
              SLI
              {selectedDs && (
                <span className="text-[10px] opacity-60 normal-case ml-1">
                  — filtered to {selectedDs.adapter_type}
                </span>
              )}
            </label>
            {!datasource ? (
              <div className="rounded border border-border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
                Select a datasource first
              </div>
            ) : (
              <SearchableComboBox
                value={sliName}
                items={sliItems}
                onSelect={setSliName}
                placeholder="Select SLI..."
              />
            )}
          </div>

          {/* Step 3: SLO (locked or selectable) */}
          <div>
            <label className="block text-xs text-muted-foreground mb-1">SLO</label>
            {lockedSloName ? (
              <div className="bg-muted/30 border border-border rounded px-3 py-2 text-sm text-muted-foreground">
                {lockedSloName} <span className="text-xs opacity-50">(locked)</span>
              </div>
            ) : (
              <SearchableComboBox
                value={sloName}
                items={sloItems}
                onSelect={setSloName}
                placeholder="Select SLO..."
              />
            )}
          </div>

          {/* Step 4: Group (locked or selectable) */}
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Asset Group</label>
            {lockedGroupName ? (
              <div className="bg-muted/30 border border-border rounded px-3 py-2 text-sm text-muted-foreground">
                {lockedGroupName} <span className="text-xs opacity-50">(locked)</span>
              </div>
            ) : (
              <SearchableComboBox
                value={groupName}
                items={groupItems}
                onSelect={setGroupName}
                placeholder="Select group..."
              />
            )}
          </div>

          {isDuplicate && (
            <p className="text-xs text-destructive">This SLO is already linked to this group</p>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-4 py-3 border-t border-border bg-muted/20">
          <Button size="xs" variant="outline" type="button" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            size="xs"
            type="button"
            disabled={!isValid || createLink.isPending}
            onClick={handleLink}
          >
            {createLink.isPending ? 'Linking...' : 'Link'}
          </Button>
        </div>
      </div>
    </div>
  )
}
