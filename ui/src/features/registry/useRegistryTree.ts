import type { TreeNode } from './types'

export interface MinSlo {
  name: string
  display_name?: string | null
  version: number
  active: boolean
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

export interface MinLink {
  slo_name: string
  sli_name: string
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
  links: MinLink[],
): TreeNode[] {
  const sliByName = new Map(slis.map(s => [s.name, s]))
  const dsByName = new Map(datasources.map(d => [d.name, d]))

  return slos.filter(s => s.active).map(slo => {
    const sloLinks = links.filter(l => l.slo_name === slo.name)
    const sliNames = [...new Set(sloLinks.map(l => l.sli_name))]

    const sliChildren: TreeNode[] = sliNames.map(sliName => {
      const sli = sliByName.get(sliName)
      const dsNames = [
        ...new Set(sloLinks.filter(l => l.sli_name === sliName).map(l => l.data_source_name)),
      ]
      const dsChildren: TreeNode[] = dsNames.map(dsName => ({
        id: `ds:${dsName}`,
        name: dsName,
        displayName: dsByName.get(dsName)?.display_name ?? undefined,
        type: 'datasource' as const,
      }))
      const indicatorCount = sli?.indicators ? Object.keys(sli.indicators).length : 0
      return {
        id: `sli:${sliName}`,
        name: sliName,
        displayName: sli?.display_name ?? undefined,
        type: 'sli' as const,
        badge: `${indicatorCount} indicators`,
        children: dsChildren,
      }
    })

    return {
      id: `slo:${slo.name}`,
      name: slo.name,
      displayName: slo.display_name ?? undefined,
      type: 'slo' as const,
      badge: `v${slo.version}`,
      children: sliChildren,
    }
  })
}

export function buildDatasourceTree(
  datasources: MinDs[],
  slis: MinSli[],
  slos: MinSlo[],
  links: MinLink[],
): TreeNode[] {
  const sloByName = new Map(slos.map(s => [s.name, s]))

  return datasources.map(ds => {
    const dsSlis = slis.filter(s => s.adapter_type === ds.adapter_type && s.active)
    const sliChildren: TreeNode[] = dsSlis.map(sli => {
      const sloNames = [
        ...new Set(
          links
            .filter(l => l.sli_name === sli.name && l.data_source_name === ds.name)
            .map(l => l.slo_name),
        ),
      ]
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
      const indicatorCount = sli.indicators ? Object.keys(sli.indicators).length : 0
      return {
        id: `sli:${sli.name}`,
        name: sli.name,
        displayName: sli.display_name ?? undefined,
        type: 'sli' as const,
        badge: `${indicatorCount} indicators`,
        children: sloChildren,
      }
    })

    return {
      id: `ds:${ds.name}`,
      name: ds.name,
      displayName: ds.display_name ?? undefined,
      type: 'datasource' as const,
      badge: `[${ds.adapter_type}]`,
      children: sliChildren,
    }
  })
}

export function buildAssetTree(
  groups: MinGroup[],
  groupLinksMap: Record<string, MinLink[]>,
): TreeNode[] {
  return groups.map(group => {
    const groupLinks = groupLinksMap[group.name] ?? []
    const memberChildren: TreeNode[] = (group.members ?? []).map(member => {
      const bindingChildren: TreeNode[] = groupLinks.map(link => ({
        id: `binding:${member.asset_name}:${link.slo_name}`,
        name: link.slo_name,
        type: 'binding' as const,
        bindingChain: {
          sloName: link.slo_name,
          sliName: link.sli_name,
          dsName: link.data_source_name,
        },
        badge: `→ ${link.sli_name} → ${link.data_source_name}`,
      }))
      return {
        id: `asset:${member.asset_name}`,
        name: member.asset_name,
        type: 'asset' as const,
        children: bindingChildren.length > 0 ? bindingChildren : undefined,
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
