import { useState, useMemo, useRef, useEffect } from 'react'
import { useQueries } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { TreeFilter, TreeNode, getEntityIcon } from '@/components/tree'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import { groupKeys } from '@/lib/queryKeys'
import { TagFilterBar } from '@/components/shared/TagFilterBar'
import { RegistryTree } from './RegistryTree'
import { buildSloTree, buildDatasourceTree, buildAssetTree, filterTree } from './useRegistryTree'
import type { MinBinding } from './useRegistryTree'
import { useSlos, useGroupTree, useSloTagKeys, useSloTagValues } from '@/features/slos/hooks'
import { fetchGroupSloBindings } from '@/features/slos/api'
import { useSliDefinitions } from '@/features/slis/hooks'
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
  onSelect: (node: SelectedNode | null) => void
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

  // Fetch SLO bindings for all groups to build hierarchical trees
  const groupNames = useMemo(
    () => (tree?.all_groups ?? []).map(g => g.name).filter(n => n !== '__ungrouped__'),
    [tree],
  )
  const bindingQueries = useQueries({
    queries: groupNames.map(name => ({
      queryKey: groupKeys.bindings(name),
      queryFn: () => fetchGroupSloBindings(name),
    })),
  })

  const { allBindings, groupBindingsMap } = useMemo(() => {
    const flat: MinBinding[] = []
    const byGroup: Record<string, MinBinding[]> = {}
    for (let i = 0; i < groupNames.length; i++) {
      const data = bindingQueries[i]?.data ?? []
      const bindings: MinBinding[] = data.map(b => ({
        slo_name: b.slo_name,
        data_source_name: b.data_source_name,
      }))
      byGroup[groupNames[i]] = bindings
      flat.push(...bindings)
    }
    // Deduplicate flat bindings for SLO/DS trees
    const seen = new Set<string>()
    const unique = flat.filter(b => {
      const key = `${b.slo_name}|${b.data_source_name}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    return { allBindings: unique, groupBindingsMap: byGroup }
  }, [groupNames, bindingQueries])

  const treeNodes = useMemo(() => {
    if (mode === 'slo') return buildSloTree(slos ?? [], slis ?? [], datasources ?? [], allBindings)
    if (mode === 'datasource') return buildDatasourceTree(datasources ?? [], slis ?? [], slos ?? [], allBindings)
    return buildAssetTree(tree?.all_groups ?? [], groupBindingsMap, slos ?? [], slis ?? [])
  }, [mode, slos, slis, datasources, tree, allBindings, groupBindingsMap])

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

      {/* Search filter */}
      <div className="px-2 pt-2">
        <TreeFilter
          value={search}
          onChange={setSearch}
          placeholder="Filter..."
          resultCount={search ? filteredNodes.length : undefined}
        />
      </div>

      {/* Tag filter */}
      <div className="mt-1">
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
          hideSearch
        />
      </div>

      {/* "All" row */}
      <div style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}>
        <TreeNode
          icon={getEntityIcon('all')}
          iconColor={!selected ? 'var(--primary)' : '#8b949e'}
          label={mode === 'slo' ? 'All SLOs' : mode === 'datasource' ? 'All Datasources' : 'All Assets'}
          depth={0}
          isExpandable={false}
          isExpanded={false}
          isSelected={!selected}
          selectionColor="var(--primary)"
          isGroup
          onClick={() => onSelect(null)}
        />
        <div className="mx-3 my-1 border-t border-border/50" />
      </div>

      {/* Tree */}
      <RegistryTree nodes={filteredNodes} selected={selected} onSelect={onSelect} />

      {/* Create button */}
      <div className="p-2 border-t border-border">
        <CreateDropdown onCreateAction={onCreateAction} />
      </div>
    </div>
  )
}

function CreateDropdown({
  onCreateAction,
}: {
  onCreateAction: Props['onCreateAction']
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Close on click outside
  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  const items = [
    { type: 'slo' as const, label: 'New SLO', desc: 'Versioned quality gate definition', color: ENTITY_COLORS.slo },
    { type: 'sli' as const, label: 'New SLI Definition', desc: 'Service level indicator template', color: ENTITY_COLORS.sli },
    { type: 'datasource' as const, label: 'New Datasource', desc: 'Metric source connection', color: ENTITY_COLORS.ds },
    { type: 'group' as const, label: 'New Asset Group', desc: 'Group assets and bind SLOs', color: ENTITY_COLORS.group },
  ]

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-center gap-1.5 py-2 text-xs font-medium rounded border border-primary/40 text-primary hover:bg-primary/10 transition-colors"
      >
        <Plus className="size-3.5" /> Create
      </button>
      {open && (
        <div
          className="absolute bottom-full mb-1 left-0 w-full min-w-[280px] bg-popover border border-border rounded-xl shadow-xl overflow-hidden py-2 z-50"
          style={{ fontFamily: SANS_SERIF }}
        >
          {items.map(item => (
            <button
              key={item.type}
              className="flex items-start gap-3 w-full text-left px-3 py-2.5 transition-colors hover:bg-accent group"
              onClick={() => {
                onCreateAction(item.type)
                setOpen(false)
              }}
            >
              <div
                className="w-[3px] rounded-full shrink-0 mt-0.5"
                style={{ backgroundColor: item.color, height: 36 }}
              />
              <div className="min-w-0">
                <div className="text-[13px] font-medium text-popover-foreground">{item.label}</div>
                <div className="text-[11px] text-muted-foreground mt-0.5">{item.desc}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
