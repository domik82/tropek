// Centralized status color/text constants for evaluation outcomes.
// Used across SLIBreakdownTable, MetricTrendBlock, and other evaluation UI.

export const STATUS_TEXT: Record<string, string> = {
  pass: 'text-pass',
  warning: 'text-warning',
  fail: 'text-fail',
  info: 'text-muted-foreground',
  invalidated: 'text-invalidated',
}

export const STATUS_LABEL: Record<string, string> = {
  pass: 'Pass',
  warning: 'Warning',
  fail: 'Fail',
  info: 'Info',
  invalidated: 'Invalidated',
}
