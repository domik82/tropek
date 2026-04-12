import { useEffect, useState } from 'react'
import { FieldLabel } from '@/components/ui/field-label'
import { Input } from '@/components/ui/input'
import { FormDialog } from '@/components/ui/form-dialog'
import { GroupTreeSelector } from '@/features/assets/components/GroupTreeSelector'
import {
  useUpdateGroup, useGroupSloAssignments, useDeleteGroupSloAssignment, useGroupTree,
  useAddSubgroup,
} from '../hooks'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  groupName: string | null
}

export function GroupEditDialog({ open, onOpenChange, groupName }: Props) {
  const { data: tree } = useGroupTree()
  const group = tree?.all_groups.find(g => g.name === groupName)
  const { data: assignments } = useGroupSloAssignments(groupName ?? '')
  const updateGroup = useUpdateGroup()
  const unlinkSlo = useDeleteGroupSloAssignment()
  const addSubgroup = useAddSubgroup()

  const [displayName, setDisplayName] = useState('')
  const [description, setDescription] = useState('')
  const [parentGroup, setParentGroup] = useState('')

  const currentParent = tree?.all_groups.find(g =>
    g.subgroups.some(sg => sg.group_id === group?.id)
  )

  /* eslint-disable react-hooks/set-state-in-effect -- intentional reset on prop change */
  useEffect(() => {
    if (group) {
      setDisplayName(group.display_name ?? '')
      setDescription(group.description ?? '')
      setParentGroup(currentParent?.name ?? '')
    }
  }, [group, currentParent])
  /* eslint-enable react-hooks/set-state-in-effect */

  if (!groupName || !group) return null

  const handleSave = async () => {
    await updateGroup.mutateAsync({
      name: groupName,
      display_name: displayName || undefined,
      description: description || undefined,
    })
    const newParent = parentGroup || null
    const oldParent = currentParent?.name ?? null
    if (newParent !== oldParent && newParent && tree) {
      await addSubgroup.mutateAsync({
        parentName: newParent,
        childGroupId: group.id,
      })
    }
    onOpenChange(false)
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Edit Asset Group"
      submitLabel="Save"
      onSubmit={() => void handleSave()}
      canSubmit={true}
      isPending={updateGroup.isPending}
    >
      <div>
        <FieldLabel>Name</FieldLabel>
        <div className="bg-muted/30 border border-border rounded px-3 py-2 text-sm text-muted-foreground">
          {groupName}
        </div>
      </div>
      <div>
        <FieldLabel>Display Name</FieldLabel>
        <Input value={displayName} onChange={e => setDisplayName(e.target.value)} />
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
            excludeName={groupName}
          />
        )}
      </div>
      {assignments && assignments.length > 0 && (
        <div>
          <FieldLabel>Linked SLOs ({assignments.length})</FieldLabel>
          <div className="space-y-1">
            {assignments.map(assignment => (
              <div
                key={assignment.id}
                className="flex items-center justify-between text-xs py-1 border-b border-border/50"
              >
                <span className="text-foreground">
                  {assignment.sloName} → {assignment.dataSourceName}
                </span>
                <button
                  onClick={() => unlinkSlo.mutate({ groupName: groupName!, assignmentId: assignment.id })}
                  className="text-muted-foreground hover:text-destructive transition-colors"
                  title="Unlink"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </FormDialog>
  )
}
