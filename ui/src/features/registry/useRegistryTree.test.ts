import { describe, it, expect } from 'vitest'
import { buildSloTree, buildDatasourceTree, buildAssetTree, filterTree, buildSloSections, buildSloGroupMap, mergeBindings } from './useRegistryTree'
import type { MinSlo } from './useRegistryTree'
import type { TreeNode } from './ui-types'
import type { SloGroup } from '@/features/slo-groups'

describe('buildSloTree', () => {
  it('builds SLO → SLI → DS hierarchy from bindings and SLO sliName', () => {
    const slos = [{ name: 'http-slo', displayName: 'HTTP SLO', version: 3, active: true, sliName: 'http-sli', sliVersion: 1 }]
    const slis = [{ name: 'http-sli', displayName: null, adapterType: 'prometheus', active: true, indicators: { rt: 'q1', err: 'q2' } }]
    const datasources = [{ name: 'prom', displayName: null, adapterType: 'prometheus' }]
    const bindings = [{ sloName: 'http-slo', dataSourceName: 'prom' }]

    const tree = buildSloTree(slos, slis, datasources, bindings)
    expect(tree).toHaveLength(1)
    expect(tree[0]).toMatchObject({ name: 'http-slo', type: 'slo', badge: 'v3' })
    expect(tree[0].children).toHaveLength(1)
    expect(tree[0].children![0]).toMatchObject({ name: 'http-sli', type: 'sli' })
    expect(tree[0].children![0].children).toHaveLength(1)
    expect(tree[0].children![0].children![0]).toMatchObject({ name: 'prom', type: 'datasource' })
  })

  it('shows DS directly under SLO when no sliName on SLO', () => {
    const slos = [{ name: 'http-slo', version: 1, active: true }]
    const bindings = [{ sloName: 'http-slo', dataSourceName: 'prom' }]
    const datasources = [{ name: 'prom', displayName: null, adapterType: 'prometheus' }]
    const tree = buildSloTree(slos, [], datasources, bindings)
    expect(tree).toHaveLength(1)
    expect(tree[0].children).toHaveLength(1)
    expect(tree[0].children![0]).toMatchObject({ name: 'prom', type: 'datasource' })
  })

  it('shows SLO with no bindings as leaf node', () => {
    const slos = [{ name: 'orphan-slo', version: 1, active: true }]
    const tree = buildSloTree(slos, [], [], [])
    expect(tree).toHaveLength(1)
    expect(tree[0].children).toHaveLength(0)
  })
})

describe('buildDatasourceTree', () => {
  it('builds DS → SLI → SLO hierarchy using sliName from SLO definition', () => {
    const datasources = [{ name: 'prom', displayName: null, adapterType: 'prometheus' }]
    const slis = [{ name: 'http-sli', displayName: null, adapterType: 'prometheus', active: true, indicators: { rt: 'q' } }]
    const slos = [{ name: 'http-slo', displayName: null, version: 2, active: true, sliName: 'http-sli', sliVersion: 1 }]
    const bindings = [{ sloName: 'http-slo', dataSourceName: 'prom' }]

    const tree = buildDatasourceTree(datasources, slis, slos, bindings)
    expect(tree).toHaveLength(1)
    expect(tree[0]).toMatchObject({ type: 'datasource', badge: '[prometheus]' })
    expect(tree[0].children![0]).toMatchObject({ type: 'sli' })
    expect(tree[0].children![0].children![0]).toMatchObject({ type: 'slo' })
  })

  it('shows SLOs without sliName directly under datasource', () => {
    const datasources = [{ name: 'prom', displayName: null, adapterType: 'prometheus' }]
    const slos = [{ name: 'bare-slo', displayName: null, version: 1, active: true }]
    const bindings = [{ sloName: 'bare-slo', dataSourceName: 'prom' }]

    const tree = buildDatasourceTree(datasources, [], slos, bindings)
    expect(tree).toHaveLength(1)
    expect(tree[0].children).toHaveLength(1)
    expect(tree[0].children![0]).toMatchObject({ type: 'slo', name: 'bare-slo' })
  })
})

describe('buildAssetTree', () => {
  it('builds Group → Asset → SLO → SLI → DS hierarchy when SLO has sliName', () => {
    const groups = [{ name: 'core', displayName: null, members: [{ asset_name: 'checkout-api' }] }]
    const groupBindingsMap = { core: [{ sloName: 'http-slo', dataSourceName: 'prom' }] }
    const slos = [{ name: 'http-slo', displayName: 'HTTP SLO', version: 2, active: true, sliName: 'http-sli', sliVersion: 1 }]
    const slis = [{ name: 'http-sli', displayName: null, adapterType: 'prometheus', active: true, indicators: { rt: 'q1', err: 'q2' } }]

    const tree = buildAssetTree(groups, groups, groupBindingsMap, {}, slos, slis)
    expect(tree).toHaveLength(1)
    expect(tree[0]).toMatchObject({ type: 'group', name: 'core' })
    expect(tree[0].children).toHaveLength(1)
    expect(tree[0].children![0]).toMatchObject({ type: 'asset', name: 'checkout-api' })
    expect(tree[0].children![0].children).toHaveLength(1)
    // SLO node
    const sloNode = tree[0].children![0].children![0]
    expect(sloNode).toMatchObject({ type: 'slo', name: 'http-slo', badge: 'v2' })
    // SLI node under SLO
    expect(sloNode.children).toHaveLength(1)
    expect(sloNode.children![0]).toMatchObject({ type: 'sli', name: 'http-sli', badge: '2' })
    // DS node under SLI
    expect(sloNode.children![0].children).toHaveLength(1)
    expect(sloNode.children![0].children![0]).toMatchObject({ type: 'datasource', name: 'prom' })
  })

  it('shows DS directly under SLO when SLO has no sliName', () => {
    const groups = [{ name: 'core', displayName: null, members: [{ asset_name: 'checkout-api' }] }]
    const groupBindingsMap = { core: [{ sloName: 'bare-slo', dataSourceName: 'prom' }] }
    const slos = [{ name: 'bare-slo', version: 1, active: true }]

    const tree = buildAssetTree(groups, groups, groupBindingsMap, {}, slos, [])
    const sloNode = tree[0].children![0].children![0]
    expect(sloNode).toMatchObject({ type: 'slo', name: 'bare-slo' })
    expect(sloNode.children).toHaveLength(1)
    expect(sloNode.children![0]).toMatchObject({ type: 'datasource', name: 'prom' })
  })

  it('shows asset with no bindings as leaf', () => {
    const groups = [{ name: 'core', members: [{ asset_name: 'lonely-svc' }] }]
    const tree = buildAssetTree(groups, groups, {}, {})
    expect(tree[0].children![0].children).toBeUndefined()
  })

  it('shows asset-level assignments when no group-level bindings exist', () => {
    const groups = [{ name: 'core', displayName: null, members: [{ asset_name: 'checkout-api' }] }]
    const assetBindingsMap = { 'checkout-api': [{ sloName: 'asset-slo', dataSourceName: 'prom' }] }
    const slos = [{ name: 'asset-slo', displayName: 'Asset SLO', version: 1, active: true, sliName: 'http-sli' }]
    const slis = [{ name: 'http-sli', displayName: null, adapterType: 'prometheus', active: true, indicators: { rt: 'q1' } }]

    const tree = buildAssetTree(groups, groups, {}, assetBindingsMap, slos, slis)
    expect(tree[0].children![0].children).toHaveLength(1)
    expect(tree[0].children![0].children![0]).toMatchObject({ type: 'slo', name: 'asset-slo' })
  })
})

describe('buildSloSections', () => {
  const slis = [
    { name: 'http-sli', displayName: null, adapterType: 'prometheus', active: true, indicators: { latency: 'q' } },
  ]
  const datasources = [{ name: 'prom', displayName: null, adapterType: 'prometheus' }]
  const bindings = [{ sloName: 'web-perf', dataSourceName: 'prom' }]

  it('separates standard SLOs from templates', () => {
    const slos = [
      { name: 'web-perf', displayName: null, version: 3, active: true, sliName: 'http-sli', sliVersion: 1, kind: 'standard' },
      { name: 'plugin-tpl', displayName: null, version: 1, active: true, sliName: 'http-sli', sliVersion: 1, kind: 'template' },
    ]
    const groups: SloGroup[] = []
    const { standard, templates, groupNodes } = buildSloSections(slos, slis, datasources, bindings, groups)
    expect(standard).toHaveLength(1)
    expect(standard[0].name).toBe('web-perf')
    expect(templates).toHaveLength(1)
    expect(templates[0].name).toBe('plugin-tpl')
    expect(templates[0].type).toBe('template')
    expect(groupNodes).toHaveLength(0)
  })

  it('builds group nodes with badge and subtitle', () => {
    const slos = [
      { name: 'web-perf', displayName: null, version: 1, active: true, sliName: null, sliVersion: null, kind: 'standard' },
    ]
    const groups: SloGroup[] = [
      { id: '1', name: 'app-plugins', displayName: 'App Plugins', templateSloName: 'plugin-tpl',
        templateSloVersion: 1, genVariables: {}, tags: {}, author: null, version: 1,
        active: true, createdAt: new Date(0), updatedAt: new Date(0), generatedSloCount: 30 },
    ]
    const { groupNodes } = buildSloSections(slos, slis, datasources, bindings, groups)
    expect(groupNodes).toHaveLength(1)
    expect(groupNodes[0].name).toBe('app-plugins')
    expect(groupNodes[0].type).toBe('slo-group')
    expect(groupNodes[0].badge).toBe('30 SLOs')
    expect(groupNodes[0].subtitle).toBe('via plugin-tpl')
  })
})

describe('filterTree', () => {
  it('filters by name substring', () => {
    const tree: TreeNode[] = [
      { id: '1', name: 'http-slo', type: 'slo' },
      { id: '2', name: 'db-slo', type: 'slo' },
    ]
    expect(filterTree(tree, 'http')).toHaveLength(1)
    expect(filterTree(tree, 'http')[0].name).toBe('http-slo')
  })

  it('keeps parent if any child matches', () => {
    const tree: TreeNode[] = [
      { id: '1', name: 'parent', type: 'slo', children: [
        { id: '2', name: 'matching-child', type: 'sli' },
        { id: '3', name: 'other', type: 'sli' },
      ]},
    ]
    const result = filterTree(tree, 'matching')
    expect(result).toHaveLength(1)
    expect(result[0].children).toHaveLength(1)
  })

  it('returns all nodes when search is empty', () => {
    const tree: TreeNode[] = [
      { id: '1', name: 'a', type: 'slo' },
      { id: '2', name: 'b', type: 'slo' },
    ]
    expect(filterTree(tree, '')).toHaveLength(2)
  })
})

describe('buildSloGroupMap', () => {
  it('maps slo_group tag to SLO names', () => {
    const slos = [
      { name: 'gen-slo-1', version: 1, active: true, tags: { slo_group: 'perf-group' } },
      { name: 'gen-slo-2', version: 1, active: true, tags: { slo_group: 'perf-group' } },
      { name: 'standalone', version: 1, active: true, tags: {} },
    ] as MinSlo[]
    const map = buildSloGroupMap(slos)
    expect(map.get('perf-group')).toEqual(['gen-slo-1', 'gen-slo-2'])
    expect(map.has('standalone')).toBe(false)
  })

  it('returns empty map when no SLOs have slo_group tag', () => {
    const slos: MinSlo[] = [{ name: 'plain', version: 1, active: true, tags: {} }]
    expect(buildSloGroupMap(slos).size).toBe(0)
  })
})

describe('mergeBindings', () => {
  it('includes group-level bindings for assets', () => {
    const result = mergeBindings(
      ['core'],
      ['checkout-api'],
      [[{ sloName: 'http-slo', dataSourceName: 'prom' }]],
      [[]],
      [[]],
      new Map(),
    )
    expect(result.groupBindingsMap['core']).toHaveLength(1)
    expect(result.allBindings).toHaveLength(1)
  })

  it('includes direct asset assignments', () => {
    const result = mergeBindings(
      [],
      ['checkout-api'],
      [],
      [[{ sloName: 'asset-slo', dataSourceName: 'prom' }]],
      [[]],
      new Map(),
    )
    expect(result.assetBindingsMap['checkout-api']).toHaveLength(1)
    expect(result.assetBindingsMap['checkout-api'][0].sloName).toBe('asset-slo')
  })

  it('resolves SLO group assignments to individual SLO names', () => {
    const sloGroupMap = new Map([['perf-group', ['gen-slo-1', 'gen-slo-2']]])
    const result = mergeBindings(
      [],
      ['checkout-api'],
      [],
      [[]],
      [[{ sloGroupName: 'perf-group', dataSourceName: 'prom' }]],
      sloGroupMap,
    )
    expect(result.assetBindingsMap['checkout-api']).toHaveLength(2)
    expect(result.assetBindingsMap['checkout-api'].map(b => b.sloName)).toEqual(['gen-slo-1', 'gen-slo-2'])
  })

  it('falls back to group name when sloGroupMap has no entry', () => {
    const result = mergeBindings(
      [],
      ['checkout-api'],
      [],
      [[]],
      [[{ sloGroupName: 'unknown-group', dataSourceName: 'prom' }]],
      new Map(),
    )
    expect(result.assetBindingsMap['checkout-api']).toHaveLength(1)
    expect(result.assetBindingsMap['checkout-api'][0].sloName).toBe('unknown-group')
  })

  it('combines direct and group assignments for same asset', () => {
    const sloGroupMap = new Map([['perf-group', ['gen-slo']]])
    const result = mergeBindings(
      [],
      ['checkout-api'],
      [],
      [[{ sloName: 'direct-slo', dataSourceName: 'prom' }]],
      [[{ sloGroupName: 'perf-group', dataSourceName: 'prom' }]],
      sloGroupMap,
    )
    expect(result.assetBindingsMap['checkout-api']).toHaveLength(2)
    expect(result.assetBindingsMap['checkout-api'].map(b => b.sloName)).toEqual(['direct-slo', 'gen-slo'])
  })

  it('deduplicates allBindings across groups and assets', () => {
    const result = mergeBindings(
      ['core'],
      ['checkout-api'],
      [[{ sloName: 'http-slo', dataSourceName: 'prom' }]],
      [[{ sloName: 'http-slo', dataSourceName: 'prom' }]],
      [[]],
      new Map(),
    )
    expect(result.allBindings).toHaveLength(1)
  })
})
