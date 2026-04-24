import { useCallback } from 'react'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR } from '@/lib/theme'
import { fmtDateTime } from '@/lib/format'
import { HeatmapChart } from '@/components/charts/HeatmapChart'
import type { SlotNote } from '@/components/charts/NoteIndicatorRow'
import type { HeatmapEChartsCell } from '../ui-types'
import type { MiniHeatmapView } from '../domain'

interface Props {
  view: MiniHeatmapView
  slots: string[]
  slotLabels: Map<string, string>
  selectedColumn?: number
  onCellClick: (cell: HeatmapEChartsCell) => void
  showXAxis: boolean
  notedColumns?: Map<string, SlotNote>
  onNoteIndicatorClick?: (slot: string) => void
}

export function SloMiniHeatmap({
  view,
  slots,
  slotLabels,
  selectedColumn,
  onCellClick,
  showXAxis,
  notedColumns,
  onNoteIndicatorClick,
}: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]

  const formatColumnLabel = useCallback(
    (slot: string) => fmtDateTime(slotLabels.get(slot) ?? slot),
    [slotLabels],
  )

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
    const changePointLine = cell.changePoint
      ? `<span style="color:${cell.changePoint.direction === 'regression' ? '#f85149' : '#3fb950'}">◆ Change point: ${cell.changePoint.direction} (${cell.changePoint.changeRelativePct > 0 ? '+' : ''}${cell.changePoint.changeRelativePct.toFixed(1)}%)</span>`
      : ''
    return [
      cell.evaluation_name ? `<span style="color:#94a3b8">${cell.evaluation_name}</span>` : '',
      `<b>${cell.rowLabel}</b>`,
      fmtDateTime(cell.periodStart),
      `Score: <b style="color:${rc}">${cell.score}</b> · <b style="color:${rc}">${cell.result.toUpperCase()}</b>`,
      changePointLine,
      cell.evalId
        ? `<span style="color:#888;font-size:10px">Click to select this evaluation</span>`
        : '',
    ].filter(Boolean).join('<br/>')
  }, [colours])

  return (
    <HeatmapChart
      rows={view.rows}
      columns={slots}
      cells={view.cells}
      selectedColumn={selectedColumn}
      onCellClick={onCellClick}
      formatTooltip={formatTooltip}
      formatColumnLabel={formatColumnLabel}
      headerRowIndices={view.headerRowIndices}
      showXAxis={showXAxis}
      showLegend={false}
      compact
      notedColumns={notedColumns}
      onNoteIndicatorClick={onNoteIndicatorClick}
    />
  )
}
