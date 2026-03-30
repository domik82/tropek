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
}

export function AssetHeatmap({ data, selectedEvalId, onEvalSelect, onSlotSelect, notedSlots }: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]

  const { slots, rows, cells } = buildAssetHeatmapData(data)

  const selectedColumn = selectedEvalId
    ? (() => {
        const cell = cells.find(c => c.evalId === selectedEvalId)
        return cell ? cell.value[0] : undefined
      })()
    : undefined

  function formatTooltip(cell: HeatmapCell): string {
    if (cell.result === 'none') {
      return `${cell.rowLabel}<br/>${fmtDateTime(cell.slot)}<br/><em>no data</em>`
    }
    const rc = colours[cell.result as keyof typeof colours] ?? '#ccc'
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
    if (onSlotSelect) {
      // Collect all eval IDs in the same column (same slot + evaluation_name).
      // Filter by column index, not slot string, because multiple columns can
      // share the same timestamp when evaluation_names differ.
      const colIdx = cell.value[0]
      const colCells = cells.filter(c => c.value[0] === colIdx && c.evalId)
      const evalIds = [...new Set(colCells.map(c => c.evalId!))]
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
      instructionText="Click a cell to select that evaluation."
      aboveChart={
        notedSlots && notedSlots.size > 0 ? (
          <NoteIndicatorRow columns={slots} notedColumns={notedSlots} />
        ) : undefined
      }
    />
  )
}
