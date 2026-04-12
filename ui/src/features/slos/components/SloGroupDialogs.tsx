// ui/src/features/slos/components/SloGroupDialogs.tsx
import { GroupCreateDialog, GroupEditDialog, GroupDeleteDialog } from '@/features/assets'
import { SloLinkDialog } from './SloLinkDialog'

interface Props {
  createGroupOpen: boolean
  onCloseCreateGroup: () => void
  editGroupName: string | null
  onCloseEditGroup: () => void
  deleteGroupName: string | null
  onCloseDeleteGroup: () => void
  onGroupDeleted: () => void
  linkFromGroup: string | null
  onCloseLinkFromGroup: () => void
  linkFromSlo: string | null
  onCloseLinkFromSlo: () => void
}

export function SloGroupDialogs({
  createGroupOpen, onCloseCreateGroup,
  editGroupName, onCloseEditGroup,
  deleteGroupName, onCloseDeleteGroup, onGroupDeleted,
  linkFromGroup, onCloseLinkFromGroup,
  linkFromSlo, onCloseLinkFromSlo,
}: Props) {
  return (
    <>
      <GroupCreateDialog
        open={createGroupOpen}
        onOpenChange={open => { if (!open) onCloseCreateGroup() }}
      />
      <GroupEditDialog
        open={editGroupName !== null}
        onOpenChange={open => { if (!open) onCloseEditGroup() }}
        groupName={editGroupName}
      />
      <GroupDeleteDialog
        open={deleteGroupName !== null}
        onOpenChange={open => { if (!open) onCloseDeleteGroup() }}
        groupName={deleteGroupName}
        onDeleted={onGroupDeleted}
      />

      {/* SLO Link Dialogs - group entry point */}
      <SloLinkDialog
        open={linkFromGroup !== null}
        onOpenChange={open => { if (!open) onCloseLinkFromGroup() }}
        lockedGroupName={linkFromGroup ?? undefined}
      />

      {/* SLO Link Dialogs - SLO entry point */}
      <SloLinkDialog
        open={linkFromSlo !== null}
        onOpenChange={open => { if (!open) onCloseLinkFromSlo() }}
        lockedSloName={linkFromSlo ?? undefined}
      />
    </>
  )
}
