// ui/src/features/navigator/components/treeUtils.ts
// Pure utility functions for the asset tree panel — no React dependencies.

import type { AssetGroup, AssetGroupTree } from '@/features/assets/types'

/**
 * Recursively count the total number of leaf asset members in a group,
 * including all assets from nested subgroups.
 */
export function countLeafMembers(group: AssetGroup, tree: AssetGroupTree): number {
  let count = group.members.length
  for (const sg of group.subgroups) {
    const resolved = tree.all_groups.find(g => g.id === sg.group_id)
    if (resolved) count += countLeafMembers(resolved, tree)
  }
  return count
}
