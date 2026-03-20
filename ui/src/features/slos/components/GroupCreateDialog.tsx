import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
} from '@/components/ui/dialog'
import { GroupTreeSelector } from '@/features/assets/components/GroupTreeSelector'
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

  const isValid = name.length > 0 && /^[a-z0-9-]+$/.test(name)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Asset Group</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">
              Name <span className="text-destructive">*</span>
            </label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="production-apis"
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
            />
            {name && !isValid && (
              <p className="text-xs text-destructive mt-1">lowercase letters, numbers, hyphens only</p>
            )}
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">Display Name</label>
            <input
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder="Production APIs"
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
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
              />
            )}
          </div>
        </div>
        <DialogFooter>
          <DialogClose className="px-3 py-1.5 text-sm border border-border rounded text-muted-foreground hover:text-foreground transition-colors">
            Cancel
          </DialogClose>
          <button
            onClick={handleCreate}
            disabled={!isValid || create.isPending}
            className="px-3 py-1.5 text-sm bg-primary/30 border border-primary/50 rounded text-primary hover:bg-primary/40 transition-colors disabled:opacity-40"
          >
            {create.isPending ? 'Creating…' : 'Create'}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
