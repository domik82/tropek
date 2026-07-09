// src/pages/AssetsPage.tsx
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AssetTree } from '@/components/AssetTree'
import { GroupDetailPanel, AllAssetsPanel, AssetCreateDialog } from '@/features/assets'

export function AssetsPage() {
  const [params, setParams] = useSearchParams()
  const selectedGroup = params.get('group') ?? null
  const selectedAsset = params.get('asset') ?? null
  const [createAssetOpen, setCreateAssetOpen] = useState(false)

  return (
    <div className="flex h-[calc(100vh-49px)] overflow-hidden">
      <AssetTree
        mode="assets"
        selectedGroup={selectedGroup}
        selectedAsset={selectedAsset}
        onSelectGroup={name => setParams(prev => {
          const next = new URLSearchParams(prev)
          next.delete('group'); next.delete('asset')
          if (name) next.set('group', name)
          return next
        })}
        onSelectAsset={(name, groupName) => setParams(prev => {
          const next = new URLSearchParams(prev)
          next.delete('group'); next.delete('asset')
          if (groupName) next.set('group', groupName)
          next.set('asset', name)
          return next
        })}
        width={260}
        onAddAsset={() => setCreateAssetOpen(true)}
      />
      <div className="flex-1 overflow-y-auto">
        {selectedGroup && selectedGroup !== '__ungrouped__' && (
          <GroupDetailPanel
            groupName={selectedGroup}
            onSelectGroup={name => setParams(prev => {
              const next = new URLSearchParams(prev)
              next.delete('asset')
              next.set('group', name)
              return next
            })}
            selectedAsset={selectedAsset}
          />
        )}
        {(!selectedGroup || selectedGroup === '__ungrouped__') && (
          <AllAssetsPanel />
        )}
      </div>
      <AssetCreateDialog open={createAssetOpen} onOpenChange={setCreateAssetOpen} />
    </div>
  )
}
