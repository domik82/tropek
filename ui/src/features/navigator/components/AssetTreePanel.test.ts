import { describe, it, expect } from 'vitest'
import { countLeafMembers } from './treeUtils'
import type { AssetGroup, AssetGroupTree } from '@/features/assets/types'

function mkGroup(
  id: string,
  members: number,
  subgroupIds: string[] = [],
): AssetGroup {
  return {
    id,
    name: id,
    members: Array.from({ length: members }, (_, i) => ({
      asset_id: `${id}-asset-${i}`,
      asset_name: `${id}-asset-${i}`,
      weight: 1,
    })),
    subgroups: subgroupIds.map(gid => ({ group_id: gid, weight: 1 })),
  }
}

describe('countLeafMembers', () => {
  it('returns direct member count for a group with no subgroups', () => {
    const group = mkGroup('g1', 3)
    const tree: AssetGroupTree = { top_level: [group], all_groups: [group] }
    expect(countLeafMembers(group, tree)).toBe(3)
  })

  it('sums members recursively through subgroups', () => {
    const child1 = mkGroup('child1', 5)
    const child2 = mkGroup('child2', 6)
    const parent = mkGroup('parent', 0, ['child1', 'child2'])
    const tree: AssetGroupTree = {
      top_level: [parent],
      all_groups: [parent, child1, child2],
    }
    expect(countLeafMembers(parent, tree)).toBe(11)
  })

  it('handles nested subgroups (grandchildren)', () => {
    const grandchild = mkGroup('gc', 4)
    const child = mkGroup('child', 2, ['gc'])
    const root = mkGroup('root', 1, ['child'])
    const tree: AssetGroupTree = {
      top_level: [root],
      all_groups: [root, child, grandchild],
    }
    expect(countLeafMembers(root, tree)).toBe(7)
  })

  it('returns 0 for a group with no members and no subgroups', () => {
    const group = mkGroup('empty', 0)
    const tree: AssetGroupTree = { top_level: [group], all_groups: [group] }
    expect(countLeafMembers(group, tree)).toBe(0)
  })

  it('skips unresolved subgroup IDs', () => {
    const parent = mkGroup('parent', 3, ['nonexistent'])
    const tree: AssetGroupTree = { top_level: [parent], all_groups: [parent] }
    expect(countLeafMembers(parent, tree)).toBe(3)
  })
})
