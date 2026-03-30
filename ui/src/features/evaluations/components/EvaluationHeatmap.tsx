// src/features/evaluations/components/EvaluationHeatmap.tsx
//
// Thin wrapper over the shared HeatmapChart component.
// Rows are keyed by asset name only; eval name appears in the tooltip only.
// All rendering logic lives in HeatmapChart.

import { useMemo } from 'react'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR } from '@/lib/theme'
import type { ResultColours } from '@/lib/theme'
import { fmtDateTime } from '@/lib/format'
import type { EvaluationSummary } from '../types'
import { HeatmapChart } from '@/components/charts/HeatmapChart'
import type { HeatmapCell } from '@/features/navigator/types'

interface Props {
  evaluations: EvaluationSummary[]
  selectedDate: string | null
  onDateSelect: (date: string | null) => void
  onAssetSelect?: (assetName: string) => void
  /** Fallback lookup for asset display names (for evaluations created before snapshot included display_name). */
  assetDisplayNames?: Map<string, string>
}

// Severity ranking — higher number = worse result.
// Used to pick the worst result when multiple evaluations fall in the same cell.
const RESULT_RANK: Record<string, number> = { pass: 0, warning: 1, fail: 2, error: 3, invalidated: 4 }

type CellAccum = { result: string; score: number; count: number; hasNote: boolean; noteContent: string; evalName: string }

function buildData(evals: EvaluationSummary[], fallbackNames?: Map<string, string>): { slots: string[]; rows: string[]; cells: HeatmapCell[]; evalNameMap: Map<string, string>; assetNames: string[] } {
  // Step 1: build sorted axes — rows are asset name only
  const slots = Array.from(new Set(evals.map(e => e.period_start))).sort()
  // Internal keys: raw asset names. Display: snapshot display_name → fallback map → raw name.
  const displayNameMap = new Map<string, string>()
  for (const e of evals) {
    if (!displayNameMap.has(e.asset_snapshot.name)) {
      const dn = e.asset_snapshot.display_name ?? fallbackNames?.get(e.asset_snapshot.name)
      if (dn) displayNameMap.set(e.asset_snapshot.name, dn)
    }
  }
  const assetNames = Array.from(new Set(evals.map(e => e.asset_snapshot.name))).sort()
  const rows = assetNames.map(n => displayNameMap.get(n) ?? n)

  // Step 2: group evaluations into cells, keyed by asset+slot+evalName
  const cellMap = new Map<string, CellAccum>()

  for (const e of evals) {
    const key = `${e.asset_snapshot.name}\0${e.period_start}\0${e.evaluation_name}`
    const existing = cellMap.get(key)
    const effectiveResult = e.invalidated ? 'invalidated' : e.result
    const hasNote = (e.annotation_count ?? 0) > 0
    const note = e.latest_annotation?.content ?? ''
    if (!existing) {
      cellMap.set(key, { result: effectiveResult, score: e.score, count: 1, hasNote, noteContent: note, evalName: e.evaluation_name })
    } else {
      const rank = (r: string) => RESULT_RANK[r] ?? 0
      const newIsWorse = rank(effectiveResult) > rank(existing.result)
      cellMap.set(key, {
        result: newIsWorse ? effectiveResult : existing.result,
        score: (existing.score * existing.count + e.score) / (existing.count + 1),
        count: existing.count + 1,
        hasNote: existing.hasNote || hasNote,
        noteContent: existing.noteContent || note,
        evalName: newIsWorse ? e.evaluation_name : existing.evalName,
      })
    }
  }

  // Step 3: produce HeatmapCells per grid position + build evalName lookup for tooltip
  const cells: HeatmapCell[] = []
  const evalNameMap = new Map<string, string>()
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
          hasNote: false,
          noteContent: '',
        })
      } else {
        for (const mk of matchingKeys) {
          const cell = cellMap.get(mk)!
          evalNameMap.set(`${rows[yi]}::${slots[xi]}`, cell.evalName)
          cells.push({
            value: [xi, yi],
            result: cell.result,
            score: Math.round(cell.score),
            slot: slots[xi],
            rowLabel: rows[yi],
            hasNote: cell.hasNote,
            noteContent: cell.noteContent,
            evaluation_name: cell.evalName,
          })
        }
      }
    }
  }

  return { slots, rows, cells, evalNameMap, assetNames }
}

export function EvaluationHeatmap({ evaluations, selectedDate, onDateSelect, onAssetSelect, assetDisplayNames }: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]

  const { slots, rows, cells, evalNameMap, assetNames } = useMemo(() => buildData(evaluations, assetDisplayNames), [evaluations, assetDisplayNames])

  const selectedColumn = selectedDate ? slots.indexOf(selectedDate) : undefined

  const formatTooltip = useMemo(
    () => (cell: HeatmapCell): string => {
      if (cell.result === 'none') {
        return `${cell.rowLabel}<br/>${fmtDateTime(cell.slot)}<br/><em>no data</em>`
      }
      const rc = colours[cell.result as keyof ResultColours] ?? 'var(--heatmap-text)'
      const evalName = cell.evaluation_name ?? evalNameMap.get(`${cell.rowLabel}::${cell.slot}`)
      const lines = [
        `<b>${cell.rowLabel}</b>`,
        evalName ? `<span style="color:var(--heatmap-text)">${evalName}</span>` : '',
        fmtDateTime(cell.slot),
        `Score: <b style="color:${rc}">${cell.score}%</b> · <b style="color:${rc}">${cell.result.toUpperCase()}</b>`,
      ].filter(Boolean)
      if (cell.hasNote && cell.noteContent) {
        const escaped = cell.noteContent.replace(/</g, '&lt;').replace(/>/g, '&gt;')
        lines.push(`<em style="color:var(--indicator-note)">Note: ${escaped}</em>`)
      }
      return lines.join('<br/>')
    },
    [colours, evalNameMap],
  )

  function onCellClick(cell: HeatmapCell) {
    if (cell.slot !== selectedDate) {
      onDateSelect(cell.slot)
    } else if (onAssetSelect) {
      const rowIdx = rows.indexOf(cell.rowLabel)
      const assetName = rowIdx >= 0 ? assetNames[rowIdx] : cell.rowLabel
      if (assetName.trim()) onAssetSelect(assetName)
    } else {
      onDateSelect(null)
    }
  }

  return (
    <HeatmapChart
      rows={rows}
      columns={slots}
      cells={cells}
      selectedColumn={selectedColumn}
      onCellClick={onCellClick}
      annotations={true}
      instructionText="Click any cell to filter the table below."
      formatTooltip={formatTooltip}
    />
  )
}
