import type { SloGroup } from '@/features/slo-groups/types'
import type { TreeNode } from './types'

export interface MinSlo {
  name: string
  display_name?: string | null
  version: number
  active: boolean
  sli_name?: string | null
  sli_version?: number | null
  kind?: string
  tags?: Record<string, string>
}

export interface MinSli {
  name: string
  display_name?: string | null
  adapter_type: string
  active: boolean
  indicators?: Record<string, string>
}

export interface MinDs {
  name: string
  displayName?: string | null
  adapterType: string
}

export interface MinBinding {
  slo_name: string
  data_source_name: string
}

export interface MinGroup {
  name: string
  display_name?: string | null
  members?: { asset_name: string; asset_type_name?: string }[]
  subgroups?: { group_id: string; group_name: string }[]
}

export function buildSloTree(
  slos: MinSlo[],
  slis: MinSli[],
  datasources: MinDs[],
  bindings: MinBinding[],
): TreeNode[] {
  const sliByName = new Map(slis.map(s => [s.name, s]))
  const dsByName = new Map(datasources.map(d => [d.name, d]))

  return slos.filter(s => s.active).map(slo => {
    const sloBindings = bindings.filter(b => b.slo_name === slo.name)
    const dsNames = [...new Set(sloBindings.map(b => b.data_source_name))]

    const dsChildren: TreeNode[] = dsNames.map(dsName => ({
      id: `ds:${dsName}`,
      name: dsName,
      displayName: dsByName.get(dsName)?.displayName ?? undefined,
      type: 'datasource' as const,
    }))

    // SLI comes from the SLO definition, not from bindings
    const sliChildren: TreeNode[] = []
    if (slo.sli_name) {
      const sli = sliByName.get(slo.sli_name)
      const indicatorCount = sli?.indicators ? Object.keys(sli.indicators).length : 0
      sliChildren.push({
        id: `sli:${slo.sli_name}`,
        name: slo.sli_name,
        displayName: sli?.display_name ?? undefined,
        type: 'sli' as const,
        badge: indicatorCount > 0 ? `${indicatorCount}` : undefined,
        children: dsChildren,
      })
    }

    return {
      id: `slo:${slo.name}`,
      name: slo.name,
      displayName: slo.display_name ?? undefined,
      type: 'slo' as const,
      badge: `v${slo.version}`,
      children: sliChildren.length > 0 ? sliChildren : dsChildren,
    }
  })
}

export function buildDatasourceTree(
  datasources: MinDs[],
  slis: MinSli[],
  slos: MinSlo[],
  bindings: MinBinding[],
): TreeNode[] {
  const sloByName = new Map(slos.map(s => [s.name, s]))

  return datasources.map(ds => {
    // Find SLOs bound to this datasource
    const boundSloNames = [...new Set(
      bindings.filter(b => b.data_source_name === ds.name).map(b => b.slo_name),
    )]
    // Group bound SLOs by their sli_name (from the SLO definition)
    const sliToSlos = new Map<string, string[]>()
    for (const sloName of boundSloNames) {
      const slo = sloByName.get(sloName)
      const sliName = slo?.sli_name ?? '__none__'
      const existing = sliToSlos.get(sliName) ?? []
      existing.push(sloName)
      sliToSlos.set(sliName, existing)
    }

    const sliByName = new Map(slis.map(s => [s.name, s]))
    const sliChildren: TreeNode[] = []
    for (const [sliName, sloNames] of sliToSlos) {
      if (sliName === '__none__') continue
      const sli = sliByName.get(sliName)
      const sloChildren: TreeNode[] = sloNames.map(sloName => {
        const slo = sloByName.get(sloName)
        return {
          id: `slo:${sloName}`,
          name: sloName,
          displayName: slo?.display_name ?? undefined,
          type: 'slo' as const,
          badge: slo ? `v${slo.version}` : undefined,
        }
      })
      const indicatorCount = sli?.indicators ? Object.keys(sli.indicators).length : 0
      sliChildren.push({
        id: `sli:${sliName}`,
        name: sliName,
        displayName: sli?.display_name ?? undefined,
        type: 'sli' as const,
        badge: indicatorCount > 0 ? `${indicatorCount}` : undefined,
        children: sloChildren,
      })
    }
    // Also add SLOs without an SLI directly under the datasource
    const orphanSlos = sliToSlos.get('__none__') ?? []
    const orphanChildren: TreeNode[] = orphanSlos.map(sloName => {
      const slo = sloByName.get(sloName)
      return {
        id: `slo:${sloName}`,
        name: sloName,
        displayName: slo?.display_name ?? undefined,
        type: 'slo' as const,
        badge: slo ? `v${slo.version}` : undefined,
      }
    })

    return {
      id: `ds:${ds.name}`,
      name: ds.name,
      displayName: ds.displayName ?? undefined,
      type: 'datasource' as const,
      badge: `[${ds.adapterType}]`,
      children: [...sliChildren, ...orphanChildren],
    }
  })
}

export function buildAssetTree(
  topLevelGroups: MinGroup[],
  allGroups: MinGroup[],
  groupBindingsMap: Record<string, MinBinding[]>,
  assetBindingsMap: Record<string, MinBinding[]>,
  slos?: MinSlo[],
  slis?: MinSli[],
): TreeNode[] {
  const sloByName = new Map((slos ?? []).map(s => [s.name, s]))
  const sliByName = new Map((slis ?? []).map(s => [s.name, s]))
  const groupByName = new Map(allGroups.map(g => [g.name, g]))

  function buildGroupNode(group: MinGroup): TreeNode {
    const groupBindings = groupBindingsMap[group.name] ?? []

    // Subgroup children (recursive)
    const subgroupChildren: TreeNode[] = (group.subgroups ?? [])
      .map(sg => groupByName.get(sg.group_name))
      .filter((g): g is MinGroup => g != null)
      .map(buildGroupNode)

    // Asset member children — merge group-level and asset-level bindings
    const memberChildren: TreeNode[] = (group.members ?? []).map(member => {
      const assetBindings = assetBindingsMap[member.asset_name] ?? []
      // Deduplicate: asset-level bindings take precedence, then add group-level ones
      const seen = new Set(assetBindings.map(b => `${b.slo_name}|${b.data_source_name}`))
      const mergedBindings = [
        ...assetBindings,
        ...groupBindings.filter(b => !seen.has(`${b.slo_name}|${b.data_source_name}`)),
      ]
      const sloChildren: TreeNode[] = mergedBindings.map(binding => {
        const slo = sloByName.get(binding.slo_name)
        const dsNode: TreeNode = {
          id: `binding-ds:${member.asset_name}:${binding.data_source_name}`,
          name: binding.data_source_name,
          type: 'datasource' as const,
          groupName: group.name,
        }

        let sloLeaf: TreeNode[]
        if (slo?.sli_name) {
          const sli = sliByName.get(slo.sli_name)
          const indicatorCount = sli?.indicators ? Object.keys(sli.indicators).length : 0
          sloLeaf = [{
            id: `binding-sli:${member.asset_name}:${slo.sli_name}`,
            name: slo.sli_name,
            displayName: sli?.display_name ?? undefined,
            type: 'sli' as const,
            badge: indicatorCount > 0 ? `${indicatorCount}` : undefined,
            groupName: group.name,
            children: [dsNode],
          }]
        } else {
          sloLeaf = [dsNode]
        }

        return {
          id: `binding-slo:${member.asset_name}:${binding.slo_name}`,
          name: binding.slo_name,
          displayName: slo?.display_name ?? undefined,
          type: 'slo' as const,
          badge: slo ? `v${slo.version}` : undefined,
          groupName: group.name,
          children: sloLeaf,
        }
      })
      return {
        id: `asset:${member.asset_name}`,
        name: member.asset_name,
        type: 'asset' as const,
        assetTypeName: member.asset_type_name,
        groupName: group.name,
        children: sloChildren.length > 0 ? sloChildren : undefined,
      }
    })

    const allChildren = [...subgroupChildren, ...memberChildren]
    return {
      id: `group:${group.name}`,
      name: group.name,
      displayName: group.display_name ?? undefined,
      type: 'group' as const,
      badge: (group.members?.length ?? 0) > 0 ? `${group.members!.length}` : undefined,
      children: allChildren.length > 0 ? allChildren : undefined,
    }
  }

  return topLevelGroups.map(buildGroupNode)
}

export function buildSloSections(
  slos: MinSlo[],
  slis: MinSli[],
  datasources: MinDs[],
  bindings: MinBinding[],
  groups: SloGroup[],
): { standard: TreeNode[]; templates: TreeNode[]; groupNodes: TreeNode[] } {
  const sliByName = new Map(slis.map(s => [s.name, s]))
  const dsByName = new Map(datasources.map(d => [d.name, d]))

  const activeSlos = slos.filter(s => s.active)
  const standardSlos = activeSlos.filter(s => (s.kind ?? 'standard') === 'standard')
  const templateSlos = activeSlos.filter(s => s.kind === 'template')

  // Build standard SLO nodes (same logic as buildSloTree)
  const standard: TreeNode[] = standardSlos.map(slo => {
    const sloBindings = bindings.filter(b => b.slo_name === slo.name)
    const dsNames = [...new Set(sloBindings.map(b => b.data_source_name))]
    const dsChildren: TreeNode[] = dsNames.map(dsName => ({
      id: `ds:${dsName}`,
      name: dsName,
      displayName: dsByName.get(dsName)?.displayName ?? undefined,
      type: 'datasource' as const,
    }))
    const sliChildren: TreeNode[] = []
    if (slo.sli_name) {
      const sli = sliByName.get(slo.sli_name)
      const indicatorCount = sli?.indicators ? Object.keys(sli.indicators).length : 0
      sliChildren.push({
        id: `sli:${slo.sli_name}`,
        name: slo.sli_name,
        displayName: sli?.display_name ?? undefined,
        type: 'sli' as const,
        badge: `${indicatorCount} indicators`,
        children: dsChildren,
      })
    }
    return {
      id: `slo:${slo.name}`,
      name: slo.name,
      displayName: slo.display_name ?? undefined,
      type: 'slo' as const,
      badge: `v${slo.version}`,
      children: sliChildren.length > 0 ? sliChildren : dsChildren,
    }
  })

  // Build template nodes
  const templates: TreeNode[] = templateSlos.map(slo => {
    const refGroups = groups.filter(g => g.template_slo_name === slo.name)
    return {
      id: `template:${slo.name}`,
      name: slo.name,
      displayName: slo.display_name ?? undefined,
      type: 'template' as const,
      badge: `v${slo.version}`,
      subtitle: `${refGroups.length} group${refGroups.length !== 1 ? 's' : ''}`,
    }
  })

  // Build group nodes
  const groupNodes: TreeNode[] = groups.filter(g => g.active).map(g => ({
    id: `slo-group:${g.name}`,
    name: g.name,
    displayName: g.display_name ?? undefined,
    type: 'slo-group' as const,
    badge: `${g.generated_slo_count} SLOs`,
    subtitle: `via ${g.template_slo_name}`,
  }))

  return { standard, templates, groupNodes }
}

export interface MinGroupAssignment {
  slo_group_name: string
  data_source_name: string
}

export function buildSloGroupMap(slos: MinSlo[]): Map<string, string[]> {
  const m = new Map<string, string[]>()
  for (const slo of slos) {
    const groupName = slo.tags?.slo_group
    if (groupName) {
      const list = m.get(groupName) ?? []
      list.push(slo.name)
      m.set(groupName, list)
    }
  }
  return m
}

export function mergeBindings(
  groupNames: string[],
  assetNames: string[],
  groupAssignments: MinBinding[][],
  directAssetAssignments: MinBinding[][],
  assetGroupAssignments: MinGroupAssignment[][],
  sloGroupMap: Map<string, string[]>,
): { allBindings: MinBinding[]; groupBindingsMap: Record<string, MinBinding[]>; assetBindingsMap: Record<string, MinBinding[]> } {
  const flat: MinBinding[] = []
  const byGroup: Record<string, MinBinding[]> = {}
  const byAsset: Record<string, MinBinding[]> = {}

  for (let i = 0; i < groupNames.length; i++) {
    const bindings: MinBinding[] = (groupAssignments[i] ?? []).map(a => ({
      slo_name: a.slo_name,
      data_source_name: a.data_source_name,
    }))
    byGroup[groupNames[i]] = bindings
    flat.push(...bindings)
  }

  for (let i = 0; i < assetNames.length; i++) {
    const directBindings: MinBinding[] = (directAssetAssignments[i] ?? []).map(a => ({
      slo_name: a.slo_name,
      data_source_name: a.data_source_name,
    }))

    const groupBindings: MinBinding[] = (assetGroupAssignments[i] ?? []).flatMap(ga => {
      const sloNames = sloGroupMap.get(ga.slo_group_name) ?? [ga.slo_group_name]
      return sloNames.map(sloName => ({
        slo_name: sloName,
        data_source_name: ga.data_source_name,
      }))
    })

    const combined = [...directBindings, ...groupBindings]
    byAsset[assetNames[i]] = combined
    flat.push(...combined)
  }

  const seen = new Set<string>()
  const unique = flat.filter(b => {
    const key = `${b.slo_name}|${b.data_source_name}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })

  return { allBindings: unique, groupBindingsMap: byGroup, assetBindingsMap: byAsset }
}

export function filterTree(nodes: TreeNode[], search: string): TreeNode[] {
  if (!search) return nodes
  const lower = search.toLowerCase()
  return nodes.reduce<TreeNode[]>((acc, node) => {
    const nameMatch =
      node.name.toLowerCase().includes(lower) ||
      (node.displayName?.toLowerCase().includes(lower) ?? false)
    const filteredChildren = node.children ? filterTree(node.children, search) : []
    if (nameMatch || filteredChildren.length > 0) {
      acc.push({
        ...node,
        children: nameMatch
          ? node.children
          : filteredChildren.length > 0
            ? filteredChildren
            : undefined,
      })
    }
    return acc
  }, [])
}
