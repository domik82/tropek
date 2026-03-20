// src/features/assets/utils.ts
// Shared asset utility functions.
// Fixes DRY violation: collectGroupAssets() was duplicated in api/client.ts
// and TriggerEvaluationModal.tsx. Single implementation here.

import type { AssetGroup, AssetGroupTree } from './types'

/**
 * Recursively collect all asset names from a group and its subgroups.
 */
export function collectGroupAssetNames(
  group: AssetGroup,
  tree: AssetGroupTree
): string[] {
  const directMembers = group.members.map(m => m.asset_name)
  const subgroupMembers = group.subgroups.flatMap(sg => {
    const subGroup = tree.all_groups.find(g => g.id === sg.group_id)
    return subGroup ? collectGroupAssetNames(subGroup, tree) : []
  })
  return [...new Set([...directMembers, ...subgroupMembers])]
}
