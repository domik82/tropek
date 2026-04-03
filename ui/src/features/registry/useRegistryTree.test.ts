import { describe, it, expect } from 'vitest'
import { buildSloTree, buildDatasourceTree, buildAssetTree, filterTree, buildSloSections, buildSloGroupMap, mergeBindings } from './useRegistryTree'
import type { TreeNode } from './types'
import type { SloGroup } from '@/features/slo-groups/types'

describe('buildSloTree', () => {
  it('builds SLO → SLI → DS hierarchy from bindings and SLO sli_name', () => {
    const slos = [{ name: 'http-slo', display_name: 'HTTP SLO', version: 3, active: true, sli_name: 'http-sli', sli_version: 1 }]
    const slis = [{ name: 'http-sli', display_name: null, adapter_type: 'prometheus', active: true, indicators: { rt: 'q1', err: 'q2' } }]
    const datasources = [{ name: 'prom', display_name: null, adapter_type: 'prometheus' }]
    const bindings = [{ slo_name: 'http-slo', data_source_name: 'prom' }]

    const tree = buildSloTree(slos, slis, datasources, bindings)
    expect(tree).toHaveLength(1)
    expect(tree[0]).toMatchObject({ name: 'http-slo', type: 'slo', badge: 'v3' })
    expect(tree[0].children).toHaveLength(1)
    expect(tree[0].children![0]).toMatchObject({ name: 'http-sli', type: 'sli' })
    expect(tree[0].children![0].children).toHaveLength(1)
    expect(tree[0].children![0].children![0]).toMatchObject({ name: 'prom', type: 'datasource' })
  })

  it('shows DS directly under SLO when no sli_name on SLO', () => {
    const slos = [{ name: 'http-slo', version: 1, active: true }]
    const bindings = [{ slo_name: 'http-slo', data_source_name: 'prom' }]
    const datasources = [{ name: 'prom', display_name: null, adapter_type: 'prometheus' }]
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
  it('builds DS → SLI → SLO hierarchy using sli_name from SLO definition', () => {
    const datasources = [{ name: 'prom', display_name: null, adapter_type: 'prometheus' }]
    const slis = [{ name: 'http-sli', display_name: null, adapter_type: 'prometheus', active: true, indicators: { rt: 'q' } }]
    const slos = [{ name: 'http-slo', display_name: null, version: 2, active: true, sli_name: 'http-sli', sli_version: 1 }]
    const bindings = [{ slo_name: 'http-slo', data_source_name: 'prom' }]

    const tree = buildDatasourceTree(datasources, slis, slos, bindings)
    expect(tree).toHaveLength(1)
    expect(tree[0]).toMatchObject({ type: 'datasource', badge: '[prometheus]' })
    expect(tree[0].children![0]).toMatchObject({ type: 'sli' })
    expect(tree[0].children![0].children![0]).toMatchObject({ type: 'slo' })
  })

  it('shows SLOs without sli_name directly under datasource', () => {
    const datasources = [{ name: 'prom', display_name: null, adapter_type: 'prometheus' }]
    const slos = [{ name: 'bare-slo', display_name: null, version: 1, active: true }]
    const bindings = [{ slo_name: 'bare-slo', data_source_name: 'prom' }]

    const tree = buildDatasourceTree(datasources, [], slos, bindings)
    expect(tree).toHaveLength(1)
    expect(tree[0].children).toHaveLength(1)
    expect(tree[0].children![0]).toMatchObject({ type: 'slo', name: 'bare-slo' })
  })
})

describe('buildAssetTree', () => {
  it('builds Group → Asset → SLO → SLI → DS hierarchy when SLO has sli_name', () => {
    const groups = [{ name: 'core', display_name: null, members: [{ asset_name: 'checkout-api' }] }]
    const groupBindingsMap = { core: [{ slo_name: 'http-slo', data_source_name: 'prom' }] }
    const slos = [{ name: 'http-slo', display_name: 'HTTP SLO', version: 2, active: true, sli_name: 'http-sli', sli_version: 1 }]
    const slis = [{ name: 'http-sli', display_name: null, adapter_type: 'prometheus', active: true, indicators: { rt: 'q1', err: 'q2' } }]

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

  it('shows DS directly under SLO when SLO has no sli_name', () => {
    const groups = [{ name: 'core', display_name: null, members: [{ asset_name: 'checkout-api' }] }]
    const groupBindingsMap = { core: [{ slo_name: 'bare-slo', data_source_name: 'prom' }] }
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
    const groups = [{ name: 'core', display_name: null, members: [{ asset_name: 'checkout-api' }] }]
    const assetBindingsMap = { 'checkout-api': [{ slo_name: 'asset-slo', data_source_name: 'prom' }] }
    const slos = [{ name: 'asset-slo', display_name: 'Asset SLO', version: 1, active: true, sli_name: 'http-sli' }]
    const slis = [{ name: 'http-sli', display_name: null, adapter_type: 'prometheus', active: true, indicators: { rt: 'q1' } }]

    const tree = buildAssetTree(groups, groups, {}, assetBindingsMap, slos, slis)
    expect(tree[0].children![0].children).toHaveLength(1)
    expect(tree[0].children![0].children![0]).toMatchObject({ type: 'slo', name: 'asset-slo' })
  })
})

describe('buildSloSections', () => {
  const slis = [
    { name: 'http-sli', display_name: null, adapter_type: 'prometheus', active: true, indicators: { latency: 'q' } },
  ]
  const datasources = [{ name: 'prom', display_name: null, adapter_type: 'prometheus' }]
  const bindings = [{ slo_name: 'web-perf', data_source_name: 'prom' }]

  it('separates standard SLOs from templates', () => {
    const slos = [
      { name: 'web-perf', display_name: null, version: 3, active: true, sli_name: 'http-sli', sli_version: 1, kind: 'standard' },
      { name: 'plugin-tpl', display_name: null, version: 1, active: true, sli_name: 'http-sli', sli_version: 1, kind: 'template' },
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
      { name: 'web-perf', display_name: null, version: 1, active: true, sli_name: null, sli_version: null, kind: 'standard' },
    ]
    const groups: SloGroup[] = [
      { id: '1', name: 'app-plugins', display_name: 'App Plugins', template_slo_name: 'plugin-tpl',
        template_slo_version: 1, gen_variables: {}, tags: {}, author: null, version: 1,
        active: true, created_at: '', updated_at: '', generated_slo_count: 30 },
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
    ] as any
    const map = buildSloGroupMap(slos)
    expect(map.get('perf-group')).toEqual(['gen-slo-1', 'gen-slo-2'])
    expect(map.has('standalone')).toBe(false)
  })

  it('returns empty map when no SLOs have slo_group tag', () => {
    const slos = [{ name: 'plain', version: 1, active: true, tags: {} }] as any
    expect(buildSloGroupMap(slos).size).toBe(0)
  })
})

describe('mergeBindings', () => {
  it('includes group-level bindings for assets', () => {
    const result = mergeBindings(
      ['core'],
      ['checkout-api'],
      [[{ slo_name: 'http-slo', data_source_name: 'prom' }]],
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
      [[{ slo_name: 'asset-slo', data_source_name: 'prom' }]],
      [[]],
      new Map(),
    )
    expect(result.assetBindingsMap['checkout-api']).toHaveLength(1)
    expect(result.assetBindingsMap['checkout-api'][0].slo_name).toBe('asset-slo')
  })

  it('resolves SLO group assignments to individual SLO names', () => {
    const sloGroupMap = new Map([['perf-group', ['gen-slo-1', 'gen-slo-2']]])
    const result = mergeBindings(
      [],
      ['checkout-api'],
      [],
      [[]],
      [[{ slo_group_name: 'perf-group', data_source_name: 'prom' }]],
      sloGroupMap,
    )
    expect(result.assetBindingsMap['checkout-api']).toHaveLength(2)
    expect(result.assetBindingsMap['checkout-api'].map(b => b.slo_name)).toEqual(['gen-slo-1', 'gen-slo-2'])
  })

  it('falls back to group name when sloGroupMap has no entry', () => {
    const result = mergeBindings(
      [],
      ['checkout-api'],
      [],
      [[]],
      [[{ slo_group_name: 'unknown-group', data_source_name: 'prom' }]],
      new Map(),
    )
    expect(result.assetBindingsMap['checkout-api']).toHaveLength(1)
    expect(result.assetBindingsMap['checkout-api'][0].slo_name).toBe('unknown-group')
  })

  it('combines direct and group assignments for same asset', () => {
    const sloGroupMap = new Map([['perf-group', ['gen-slo']]])
    const result = mergeBindings(
      [],
      ['checkout-api'],
      [],
      [[{ slo_name: 'direct-slo', data_source_name: 'prom' }]],
      [[{ slo_group_name: 'perf-group', data_source_name: 'prom' }]],
      sloGroupMap,
    )
    expect(result.assetBindingsMap['checkout-api']).toHaveLength(2)
    expect(result.assetBindingsMap['checkout-api'].map(b => b.slo_name)).toEqual(['direct-slo', 'gen-slo'])
  })

  it('deduplicates allBindings across groups and assets', () => {
    const result = mergeBindings(
      ['core'],
      ['checkout-api'],
      [[{ slo_name: 'http-slo', data_source_name: 'prom' }]],
      [[{ slo_name: 'http-slo', data_source_name: 'prom' }]],
      [[]],
      new Map(),
    )
    expect(result.allBindings).toHaveLength(1)
  })
})
