// ui/src/features/navigator/types.ts

// Grid cell for both group and asset heatmaps
export interface HeatmapCell {
  value: [number, number]       // [xIndex (slot), yIndex (row)]
  result: string                // pass | warning | fail | error | invalidated | none
  score: number
  slot: string                  // ISO timestamp for column
  rowLabel: string              // asset name (group view) or metric display name (asset view)
  evalId?: string               // defined in asset view — for click navigation
  hasNote?: boolean             // triggers annotation triangle in HeatmapChart
  noteContent?: string          // shown in tooltip
}

// Pre-computed group heatmap: rows=assets, cols=slots
export interface GroupHeatmapData {
  slots: string[]               // unique ISO timestamps, sorted
  rows: string[]                // unique asset names
  cells: HeatmapCell[]
}

// One data point in the stacked bar chart
export interface AssetScorePoint {
  slot: string
  assetName: string
  score: number                 // 0–100
  result: string
  maxScore: number              // always 100 (per asset)
}

// Grouped by slot for stacked bar rendering
export interface SlotScoreData {
  slot: string
  assets: AssetScorePoint[]
  totalAchieved: number
  totalMax: number
}

// API response for GET /api/evaluations/metric-heatmap?asset_name=X
export interface MetricHeatmapCell {
  slot: string
  metric: string
  display_name: string
  result: string
  score: number
  eval_id: string
}

export interface MetricHeatmapResponse {
  asset_name: string
  slots: string[]
  metrics: Array<{ name: string; display_name: string; tab_group?: string }>
  cells: MetricHeatmapCell[]
}

// Pre-computed asset heatmap: rows=metrics, cols=evaluations
export interface AssetHeatmapData {
  slots: string[]
  rows: string[]                // display_names in metric order
  cells: HeatmapCell[]
}
