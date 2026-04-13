// ui/src/features/evaluations/ui-types.ts
//
// UI-only types for the evaluations feature. These are NOT domain types —
// they describe component/view state, column picker shape, and other things
// with no backend equivalent. Never exported from './index.ts'; imported
// directly by the components that need them.

export type ActionKind = 'invalidate' | 'override' | 'baseline' | 're-evaluate' | 'restore'

export interface ColumnDef {
  key: string
  label: string
  required: boolean
}
