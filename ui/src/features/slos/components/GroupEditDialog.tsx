import { useEffect, useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
} from '@/components/ui/dialog'
import { GroupTreeSelector } from '@/features/assets/components/GroupTreeSelector'
import {
  useUpdateGroup, useGroupSloBindings, useDeleteGroupSloBinding, useGroupTree,
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
  const { data: bindings } = useGroupSloBindings(groupName ?? '')
  const updateGroup = useUpdateGroup()
  const unlinkSlo = useDeleteGroupSloBinding()
  const addSubgroup = useAddSubgroup()

  const [displayName, setDisplayName] = useState('')
  const [description, setDescription] = useState('')
  const [parentGroup, setParentGroup] = useState('')

  const currentParent = tree?.all_groups.find(g =>
    g.subgroups.some(sg => sg.group_id === group?.id)
  )

  useEffect(() => {
    if (group) {
      setDisplayName(group.display_name ?? '')
      setDescription(group.description ?? '')
      setParentGroup(currentParent?.name ?? '')
    }
  }, [group, currentParent])

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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Asset Group</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">Name</label>
            <div className="bg-muted/30 border border-border rounded px-3 py-2 text-sm text-muted-foreground">
              {groupName}
            </div>
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">Display Name</label>
            <input
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50"
            />
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">Description</label>
            <input
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Optional description…"
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
            />
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">Parent Group</label>
            {tree && (
              <GroupTreeSelector
                tree={tree}
                value={parentGroup || null}
                onChange={name => setParentGroup(name ?? '')}
                excludeName={groupName}
              />
            )}
          </div>
          {bindings && bindings.length > 0 && (
            <div>
              <label className="text-xs uppercase text-muted-foreground block mb-1">
                Linked SLOs ({bindings.length})
              </label>
              <div className="space-y-1">
                {bindings.map(binding => (
                  <div
                    key={binding.id}
                    className="flex items-center justify-between text-xs py-1 border-b border-border/50"
                  >
                    <span className="text-foreground">
                      {binding.slo_name} → {binding.data_source_name}
                    </span>
                    <button
                      onClick={() => unlinkSlo.mutate({ groupName: groupName!, sloName: binding.slo_name })}
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
        </div>
        <DialogFooter>
          <DialogClose className="px-3 py-1.5 text-sm border border-border rounded text-muted-foreground hover:text-foreground transition-colors">
            Cancel
          </DialogClose>
          <button
            onClick={handleSave}
            disabled={updateGroup.isPending}
            className="px-3 py-1.5 text-sm bg-primary/30 border border-primary/50 rounded text-primary hover:bg-primary/40 transition-colors disabled:opacity-40"
          >
            {updateGroup.isPending ? 'Saving…' : 'Save'}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
