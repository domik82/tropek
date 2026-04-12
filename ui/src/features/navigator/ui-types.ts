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
  slot: string                  // ISO timestamp for column label (period_start)
  rowLabel: string              // asset name / metric display name / SLO name
  evalId?: string               // slo_evaluation_id for indicator cells
  columnKey?: string            // parent evaluation_id (column identity)
  evaluation_name?: string      // tooltip label
  hasNote?: boolean
  noteContent?: string
  isSloHeader?: boolean
  sloName?: string
  metricName?: string
}

// Emitted by the asset heatmap when a user clicks a cell — describes which
// time-slot and which SLO evaluations were selected together.
export interface TimeSlotSelection {
  periodStart: string
  evalIds: string[]
  columnEvalId?: string
}
