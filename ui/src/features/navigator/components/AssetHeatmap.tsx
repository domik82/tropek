// ui/src/features/navigator/components/AssetHeatmap.tsx
import { useMemo, useCallback } from 'react'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR } from '@/lib/theme'
import { fmtDateTime } from '@/lib/format'
import { HeatmapChart } from '@/components/charts/HeatmapChart'
import type { SlotNote } from '@/components/charts/NoteIndicatorRow'
import { assetHeatmapDtoToDomain } from '../mappers'
import type { GroupedMetricHeatmapResponseDto } from '../mappers'
import type { HeatmapEChartsCell, TimeSlotSelection } from '../ui-types'

export type { TimeSlotSelection } from '../ui-types'

interface Props {
  data: GroupedMetricHeatmapResponseDto
  selectedEvalId?: string
  onEvalSelect?: (evalId: string) => void
  onSlotSelect?: (slot: TimeSlotSelection) => void
  onMetricClick?: (metricName: string, sloName: string) => void
  notedSlots?: Map<string, SlotNote>
  expandState: Map<string, boolean>
  onSloToggle: (sloName: string) => void
}

export function AssetHeatmap({
  data,
  selectedEvalId,
  onEvalSelect,
  onSlotSelect,
  onMetricClick,
  notedSlots,
  expandState,
  onSloToggle,
}: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]

  const { slots, slotLabels, rows, cells, headerRowIndices } = useMemo(
    () => assetHeatmapDtoToDomain(data, expandState),
    [data, expandState],
  )

  const formatColumnLabel = useCallback(
    (slot: string) => fmtDateTime(slotLabels.get(slot) ?? slot),
    [slotLabels],
  )

  const selectedColumn = useMemo(() => {
    if (!selectedEvalId) return undefined
    // Try visible indicator cells first
    const cell = cells.find(c => c.evalId === selectedEvalId)
    if (cell) return cell.value[0]
    // Fallback: groups may be collapsed so indicator cells aren't in `cells`.
    const colIdx = data.columns.findIndex(col =>
      data.groups.some(g =>
        g.cells.some(c => c.slo_evaluation_id === selectedEvalId && c.evaluation_id === col.evaluation_id)
      )
    )
    return colIdx >= 0 ? colIdx : undefined
  }, [selectedEvalId, cells, data])

  const formatTooltip = useCallback((cell: HeatmapEChartsCell): string => {
    if (cell.result === 'none') {
      return `${cell.rowLabel}<br/>${fmtDateTime(cell.periodStart)}<br/><em>no data</em>`
    }
    const rc = colours[cell.result as keyof typeof colours] ?? '#ccc'
    if (cell.isSloHeader) {
      return [
        `<b style="color:#58a6ff">${cell.rowLabel}</b>`,
        fmtDateTime(cell.periodStart),
        `Score: <b style="color:${rc}">${cell.score}</b> · <b style="color:${rc}">${cell.result.toUpperCase()}</b>`,
        `<span style="color:#888;font-size:10px">Click to expand/collapse</span>`,
      ].join('<br/>')
    }
    return [
      cell.evaluation_name ? `<span style="color:#94a3b8">${cell.evaluation_name}</span>` : '',
      `<b>${cell.rowLabel}</b>`,
      fmtDateTime(cell.periodStart),
      `Score: <b style="color:${rc}">${cell.score}</b> · <b style="color:${rc}">${cell.result.toUpperCase()}</b>`,
      cell.evalId
        ? `<span style="color:#888;font-size:10px">Click to select this evaluation</span>`
        : '',
    ].filter(Boolean).join('<br/>')
  }, [colours])

  const onCellClick = useCallback((cell: HeatmapEChartsCell): void => {
    // SLO header row click → toggle expand/collapse AND select the column
    if (cell.isSloHeader && cell.sloName) {
      onSloToggle(cell.sloName)
      // fall through to also select this column
    }
    // Indicator cell re-click (column already selected) → scroll to SLI table
    if (!cell.isSloHeader && cell.metricName && cell.sloName && onMetricClick
        && selectedColumn === cell.value[0]) {
      onMetricClick(cell.metricName, cell.sloName)
    }
    if (onSlotSelect) {
      // Always collect eval IDs from raw data so collapsed groups are included.
      const columnKey = cell.columnKey ?? (() => {
        const colIdx = cell.value[0]
        const c = cells.find(cc => cc.value[0] === colIdx && cc.columnKey)
        return c?.columnKey
      })()
      let evalIds: string[] = []
      if (columnKey) {
        evalIds = [...new Set(
          data.groups.flatMap(g =>
            g.cells
              .filter(c => c.evaluation_id === columnKey)
              .map(c => c.slo_evaluation_id)
          )
        )]
      }
      if (evalIds.length > 0) {
        onSlotSelect({ periodStart: cell.periodStart, evalIds, columnEvalId: columnKey })
      }
    } else if (cell.evalId && onEvalSelect) {
      onEvalSelect(cell.evalId)
    }
  }, [onSloToggle, onMetricClick, onSlotSelect, onEvalSelect, selectedColumn, cells, data])

  return (
    <HeatmapChart
      rows={rows}
      columns={slots}
      cells={cells}
      selectedColumn={selectedColumn}
      onCellClick={onCellClick}
      formatTooltip={formatTooltip}
      formatColumnLabel={formatColumnLabel}
      headerRowIndices={headerRowIndices}
      instructionText="Click an indicator cell to select that evaluation. Click an SLO row to expand/collapse."
      notedColumns={notedSlots}
    />
  )
}
