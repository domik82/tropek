// ui/src/pages/AssetNavigatorPage.tsx
import { useSearchParams } from 'react-router-dom'
import { AssetTreePanel } from '@/features/navigator/components/AssetTreePanel'
import { GroupPanel } from '@/features/navigator/components/GroupPanel'
import { AssetPanel } from '@/features/navigator/components/AssetPanel'
import { AllEvaluationsPanel } from '@/features/navigator/components/AllEvaluationsPanel'

export function AssetNavigatorPage() {
  const [params, setParams] = useSearchParams()
  const selectedGroup = params.get('group') ?? undefined
  const selectedAsset = params.get('asset') ?? undefined
  const selectedEvalId = params.get('eval') ?? undefined

  function selectGroup(name: string) {
    setParams({ group: name })
  }

  function selectAsset(name: string, evalId?: string) {
    setParams(evalId ? { asset: name, eval: evalId } : { asset: name })
  }

  function selectAll() {
    setParams({})
  }

  return (
    <div className="flex h-[calc(100vh-49px)] overflow-hidden">
      <div className="w-64 shrink-0 border-r border-slate-700 overflow-y-auto">
        <AssetTreePanel
          selectedGroup={selectedGroup}
          selectedAsset={selectedAsset}
          onSelectGroup={selectGroup}
          onSelectAsset={selectAsset}
          onClearSelection={selectAll}
        />
      </div>
      <div className="flex-1 overflow-y-auto">
        {selectedAsset && <AssetPanel assetName={selectedAsset} initialEvalId={selectedEvalId} />}
        {!selectedAsset && selectedGroup && (
          <GroupPanel groupName={selectedGroup} onSelectAsset={selectAsset} />
        )}
        {!selectedAsset && !selectedGroup && (
          <AllEvaluationsPanel onSelectAsset={selectAsset} />
        )}
      </div>
    </div>
  )
}
