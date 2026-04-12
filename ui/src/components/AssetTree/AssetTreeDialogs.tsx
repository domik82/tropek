// ui/src/components/AssetTree/AssetTreeDialogs.tsx
import { useState } from 'react'
import { SloLinkDialog } from '@/features/slos'
import {
  AssetTypesDialog, AddAssetToGroupDialog, AssetEditDialog,
  GroupCreateDialog, GroupEditDialog, GroupDeleteDialog,
} from '@/features/assets'
import type { TreeMode } from './types'

export interface DialogState {
  createDialogOpen: boolean
  editingGroupName: string | null
  deletingGroupName: string | null
  linkingGroupName: string | null
  typesDialogOpen: boolean
  addAssetGroupName: string | null
  editingAssetName: string | null
}

// eslint-disable-next-line react-refresh/only-export-components
export function useDialogState() {
  const [state, setState] = useState<DialogState>({
    createDialogOpen: false,
    editingGroupName: null,
    deletingGroupName: null,
    linkingGroupName: null,
    typesDialogOpen: false,
    addAssetGroupName: null,
    editingAssetName: null,
  })

  function update<K extends keyof DialogState>(key: K, value: DialogState[K]) {
    setState(prev => ({ ...prev, [key]: value }))
  }

  return { dialogState: state, updateDialog: update }
}

interface Props {
  dialogState: DialogState
  mode: TreeMode
  selectedGroup: string | null
  onSelectGroup: (name: string | null) => void
  onCloseCreate: () => void
  onCloseEdit: () => void
  onCloseDelete: () => void
  onCloseLink: () => void
  onCloseTypes: () => void
  onCloseAddAsset: () => void
  onCloseEditAsset: () => void
  hasExternalCreateGroup: boolean
  hasExternalEditGroup: boolean
  hasExternalDeleteGroup: boolean
  hasExternalAddSloLink: boolean
}

export function AssetTreeDialogs({
  dialogState, mode, selectedGroup, onSelectGroup,
  onCloseCreate, onCloseEdit, onCloseDelete, onCloseLink,
  onCloseTypes, onCloseAddAsset, onCloseEditAsset,
  hasExternalCreateGroup, hasExternalEditGroup,
  hasExternalDeleteGroup, hasExternalAddSloLink,
}: Props) {
  return (
    <>
      {!hasExternalCreateGroup && (
        <GroupCreateDialog
          open={dialogState.createDialogOpen}
          onOpenChange={open => { if (!open) onCloseCreate() }}
        />
      )}
      {!hasExternalEditGroup && (
        <GroupEditDialog
          open={dialogState.editingGroupName !== null}
          onOpenChange={open => { if (!open) onCloseEdit() }}
          groupName={dialogState.editingGroupName}
        />
      )}
      {!hasExternalDeleteGroup && (
        <GroupDeleteDialog
          open={dialogState.deletingGroupName !== null}
          onOpenChange={open => { if (!open) onCloseDelete() }}
          groupName={dialogState.deletingGroupName}
          onDeleted={() => {
            if (dialogState.deletingGroupName === selectedGroup) onSelectGroup(null)
            onCloseDelete()
          }}
        />
      )}
      <AssetTypesDialog
        open={dialogState.typesDialogOpen}
        onOpenChange={open => { if (!open) onCloseTypes() }}
      />
      <AddAssetToGroupDialog
        open={dialogState.addAssetGroupName !== null}
        onOpenChange={open => { if (!open) onCloseAddAsset() }}
        groupName={dialogState.addAssetGroupName}
      />
      <AssetEditDialog
        open={dialogState.editingAssetName !== null}
        onOpenChange={open => { if (!open) onCloseEditAsset() }}
        assetName={dialogState.editingAssetName}
      />
      {!hasExternalAddSloLink && mode === 'slo' && (
        <SloLinkDialog
          open={dialogState.linkingGroupName !== null}
          onOpenChange={open => { if (!open) onCloseLink() }}
          lockedGroupName={dialogState.linkingGroupName ?? undefined}
        />
      )}
    </>
  )
}
