import type { TreeNode } from './types'

export interface MinSlo {
  name: string
  display_name?: string | null
  version: number
  active: boolean
  sli_name?: string | null
  sli_version?: number | null
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
  display_name?: string | null
  adapter_type: string
}

export interface MinBinding {
  slo_name: string
  data_source_name: string
}

export interface MinGroup {
  name: string
  display_name?: string | null
  members?: { asset_name: string }[]
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
      displayName: dsByName.get(dsName)?.display_name ?? undefined,
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
        badge: `${indicatorCount} indicators`,
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
      displayName: ds.display_name ?? undefined,
      type: 'datasource' as const,
      badge: `[${ds.adapter_type}]`,
      children: [...sliChildren, ...orphanChildren],
    }
  })
}

export function buildAssetTree(
  groups: MinGroup[],
  groupBindingsMap: Record<string, MinBinding[]>,
  slos?: MinSlo[],
  slis?: MinSli[],
): TreeNode[] {
  const sloByName = new Map((slos ?? []).map(s => [s.name, s]))
  const sliByName = new Map((slis ?? []).map(s => [s.name, s]))

  return groups.map(group => {
    const groupBindings = groupBindingsMap[group.name] ?? []
    const memberChildren: TreeNode[] = (group.members ?? []).map(member => {
      // Build nested SLO → SLI → DS tree per binding
      const sloChildren: TreeNode[] = groupBindings.map(binding => {
        const slo = sloByName.get(binding.slo_name)
        const dsNode: TreeNode = {
          id: `binding-ds:${member.asset_name}:${binding.data_source_name}`,
          name: binding.data_source_name,
          type: 'datasource' as const,
          groupName: group.name,
        }

        // Insert SLI node between SLO and DS when SLO references an SLI
        let sloLeaf: TreeNode[]
        if (slo?.sli_name) {
          const sli = sliByName.get(slo.sli_name)
          const indicatorCount = sli?.indicators ? Object.keys(sli.indicators).length : 0
          sloLeaf = [{
            id: `binding-sli:${member.asset_name}:${slo.sli_name}`,
            name: slo.sli_name,
            displayName: sli?.display_name ?? undefined,
            type: 'sli' as const,
            badge: `${indicatorCount} indicators`,
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
        groupName: group.name,
        children: sloChildren.length > 0 ? sloChildren : undefined,
      }
    })
    return {
      id: `group:${group.name}`,
      name: group.name,
      displayName: group.display_name ?? undefined,
      type: 'group' as const,
      badge: `${group.members?.length ?? 0} assets`,
      children: memberChildren,
    }
  })
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
