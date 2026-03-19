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
}

// Severity ranking — higher number = worse result.
// Used to pick the worst result when multiple evaluations fall in the same cell.
const RESULT_RANK: Record<string, number> = { pass: 0, warning: 1, fail: 2, error: 3, invalidated: 4 }

type CellAccum = { result: string; score: number; count: number; hasNote: boolean; noteContent: string; evalName: string }

function buildData(evals: EvaluationSummary[]): { slots: string[]; rows: string[]; cells: HeatmapCell[]; evalNameMap: Map<string, string> } {
  // Step 1: build sorted axes — rows are asset name only
  const slots = Array.from(new Set(evals.map(e => e.period_start))).sort()
  const rows = Array.from(new Set(evals.map(e => e.asset_snapshot.name))).sort()

  // Step 2: group evaluations into cells, merging duplicates by asset+slot
  const cellMap = new Map<string, CellAccum>()

  for (const e of evals) {
    const rowKey = e.asset_snapshot.name
    const key = `${rowKey}::${e.period_start}`
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

  // Step 3: produce one HeatmapCell per grid position + build evalName lookup for tooltip
  const cells: HeatmapCell[] = []
  const evalNameMap = new Map<string, string>()
  for (let xi = 0; xi < slots.length; xi++) {
    for (let yi = 0; yi < rows.length; yi++) {
      const key = `${rows[yi]}::${slots[xi]}`
      const cell = cellMap.get(key)
      if (cell) evalNameMap.set(key, cell.evalName)
      cells.push({
        value: [xi, yi],
        result: cell?.result ?? 'none',
        score: cell ? Math.round(cell.score) : 0,
        slot: slots[xi],
        rowLabel: rows[yi],
        hasNote: cell?.hasNote ?? false,
        noteContent: cell?.noteContent ?? '',
      })
    }
  }

  return { slots, rows, cells, evalNameMap }
}

export function EvaluationHeatmap({ evaluations, selectedDate, onDateSelect, onAssetSelect }: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]

  const { slots, rows, cells, evalNameMap } = useMemo(() => buildData(evaluations), [evaluations])

  const selectedColumn = selectedDate ? slots.indexOf(selectedDate) : undefined

  const formatTooltip = useMemo(
    () => (cell: HeatmapCell): string => {
      if (cell.result === 'none') {
        return `${cell.rowLabel}<br/>${fmtDateTime(cell.slot)}<br/><em>no data</em>`
      }
      const rc = colours[cell.result as keyof ResultColours] ?? '#ccc'
      const evalName = evalNameMap.get(`${cell.rowLabel}::${cell.slot}`)
      const lines = [
        `<b>${cell.rowLabel}</b>`,
        evalName ? `<span style="color:#94a3b8">${evalName}</span>` : '',
        fmtDateTime(cell.slot),
        `Score: <b style="color:${rc}">${cell.score}%</b> · <b style="color:${rc}">${cell.result.toUpperCase()}</b>`,
      ].filter(Boolean)
      if (cell.hasNote && cell.noteContent) {
        const escaped = cell.noteContent.replace(/</g, '&lt;').replace(/>/g, '&gt;')
        lines.push(`<em style="color:#fbbf24">Note: ${escaped}</em>`)
      }
      return lines.join('<br/>')
    },
    [colours, evalNameMap],
  )

  function onCellClick(cell: HeatmapCell) {
    if (cell.slot !== selectedDate) {
      onDateSelect(cell.slot)
    } else if (onAssetSelect) {
      if (cell.rowLabel.trim()) onAssetSelect(cell.rowLabel)
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
