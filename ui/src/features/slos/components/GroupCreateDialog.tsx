import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
} from '@/components/ui/dialog'
import { FieldLabel } from '@/components/ui/field-label'
import { Input } from '@/components/ui/input'
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
            <FieldLabel required>Name</FieldLabel>
            <Input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="production-apis"
            />
            {name && !isValid && (
              <p className="text-xs text-destructive mt-1">lowercase letters, numbers, hyphens only</p>
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
