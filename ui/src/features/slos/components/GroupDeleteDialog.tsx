import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
} from '@/components/ui/dialog'
import { useDeleteGroup, useGroupTree } from '@/features/assets'
import { useGroupSloAssignments } from '../hooks'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  groupName: string | null
  onDeleted: () => void
}

export function GroupDeleteDialog({ open, onOpenChange, groupName, onDeleted }: Props) {
  const { data: tree } = useGroupTree()
  const group = tree?.allGroups.find(g => g.name === groupName)
  const { data: assignments } = useGroupSloAssignments(groupName ?? '')
  const deleteGroup = useDeleteGroup()
  const [choice, setChoice] = useState<'keep' | 'deactivate' | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)

  if (!groupName || !group) return null

  const subgroupCount = group.subgroups.length
  const linkCount = assignments?.length ?? 0

  const handleDelete = async () => {
    await deleteGroup.mutateAsync({
      name: groupName,
      deactivateSlos: choice === 'deactivate',
    })
    setChoice(null)
    setConfirmOpen(false)
    onOpenChange(false)
    onDeleted()
  }

  const confirmMessage = choice === 'keep'
    ? `Delete "${group.displayName ?? groupName}" and keep ${linkCount} SLO(s) active?`
    : `Delete "${group.displayName ?? groupName}" and deactivate ${linkCount} SLO(s)?`

  return (
    <>
      <Dialog open={open && !confirmOpen} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete "{group.displayName ?? groupName}"?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground leading-relaxed">
            This group has <strong>{linkCount} linked SLO(s)</strong>
            {subgroupCount > 0 && <> and <strong>{subgroupCount} subgroup(s)</strong></>}.
            Choose how to handle them:
          </p>
          <div className="space-y-2 py-2">
            <label
              className={`flex items-start gap-3 p-3 rounded border cursor-pointer transition-colors ${
                choice === 'keep' ? 'border-border bg-muted/30' : 'border-border/50 hover:border-border'
              }`}
            >
              <input
                type="radio"
                name="delete-choice"
                checked={choice === 'keep'}
                onChange={() => setChoice('keep')}
                className="mt-0.5"
              />
              <div>
                <div className="text-sm font-medium">Delete & Keep SLOs Active</div>
                <div className="text-xs text-muted-foreground">
                  Group and subgroups are deleted. Linked SLOs remain active and become ungrouped.
                </div>
              </div>
            </label>
            <label
              className={`flex items-start gap-3 p-3 rounded border cursor-pointer transition-colors ${
                choice === 'deactivate'
                  ? 'border-destructive/50 bg-destructive/5'
                  : 'border-border/50 hover:border-border'
              }`}
            >
              <input
                type="radio"
                name="delete-choice"
                checked={choice === 'deactivate'}
                onChange={() => setChoice('deactivate')}
                className="mt-0.5"
              />
              <div>
                <div className="text-sm font-medium text-destructive">Delete & Deactivate SLOs</div>
                <div className="text-xs text-muted-foreground">
                  Group and subgroups are deleted. All linked SLOs are marked inactive.
                </div>
              </div>
            </label>
          </div>
          <DialogFooter>
            <DialogClose className="px-3 py-1.5 text-sm border border-border rounded text-muted-foreground hover:text-foreground transition-colors">
              Cancel
            </DialogClose>
            <button
              onClick={() => setConfirmOpen(true)}
              disabled={choice === null}
              className="px-3 py-1.5 text-sm bg-destructive/30 border border-destructive/50 rounded text-destructive hover:bg-destructive/40 transition-colors disabled:opacity-40"
            >
              Delete
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Deletion</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">{confirmMessage}</p>
          <DialogFooter>
            <button
              onClick={() => setConfirmOpen(false)}
              className="px-3 py-1.5 text-sm border border-border rounded text-muted-foreground hover:text-foreground transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={deleteGroup.isPending}
              className="px-3 py-1.5 text-sm bg-destructive/30 border border-destructive/50 rounded text-destructive hover:bg-destructive/40 transition-colors disabled:opacity-40"
            >
              {deleteGroup.isPending ? 'Deleting…' : 'Confirm Delete'}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
