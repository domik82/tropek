// UI-only types for the navigator feature. These have no backend analogue —
// they describe visualization primitives (ECharts cell tuples, row/column
// display state, selection targets). Never imported by non-component code.

// Grid cell consumed by the ECharts heatmap. `value` is `[xIndex, yIndex]`
// — i.e. column index and ECharts y-index (bottom-to-top). Previously named
// `HeatmapCell`; renamed to disambiguate from the backend `HeatmapCell` DTO
// which is a completely different shape. See discovery doc D5 for context.
export interface HeatmapEChartsCell {
  value: [number, number]
  result: string                // canonical result union — see mappers.ts
  score: number
  /**
   * Unique column key = parent EvaluationRun id. Two runs can share a
   * period_start (e.g. load-test + prod-validation both at 16:00), so
   * the slot key cannot be the timestamp — use evaluation_id, which is
   * unique per run. For human display, use `periodStart`.
   */
  slot: string
  periodStart: string           // ISO timestamp — used for tooltips and x-axis labels
  rowLabel: string              // asset name / metric display name / SLO name
  evalId?: string               // slo_evaluation_id for indicator cells
  columnKey?: string            // parent evaluation_id (== slot, kept for clarity)
  evaluation_name?: string      // tooltip label
  hasNote?: boolean
  noteContent?: string
  isSloHeader?: boolean
  sloName?: string
  metricName?: string
  changePoint?: { direction: 'regression' | 'improvement'; changeRelativePct: number }
}

// Emitted by the asset heatmap when a user clicks a cell — describes which
// time-slot and which SLO evaluations were selected together. When the click
// landed on a per-SLO indicator cell (not the composite "Overall Score" row
// and not an SLO-header row), `specificSloEvalId` carries that cell's
// slo_evaluation_id so consumers can default SLO-scoped actions to the
// clicked SLO. Column/header clicks leave it undefined.
export interface TimeSlotSelection {
  periodStart: string
  evalIds: string[]
  columnEvalId?: string
  specificSloEvalId?: string
}
