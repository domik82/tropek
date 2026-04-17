export type CategoryColor =
  | 'sky'
  | 'green'
  | 'amber'
  | 'red'
  | 'purple'
  | 'pink'
  | 'slate'
  | 'gray'

export interface NoteCategory {
  id: string
  name: string
  label: string
  color: CategoryColor
  showOnGraph: boolean
  isSystem: boolean
  createdAt: Date
  updatedAt: Date | null
}

export interface NoteCategoryInput {
  name: string
  label: string
  color: CategoryColor
  showOnGraph: boolean
}

export interface NoteCategoryPatch {
  name?: string
  label?: string
  color?: CategoryColor
  showOnGraph?: boolean
}
