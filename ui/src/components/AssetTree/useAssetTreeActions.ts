import { useUpdateGroup } from '@/features/slos/hooks'
import type { TreeMode } from './types'

interface ActionCallbacks {
  onCreateGroup: (parentName?: string) => void
  onEditGroup: (name: string) => void
  onDeleteGroup: (name: string) => void
  onAddSloLink?: (groupName: string) => void
  onStartRename: (name: string) => void
  onSelectAsset?: (name: string) => void
}

export function useAssetTreeActions(_mode: TreeMode, callbacks: ActionCallbacks) {
  const updateGroup = useUpdateGroup()

  const handleRename = (name: string, newDisplayName: string) => {
    updateGroup.mutate({ name, display_name: newDisplayName })
  }

  const dispatch = (action: string, targetName: string) => {
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
        callbacks.onSelectAsset?.(targetName)
        break
      case 'removeFromGroup':
      case 'addAssetToGroup':
      case 'moveGroup':
      case 'duplicateGroup':
      case 'editAsset':
      case 'deleteAsset':
        // Phase 2 — no-op
        break
    }
  }

  return { dispatch, handleRename }
}
