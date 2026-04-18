import type { Annotation, TrendPoint } from '@/features/evaluations/domain'
import type { NoteCategory } from '@/features/note-categories'
import { paletteOf } from '@/features/note-categories'

export interface MarkLineDataItem {
  xAxis: number
  lineStyle: { color: string; type: 'dashed'; width: number; opacity: number }
}

export interface MarkLineOption {
  silent: true
  symbol: ['none', 'none']
  label: { show: false }
  data: MarkLineDataItem[]
}

export interface MarkPointLabelStyle {
  show: true
  formatter: string
  color: string
  fontSize: number
  lineHeight: number
  backgroundColor: string
  borderColor: string
  borderWidth: number
  borderRadius: number
  padding: [number, number]
  align: 'center'
  verticalAlign: 'middle'
}

export interface MarkPointDataItem {
  x: number
  y: number
  relativeTo: 'container'
  symbol: 'rect'
  symbolSize: [number, number]
  itemStyle: { color: 'transparent' }
  label: MarkPointLabelStyle
  tooltip?: { trigger: 'item'; formatter: string }
  evalId: string
}

export interface MarkPointOption {
  silent: false
  data: MarkPointDataItem[]
}

export interface NoteAnnotationsResult {
  markLine: MarkLineOption
  markPoint: MarkPointOption
  /** Extra pixels to add to the OUTER chart container height so labels sit
   * above the plot area without shrinking it. Zero when no annotations. */
  labelBandPx: number
}

interface Input {
  trendPoints: TrendPoint[]
  annotationsByEvalId: Map<string, Annotation[]>
  categoriesById: Map<string, NoteCategory>
  chartWidth: number
}

const LABEL_ROW_HEIGHT_PX = 16
const ROW_SPACING_PX = 4
const ROW_STRIDE_PX = LABEL_ROW_HEIGHT_PX + ROW_SPACING_PX
const LABEL_ROW_Y = [6, 6 + ROW_STRIDE_PX, 6 + 2 * ROW_STRIDE_PX]
const MAX_ROWS = LABEL_ROW_Y.length
function bandPxForRows(rowsUsed: number): number {
  if (rowsUsed <= 0) return 0
  return LABEL_ROW_Y[rowsUsed - 1] + LABEL_ROW_HEIGHT_PX / 2 + 6
}
const FONT_SIZE = 10
const LINE_HEIGHT = 12
const GRID_LEFT_PX = 56
const GRID_RIGHT_PX = 16
const MIN_LABEL_GAP_PX = 2
/** Approximate average-character width at FONT_SIZE=10 for typical proportional
 * UI fonts (system-ui / Segoe UI). Used to size pills so they fit their text
 * without echarts' built-in measurement, since we need the width at build-time
 * for collision detection. */
const AVG_CHAR_WIDTH_PX = 5.0
/** Horizontal padding per side inside the pill (matches label.padding[1]). */
const LABEL_PAD_X_PX = 4
/** Border adds 1px per side. */
const LABEL_BORDER_PX = 1
/** Upper bound for a single pill so one long note can't hog the label band.
 * Text longer than this is clipped with an ellipsis; full text lives in the
 * hover tooltip. */
const MAX_LABEL_WIDTH_PX = 160

function resolveCssVar(value: string): string {
  if (typeof window === 'undefined') return value
  const match = value.match(/^var\((--[^),]+)(?:,\s*([^)]*))?\)$/)
  if (!match) return value
  const [, varName, fallback] = match
  const computed = getComputedStyle(document.documentElement).getPropertyValue(varName).trim()
  if (computed) return resolveCssVar(computed)
  return fallback ? resolveCssVar(fallback.trim()) : value
}

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

function rawLabelText(visible: Annotation[]): string {
  const primary = visible[0].content
  return visible.length > 1 ? `${primary} (+${visible.length - 1})` : primary
}

function estimateLabelWidth(text: string): number {
  return Math.ceil(text.length * AVG_CHAR_WIDTH_PX) + 2 * LABEL_PAD_X_PX + 2 * LABEL_BORDER_PX
}

/** Clip the label text so the pill fits within MAX_LABEL_WIDTH_PX. Full text
 * remains available in the hover tooltip. */
function clipLabelText(text: string): string {
  if (estimateLabelWidth(text) <= MAX_LABEL_WIDTH_PX) return text
  const chrome = 2 * LABEL_PAD_X_PX + 2 * LABEL_BORDER_PX
  const maxTextChars = Math.max(
    Math.floor((MAX_LABEL_WIDTH_PX - chrome) / AVG_CHAR_WIDTH_PX) - 1,
    1,
  )
  return `${text.slice(0, maxTextChars).trimEnd()}…`
}

/** Category-axis line chart: boundaryGap defaults to false, so the first
 * category sits at the grid's left edge and the last at the right edge. */
function pixelXForIndex(i: number, numPoints: number, chartWidth: number): number {
  if (numPoints <= 1) return GRID_LEFT_PX
  const plotWidth = Math.max(chartWidth - GRID_LEFT_PX - GRID_RIGHT_PX, 1)
  return GRID_LEFT_PX + (i * plotWidth) / (numPoints - 1)
}

/** Keep the label pill fully inside the chart container so text isn't clipped
 * at either edge. The dashed markLine stays vertical at the data point, so the
 * pill may sit slightly offset from its line at the chart extremes. */
function clampLabelX(pixelX: number, labelWidth: number, chartWidth: number): number {
  const halfLabel = labelWidth / 2
  const minX = halfLabel + 2
  const maxX = Math.max(chartWidth - halfLabel - 2, minX)
  return Math.min(Math.max(pixelX, minX), maxX)
}

interface PackItem {
  pixelX: number
  labelWidth: number
}

/** Try to pack items into exactly `rowCount` rows using first-fit. Returns
 * the row assignment array if every item fits without overlap, or null if
 * the layout is infeasible at this row count. */
function tryPack(items: PackItem[], rowCount: number): number[] | null {
  const lastRightByRow = Array.from({ length: rowCount }, () => -Infinity)
  const assignments: number[] = []
  for (const item of items) {
    const leftEdge = item.pixelX - item.labelWidth / 2
    const rightEdge = item.pixelX + item.labelWidth / 2
    let placedRow = -1
    for (let row = 0; row < rowCount; row++) {
      if (leftEdge - lastRightByRow[row] >= MIN_LABEL_GAP_PX) {
        lastRightByRow[row] = rightEdge
        placedRow = row
        break
      }
    }
    if (placedRow === -1) return null
    assignments.push(placedRow)
  }
  return assignments
}

/** Pick the minimum number of rows that fits every label without overlap,
 * up to MAX_ROWS. If even MAX_ROWS is infeasible, fall back to alternating
 * rows so the stagger pattern stays visible for unavoidable collisions. */
function packRows(items: PackItem[]): number[] {
  for (let rowCount = 1; rowCount <= MAX_ROWS; rowCount++) {
    const assignments = tryPack(items, rowCount)
    if (assignments) return assignments
  }
  return items.map((_, i) => i % MAX_ROWS)
}

export function buildNoteAnnotations(input: Input): NoteAnnotationsResult {
  const { trendPoints, annotationsByEvalId, chartWidth } = input

  const emptyResult: NoteAnnotationsResult = {
    markLine: { silent: true, symbol: ['none', 'none'], label: { show: false }, data: [] },
    markPoint: { silent: false, data: [] },
    labelBandPx: 0,
  }

  // Pixel positions for labels depend on the chart's rendered width. Skip the
  // first render when the container hasn't been measured yet (width ≤ grid
  // margins) — the ResizeObserver in the parent triggers a re-render with the
  // real width, at which point labels render at the correct data-point x.
  if (chartWidth <= GRID_LEFT_PX + GRID_RIGHT_PX) return emptyResult

  interface Prepared {
    index: number
    visible: Annotation[]
    pixelX: number
    labelWidth: number
    labelText: string
    tooltipBody: string
    bg: string
    fg: string
    evalId: string
  }

  const prepared: Prepared[] = []
  for (let i = 0; i < trendPoints.length; i++) {
    const point = trendPoints[i]
    const annotations = annotationsByEvalId.get(point.evalId) ?? []
    const visible = annotations.filter(a => a.category.showOnGraph)
    if (visible.length === 0) continue

    const category = dominantCategory(visible)
    const palette = paletteOf(category.color)
    const tooltipBody = visible
      .map(a => `<div><b>${a.category.label}</b>: ${escapeHtml(a.content)}</div>`)
      .join('')
    const labelText = clipLabelText(rawLabelText(visible))
    const labelWidth = estimateLabelWidth(labelText)
    const rawX = pixelXForIndex(i, trendPoints.length, chartWidth)
    const pixelX = clampLabelX(rawX, labelWidth, chartWidth)

    prepared.push({
      index: i,
      visible,
      pixelX,
      labelWidth,
      labelText,
      tooltipBody,
      bg: resolveCssVar(palette.bg),
      fg: resolveCssVar(palette.fg),
      evalId: point.evalId,
    })
  }

  const rowAssignments = packRows(prepared.map(p => ({ pixelX: p.pixelX, labelWidth: p.labelWidth })))
  const maxRowUsed = rowAssignments.reduce((m, r) => Math.max(m, r), -1)

  const markLineData: MarkLineDataItem[] = []
  const markPointData: MarkPointDataItem[] = []

  for (let k = 0; k < prepared.length; k++) {
    const p = prepared[k]
    const row = rowAssignments[k]

    markLineData.push({
      xAxis: p.index,
      lineStyle: { color: p.fg, type: 'dashed', width: 1, opacity: 0.4 },
    })

    markPointData.push({
      x: p.pixelX,
      y: LABEL_ROW_Y[row] + LABEL_ROW_HEIGHT_PX / 2,
      relativeTo: 'container',
      symbol: 'rect',
      symbolSize: [p.labelWidth, LABEL_ROW_HEIGHT_PX],
      itemStyle: { color: 'transparent' },
      label: {
        show: true,
        formatter: p.labelText,
        color: p.fg,
        fontSize: FONT_SIZE,
        lineHeight: LINE_HEIGHT,
        backgroundColor: p.bg,
        borderColor: p.fg,
        borderWidth: 1,
        borderRadius: 4,
        padding: [2, LABEL_PAD_X_PX],
        align: 'center',
        verticalAlign: 'middle',
      },
      tooltip: { trigger: 'item', formatter: p.tooltipBody },
      evalId: p.evalId,
    })
  }

  return {
    markLine: {
      silent: true,
      symbol: ['none', 'none'],
      label: { show: false },
      data: markLineData,
    },
    markPoint: {
      silent: false,
      data: markPointData,
    },
    labelBandPx: bandPxForRows(maxRowUsed + 1),
  }
}
