// Mappers for the navigator feature. See §15.5 of the UI layering spec for
// the assetHeatmapDtoToDomain contract.
//
// IMPORTANT — fetch-boundary deviation: assetHeatmapDtoToDomain takes
// `expandState` (UI state) as a second argument and is invoked from
// AssetHeatmap.tsx's useMemo, not from queryFn. React Query stores the DTO
// wrapped as GroupedMetricHeatmapResponseDto. Other navigator endpoints (if
// added later) should prefer the standard fetch-boundary pattern.

import type { components } from '@/generated/api'
import type { AssetHeatmapView, HeatmapResult } from './domain'
import type { HeatmapEChartsCell } from './ui-types'

// --- DTO aliases -----------------------------------------------------------

export type GroupedMetricHeatmapResponseDto =
  components['schemas']['GroupedMetricHeatmapResponse']
export type HeatmapCellGroupedDto = components['schemas']['HeatmapCellGrouped']
export type HeatmapSummaryCellDto = components['schemas']['HeatmapSummaryCell']

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

// --- assetHeatmapDtoToDomain ----------------------------------------------

/**
 * Presentational mapper for the asset metric heatmap.
 *
 * Owns:
 *   - ECharts y-index math (rows rendered bottom-to-top)
 *   - Cell coordinate attachment (`value: [xi, yi]` filled in once)
 *   - Collapsing `invalidated` into the canonical `result` union
 *   - Per-SLO summary lookup construction
 *
 * Will replace `buildAssetHeatmapData` in `utils.ts` (removed in Task 9).
 */
export function assetHeatmapDtoToDomain(
  dto: GroupedMetricHeatmapResponseDto,
  expandState: Map<string, boolean>,
): AssetHeatmapView {
  const columns = dto.columns
  const columnCount = columns.length
  const sortedGroups = [...dto.groups].sort((a, b) =>
    a.slo_name.localeCompare(b.slo_name),
  )

  // Build the display row plan, visual top-to-bottom.
  // displayRows[0] is the "Overall Score" row; then one SLO-header row per
  // sorted group; indicator rows follow each header when that group is
  // expanded.
  const displayRows: Array<{
    label: string
    type: 'overall' | 'slo-header' | 'indicator'
    sloName?: string
    metricName?: string
  }> = [{ label: 'Overall Score', type: 'overall' }]

  for (const group of sortedGroups) {
    const label = group.slo_display_name ?? group.slo_name
    displayRows.push({ label, type: 'slo-header', sloName: group.slo_name })
    const isExpanded = expandState.get(group.slo_name) ?? false
    if (isExpanded) {
      for (const metric of group.metrics) {
        displayRows.push({
          label: metric.display_name,
          type: 'indicator',
          sloName: group.slo_name,
          metricName: metric.name,
        })
      }
    }
  }

  const displayRowCount = displayRows.length
  // ECharts category axis renders bottom-to-top — reverse to emit the row
  // labels in visual order.
  const rows = [...displayRows].reverse().map(r => r.label)
  const yIndexFor = (displayIndex: number): number =>
    displayRowCount - 1 - displayIndex

  // Indicator lookup: `${sloName}\0${evaluationId}\0${metricName}` → cell
  const indicatorLookup = new Map<string, HeatmapCellGroupedDto>()
  for (const group of sortedGroups) {
    for (const cell of group.cells) {
      indicatorLookup.set(
        `${group.slo_name}\0${cell.evaluation_id}\0${cell.metric}`,
        cell,
      )
    }
  }

  // Composite summary lookup: evaluation_id → summary cell
  const compositeLookup = new Map<string, HeatmapSummaryCellDto>()
  for (const summary of dto.composite) {
    compositeLookup.set(summary.evaluation_id, summary)
  }

  // Per-SLO summary lookup: `${sloName}\0${evaluationId}` → summary cell
  const sloSummaryLookup = new Map<string, HeatmapSummaryCellDto>()
  for (const group of sortedGroups) {
    for (const summary of group.summary) {
      sloSummaryLookup.set(
        `${group.slo_name}\0${summary.evaluation_id}`,
        summary,
      )
    }
  }

  const cells: HeatmapEChartsCell[] = []
  const headerRowIndices = new Set<number>()

  for (let displayIndex = 0; displayIndex < displayRowCount; displayIndex++) {
    const row = displayRows[displayIndex]
    const rowYIndex = yIndexFor(displayIndex)

    if (row.type === 'overall') {
      for (let xi = 0; xi < columnCount; xi++) {
        const column = columns[xi]
        const summary = compositeLookup.get(column.evaluation_id)
        cells.push({
          value: [xi, rowYIndex],
          result: summary ? canonicalSummaryResult(summary) : 'none',
          score: scoreToDisplay(summary?.score),
          slot: column.evaluation_id,
          periodStart: column.period_start,
          rowLabel: row.label,
          columnKey: column.evaluation_id,
          evaluation_name: column.eval_name,
        })
      }
      continue
    }

    if (row.type === 'slo-header') {
      headerRowIndices.add(rowYIndex)
      for (let xi = 0; xi < columnCount; xi++) {
        const column = columns[xi]
        const summary = sloSummaryLookup.get(
          `${row.sloName}\0${column.evaluation_id}`,
        )
        cells.push({
          value: [xi, rowYIndex],
          result: summary ? canonicalSummaryResult(summary) : 'none',
          score: scoreToDisplay(summary?.score),
          slot: column.evaluation_id,
          periodStart: column.period_start,
          rowLabel: row.label,
          columnKey: column.evaluation_id,
          evaluation_name: column.eval_name,
          isSloHeader: true,
          sloName: row.sloName,
        })
      }
      continue
    }

    // indicator row
    for (let xi = 0; xi < columnCount; xi++) {
      const column = columns[xi]
      const lookupKey = `${row.sloName}\0${column.evaluation_id}\0${row.metricName}`
      const indicator = indicatorLookup.get(lookupKey)
      cells.push({
        value: [xi, rowYIndex],
        result: indicator ? normalizeResult(indicator.result) : 'none',
        score: scoreToDisplay(indicator?.score),
        slot: column.evaluation_id,
        periodStart: column.period_start,
        rowLabel: row.label,
        columnKey: column.evaluation_id,
        evaluation_name: column.eval_name,
        evalId: indicator?.slo_evaluation_id,
        sloName: row.sloName,
        metricName: row.metricName,
      })
    }
  }

  // Slot key must be unique per column. Two distinct runs can share a
  // period_start (e.g. load-test and prod-validation both at 16:00), so
  // keying on period_start would collide — use evaluation_id, which is
  // guaranteed unique per EvaluationRun. The display label (the ISO
  // timestamp shown on the x-axis) is provided via a separate
  // `slotLabels` map consumed by HeatmapChart.formatColumnLabel.
  const slots = columns.map(column => column.evaluation_id)
  const slotLabels = new Map<string, string>()
  for (const column of columns) {
    slotLabels.set(column.evaluation_id, column.period_start)
  }
  return { slots, slotLabels, rows, cells, headerRowIndices }
}
