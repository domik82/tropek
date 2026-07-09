// Mappers for the navigator feature. See §15.5 of the UI layering spec.
//
// IMPORTANT — fetch-boundary deviation: per-segment mappers
// (overallScoreToMiniView, sloGroupToMiniView) are invoked from
// AssetHeatmap.tsx's useMemo, not from queryFn. React Query stores the DTO
// wrapped as GroupedMetricHeatmapResponseDto. Other navigator endpoints (if
// added later) should prefer the standard fetch-boundary pattern.

import type { components } from '@/generated/api'
import type { ChangePointMarker, HeatmapResult, MiniHeatmapView } from './domain'
import type { HeatmapEChartsCell } from './ui-types'

// --- DTO aliases -----------------------------------------------------------

export type GroupedMetricHeatmapResponseDto =
  components['schemas']['GroupedMetricHeatmapResponse']
export type HeatmapCellGroupedDto = components['schemas']['HeatmapCellGrouped']
export type HeatmapSummaryCellDto = components['schemas']['HeatmapSummaryCell']
export type ChangePointMarkerDto = components['schemas']['ChangePointMarker']

// --- Exhaustiveness check for the top-level response ----------------------

type DroppedGroupedResponseKeys = never

type MappedGroupedResponseKeys = 'asset_name' | 'columns' | 'composite' | 'groups'

type _GroupedCoverage = Exclude<
  keyof GroupedMetricHeatmapResponseDto,
  MappedGroupedResponseKeys | DroppedGroupedResponseKeys
>
const _groupedExhaustive: _GroupedCoverage extends never ? true : _GroupedCoverage = true
void _groupedExhaustive

// --- Canonical result union ------------------------------------------------

// Collapse the backend's (result: string, invalidated: boolean) pair into
// a single discriminated union value. The UI never branches on `invalidated`
// again after this call — an invalidated summary cell surfaces as
// `result: 'invalidated'` directly.
function canonicalSummaryResult(summary: HeatmapSummaryCellDto): HeatmapResult {
  if (summary.invalidated) return 'invalidated'
  return normalizeResult(summary.result)
}

// Round a nullable score to the integer we display in cells. Centralised so
// the overall / slo-header / indicator branches share one rule.
function scoreToDisplay(raw: number | null | undefined): number {
  return raw == null ? 0 : Math.round(raw)
}

function normalizeResult(raw: string | null | undefined): HeatmapResult {
  switch (raw) {
    case 'pass':
    case 'warning':
    case 'fail':
    case 'error':
    case 'invalidated':
      return raw
    case null:
    case undefined:
    case '':
      return 'none'
    default:
      // Unknown backend value — surface as 'error' so colouring degrades
      // gracefully rather than crashing on the switch in theme.ts.
      return 'error'
  }
}

// --- changePointToMarker ----------------------------------------------------

/**
 * Maps the change_point DTO attached to heatmap cells (and trend points) to
 * the domain ChangePointMarker. Single mapping point shared by the mini-view
 * mapper and the AssetPanel/AssetPanelHeatmapView useMemo call sites.
 */
export function changePointToMarker(
  changePointDto: ChangePointMarkerDto | null | undefined,
): ChangePointMarker | null {
  if (!changePointDto) return null
  return {
    direction: changePointDto.direction,
    changeRelativePct: changePointDto.change_relative_pct ?? null,
    transition: changePointDto.transition ?? null,
    changeAbsolute: changePointDto.change_absolute ?? null,
  }
}

// --- overallScoreToMiniView -----------------------------------------------

/**
 * Produces a 1-row MiniHeatmapView for the "Overall Score" composite row.
 * One cell per column; y is always 0 (single row). headerRowIndices is
 * empty — the overall row carries no header styling in mini views.
 */
export function overallScoreToMiniView(
  columns: GroupedMetricHeatmapResponseDto['columns'],
  composite: GroupedMetricHeatmapResponseDto['composite'],
): MiniHeatmapView {
  const compositeLookup = new Map<string, HeatmapSummaryCellDto>()
  for (const summaryCell of composite) {
    compositeLookup.set(summaryCell.evaluation_id, summaryCell)
  }

  const cells: HeatmapEChartsCell[] = []

  for (let xi = 0; xi < columns.length; xi++) {
    const column = columns[xi]
    const summaryCell = compositeLookup.get(column.evaluation_id)
    cells.push({
      value: [xi, 0],
      result: summaryCell ? canonicalSummaryResult(summaryCell) : 'none',
      score: scoreToDisplay(summaryCell?.score),
      slot: column.evaluation_id,
      periodStart: column.period_start,
      rowLabel: 'Overall Score',
      columnKey: column.evaluation_id,
      evaluation_name: column.eval_name,
    })
  }

  return {
    rows: ['Overall Score'],
    cells,
    headerRowIndices: new Set(),
  }
}

// --- sloGroupToMiniView ---------------------------------------------------

/**
 * Produces a MiniHeatmapView for a single SLO group.
 *
 * Collapsed: 1 row — the SLO header only (isSloHeader=true on all cells).
 * Expanded:  1 header row + N indicator rows (one per metric in group.metrics).
 *
 * ECharts renders the category axis bottom-to-top, so:
 *   - The header row (displayed at top) receives the highest y-index.
 *   - The `rows` array is therefore reversed (bottom-to-top label order).
 *   - yIndex = rowCount - 1 - displayIndex (display top=0, ECharts top=rowCount-1).
 */
export function sloGroupToMiniView(
  group: GroupedMetricHeatmapResponseDto['groups'][number],
  columns: GroupedMetricHeatmapResponseDto['columns'],
  isExpanded: boolean,
): MiniHeatmapView {
  const rowLabel = group.slo_display_name ?? group.slo_name

  // Build display rows top-to-bottom: header first, then indicator rows.
  const displayRows: Array<{
    label: string
    type: 'slo-header' | 'indicator'
    metricName?: string
  }> = [{ label: rowLabel, type: 'slo-header' }]

  if (isExpanded) {
    for (const metric of group.metrics) {
      displayRows.push({ label: metric.display_name, type: 'indicator', metricName: metric.name })
    }
  }

  const rowCount = displayRows.length
  const yIndexFor = (displayIndex: number): number => rowCount - 1 - displayIndex

  // Per-SLO summary lookup: evaluation_id → summary cell
  const sloSummaryLookup = new Map<string, HeatmapSummaryCellDto>()
  for (const summaryCell of group.summary) {
    sloSummaryLookup.set(summaryCell.evaluation_id, summaryCell)
  }

  // Indicator lookup: `${evaluationId}\0${metricName}` → indicator cell
  const indicatorLookup = new Map<string, HeatmapCellGroupedDto>()
  for (const indicatorCell of group.cells) {
    indicatorLookup.set(`${indicatorCell.evaluation_id}\0${indicatorCell.metric}`, indicatorCell)
  }

  const cells: HeatmapEChartsCell[] = []
  const headerRowIndices = new Set<number>()

  for (let displayIndex = 0; displayIndex < rowCount; displayIndex++) {
    const displayRow = displayRows[displayIndex]
    const rowYIndex = yIndexFor(displayIndex)

    if (displayRow.type === 'slo-header') {
      headerRowIndices.add(rowYIndex)
      for (let xi = 0; xi < columns.length; xi++) {
        const column = columns[xi]
        const summaryCell = sloSummaryLookup.get(column.evaluation_id)
        cells.push({
          value: [xi, rowYIndex],
          result: summaryCell ? canonicalSummaryResult(summaryCell) : 'none',
          score: scoreToDisplay(summaryCell?.score),
          slot: column.evaluation_id,
          periodStart: column.period_start,
          rowLabel: displayRow.label,
          columnKey: column.evaluation_id,
          evaluation_name: column.eval_name,
          isSloHeader: true,
          sloName: group.slo_name,
        })
      }
      continue
    }

    // indicator row
    for (let xi = 0; xi < columns.length; xi++) {
      const column = columns[xi]
      const lookupKey = `${column.evaluation_id}\0${displayRow.metricName}`
      const indicatorCell = indicatorLookup.get(lookupKey)
      cells.push({
        value: [xi, rowYIndex],
        result: indicatorCell ? normalizeResult(indicatorCell.result) : 'none',
        score: scoreToDisplay(indicatorCell?.score),
        slot: column.evaluation_id,
        periodStart: column.period_start,
        rowLabel: displayRow.label,
        columnKey: column.evaluation_id,
        evaluation_name: column.eval_name,
        evalId: indicatorCell?.slo_evaluation_id,
        sloName: group.slo_name,
        metricName: displayRow.metricName,
        changePoint: changePointToMarker(indicatorCell?.change_point) ?? undefined,
      })
    }
  }

  // ECharts category axis is bottom-to-top — reverse display rows to emit
  // labels in the order ECharts expects (lowest y-index first in the array).
  const rows = [...displayRows].reverse().map(r => r.label)

  return { rows, cells, headerRowIndices }
}
