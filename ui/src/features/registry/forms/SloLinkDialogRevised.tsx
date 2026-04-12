import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SearchableComboBox } from '@/components/shared/SearchableComboBox'
import { useDatasources } from '@/features/datasources'
import { useGroupTree, useSlos, useCreateGroupSloAssignment, useGroupSloAssignments } from '@/features/slos'
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
  const [groupName, setGroupName] = useState(lockedGroupName ?? '')
  const [sloName, setSloName] = useState(lockedSloName ?? '')

  const { data: datasources } = useDatasources()
  const { data: tree } = useGroupTree()
  const { data: slos } = useSlos()
  const { data: existingAssignments } = useGroupSloAssignments(groupName || lockedGroupName || '')
  const createAssignment = useCreateGroupSloAssignment()

  const selectedSlo = slos?.find((s) => s.name === sloName)

  const dsItems = (datasources ?? []).map((ds) => ({
    value: ds.name,
    label: ds.displayName ?? ds.name,
    badge: ds.adapterType,
  }))

  /* eslint-disable react-hooks/set-state-in-effect -- intentional sync from props */
  useEffect(() => {
    if (lockedGroupName) setGroupName(lockedGroupName)
    if (lockedSloName) setSloName(lockedSloName)
  }, [lockedGroupName, lockedSloName])

  // Reset all when dialog opens
  useEffect(() => {
    if (open) {
      setDatasource('')
      if (!lockedGroupName) setGroupName('')
      if (!lockedSloName) setSloName('')
    }
  }, [open, lockedGroupName, lockedSloName])
  /* eslint-enable react-hooks/set-state-in-effect */

  const isDuplicate = existingAssignments?.some((a) => a.sloName === sloName) ?? false
  const isValid = datasource && groupName && sloName && selectedSlo && !isDuplicate

  const handleLink = async () => {
    if (!selectedSlo) return
    const targetGroup = lockedGroupName ?? groupName
    await createAssignment.mutateAsync({
      groupName: targetGroup,
      slo_definition_id: selectedSlo.id,
      data_source_name: datasource,
    })
    onOpenChange(false)
  }

  if (!open) return null

  const sloItems = (slos ?? [])
    .filter((s) => s.active)
    .map((s) => ({
      value: s.name,
      label: s.displayName ?? s.name,
      badge: s.sliName ?? undefined,
    }))

  const groupItems = (tree?.all_groups ?? []).map((g) => ({
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
            Assign SLO to Asset Group
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
          {/* Step 1: SLO (locked or selectable) */}
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
            {selectedSlo?.sliName && (
              <p className="mt-1 text-[10px] text-muted-foreground">
                SLI: <span className="text-foreground/70">{selectedSlo.sliName}</span>
                {selectedSlo.sliVersion != null && (
                  <span className="opacity-50"> v{selectedSlo.sliVersion}</span>
                )}
              </p>
            )}
          </div>

          {/* Step 2: Datasource */}
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Datasource</label>
            <SearchableComboBox
              value={datasource}
              items={dsItems}
              onSelect={setDatasource}
              placeholder="Select datasource..."
            />
          </div>

          {/* Step 3: Group (locked or selectable) */}
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
            <p className="text-xs text-destructive">This SLO is already assigned to this group</p>
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
            disabled={!isValid || createAssignment.isPending}
            onClick={handleLink}
          >
            {createAssignment.isPending ? 'Assigning...' : 'Assign'}
          </Button>
        </div>
      </div>
    </div>
  )
}
