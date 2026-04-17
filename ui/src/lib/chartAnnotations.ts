import type { Annotation, TrendPoint } from '@/features/evaluations/domain'
import type { NoteCategory } from '@/features/note-categories'
import { paletteOf } from '@/features/note-categories'

export interface MarkPointDataItem {
  xAxis: number
  yAxis: number
  itemStyle: { color: string }
  label: { show: boolean; formatter: string; color: string; fontSize: number }
  tooltip?: { formatter: string }
  evalId: string
}

export interface MarkPointOption {
  symbol: string
  symbolSize: [number, number]
  symbolOffset: [number, number]
  data: MarkPointDataItem[]
}

interface Input {
  trendPoints: TrendPoint[]
  annotationsByEvalId: Map<string, Annotation[]>
  categoriesById: Map<string, NoteCategory>
  chartWidth: number
}

const TEARDROP_SVG =
  'path://M12,0 C5.4,0 0,5.4 0,12 C0,21 12,28 12,28 C12,28 24,21 24,12 C24,5.4 18.6,0 12,0 Z'
const LABEL_DENSITY_THRESHOLD_PX = 40

function dominantCategory(visible: Annotation[]): NoteCategory {
  const sorted = [...visible].sort((x, y) => x.category.name.localeCompare(y.category.name))
  return sorted[0].category
}

function escapeHtml(s: string): string {
  return s.replace(
    /[&<>"']/g,
    ch =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]!,
  )
}

export function buildNoteMarkPoint(input: Input): MarkPointOption {
  const { trendPoints, annotationsByEvalId, chartWidth } = input

  const visibleCount = trendPoints.filter(p => {
    const annotations = annotationsByEvalId.get(p.evalId) ?? []
    return annotations.some(a => a.category.showOnGraph)
  }).length

  const labelsOn =
    visibleCount === 0 || chartWidth / visibleCount >= LABEL_DENSITY_THRESHOLD_PX

  const data: MarkPointDataItem[] = []

  for (let i = 0; i < trendPoints.length; i++) {
    const point = trendPoints[i]
    const annotations = annotationsByEvalId.get(point.evalId) ?? []
    const visible = annotations.filter(a => a.category.showOnGraph)
    if (visible.length === 0) continue

    const category = dominantCategory(visible)
    const palette = paletteOf(category.color)
    const suffix = visible.length > 1 ? ` (${visible.length})` : ''

    const tooltipBody = visible
      .map(a => `<div><b>${a.category.label}</b>: ${escapeHtml(a.content)}</div>`)
      .join('')

    data.push({
      xAxis: i,
      yAxis: point.value,
      itemStyle: { color: palette.bg },
      label: {
        show: labelsOn,
        formatter: `${category.label}${suffix}`,
        color: palette.fg,
        fontSize: 10,
      },
      tooltip: { formatter: tooltipBody },
      evalId: point.evalId,
    })
  }

  return {
    symbol: TEARDROP_SVG,
    symbolSize: [18, 14],
    symbolOffset: [0, -14],
    data,
  }
}
