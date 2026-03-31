// ui/src/features/navigator/components/AssetHeatmap.tsx
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR } from '@/lib/theme'
import { fmtDateTime } from '@/lib/format'
import { HeatmapChart } from '@/components/charts/HeatmapChart'
import { NoteIndicatorRow, type SlotNote } from '@/components/charts/NoteIndicatorRow'
import { buildAssetHeatmapData } from '../utils'
import type { MetricHeatmapResponse, HeatmapCell } from '../types'

export interface TimeSlotSelection {
  periodStart: string
  evalIds: string[]
}

interface Props {
  data: MetricHeatmapResponse
  selectedEvalId?: string
  onEvalSelect?: (evalId: string) => void
  onSlotSelect?: (slot: TimeSlotSelection) => void
  notedSlots?: Map<string, SlotNote>
  expandState: Map<string, boolean>
  onSloToggle: (sloName: string) => void
}

export function AssetHeatmap({
  data,
  selectedEvalId,
  onEvalSelect,
  onSlotSelect,
  notedSlots,
  expandState,
  onSloToggle,
}: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]

  const { slots, rows, cells, headerRowIndices } = buildAssetHeatmapData(data, expandState)

  const selectedColumn = selectedEvalId
    ? (() => {
        // Try visible indicator cells first
        const cell = cells.find(c => c.evalId === selectedEvalId)
        if (cell) return cell.value[0]
        // Fallback: groups may be collapsed so indicator cells aren't in `cells`.
        // Look up which EvaluationRun column owns this slo_evaluation_id.
        const colIdx = data.columns.findIndex(col =>
          data.groups.some(g =>
            g.cells.some(c => c.slo_evaluation_id === selectedEvalId && c.evaluation_id === col.evaluation_id)
          )
        )
        return colIdx >= 0 ? colIdx : undefined
      })()
    : undefined

  function formatTooltip(cell: HeatmapCell): string {
    if (cell.result === 'none') {
      return `${cell.rowLabel}<br/>${fmtDateTime(cell.slot)}<br/><em>no data</em>`
    }
    const rc = colours[cell.result as keyof typeof colours] ?? '#ccc'
    if (cell.isSloHeader) {
      return [
        `<b style="color:#58a6ff">${cell.rowLabel}</b>`,
        fmtDateTime(cell.slot),
        `Score: <b style="color:${rc}">${cell.score}</b> · <b style="color:${rc}">${cell.result.toUpperCase()}</b>`,
        `<span style="color:#888;font-size:10px">Click to expand/collapse</span>`,
      ].join('<br/>')
    }
    return [
      cell.evaluation_name ? `<span style="color:#94a3b8">${cell.evaluation_name}</span>` : '',
      `<b>${cell.rowLabel}</b>`,
      fmtDateTime(cell.slot),
      `Score: <b style="color:${rc}">${cell.score}</b> · <b style="color:${rc}">${cell.result.toUpperCase()}</b>`,
      cell.evalId
        ? `<span style="color:#888;font-size:10px">Click to select this evaluation</span>`
        : '',
    ].filter(Boolean).join('<br/>')
  }

  function onCellClick(cell: HeatmapCell): void {
    // SLO header row click → toggle expand/collapse AND select the column
    if (cell.isSloHeader && cell.sloName) {
      onSloToggle(cell.sloName)
      // fall through to also select this column
    }
    if (onSlotSelect) {
      // Collect all slo_evaluation_ids in this column from visible indicator cells.
      // Filter by column index to handle duplicate timestamps across eval names.
      const colIdx = cell.value[0]
      const colCells = cells.filter(c => c.value[0] === colIdx && c.evalId)
      let evalIds = [...new Set(colCells.map(c => c.evalId!))]
      // Fallback: groups may be collapsed so indicator cells aren't in `cells`.
      // Use raw data to find all slo_evaluation_ids for the clicked column.
      if (evalIds.length === 0 && cell.columnKey) {
        evalIds = [...new Set(
          data.groups.flatMap(g =>
            g.cells
              .filter(c => c.evaluation_id === cell.columnKey)
              .map(c => c.slo_evaluation_id)
          )
        )]
      }
      if (evalIds.length > 0) {
        onSlotSelect({ periodStart: cell.slot, evalIds })
      }
    } else if (cell.evalId && onEvalSelect) {
      onEvalSelect(cell.evalId)
    }
  }

  return (
    <HeatmapChart
      rows={rows}
      columns={slots}
      cells={cells}
      selectedColumn={selectedColumn}
      onCellClick={onCellClick}
      formatTooltip={formatTooltip}
      headerRowIndices={headerRowIndices}
      instructionText="Click an indicator cell to select that evaluation. Click an SLO row to expand/collapse."
      aboveChart={
        notedSlots && notedSlots.size > 0 ? (
          <NoteIndicatorRow columns={slots} notedColumns={notedSlots} />
        ) : undefined
      }
    />
  )
}
