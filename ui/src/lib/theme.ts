// src/lib/theme.ts
// Single source of truth for all brand colours.
// Previously duplicated in EvaluationHeatmap, ResultBadge, SLIBreakdownTable,
// MetricTrendChart, and AssetRegistryPage.

export const RESULT_COLOUR = {
  pass:        '#7dc540',
  warning:     '#e6be00',
  fail:        '#dc172a',
  error:       '#888888',
  invalidated: '#b0b0b0', // lighter gray — distinct from error, signals "not counted"
} as const

export type ResultColourKey = keyof typeof RESULT_COLOUR

// Default OS → colour mapping for the asset registry colour legend.
// Keys are OS family strings returned by the API (e.g. "linux", "windows").
export const DEFAULT_OS_COLOUR_MAP: Record<string, string> = {
  linux: '#7dc540',
  windows: '#6495ed',
  macos: '#e6be00',
  unknown: '#888888',
}
