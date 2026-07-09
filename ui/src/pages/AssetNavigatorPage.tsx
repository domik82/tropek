// ui/src/pages/AssetNavigatorPage.tsx
import { useSearchParams } from 'react-router-dom'
import { withTimeParamsLast } from '@/lib/search-params'
import { AssetTree } from '@/components/AssetTree'
import { GroupPanel, AssetPanel } from '@/features/navigator'
import { AllEvaluationsPanel } from '@/features/navigator/components/AllEvaluationsPanel'

export function AssetNavigatorPage() {
  const [params, setParams] = useSearchParams()
  const selectedGroup = params.get('group') ?? null
  const selectedAsset = params.get('asset') ?? null
  const selectedEvalId = params.get('eval') ?? undefined

  const selectGroup = (name: string | null) => {
    setParams(prev => {
      const next = new URLSearchParams(prev)
      next.delete('group')
      next.delete('asset')
      next.delete('eval')
      if (name) next.set('group', name)
      return withTimeParamsLast(next)
    })
  }

  const selectAsset = (name: string, groupName?: string, evalId?: string) => {
    setParams(prev => {
      const next = new URLSearchParams(prev)
      next.delete('asset')
      next.delete('eval')
      const group = groupName ?? selectedGroup
      if (group) next.set('group', group)
      else next.delete('group')
      next.set('asset', name)
      if (evalId) next.set('eval', evalId)
      return withTimeParamsLast(next)
    })
  }

  return (
    <div className="flex h-[calc(100vh-49px)] overflow-hidden">
      <AssetTree
        mode="navigator"
        selectedGroup={selectedGroup}
        selectedAsset={selectedAsset}
        onSelectGroup={selectGroup}
        onSelectAsset={(name, groupName) => selectAsset(name, groupName)}
        width={260}
      />
      <div className="flex-1 overflow-y-auto">
        {selectedAsset && <AssetPanel key={selectedAsset} assetName={selectedAsset} initialEvalId={selectedEvalId} />}
        {!selectedAsset && selectedGroup && (
          <GroupPanel
            groupName={selectedGroup}
            onSelectAsset={(name: string, evalId?: string) => selectAsset(name, selectedGroup, evalId)}
          />
        )}
        {!selectedAsset && !selectedGroup && (
          <AllEvaluationsPanel
            onSelectAsset={(name: string, evalId?: string) => selectAsset(name, undefined, evalId)}
          />
        )}
      </div>
    </div>
  )
}
