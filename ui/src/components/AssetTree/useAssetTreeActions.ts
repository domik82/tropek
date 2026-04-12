import { useUpdateGroup, useRemoveGroupMember, useDeleteAsset } from '@/features/assets'
import type { TreeMode, ContextMenuState } from './types'

interface ActionCallbacks {
  onCreateGroup: (parentName?: string) => void
  onEditGroup: (name: string) => void
  onDeleteGroup: (name: string) => void
  onAddSloLink?: (groupName: string) => void
  onAddAssetToGroup?: (groupName: string) => void
  onEditAsset?: (assetName: string) => void
  onStartRename: (name: string) => void
  onSelectAsset?: (name: string, groupName: string) => void
}

export function useAssetTreeActions(_mode: TreeMode, callbacks: ActionCallbacks) {
  const updateGroup = useUpdateGroup()
  const removeMember = useRemoveGroupMember()
  const deleteAsset = useDeleteAsset()

  const handleRename = (name: string, newDisplayName: string) => {
    updateGroup.mutate({ name, display_name: newDisplayName })
  }

  const dispatch = (action: string, target: ContextMenuState['target']) => {
    const { name: targetName, groupName, assetId } = target
    switch (action) {
      case 'rename':
        callbacks.onStartRename(targetName)
        break
      case 'editDetails':
        callbacks.onEditGroup(targetName)
        break
      case 'addSubgroup':
        callbacks.onCreateGroup(targetName)
        break
      case 'linkSlo':
        callbacks.onAddSloLink?.(targetName)
        break
      case 'deleteGroup':
        callbacks.onDeleteGroup(targetName)
        break
      case 'viewEvaluations':
        if (groupName) callbacks.onSelectAsset?.(targetName, groupName)
        break
      case 'addAssetToGroup':
        callbacks.onAddAssetToGroup?.(targetName)
        break
      case 'editAsset':
        callbacks.onEditAsset?.(targetName)
        break
      case 'removeFromGroup':
        if (groupName && assetId) {
          removeMember.mutate({ groupName, assetId })
        }
        break
      case 'deleteAsset':
        deleteAsset.mutate(targetName)
        break
      case 'moveGroup':
      case 'duplicateGroup':
        // Coming soon — no-op
        break
    }
  }

  return { dispatch, handleRename }
}
