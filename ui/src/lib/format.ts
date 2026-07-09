// src/lib/format.ts
// Shared number and date formatters.
// Previously redefined inline in SLIBreakdownTable, EvaluationDetailPage,
// EvaluationListPage, and EvaluationHeatmap.

export function fmt(v: number | null | undefined): string {
  if (v == null) return '—'
  if (v === 0) return '0'
  const abs = Math.abs(v)
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`
  if (abs >= 1_000) return `${(v / 1_000).toFixed(2)}K`
  if (abs >= 0.01) return v.toFixed(2)
  // For very small values, show up to 6 significant digits and strip trailing zeros
  const digits = Math.min(6, -Math.floor(Math.log10(abs)) + 2)
  return v.toFixed(digits).replace(/0+$/, '').replace(/\.$/, '')
}

export function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v.toFixed(1)}%`
}

/**
 * Format a change point's local magnitude for display. When the metric appeared
 * from or vanished to zero, `changeRelativePct` is null and `transition` carries
 * the reason instead — a percent has no meaning in that case.
 */
export function formatChangePointPct(
  changeRelativePct: number | null,
  transition: 'appeared' | 'vanished' | null,
): string {
  if (transition != null) return transition
  if (changeRelativePct == null) return '—'
  const sign = changeRelativePct > 0 ? '+' : ''
  return `${sign}${changeRelativePct.toFixed(1)}%`
}

/** Compact heatmap X-axis label: "MM-DD HH:MM" */
export function fmtSlot(slot: string): string {
  if (!slot) return '—'
  // slot is ISO "YYYY-MM-DDTHH:MM:SSZ" — take "MM-DD HH:MM"
  return slot.slice(5, 7) + '-' + slot.slice(8, 10) + ' ' + slot.slice(11, 16)
}

/** Full datetime for table cells and tooltips: "YYYY-MM-DD HH:MM" */
export function fmtDateTime(iso: string): string {
  if (!iso) return '—'
  return iso.slice(0, 10) + ' ' + iso.slice(11, 16)
}

export function fmtDate(iso: string): string {
  if (!iso) return '—'
  return iso.slice(0, 10) // "YYYY-MM-DD"
}
