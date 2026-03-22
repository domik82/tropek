import { describe, it, expect } from 'vitest'
import { buildSloTree, buildDatasourceTree, buildAssetTree, filterTree } from './useRegistryTree'
import type { TreeNode } from './types'

describe('buildSloTree', () => {
  it('builds SLO → SLI → DS hierarchy from links', () => {
    const slos = [{ name: 'http-slo', display_name: 'HTTP SLO', version: 3, active: true }]
    const slis = [{ name: 'http-sli', display_name: null, adapter_type: 'prometheus', active: true, indicators: { rt: 'q1', err: 'q2' } }]
    const datasources = [{ name: 'prom', display_name: null, adapter_type: 'prometheus' }]
    const links = [{ slo_name: 'http-slo', sli_name: 'http-sli', data_source_name: 'prom' }]

    const tree = buildSloTree(slos, slis, datasources, links)
    expect(tree).toHaveLength(1)
    expect(tree[0]).toMatchObject({ name: 'http-slo', type: 'slo', badge: 'v3' })
    expect(tree[0].children).toHaveLength(1)
    expect(tree[0].children![0]).toMatchObject({ name: 'http-sli', type: 'sli' })
    expect(tree[0].children![0].children).toHaveLength(1)
    expect(tree[0].children![0].children![0]).toMatchObject({ name: 'prom', type: 'datasource' })
  })

  it('shows SLO with no links as leaf node', () => {
    const slos = [{ name: 'orphan-slo', version: 1, active: true }]
    const tree = buildSloTree(slos, [], [], [])
    expect(tree).toHaveLength(1)
    expect(tree[0].children).toHaveLength(0)
  })
})

describe('buildDatasourceTree', () => {
  it('builds DS → SLI → SLO hierarchy', () => {
    const datasources = [{ name: 'prom', display_name: null, adapter_type: 'prometheus' }]
    const slis = [{ name: 'http-sli', display_name: null, adapter_type: 'prometheus', active: true, indicators: { rt: 'q' } }]
    const slos = [{ name: 'http-slo', display_name: null, version: 2, active: true }]
    const links = [{ slo_name: 'http-slo', sli_name: 'http-sli', data_source_name: 'prom' }]

    const tree = buildDatasourceTree(datasources, slis, slos, links)
    expect(tree).toHaveLength(1)
    expect(tree[0]).toMatchObject({ type: 'datasource', badge: '[prometheus]' })
    expect(tree[0].children![0]).toMatchObject({ type: 'sli' })
    expect(tree[0].children![0].children![0]).toMatchObject({ type: 'slo' })
  })
})

describe('buildAssetTree', () => {
  it('builds Group → Asset → Binding chain hierarchy', () => {
    const groups = [{ name: 'core', display_name: null, members: [{ asset_name: 'checkout-api' }] }]
    const groupLinksMap = { core: [{ slo_name: 'http-slo', sli_name: 'http-sli', data_source_name: 'prom' }] }

    const tree = buildAssetTree(groups, groupLinksMap)
    expect(tree).toHaveLength(1)
    expect(tree[0]).toMatchObject({ type: 'group', name: 'core' })
    expect(tree[0].children).toHaveLength(1)
    expect(tree[0].children![0]).toMatchObject({ type: 'asset', name: 'checkout-api' })
    expect(tree[0].children![0].children).toHaveLength(1)
    expect(tree[0].children![0].children![0]).toMatchObject({
      type: 'binding',
      bindingChain: { sloName: 'http-slo', sliName: 'http-sli', dsName: 'prom' },
    })
  })

  it('shows asset with no links as leaf', () => {
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
