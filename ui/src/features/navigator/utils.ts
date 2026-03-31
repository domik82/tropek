// ui/src/features/navigator/utils.ts
import type { EvaluationSummary } from '@/features/evaluations/types'
import type { HeatmapCell, GroupHeatmapData, SlotScoreData, AssetHeatmapData, MetricHeatmapResponse, HeatmapSummaryCell, MetricHeatmapCell } from './types'

const RESULT_RANK: Record<string, number> = { pass: 0, warning: 1, fail: 2, error: 3, invalidated: 4 }

export function buildGroupHeatmapData(evals: EvaluationSummary[], fallbackNames?: Map<string, string>): GroupHeatmapData {
  const slots = Array.from(new Set(evals.map(e => e.period_start))).sort()
  const assetNames = Array.from(new Set(evals.map(e => e.asset_snapshot.name))).sort()

  // Build display name lookup: snapshot display_name → fallback map → raw name
  const displayNameMap = new Map<string, string>()
  for (const e of evals) {
    if (!displayNameMap.has(e.asset_snapshot.name)) {
      const dn = e.asset_snapshot.display_name ?? fallbackNames?.get(e.asset_snapshot.name)
      if (dn) displayNameMap.set(e.asset_snapshot.name, dn)
    }
  }
  const rows = assetNames.map(n => displayNameMap.get(n) ?? n)

  // Key by asset+slot+evalName to prevent cross-name merging
  const cellMap = new Map<string, { result: string; score: number; count: number; evalName: string }>()
  for (const e of evals) {
    const key = `${e.asset_snapshot.name}\0${e.period_start}\0${e.evaluation_name}`
    const effectiveResult = e.invalidated ? 'invalidated' : e.result
    const existing = cellMap.get(key)
    if (!existing) {
      cellMap.set(key, { result: effectiveResult, score: e.score, count: 1, evalName: e.evaluation_name })
    } else {
      cellMap.set(key, {
        result: (RESULT_RANK[effectiveResult] ?? 0) > (RESULT_RANK[existing.result] ?? 0)
          ? effectiveResult : existing.result,
        score: (existing.score * existing.count + e.score) / (existing.count + 1),
        count: existing.count + 1,
        evalName: existing.evalName,
      })
    }
  }

  const cells: HeatmapCell[] = []
  for (let xi = 0; xi < slots.length; xi++) {
    for (let yi = 0; yi < assetNames.length; yi++) {
      const prefix = `${assetNames[yi]}\0${slots[xi]}\0`
      const matchingKeys = [...cellMap.keys()].filter(k => k.startsWith(prefix))
      if (matchingKeys.length === 0) {
        cells.push({
          value: [xi, yi],
          result: 'none',
          score: 0,
          slot: slots[xi],
          rowLabel: rows[yi],
        })
      } else {
        for (const mk of matchingKeys) {
          const cell = cellMap.get(mk)!
          cells.push({
            value: [xi, yi],
            result: cell.result,
            score: Math.round(cell.score),
            slot: slots[xi],
            rowLabel: rows[yi],
            evaluation_name: cell.evalName,
          })
        }
      }
    }
  }

  return { slots, rows, cells }
}

export function buildGroupScoreData(evals: EvaluationSummary[]): SlotScoreData[] {
  const slots = Array.from(new Set(evals.map(e => e.period_start))).sort()

  return slots.map(slot => {
    const slotEvals = evals.filter(e => e.period_start === slot)
    const assets = slotEvals.map(e => ({
      slot,
      assetName: e.asset_snapshot.name,
      score: e.score,
      result: e.invalidated ? 'invalidated' : e.result,
      maxScore: 100,
    }))
    return {
      slot,
      assets,
      totalAchieved: assets.reduce((s, a) => s + a.score, 0),
      totalMax: assets.length * 100,
    }
  })
}

export function buildAssetHeatmapData(
  resp: MetricHeatmapResponse,
  expandState: Map<string, boolean>,
): AssetHeatmapData {
  const columns = resp.columns
  const n = columns.length

  // Build column index map: evaluation_id → xi
  const colIdx = new Map<string, number>()
  for (let i = 0; i < columns.length; i++) colIdx.set(columns[i].evaluation_id, i)

  // Build display rows in visual top-to-bottom order:
  //   displayRows[0] = "Overall Score" (top)
  //   displayRows[1] = SLO header (nginx)
  //   displayRows[2..] = nginx indicators if expanded
  //   ... etc.
  const displayRows: Array<{
    label: string
    type: 'overall' | 'slo-header' | 'indicator'
    sloName?: string
    metricName?: string
  }> = [{ label: 'Overall Score', type: 'overall' }]

  for (const group of resp.groups) {
    const label = group.slo_display_name ?? group.slo_name
    const isExpanded = expandState.get(group.slo_name) ?? false
    displayRows.push({ label, type: 'slo-header', sloName: group.slo_name })
    if (isExpanded) {
      for (const m of group.metrics) {
        displayRows.push({ label: m.display_name, type: 'indicator', sloName: group.slo_name, metricName: m.name })
      }
    }
  }

  const N = displayRows.length
  // ECharts renders category axis bottom-to-top, so reverse for correct visual order
  const rows = [...displayRows].reverse().map(r => r.label)

  // ECharts y-index for displayRows[i] = N - 1 - i
  function yi(displayRowIndex: number): number {
    return N - 1 - displayRowIndex
  }

  // Build indicator cell lookup: `${sloName}\0${evaluationId}\0${metricName}` → MetricHeatmapCell
  const indicatorMap = new Map<string, MetricHeatmapCell>()
  for (const group of resp.groups) {
    for (const cell of group.cells) {
      indicatorMap.set(`${group.slo_name}\0${cell.evaluation_id}\0${cell.metric}`, cell)
    }
  }

  // Build summary cell lookups
  const compositeByCol = new Map<string, HeatmapSummaryCell>()
  for (const s of resp.composite) compositeByCol.set(s.evaluation_id, s)

  const summaryByGroupCol = new Map<string, HeatmapSummaryCell>()
  for (const group of resp.groups) {
    for (const s of group.summary) {
      summaryByGroupCol.set(`${group.slo_name}\0${s.evaluation_id}`, s)
    }
  }

  const gridCells: HeatmapCell[] = []
  const headerRowIndices = new Set<number>()

  for (let di = 0; di < displayRows.length; di++) {
    const row = displayRows[di]
    const rowYi = yi(di)

    if (row.type === 'overall') {
      for (let xi = 0; xi < n; xi++) {
        const col = columns[xi]
        const s = compositeByCol.get(col.evaluation_id)
        gridCells.push({
          value: [xi, rowYi],
          result: s?.result ?? 'none',
          score: s ? Math.round(s.score) : 0,
          slot: col.period_start,
          rowLabel: row.label,
          columnKey: col.evaluation_id,
          evaluation_name: col.eval_name,
        })
      }
    } else if (row.type === 'slo-header') {
      headerRowIndices.add(rowYi)
      for (let xi = 0; xi < n; xi++) {
        const col = columns[xi]
        const s = summaryByGroupCol.get(`${row.sloName}\0${col.evaluation_id}`)
        gridCells.push({
          value: [xi, rowYi],
          result: s?.result ?? 'none',
          score: s ? Math.round(s.score) : 0,
          slot: col.period_start,
          rowLabel: row.label,
          columnKey: col.evaluation_id,
          evaluation_name: col.eval_name,
          isSloHeader: true,
          sloName: row.sloName,
        })
      }
    } else {
      // indicator row
      for (let xi = 0; xi < n; xi++) {
        const col = columns[xi]
        const key = `${row.sloName}\0${col.evaluation_id}\0${row.metricName}`
        const cell = indicatorMap.get(key)
        gridCells.push({
          value: [xi, rowYi],
          result: cell?.result ?? 'none',
          score: cell ? Math.round(cell.score) : 0,
          slot: col.period_start,
          rowLabel: row.label,
          columnKey: col.evaluation_id,
          evaluation_name: col.eval_name,
          evalId: cell?.slo_evaluation_id,
        })
      }
    }
  }

  const slots = columns.map(c => c.period_start)
  return { slots, rows, cells: gridCells, headerRowIndices }
}
