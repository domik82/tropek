import { describe, it, expect } from 'vitest'
import { buildSloTree, buildDatasourceTree, buildAssetTree, filterTree } from './useRegistryTree'
import type { TreeNode } from './types'

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

    const tree = buildAssetTree(groups, groupBindingsMap, slos, slis)
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
    expect(sloNode.children![0]).toMatchObject({ type: 'sli', name: 'http-sli', badge: '2 indicators' })
    // DS node under SLI
    expect(sloNode.children![0].children).toHaveLength(1)
    expect(sloNode.children![0].children![0]).toMatchObject({ type: 'datasource', name: 'prom' })
  })

  it('shows DS directly under SLO when SLO has no sli_name', () => {
    const groups = [{ name: 'core', display_name: null, members: [{ asset_name: 'checkout-api' }] }]
    const groupBindingsMap = { core: [{ slo_name: 'bare-slo', data_source_name: 'prom' }] }
    const slos = [{ name: 'bare-slo', version: 1, active: true }]

    const tree = buildAssetTree(groups, groupBindingsMap, slos, [])
    const sloNode = tree[0].children![0].children![0]
    expect(sloNode).toMatchObject({ type: 'slo', name: 'bare-slo' })
    expect(sloNode.children).toHaveLength(1)
    expect(sloNode.children![0]).toMatchObject({ type: 'datasource', name: 'prom' })
  })

  it('shows asset with no bindings as leaf', () => {
    const groups = [{ name: 'core', members: [{ asset_name: 'lonely-svc' }] }]
    const tree = buildAssetTree(groups, {})
    expect(tree[0].children![0].children).toBeUndefined()
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
