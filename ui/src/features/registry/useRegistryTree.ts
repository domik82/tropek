import type { SloGroup } from '@/features/slo-groups'
import type { TreeNode } from './ui-types'

export interface MinSlo {
  name: string
  displayName?: string | null
  version: number
  active: boolean
  sliName?: string | null
  sliVersion?: number | null
  kind?: string
  tags?: Record<string, string>
}

export interface MinSli {
  name: string
  displayName?: string | null
  adapterType: string
  active: boolean
  indicators?: Record<string, string>
}

export interface MinDs {
  name: string
  displayName?: string | null
  adapterType: string
}

export interface MinBinding {
  sloName: string
  dataSourceName: string
}

export interface MinGroup {
  name: string
  displayName?: string | null
  members?: { assetName: string; assetTypeName?: string }[]
  subgroups?: { groupId: string; groupName: string }[]
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
    const sloBindings = bindings.filter(b => b.sloName === slo.name)
    const dsNames = [...new Set(sloBindings.map(b => b.dataSourceName))]

    const dsChildren: TreeNode[] = dsNames.map(dsName => ({
      id: `ds:${dsName}`,
      name: dsName,
      displayName: dsByName.get(dsName)?.displayName ?? undefined,
      type: 'datasource' as const,
    }))

    // SLI comes from the SLO definition, not from bindings
    const sliChildren: TreeNode[] = []
    if (slo.sliName) {
      const sli = sliByName.get(slo.sliName)
      const indicatorCount = sli?.indicators ? Object.keys(sli.indicators).length : 0
      sliChildren.push({
        id: `sli:${slo.sliName}`,
        name: slo.sliName,
        displayName: sli?.displayName ?? undefined,
        type: 'sli' as const,
        badge: indicatorCount > 0 ? `${indicatorCount}` : undefined,
        children: dsChildren,
      })
    }

    return {
      id: `slo:${slo.name}`,
      name: slo.name,
      displayName: slo.displayName ?? undefined,
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
      bindings.filter(b => b.dataSourceName === ds.name).map(b => b.sloName),
    )]
    // Group bound SLOs by their sliName (from the SLO definition)
    const sliToSlos = new Map<string, string[]>()
    for (const sloName of boundSloNames) {
      const slo = sloByName.get(sloName)
      const sliName = slo?.sliName ?? '__none__'
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
          displayName: slo?.displayName ?? undefined,
          type: 'slo' as const,
          badge: slo ? `v${slo.version}` : undefined,
        }
      })
      const indicatorCount = sli?.indicators ? Object.keys(sli.indicators).length : 0
      sliChildren.push({
        id: `sli:${sliName}`,
        name: sliName,
        displayName: sli?.displayName ?? undefined,
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
        displayName: slo?.displayName ?? undefined,
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
      .map(sg => groupByName.get(sg.groupName))
      .filter((g): g is MinGroup => g != null)
      .map(buildGroupNode)

    // Asset member children — merge group-level and asset-level bindings
    const memberChildren: TreeNode[] = (group.members ?? []).map(member => {
      const assetBindings = assetBindingsMap[member.assetName] ?? []
      // Deduplicate: asset-level bindings take precedence, then add group-level ones
      const seen = new Set(assetBindings.map(b => `${b.sloName}|${b.dataSourceName}`))
      const mergedBindings = [
        ...assetBindings,
        ...groupBindings.filter(b => !seen.has(`${b.sloName}|${b.dataSourceName}`)),
      ]
      const sloChildren: TreeNode[] = mergedBindings.map(binding => {
        const slo = sloByName.get(binding.sloName)
        const dsNode: TreeNode = {
          id: `binding-ds:${member.assetName}:${binding.dataSourceName}`,
          name: binding.dataSourceName,
          type: 'datasource' as const,
          groupName: group.name,
        }

        let sloLeaf: TreeNode[]
        if (slo?.sliName) {
          const sli = sliByName.get(slo.sliName)
          const indicatorCount = sli?.indicators ? Object.keys(sli.indicators).length : 0
          sloLeaf = [{
            id: `binding-sli:${member.assetName}:${slo.sliName}`,
            name: slo.sliName,
            displayName: sli?.displayName ?? undefined,
            type: 'sli' as const,
            badge: indicatorCount > 0 ? `${indicatorCount}` : undefined,
            groupName: group.name,
            children: [dsNode],
          }]
        } else {
          sloLeaf = [dsNode]
        }

        return {
          id: `binding-slo:${member.assetName}:${binding.sloName}`,
          name: binding.sloName,
          displayName: slo?.displayName ?? undefined,
          type: 'slo' as const,
          badge: slo ? `v${slo.version}` : undefined,
          groupName: group.name,
          children: sloLeaf,
        }
      })
      return {
        id: `asset:${member.assetName}`,
        name: member.assetName,
        type: 'asset' as const,
        assetTypeName: member.assetTypeName,
        groupName: group.name,
        children: sloChildren.length > 0 ? sloChildren : undefined,
      }
    })

    const allChildren = [...subgroupChildren, ...memberChildren]
    return {
      id: `group:${group.name}`,
      name: group.name,
      displayName: group.displayName ?? undefined,
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
    const sloBindings = bindings.filter(b => b.sloName === slo.name)
    const dsNames = [...new Set(sloBindings.map(b => b.dataSourceName))]
    const dsChildren: TreeNode[] = dsNames.map(dsName => ({
      id: `ds:${dsName}`,
      name: dsName,
      displayName: dsByName.get(dsName)?.displayName ?? undefined,
      type: 'datasource' as const,
    }))
    const sliChildren: TreeNode[] = []
    if (slo.sliName) {
      const sli = sliByName.get(slo.sliName)
      const indicatorCount = sli?.indicators ? Object.keys(sli.indicators).length : 0
      sliChildren.push({
        id: `sli:${slo.sliName}`,
        name: slo.sliName,
        displayName: sli?.displayName ?? undefined,
        type: 'sli' as const,
        badge: `${indicatorCount} indicators`,
        children: dsChildren,
      })
    }
    return {
      id: `slo:${slo.name}`,
      name: slo.name,
      displayName: slo.displayName ?? undefined,
      type: 'slo' as const,
      badge: `v${slo.version}`,
      children: sliChildren.length > 0 ? sliChildren : dsChildren,
    }
  })

  // Build template nodes
  const templates: TreeNode[] = templateSlos.map(slo => {
    const refGroups = groups.filter(g => g.templateSloName === slo.name)
    return {
      id: `template:${slo.name}`,
      name: slo.name,
      displayName: slo.displayName ?? undefined,
      type: 'template' as const,
      badge: `v${slo.version}`,
      subtitle: `${refGroups.length} group${refGroups.length !== 1 ? 's' : ''}`,
    }
  })

  // Build group nodes
  const groupNodes: TreeNode[] = groups.filter(g => g.active).map(g => ({
    id: `slo-group:${g.name}`,
    name: g.name,
    displayName: g.displayName ?? undefined,
    type: 'slo-group' as const,
    badge: `${g.generatedSloCount} SLOs`,
    subtitle: `via ${g.templateSloName}`,
  }))

  return { standard, templates, groupNodes }
}

export interface MinGroupAssignment {
  sloGroupName: string
  dataSourceName: string
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
      sloName: a.sloName,
      dataSourceName: a.dataSourceName,
    }))
    byGroup[groupNames[i]] = bindings
    flat.push(...bindings)
  }

  for (let i = 0; i < assetNames.length; i++) {
    const directBindings: MinBinding[] = (directAssetAssignments[i] ?? []).map(a => ({
      sloName: a.sloName,
      dataSourceName: a.dataSourceName,
    }))

    const groupBindings: MinBinding[] = (assetGroupAssignments[i] ?? []).flatMap(ga => {
      const sloNames = sloGroupMap.get(ga.sloGroupName) ?? [ga.sloGroupName]
      return sloNames.map(sloName => ({
        sloName,
        dataSourceName: ga.dataSourceName,
      }))
    })

    const combined = [...directBindings, ...groupBindings]
    byAsset[assetNames[i]] = combined
    flat.push(...combined)
  }

  const seen = new Set<string>()
  const unique = flat.filter(b => {
    const key = `${b.sloName}|${b.dataSourceName}`
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
