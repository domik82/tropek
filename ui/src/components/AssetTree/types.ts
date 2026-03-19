export type TreeMode = 'navigator' | 'slo'

export type NodeType = 'group' | 'asset'

export interface ContextMenuState {
  x: number
  y: number
  target: { type: NodeType; name: string; groupName?: string }
}

export interface MenuItemDef {
  label: string
  icon: string
  iconColor?: string
  action: string
  shortcut?: string
  destructive?: boolean
  disabled?: boolean
  separator?: boolean
  modes?: TreeMode[]
}
