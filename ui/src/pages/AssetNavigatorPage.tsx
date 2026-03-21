// ui/src/pages/AssetNavigatorPage.tsx
import { useSearchParams } from 'react-router-dom'
import { AssetTree } from '@/components/AssetTree'
import { GroupPanel } from '@/features/navigator/components/GroupPanel'
import { AssetPanel } from '@/features/navigator/components/AssetPanel'
import { AllEvaluationsPanel } from '@/features/navigator/components/AllEvaluationsPanel'

export function AssetNavigatorPage() {
  const [params, setParams] = useSearchParams()
  const selectedGroup = params.get('group') ?? null
  const selectedAsset = params.get('asset') ?? null
  const selectedEvalId = params.get('eval') ?? undefined

  const handleSelectAsset = (name: string, groupName?: string) => {
    const next: Record<string, string> = { asset: name }
    const group = groupName ?? selectedGroup
    if (group) next.group = group
    setParams(next)
  }

  return (
    <div className="flex h-[calc(100vh-49px)] overflow-hidden">
      <AssetTree
        mode="navigator"
        selectedGroup={selectedGroup}
        selectedAsset={selectedAsset}
        onSelectGroup={name => name ? setParams({ group: name }) : setParams({})}
        onSelectAsset={handleSelectAsset}
        width={260}
      />
      <div className="flex-1 overflow-y-auto">
        {selectedAsset && <AssetPanel key={selectedAsset} assetName={selectedAsset} initialEvalId={selectedEvalId} />}
        {!selectedAsset && selectedGroup && (
          <GroupPanel groupName={selectedGroup} onSelectAsset={(name: string) => handleSelectAsset(name)} />
        )}
        {!selectedAsset && !selectedGroup && (
          <AllEvaluationsPanel onSelectAsset={(name: string) => handleSelectAsset(name)} />
        )}
      </div>
    </div>
  )
}
