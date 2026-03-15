// src/lib/format.ts
// Shared number and date formatters.
// Previously redefined inline in SLIBreakdownTable, EvaluationDetailPage,
// EvaluationListPage, and EvaluationHeatmap.

export function fmt(v: number | null | undefined): string {
  if (v == null) return '—'
  return v.toFixed(2)
}

export function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v.toFixed(1)}%`
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
