import { useState, useMemo, useRef, useEffect } from 'react'
import { useSloGroups } from '@/features/slo-groups'
import { useQueries } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { TreeFilter, TreeNode, getEntityIcon } from '@/components/tree'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import { groupKeys } from '@/lib/queryKeys'
import { TagFilterBar } from '@/components/shared/TagFilterBar'
import { RegistryTree, SectionHeader } from './RegistryTree'
import { buildSloTree, buildSloSections, buildDatasourceTree, buildAssetTree, filterTree, buildSloGroupMap, mergeBindings } from './useRegistryTree'
import { useSlos, useGroupTree, useSloTagKeys, useSloTagValues, fetchGroupSloAssignments, fetchAssetSloAssignments, fetchAssetSloGroupAssignments } from '@/features/slos'
import { assignmentKeys } from '@/lib/queryKeys'
import { useSliDefinitions } from '@/features/slis'
import { useDatasources, useDatasourceTagKeys, useDatasourceTagValues } from '@/features/datasources'
import { useTagKeys, useTagValues } from '@/features/assets'
import type { RegistryMode, SelectedNode, TagFilter } from './ui-types'

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
  onCreateAction: (type: 'datasource' | 'sli' | 'slo' | 'group' | 'slo-template' | 'slo-group', context?: { adapterType?: string }) => void
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
  const { data: sloGroups } = useSloGroups()

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

  // Fetch SLO assignments for all groups and assets to build hierarchical trees
  const groupNames = useMemo(
    () => (tree?.allGroups ?? []).map(g => g.name).filter(n => n !== '__ungrouped__'),
    [tree],
  )
  const assetNames = useMemo(
    () => [...new Set((tree?.allGroups ?? []).flatMap(g => (g.members ?? []).map(m => m.assetName)))],
    [tree],
  )

  const groupAssignmentQueries = useQueries({
    queries: groupNames.map(name => ({
      queryKey: groupKeys.assignments(name),
      queryFn: () => fetchGroupSloAssignments(name),
    })),
  })
  const assetAssignmentQueries = useQueries({
    queries: assetNames.map(name => ({
      queryKey: assignmentKeys.asset(name),
      queryFn: () => fetchAssetSloAssignments(name),
    })),
  })
  // Also fetch SLO group assignments per asset — these are the primary
  // assignment mechanism (always-latest, no fan-out to direct assignments)
  const assetGroupAssignmentQueries = useQueries({
    queries: assetNames.map(name => ({
      queryKey: ['slo-group-assignments', 'asset', name],
      queryFn: () => fetchAssetSloGroupAssignments(name),
    })),
  })

  const sloGroupMap = useMemo(() => buildSloGroupMap(slos ?? []), [slos])

  const { allBindings, groupBindingsMap, assetBindingsMap } = useMemo(() => {
    return mergeBindings(
      groupNames,
      assetNames,
      groupAssignmentQueries.map(q => q.data ?? []),
      assetAssignmentQueries.map(q => q.data ?? []),
      assetGroupAssignmentQueries.map(q => q.data ?? []),
      sloGroupMap,
    )
  }, [groupNames, assetNames, groupAssignmentQueries, assetAssignmentQueries, assetGroupAssignmentQueries, sloGroupMap])

  const treeNodes = useMemo(() => {
    if (mode === 'slo') return buildSloTree(slos ?? [], slis ?? [], datasources ?? [], allBindings)
    if (mode === 'datasource') return buildDatasourceTree(datasources ?? [], slis ?? [], slos ?? [], allBindings)
    return buildAssetTree(tree?.topLevel ?? [], tree?.allGroups ?? [], groupBindingsMap, assetBindingsMap, slos ?? [], slis ?? [])
  }, [mode, slos, slis, datasources, tree, allBindings, groupBindingsMap, assetBindingsMap])

  const filteredNodes = useMemo(() => filterTree(treeNodes, search), [treeNodes, search])

  const sloSections = useMemo(() => {
    if (mode !== 'slo') return null
    return buildSloSections(slos ?? [], slis ?? [], datasources ?? [], allBindings, sloGroups ?? [])
  }, [mode, slos, slis, datasources, allBindings, sloGroups])

  return (
    <div className="flex flex-col h-full border-r border-border bg-sidebar-bg" style={{ width: 260 }}>
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

      {/* "All" row — only shown in asset mode where the tree has group hierarchy */}
      {mode === 'asset' && (
        <div style={{ fontFamily: SANS_SERIF }}>
          <TreeNode
            icon={getEntityIcon('all')}
            iconColor={!selected ? 'var(--primary)' : '#8b949e'}
            label="All Assets"
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
      )}

      {/* Tree */}
      {mode === 'slo' && sloSections ? (
        <div className="flex-1 overflow-y-auto" style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}>
          <SectionHeader label="STANDARD" />
          <RegistryTree nodes={filterTree(sloSections.standard, search)} selected={selected} onSelect={onSelect} />
          <SectionHeader label="TEMPLATES" />
          <RegistryTree nodes={filterTree(sloSections.templates, search)} selected={selected} onSelect={onSelect} />
          <SectionHeader label="GROUPS" />
          <RegistryTree nodes={filterTree(sloSections.groupNodes, search)} selected={selected} onSelect={onSelect} />
        </div>
      ) : (
        <RegistryTree nodes={filteredNodes} selected={selected} onSelect={onSelect} />
      )}

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
    { type: 'slo' as const, label: 'SLO Definition', desc: 'Standard SLO with criteria', color: ENTITY_COLORS.slo },
    { type: 'slo-template' as const, label: 'SLO Template', desc: 'Reusable template for groups', color: ENTITY_COLORS.template },
    { type: 'slo-group' as const, label: 'SLO Group', desc: 'Generate SLOs from template', color: ENTITY_COLORS.sloGroup },
    { type: 'sli' as const, label: 'SLI Definition', desc: 'Query templates for metrics', color: ENTITY_COLORS.sli },
    { type: 'datasource' as const, label: 'Datasource', desc: 'Connection to data backend', color: ENTITY_COLORS.ds },
    { type: 'group' as const, label: 'Asset Group', desc: 'Group assets and bind SLOs', color: ENTITY_COLORS.group },
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
