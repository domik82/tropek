// ui/src/features/navigator/utils.ts
import type { Evaluation } from '@/features/evaluations'
import type { HeatmapEChartsCell } from './ui-types'
import type { GroupHeatmapData, SlotScoreData } from './domain'

const RESULT_RANK: Record<string, number> = { pass: 0, warning: 1, fail: 2, error: 3, invalidated: 4 }

export function buildGroupHeatmapData(evals: Evaluation[], fallbackNames?: Map<string, string>): GroupHeatmapData {
  const slots = Array.from(new Set(evals.map(e => e.period.from))).sort()
  const assetNames = Array.from(new Set(evals.map(e => e.assetSnapshot.name))).sort()

  // Build display name lookup: snapshot displayName → fallback map → raw name
  const displayNameMap = new Map<string, string>()
  for (const e of evals) {
    if (!displayNameMap.has(e.assetSnapshot.name)) {
      const dn = e.assetSnapshot.displayName ?? fallbackNames?.get(e.assetSnapshot.name)
      if (dn) displayNameMap.set(e.assetSnapshot.name, dn)
    }
  }
  const rows = assetNames.map(n => displayNameMap.get(n) ?? n)

  // Key by asset+slot+evalName to prevent cross-name merging
  const cellMap = new Map<string, { result: string; score: number; count: number; evalName: string }>()
  for (const e of evals) {
    const key = `${e.assetSnapshot.name}\0${e.period.from}\0${e.evaluationName}`
    const effectiveResult = e.invalidated ? 'invalidated' : (e.outcome ?? 'error')
    const existing = cellMap.get(key)
    if (!existing) {
      cellMap.set(key, { result: effectiveResult, score: e.score ?? 0, count: 1, evalName: e.evaluationName })
    } else {
      cellMap.set(key, {
        result: (RESULT_RANK[effectiveResult] ?? 0) > (RESULT_RANK[existing.result] ?? 0)
          ? effectiveResult : existing.result,
        score: (existing.score * existing.count + (e.score ?? 0)) / (existing.count + 1),
        count: existing.count + 1,
        evalName: existing.evalName,
      })
    }
  }

  const cells: HeatmapEChartsCell[] = []
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

export function buildGroupScoreData(evals: Evaluation[]): SlotScoreData[] {
  const slots = Array.from(new Set(evals.map(e => e.period.from))).sort()

  return slots.map(slot => {
    const slotEvals = evals.filter(e => e.period.from === slot)
    const assets = slotEvals.map(e => ({
      slot,
      assetName: e.assetSnapshot.name,
      score: e.score ?? 0,
      result: e.invalidated ? 'invalidated' : (e.outcome ?? 'error'),
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
