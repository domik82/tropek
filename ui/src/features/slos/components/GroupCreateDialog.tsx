import { useState } from 'react'
import { FieldLabel } from '@/components/ui/field-label'
import { Input } from '@/components/ui/input'
import { FormDialog } from '@/components/ui/form-dialog'
import { GroupTreeSelector } from '@/features/assets/components/GroupTreeSelector'
import { isValidEntityName, ENTITY_NAME_HINT } from '@/lib/validation'
import { useCreateGroup, useGroupTree, useAddSubgroup } from '../hooks'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function GroupCreateDialog({ open, onOpenChange }: Props) {
  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [description, setDescription] = useState('')
  const [parentGroup, setParentGroup] = useState('')
  const create = useCreateGroup()
  const addSubgroup = useAddSubgroup()
  const { data: tree } = useGroupTree()

  const handleCreate = async () => {
    const group = await create.mutateAsync({
      name,
      display_name: displayName || undefined,
      description: description || undefined,
    })
    if (parentGroup && tree) {
      await addSubgroup.mutateAsync({
        parentName: parentGroup,
        childGroupId: group.id,
      })
    }
    setName('')
    setDisplayName('')
    setDescription('')
    setParentGroup('')
    onOpenChange(false)
  }

  const isValid = isValidEntityName(name)

  return (
    <FormDialog
      open={open}
      onOpenChange={onOpenChange}
      title="New Asset Group"
      submitLabel="Create"
      pendingLabel="Creating…"
      onSubmit={() => void handleCreate()}
      canSubmit={isValid}
      isPending={create.isPending}
    >
      <div>
        <FieldLabel required>Name</FieldLabel>
        <Input value={name} onChange={e => setName(e.target.value)} placeholder="production-apis" />
        {name && !isValid && (
          <p className="text-xs text-destructive mt-1">{ENTITY_NAME_HINT}</p>
        )}
      </div>
      <div>
        <FieldLabel>Display Name</FieldLabel>
        <Input
          value={displayName}
          onChange={e => setDisplayName(e.target.value)}
          placeholder="Production APIs"
        />
      </div>
      <div>
        <FieldLabel>Description</FieldLabel>
        <Input
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="Optional description…"
        />
      </div>
      <div>
        <FieldLabel>Parent Group</FieldLabel>
        {tree && (
          <GroupTreeSelector
            tree={tree}
            value={parentGroup || null}
            onChange={name => setParentGroup(name ?? '')}
          />
        )}
      </div>
    </FormDialog>
  )
}
