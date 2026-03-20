// src/features/assets/utils.test.ts
import { describe, it, expect } from 'vitest'
import { collectGroupAssetNames } from './utils'
import type { AssetGroup, AssetGroupTree } from './types'

const makeGroup = (id: string, memberNames: string[], subgroupIds: string[] = []): AssetGroup => ({
  id,
  name: id,
  members: memberNames.map(n => ({ asset_id: n, asset_name: n, weight: 1 })),
  subgroups: subgroupIds.map(gid => ({ child_group_id: gid, group_name: gid, weight: 1 })),
})

describe('collectGroupAssetNames', () => {
  it('returns direct members when no subgroups', () => {
    const group = makeGroup('g1', ['a', 'b'])
    const tree: AssetGroupTree = { top_level: [group], all_groups: [group] }
    expect(collectGroupAssetNames(group, tree)).toEqual(['a', 'b'])
  })

  it('includes members from nested subgroups', () => {
    const child = makeGroup('child', ['c'])
    const parent = makeGroup('parent', ['a', 'b'], ['child'])
    const tree: AssetGroupTree = { top_level: [parent], all_groups: [parent, child] }
    expect(collectGroupAssetNames(parent, tree)).toEqual(['a', 'b', 'c'])
  })

  it('deduplicates when an asset appears in multiple subgroups', () => {
    const child1 = makeGroup('c1', ['shared'])
    const child2 = makeGroup('c2', ['shared', 'unique'])
    const parent = makeGroup('parent', [], ['c1', 'c2'])
    const tree: AssetGroupTree = { top_level: [parent], all_groups: [parent, child1, child2] }
    expect(collectGroupAssetNames(parent, tree)).toEqual(['shared', 'unique'])
  })

  it('returns empty array for group with no members and no subgroups', () => {
    const group = makeGroup('empty', [])
    const tree: AssetGroupTree = { top_level: [group], all_groups: [group] }
    expect(collectGroupAssetNames(group, tree)).toEqual([])
  })
})
