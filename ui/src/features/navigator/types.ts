// ui/src/features/navigator/types.ts

// Grid cell for both group and asset heatmaps
export interface HeatmapCell {
  value: [number, number]       // [xIndex (col), yIndex (row)]
  result: string                // pass | warning | fail | error | invalidated | none
  score: number
  slot: string                  // ISO timestamp for column label (period_start)
  rowLabel: string              // asset name (group view) or metric display name / SLO name (asset view)
  evalId?: string               // slo_evaluation_id — defined for indicator cells
  columnKey?: string            // evaluation_id (parent run UUID) — for column identity
  evaluation_name?: string      // kept for backward compat / tooltip
  hasNote?: boolean             // triggers annotation triangle
  noteContent?: string          // shown in tooltip
  isSloHeader?: boolean         // true for SLO group header rows
  sloName?: string              // SLO name — set on header and indicator rows
  metricName?: string           // metric key — set on indicator rows only
}

// Pre-computed group heatmap: rows=assets, cols=slots
export interface GroupHeatmapData {
  slots: string[]
  rows: string[]
  cells: HeatmapCell[]
}

// One data point in the stacked bar chart
export interface AssetScorePoint {
  slot: string
  assetName: string
  score: number
  result: string
  maxScore: number
}

// Grouped by slot for stacked bar rendering
export interface SlotScoreData {
  slot: string
  assets: AssetScorePoint[]
  totalAchieved: number
  totalMax: number
}

// One column in the grouped heatmap — corresponds to one EvaluationRun
export interface EvaluationColumn {
  evaluation_id: string
  period_start: string
  period_end: string
  eval_name: string
}

// Summary cell for an SLO group header row or the Overall composite row
export interface HeatmapSummaryCell {
  evaluation_id: string
  period_start: string
  result: string
  score: number
}

// One SLO group in the grouped heatmap response
export interface HeatmapSloGroup {
  slo_name: string
  slo_display_name?: string
  metrics: Array<{ name: string; display_name: string }>
  cells: MetricHeatmapCell[]
  summary: HeatmapSummaryCell[]
}

// An individual indicator cell in the grouped heatmap
export interface MetricHeatmapCell {
  evaluation_id: string         // parent eval (column key)
  slo_evaluation_id: string     // FK to slo_evaluations (for trend nav)
  period_start: string          // display only
  metric: string
  display_name: string
  result: string
  score: number
}

// API response for GET /api/evaluate/metric-heatmap?asset_name=X
export interface MetricHeatmapResponse {
  asset_name: string
  columns: EvaluationColumn[]
  groups: HeatmapSloGroup[]
  composite: HeatmapSummaryCell[]
}

// Pre-computed asset heatmap: rows=metrics/headers, cols=evaluations
export interface AssetHeatmapData {
  slots: string[]           // ISO period_start per column (display labels)
  rows: string[]            // ECharts bottom-to-top row labels
  cells: HeatmapCell[]
  headerRowIndices: Set<number>  // ECharts y-indices of SLO header rows
}
