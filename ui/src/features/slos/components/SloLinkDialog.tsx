import { useState, useEffect } from 'react'
import { FieldLabel } from '@/components/ui/field-label'
import { FormDialog } from '@/components/ui/form-dialog'
import { useDatasources } from '@/features/datasources/hooks'
import { useSliDefinitions } from '@/features/slis/hooks'
import {
  useGroupTree, useSlos,
  useCreateGroupSloBinding, useGroupSloBindings,
} from '../hooks'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  lockedSloName?: string
  lockedGroupName?: string
}

export function SloLinkDialog({ open, onOpenChange, lockedSloName, lockedGroupName }: Props) {
  const [datasource, setDatasource] = useState('')
  const [sliName, setSliName] = useState('')
  const [groupName, setGroupName] = useState(lockedGroupName ?? '')
  const [sloName, setSloName] = useState(lockedSloName ?? '')

  const { data: datasources } = useDatasources()
  const selectedDs = datasources?.find(d => d.name === datasource)
  const { data: slis } = useSliDefinitions(selectedDs?.adapter_type)
  const { data: tree } = useGroupTree()
  const { data: slos } = useSlos()
  const { data: existingBindings } = useGroupSloBindings(groupName || lockedGroupName || '')
  const createBinding = useCreateGroupSloBinding()

  useEffect(() => {
    if (lockedGroupName) setGroupName(lockedGroupName)
    if (lockedSloName) setSloName(lockedSloName)
  }, [lockedGroupName, lockedSloName])

  useEffect(() => { setSliName('') }, [datasource])

  useEffect(() => {
    if (open) {
      setDatasource('')
      setSliName('')
      if (!lockedGroupName) setGroupName('')
      if (!lockedSloName) setSloName('')
    }
  }, [open, lockedGroupName, lockedSloName])

  const isDuplicate = existingBindings?.some(b => b.slo_name === sloName) ?? false
  const isValid = !!(datasource && sliName && groupName && sloName && !isDuplicate)

  const handleLink = async () => {
    const targetGroup = lockedGroupName ?? groupName
    await createBinding.mutateAsync({
      groupName: targetGroup,
      slo_name: sloName,
      data_source_name: datasource,
    })
    onOpenChange(false)
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Link SLO to Asset Group"
      submitLabel="Link"
      pendingLabel="Linking..."
      onSubmit={() => void handleLink()}
      canSubmit={isValid}
      isPending={createBinding.isPending}
    >
      <div>
        <FieldLabel>Datasource</FieldLabel>
        <select
          value={datasource}
          onChange={e => setDatasource(e.target.value)}
          className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50"
        >
          <option value="">Select datasource...</option>
          {datasources?.map(ds => (
            <option key={ds.id} value={ds.name}>
              {ds.display_name ?? ds.name} ({ds.adapter_type})
            </option>
          ))}
        </select>
      </div>
      <div>
        <FieldLabel>
          SLI {selectedDs && <span className="text-[10px] opacity-60 normal-case">— filtered to {selectedDs.adapter_type}</span>}
        </FieldLabel>
        <select
          value={sliName}
          onChange={e => setSliName(e.target.value)}
          disabled={!datasource}
          className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {!datasource
            ? <option value="">Select datasource first...</option>
            : <option value="">Select SLI...</option>
          }
          {slis?.filter(s => s.active).map(s => (
            <option key={s.id} value={s.name}>{s.display_name ?? s.name}</option>
          ))}
        </select>
      </div>
      {lockedSloName ? (
        <div>
          <FieldLabel>SLO</FieldLabel>
          <div className="bg-muted/30 border border-border rounded px-3 py-2 text-sm text-muted-foreground">
            {lockedSloName} <span className="text-xs opacity-50">(locked)</span>
          </div>
        </div>
      ) : (
        <div>
          <FieldLabel>SLO</FieldLabel>
          <select
            value={sloName}
            onChange={e => setSloName(e.target.value)}
            className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50"
          >
            <option value="">Select SLO...</option>
            {slos?.filter(s => s.active).map(s => (
              <option key={s.name} value={s.name}>{s.display_name ?? s.name}</option>
            ))}
          </select>
        </div>
      )}
      {lockedGroupName ? (
        <div>
          <FieldLabel>Asset Group</FieldLabel>
          <div className="bg-muted/30 border border-border rounded px-3 py-2 text-sm text-muted-foreground">
            {lockedGroupName} <span className="text-xs opacity-50">(locked)</span>
          </div>
        </div>
      ) : (
        <div>
          <FieldLabel>Asset Group</FieldLabel>
          <select
            value={groupName}
            onChange={e => setGroupName(e.target.value)}
            className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50"
          >
            <option value="">Select group...</option>
            {tree?.all_groups.map(g => (
              <option key={g.id} value={g.name}>{g.display_name ?? g.name}</option>
            ))}
          </select>
        </div>
      )}
      {isDuplicate && (
        <p className="text-xs text-destructive">This SLO is already linked to this group</p>
      )}
    </FormDialog>
  )
}
