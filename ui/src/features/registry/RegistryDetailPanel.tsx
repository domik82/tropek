import { SANS_SERIF } from '@/lib/fonts'
import type { SloDefinition } from '@/features/slos'
import type { SliDefinition } from '@/features/slis'
import type { SelectedNode } from './types'
import { DatasourceDetailView } from './details/DatasourceDetailView'
import { SliDetailView } from './details/SliDetailView'
import { SloDetailView } from './details/SloDetailView'
import { AssetBindingView } from './details/AssetBindingView'

interface RegistryDetailPanelProps {
  selected: SelectedNode | null
  onNavigate: (node: SelectedNode) => void
  onEditDatasource?: (name: string) => void
  onNewSloVersion?: (slo: SloDefinition) => void
  onNewSliVersion?: (sli: SliDefinition) => void
  onLinkSlo?: (groupName: string) => void
}

export function RegistryDetailPanel({
  selected,
  onNavigate,
  onEditDatasource,
  onNewSloVersion,
  onNewSliVersion,
  onLinkSlo,
}: RegistryDetailPanelProps) {
  if (!selected) {
    return (
      <div
        className="flex items-center justify-center h-full text-sm text-muted-foreground"
        style={{ fontFamily: SANS_SERIF }}
      >
        Select an item from the sidebar
      </div>
    )
  }

  if (selected.type === 'slo') {
    return (
      <SloDetailView
        name={selected.name}
        onNavigate={onNavigate}
        onNewVersion={onNewSloVersion ?? (() => {})}
      />
    )
  }

  if (selected.type === 'sli') {
    return (
      <SliDetailView
        name={selected.name}
        onNavigate={onNavigate}
        onNewVersion={onNewSliVersion ?? (() => {})}
      />
    )
  }

  if (selected.type === 'datasource') {
    return (
      <DatasourceDetailView
        name={selected.name}
        onNavigate={onNavigate}
        onEdit={() => onEditDatasource?.(selected.name)}
      />
    )
  }

  // asset, group, binding — show binding context
  // For group nodes, the group name IS selected.name; for asset/binding nodes it's in groupName
  const isGroup = selected.type === 'group'
  const groupName = isGroup ? selected.name : (selected.groupName ?? '')
  return (
    <AssetBindingView
      assetName={selected.name}
      groupName={groupName}
      isGroup={isGroup}
      onNavigate={onNavigate}
      onLinkSlo={() => onLinkSlo?.(groupName)}
    />
  )
}
