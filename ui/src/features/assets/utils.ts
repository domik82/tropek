// src/features/assets/utils.ts
// Shared asset utility functions.

import type { AssetGroup, AssetGroupTree } from './domain'

/**
 * Recursively collect all asset names from a group and its subgroups.
 */
export function collectGroupAssetNames(
  group: AssetGroup,
  tree: AssetGroupTree,
): string[] {
  const directMembers = group.members.map((m) => m.assetName)
  const subgroupMembers = group.subgroups.flatMap((sg) => {
    const subGroup = tree.allGroups.find((g) => g.id === sg.groupId)
    return subGroup ? collectGroupAssetNames(subGroup, tree) : []
  })
  return [...new Set([...directMembers, ...subgroupMembers])]
}
