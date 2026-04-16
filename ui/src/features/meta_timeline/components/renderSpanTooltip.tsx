import { format, formatDistanceStrict } from 'date-fns'

// vis-timeline Item shape — we only type the fields we use
interface TooltipItem {
  group: string
  content: string
  start: string
  end: string
  className?: string
  source?: string
}

export function parseIsoDate(iso: string): Date {
  return new Date(iso)
}

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function decodeGroupLabel(groupId: string): string {
  try {
    const path: string[] = JSON.parse(groupId)
    return path.join(' > ')
  } catch {
    return groupId
  }
}

export function renderSpanTooltip(item: TooltipItem): string {
  const startDate = parseIsoDate(item.start)
  const endDate = parseIsoDate(item.end)
  const startFormatted = format(startDate, "MMM d yyyy, HH:mm 'UTC'")
  const endFormatted = format(endDate, "MMM d yyyy, HH:mm 'UTC'")
  const duration = formatDistanceStrict(startDate, endDate)

  const classes = item.className ?? ''
  const isOpen = classes.includes('meta-span-open')
  const clippedLeft = classes.includes('meta-span-clipped-left')
  const clippedRight = classes.includes('meta-span-clipped-right')
  const isClosed = classes.includes('meta-span-closed')

  const fromAnnotation = clippedLeft ? ' (started before window)' : ''
  const toAnnotation =
    clippedRight ? ' (continues after window)'
    : isOpen ? ' (still open)'
    : isClosed ? ' (explicit closure)'
    : ''

  return [
    `<strong>${escapeHtml(decodeGroupLabel(item.group))}</strong>`,
    `Value: <code>${escapeHtml(item.content)}</code>`,
    `From: ${startFormatted}${fromAnnotation}`,
    `To: ${endFormatted}${toAnnotation}`,
    `Duration: ${duration}`,
    `Source: <code>${escapeHtml(item.source ?? 'unknown')}</code>`,
  ].join('<br />')
}
