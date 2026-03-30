export const AGGREGATION_METHODS = [
  'min', 'mean', 'max', 'std', 'sum', 'median', 'p75', 'p90', 'p95', 'p99',
] as const

export type AggregationMethod = typeof AGGREGATION_METHODS[number]

export const METHOD_LABELS: Record<AggregationMethod, string> = {
  min: 'Min',
  mean: 'Mean',
  max: 'Max',
  std: 'Std Dev',
  sum: 'Sum',
  median: 'Median',
  p75: 'P75',
  p90: 'P90',
  p95: 'P95',
  p99: 'P99',
}

export const INTERVAL_PRESETS = ['1m', '5m', '15m'] as const
