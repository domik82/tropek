// ui/src/features/navigator/utils.ts
import type { EvaluationSummary } from '@/features/evaluations/types'
import type { HeatmapCell, GroupHeatmapData, SlotScoreData, AssetHeatmapData, MetricHeatmapResponse } from './types'

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

  const cellMap = new Map<string, { result: string; score: number; count: number }>()
  for (const e of evals) {
    const key = `${e.asset_snapshot.name}::${e.period_start}`
    const effectiveResult = e.invalidated ? 'invalidated' : e.result
    const existing = cellMap.get(key)
    if (!existing) {
      cellMap.set(key, { result: effectiveResult, score: e.score, count: 1 })
    } else {
      cellMap.set(key, {
        result: (RESULT_RANK[effectiveResult] ?? 0) > (RESULT_RANK[existing.result] ?? 0)
          ? effectiveResult : existing.result,
        score: (existing.score * existing.count + e.score) / (existing.count + 1),
        count: existing.count + 1,
      })
    }
  }

  const cells: HeatmapCell[] = []
  for (let xi = 0; xi < slots.length; xi++) {
    for (let yi = 0; yi < assetNames.length; yi++) {
      const key = `${assetNames[yi]}::${slots[xi]}`
      const cell = cellMap.get(key)
      cells.push({
        value: [xi, yi],
        result: cell?.result ?? 'none',
        score: cell ? Math.round(cell.score) : 0,
        slot: slots[xi],
        rowLabel: rows[yi],
      })
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

export function buildAssetHeatmapData(resp: MetricHeatmapResponse): AssetHeatmapData {
  const { slots, metrics, cells } = resp

  const cellMap = new Map<string, MetricHeatmapResponse['cells'][0]>()
  for (const c of cells) {
    cellMap.set(`${c.metric}::${c.slot}`, c)
  }

  const rows = metrics.map(m => m.display_name)

  const gridCells: HeatmapCell[] = []
  for (let xi = 0; xi < slots.length; xi++) {
    for (let yi = 0; yi < metrics.length; yi++) {
      const key = `${metrics[yi].name}::${slots[xi]}`
      const c = cellMap.get(key)
      gridCells.push({
        value: [xi, yi],
        result: c?.result ?? 'none',
        score: c ? Math.round(c.score) : 0,
        slot: slots[xi],
        rowLabel: metrics[yi].display_name,
        evalId: c?.eval_id,
      })
    }
  }

  return { slots, rows, cells: gridCells }
}
