export type RegistryMode = 'asset' | 'slo' | 'datasource'

export type NodeType = 'group' | 'asset' | 'slo' | 'sli' | 'datasource' | 'binding'

export interface TreeNode {
  id: string
  name: string
  displayName?: string
  type: NodeType
  badge?: string
  children?: TreeNode[]
  bindingChain?: { sloName: string; sliName: string; dsName: string }
  groupName?: string
}

export interface SelectedNode {
  type: NodeType
  name: string
  groupName?: string
}

export interface TagFilter {
  key: string
  value: string
}
