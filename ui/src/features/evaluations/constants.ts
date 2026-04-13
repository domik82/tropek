// src/features/evaluations/constants.ts
// Configuration constants for the evaluations feature.
// Re-exports RESULT_COLOUR from lib/theme so feature components have one import.

export { RESULT_COLOUR } from '@/lib/theme'

// Fixed columns always visible in the EvaluationTable.
// Dynamic tag/metadata columns are added at runtime from eval data.
export type { ColumnDef } from './ui-types'

// Structural columns that are always present regardless of data.
// Tag and metadata columns (arch, os, branch, build, etc.) are discovered
// dynamically from evaluation data — see useDynamicColumns() in hooks.ts.
export const FIXED_COLS = [
  { key: 'test',        label: 'Evaluation', required: true  },
  { key: 'asset',       label: 'Asset',      required: true  },
  { key: 'start',       label: 'Time (UTC)', required: false },
  { key: 'score',       label: 'Score',      required: true  },
  { key: 'result',      label: 'Result',     required: true  },
  { key: 'slo',         label: 'SLO',        required: false },
  { key: 'annotations', label: 'Notes',      required: false },
]

// Keys visible by default — structural columns plus any dynamic columns
// discovered at runtime (see useColumnVisibility).
export const DEFAULT_VISIBLE_KEYS = new Set(FIXED_COLS.map(c => c.key))

// Tab group ordering hint for EvaluationDetailPage.
// Only used to sort dynamically-discovered groups from API indicator_results.
// The actual tab groups and their names come from the SLO definition via the API.
export const TAB_ORDER = ['all', 'performance', 'reliability', 'capacity']
