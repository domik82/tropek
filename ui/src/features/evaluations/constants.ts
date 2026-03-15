// src/features/evaluations/constants.ts
// Configuration constants for the evaluations feature.
// Re-exports RESULT_COLOUR from lib/theme so feature components have one import.

export { RESULT_COLOUR } from '@/lib/theme'

// Fixed columns always visible in the EvaluationTable.
// Dynamic tag/metadata columns are added at runtime from eval data.
export type { ColumnDef } from './types'

// Column order matches the original Keptn bridge table layout.
// All columns are togglable; required=true prevents hiding via the picker.
export const FIXED_COLS = [
  { key: 'test',         label: 'Evaluation',   required: true  },
  { key: 'asset',        label: 'Asset',         required: true  },
  { key: 'arch',         label: 'Arch',          required: false },
  { key: 'os',           label: 'Os',            required: false },
  { key: 'branch',       label: 'Branch',        required: false },
  { key: 'build',        label: 'Build',         required: false },
  { key: 'triggered_by', label: 'Triggered by',  required: false },
  { key: 'start',        label: 'Time (UTC)',     required: false },
  { key: 'score',        label: 'Score',         required: true  },
  { key: 'result',       label: 'Result',        required: true  },
  { key: 'slo',          label: 'SLO',           required: false },
  { key: 'annotations',  label: 'Notes',         required: false },
]

// Keys visible by default (all fixed cols except none; user can hide via picker)
export const DEFAULT_VISIBLE_KEYS = new Set(FIXED_COLS.map(c => c.key))

// Tab group ordering hint for EvaluationDetailPage.
// Only used to sort dynamically-discovered groups from API indicator_results.
// The actual tab groups and their names come from the SLO definition via the API.
export const TAB_ORDER = ['all', 'performance', 'reliability', 'capacity']
