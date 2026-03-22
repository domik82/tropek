import { useState, useMemo } from 'react'
import { Plus } from 'lucide-react'
import { TagFilterBar } from '@/components/shared/TagFilterBar'
import { RegistryTree } from './RegistryTree'
import { buildSloTree, buildDatasourceTree, buildAssetTree, filterTree } from './useRegistryTree'
import { useSlos, useGroupTree, useSloTagKeys, useSloTagValues } from '@/features/slos/hooks'
import { useSliDefinitions, useSliTagKeys, useSliTagValues } from '@/features/slis/hooks'
import { useDatasources, useDatasourceTagKeys, useDatasourceTagValues } from '@/features/datasources/hooks'
import { useTagKeys, useTagValues } from '@/features/assets/hooks'
import type { RegistryMode, SelectedNode, TagFilter } from './types'

const MODES: { key: RegistryMode; label: string }[] = [
  { key: 'asset', label: 'Asset' },
  { key: 'slo', label: 'SLO' },
  { key: 'datasource', label: 'Datasource' },
]

interface Props {
  mode: RegistryMode
  onModeChange: (mode: RegistryMode) => void
  selected: SelectedNode | null
  onSelect: (node: SelectedNode) => void
  onCreateAction: (type: 'datasource' | 'sli' | 'slo' | 'group', context?: { adapterType?: string }) => void
}

export function RegistrySidebar({ mode, onModeChange, selected, onSelect, onCreateAction }: Props) {
  const [search, setSearch] = useState('')
  const [tags, setTags] = useState<TagFilter[]>([])
  const [pendingTagKey, setPendingTagKey] = useState('')

  // Data fetching
  const { data: slos } = useSlos()
  const { data: slis } = useSliDefinitions()
  const { data: datasources } = useDatasources()
  const { data: tree } = useGroupTree()

  // Tag suggestions — mode-dependent
  const { data: sloTagKeys, isLoading: sloKeysLoading } = useSloTagKeys()
  const { data: sloTagValues, isLoading: sloValsLoading } = useSloTagValues(pendingTagKey)
  const { data: dsTagKeys, isLoading: dsKeysLoading } = useDatasourceTagKeys()
  const { data: dsTagValues, isLoading: dsValsLoading } = useDatasourceTagValues(pendingTagKey)
  const { data: assetTagKeys, isLoading: assetKeysLoading } = useTagKeys()
  const { data: assetTagValues, isLoading: assetValsLoading } = useTagValues(pendingTagKey || null)

  const tagKeySuggestions =
    mode === 'slo'
      ? (sloTagKeys ?? [])
      : mode === 'datasource'
        ? (dsTagKeys ?? [])
        : (assetTagKeys ?? [])
  const tagValueSuggestions =
    mode === 'slo'
      ? (sloTagValues ?? [])
      : mode === 'datasource'
        ? (dsTagValues ?? [])
        : (assetTagValues ?? [])
  const isLoadingKeys =
    mode === 'slo' ? sloKeysLoading : mode === 'datasource' ? dsKeysLoading : assetKeysLoading
  const isLoadingValues =
    mode === 'slo' ? sloValsLoading : mode === 'datasource' ? dsValsLoading : assetValsLoading

  // Build tree nodes (pass empty links — useAllGroupLinks not yet created)
  const treeNodes = useMemo(() => {
    if (mode === 'slo') return buildSloTree(slos ?? [], slis ?? [], datasources ?? [], [])
    if (mode === 'datasource') return buildDatasourceTree(datasources ?? [], slis ?? [], slos ?? [], [])
    return buildAssetTree(tree?.all_groups ?? [], {})
  }, [mode, slos, slis, datasources, tree])

  const filteredNodes = useMemo(() => filterTree(treeNodes, search), [treeNodes, search])

  return (
    <div className="flex flex-col h-full border-r border-border bg-black/30" style={{ width: 260 }}>
      {/* Segmented control */}
      <div className="flex gap-0.5 p-2 bg-muted/30 mx-2 mt-2 rounded-md">
        {MODES.map(m => (
          <button
            key={m.key}
            onClick={() => onModeChange(m.key)}
            className={`flex-1 text-center py-1 text-xs font-medium rounded transition-colors ${
              mode === m.key
                ? 'bg-primary/15 text-primary'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Search + tag filter */}
      <div className="mt-2">
        <TagFilterBar
          search={search}
          onSearchChange={setSearch}
          tags={tags}
          onTagsChange={setTags}
          tagKeySuggestions={tagKeySuggestions}
          tagValueSuggestions={tagValueSuggestions}
          onTagKeySelected={setPendingTagKey}
          isLoadingKeys={isLoadingKeys}
          isLoadingValues={isLoadingValues}
        />
      </div>

      {/* Tree */}
      <RegistryTree nodes={filteredNodes} selected={selected} onSelect={onSelect} />

      {/* Create button */}
      <div className="p-2 border-t border-border">
        <CreateDropdown mode={mode} onCreateAction={onCreateAction} />
      </div>
    </div>
  )
}

function CreateDropdown({
  mode: _mode,
  onCreateAction,
}: {
  mode: RegistryMode
  onCreateAction: Props['onCreateAction']
}) {
  const [open, setOpen] = useState(false)

  const items = [
    { type: 'slo' as const, label: 'New SLO', color: '#7dc540' },
    { type: 'sli' as const, label: 'New SLI Definition', color: '#A371F7' },
    { type: 'datasource' as const, label: 'New Datasource', color: '#58A6FF' },
    { type: 'group' as const, label: 'New Asset Group', color: '#8B949E' },
  ]

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-center gap-1.5 py-2 text-xs font-medium rounded border border-primary/40 text-primary hover:bg-primary/10 transition-colors"
      >
        <Plus className="size-3.5" /> Create
      </button>
      {open && (
        <div
          className="absolute bottom-full mb-1 left-0 w-full bg-popover border border-border rounded-lg shadow-lg py-1 z-50"
          style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
        >
          {items.map(item => (
            <button
              key={item.type}
              className="w-full px-3 py-1.5 text-xs text-left hover:bg-accent transition-colors flex items-center gap-2"
              onClick={() => {
                onCreateAction(item.type)
                setOpen(false)
              }}
            >
              <span className="w-1 h-4 rounded-full" style={{ backgroundColor: item.color }} />
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
