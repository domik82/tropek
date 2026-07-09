// Domain types for the navigator feature. Hand-written; UI vocabulary.
// Pass-through shapes for the grouped-heatmap endpoint live here for now;
// deeper domain renames (Indicator / Criteria / Outcome) arrive with the
// evaluations migration in Chunk B3. See §15.5 of the UI layering spec.

import type { HeatmapEChartsCell } from './ui-types'

// Period timestamps stay as ISO strings (not Date) throughout navigator:
// they are used as Map keys for column/row lookup and as ECharts x-axis
// labels, where object identity would break equality. This is a deliberate
// narrow exception to the "Date objects, not strings" domain-layer rule.

// Canonical result union used throughout navigator. The backend emits
// `result: string` on HeatmapCellGrouped / HeatmapSummaryCell, and a
// separate `invalidated: boolean` flag on summary cells. The mapper
// collapses those two fields into this single discriminated union so
// components never branch on `invalidated` again.
export type HeatmapResult =
  | 'pass'
  | 'warning'
  | 'fail'
  | 'error'
  | 'invalidated'
  | 'none'

export interface EvaluationColumn {
  evaluationId: string
  periodStart: string
  periodEnd: string
  evalName: string
  hasNotes?: boolean
}

export interface HeatmapMetric {
  name: string
  displayName: string
}

export interface ChangePointMarker {
  direction: 'regression' | 'improvement'
  changeRelativePct: number | null
  transition: 'appeared' | 'vanished' | null
}

export interface HeatmapIndicatorCell {
  evaluationId: string
  sloEvaluationId: string
  periodStart: string
  metric: string
  displayName: string
  result: HeatmapResult
  score: number
  value: number | null
  comparedValue: number | null
  changeRelativePct: number | null
  weight: number
  keySli: boolean
  passTargets: unknown[] | null
  warningTargets: unknown[] | null
  tabGroup: string | null
  aggregation: string | null
  changePoint: ChangePointMarker | null
}

export interface HeatmapSummaryCell {
  evaluationId: string
  periodStart: string
  result: HeatmapResult
  score: number
  totalScorePassThreshold: number | null
  totalScoreWarningThreshold: number | null
  sliMetadata: Record<string, unknown> | null
  invalidationNote: string | null
}

export interface HeatmapSloGroup {
  sloName: string
  sloDisplayName: string | null
  metrics: HeatmapMetric[]
  cells: HeatmapIndicatorCell[]
  summary: HeatmapSummaryCell[]
}

export interface GroupedMetricHeatmap {
  assetName: string
  columns: EvaluationColumn[]
  groups: HeatmapSloGroup[]
  composite: HeatmapSummaryCell[]
}

export interface MiniHeatmapView {
  rows: string[]
  cells: HeatmapEChartsCell[]
  headerRowIndices: Set<number>
}

// --- Pre-computed visualization shapes (group view) -----------------------
// These are render-ready structures emitted by buildGroupHeatmapData /
// buildGroupScoreData in utils.ts for the group-view heatmap and stacked
// bar chart. They consume already-domain-mapped EvaluationSummary objects
// (evaluations feature — unmigrated at time of writing; Chunk B3 will
// replace them with a proper domain type).

// Pre-computed group heatmap: rows = assets, cols = time slots.
export interface GroupHeatmapData {
  slots: string[]
  rows: string[]
  cells: HeatmapEChartsCell[]
}

// One point in the group score stacked-bar chart.
export interface AssetScorePoint {
  slot: string
  assetName: string
  score: number
  result: string
  maxScore: number
}

// Per-slot grouping for the stacked-bar render.
export interface SlotScoreData {
  slot: string
  assets: AssetScorePoint[]
  totalAchieved: number
  totalMax: number
}
