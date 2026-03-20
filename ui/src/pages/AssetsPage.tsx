// src/pages/AssetsPage.tsx
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AssetTree } from '@/components/AssetTree'
import { GroupDetailPanel } from '@/features/assets/components/GroupDetailPanel'
import { AllAssetsPanel } from '@/features/assets/components/AllAssetsPanel'
import { AssetCreateDialog } from '@/features/assets/components/AssetCreateDialog'

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
        onSelectGroup={name => name ? setParams({ group: name }) : setParams({})}
        onSelectAsset={name => setParams({ asset: name })}
        width={260}
        onAddAsset={() => setCreateAssetOpen(true)}
      />
      <div className="flex-1 overflow-y-auto">
        {selectedGroup && selectedGroup !== '__ungrouped__' && (
          <GroupDetailPanel
            groupName={selectedGroup}
            onSelectGroup={name => setParams({ group: name })}
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
