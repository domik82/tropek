// ui/src/pages/AssetNavigatorPage.tsx
import { useSearchParams } from 'react-router-dom'
import { AssetTreePanel } from '@/features/navigator/components/AssetTreePanel'
import { GroupPanel } from '@/features/navigator/components/GroupPanel'
import { AssetPanel } from '@/features/navigator/components/AssetPanel'

export function AssetNavigatorPage() {
  const [params, setParams] = useSearchParams()
  const selectedGroup = params.get('group') ?? undefined
  const selectedAsset = params.get('asset') ?? undefined

  function selectGroup(name: string) {
    setParams({ group: name })
  }

  function selectAsset(name: string) {
    setParams({ asset: name })
  }

  function clearSelection() {
    setParams({})
  }

  return (
    <div className="flex h-[calc(100vh-49px)] overflow-hidden">
      <div className="w-64 shrink-0 border-r border-border overflow-y-auto">
        <AssetTreePanel
          selectedGroup={selectedGroup}
          selectedAsset={selectedAsset}
          onSelectGroup={selectGroup}
          onSelectAsset={selectAsset}
          onClearSelection={clearSelection}
        />
      </div>
      <div className="flex-1 overflow-y-auto">
        {selectedAsset && <AssetPanel assetName={selectedAsset} />}
        {!selectedAsset && selectedGroup && (
          <GroupPanel groupName={selectedGroup} onSelectAsset={selectAsset} />
        )}
        {!selectedAsset && !selectedGroup && (
          <div className="p-8 text-muted-foreground text-sm">
            Select a group or asset from the tree to load evaluations.
          </div>
        )}
      </div>
    </div>
  )
}
