// ui/src/features/navigator/components/AssetHeatmap.tsx
import { useMemo, useCallback } from 'react'
import { overallScoreToMiniView, sloGroupToMiniView } from '../mappers'
import type { GroupedMetricHeatmapResponseDto } from '../mappers'
import type { HeatmapEChartsCell, TimeSlotSelection } from '../ui-types'
import type { SlotNote } from '@/components/charts/NoteIndicatorRow'
import { HeatmapChart } from '@/components/charts/HeatmapChart'
import { fmtDateTime } from '@/lib/format'
import { SloMiniHeatmap } from './SloMiniHeatmap'
import { LazyHeatmap } from './LazyHeatmap'
import { RESULT_COLOUR } from '@/lib/theme'
import { useTheme } from '@/lib/theme-context'

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

  // Shared column data — identical across all mini-heatmaps
  const slots = useMemo(
    () => data.columns.map(column => column.evaluation_id),
    [data.columns],
  )

  const slotLabels = useMemo(() => {
    const labels = new Map<string, string>()
    for (const column of data.columns) {
      labels.set(column.evaluation_id, column.period_start)
    }
    return labels
  }, [data.columns])

  const formatColumnLabel = useCallback(
    (slot: string) => fmtDateTime(slotLabels.get(slot) ?? slot),
    [slotLabels],
  )

  // Overall Score segment
  const overallView = useMemo(
    () => overallScoreToMiniView(data.columns, data.composite),
    [data.columns, data.composite],
  )

  // Per-SLO segments, sorted alphabetically
  const sortedGroups = useMemo(
    () => [...data.groups].sort((a, b) => a.slo_name.localeCompare(b.slo_name)),
    [data.groups],
  )

  const sloViews = useMemo(
    () => sortedGroups.map(group => ({
      sloName: group.slo_name,
      view: sloGroupToMiniView(
        group,
        data.columns,
        expandState.get(group.slo_name) ?? false,
      ),
    })),
    [sortedGroups, data.columns, expandState],
  )

  // Selected column index — computed from raw DTO, shared across all segments
  const selectedColumn = useMemo(() => {
    if (!selectedEvalId) return undefined
    const colIdx = data.columns.findIndex(col =>
      data.groups.some(g =>
        g.cells.some(c => c.slo_evaluation_id === selectedEvalId
                       && c.evaluation_id === col.evaluation_id)
      )
    )
    return colIdx >= 0 ? colIdx : undefined
  }, [selectedEvalId, data])

  // Unified click handler — routes all mini-heatmap clicks
  const onCellClick = useCallback((cell: HeatmapEChartsCell): void => {
    if (cell.isSloHeader && cell.sloName) {
      onSloToggle(cell.sloName)
    }

    if (!cell.isSloHeader && cell.metricName && cell.sloName && onMetricClick
        && selectedColumn === cell.value[0]) {
      onMetricClick(cell.metricName, cell.sloName)
    }

    if (onSlotSelect) {
      const columnKey = cell.columnKey
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
      const specificSloEvalId =
        !cell.isSloHeader && cell.evalId ? cell.evalId : undefined
      if (evalIds.length > 0) {
        onSlotSelect({
          periodStart: cell.periodStart,
          evalIds,
          columnEvalId: columnKey,
          specificSloEvalId,
        })
      }
    } else if (cell.evalId && onEvalSelect) {
      onEvalSelect(cell.evalId)
    }
  }, [onSloToggle, onMetricClick, onSlotSelect, onEvalSelect, selectedColumn, data])

  // Estimate height for lazy-mounted expanded SLOs
  const estimateHeight = (rowCount: number): number =>
    rowCount * 28

  return (
    <div className="w-full">
      {/* Instruction text */}
      <div className="mb-1 px-1">
        <span className="text-xs text-muted-foreground">
          Click an indicator cell to select that evaluation. Click an SLO row to expand/collapse.
        </span>
      </div>

      {/* Stacked mini-heatmaps — zero gap between them */}
      <div className="flex flex-col" style={{ gap: 0 }}>
        {/* Overall Score (1 row, always rendered, carries note indicators) */}
        <SloMiniHeatmap
          view={overallView}
          slots={slots}
          slotLabels={slotLabels}
          selectedColumn={selectedColumn}
          onCellClick={onCellClick}
          showXAxis={false}
          notedColumns={notedSlots}
        />

        {/* Per-SLO segments */}
        {sloViews.map(({ sloName, view }) => {
          const isExpanded = expandState.get(sloName) ?? false
          const rowCount = view.rows.length

          const needsLazy = isExpanded && rowCount > 3

          const heatmap = (
            <SloMiniHeatmap
              key={sloName}
              view={view}
              slots={slots}
              slotLabels={slotLabels}
              selectedColumn={selectedColumn}
              onCellClick={onCellClick}
              showXAxis={false}
            />
          )

          if (needsLazy) {
            return (
              <LazyHeatmap
                key={sloName}
                estimatedHeight={estimateHeight(rowCount)}
              >
                {heatmap}
              </LazyHeatmap>
            )
          }

          return <div key={sloName}>{heatmap}</div>
        })}

        {/* Axis-only chart: 0 data rows, renders only the shared x-axis labels */}
        <HeatmapChart
          rows={[]}
          columns={slots}
          cells={[]}
          onCellClick={onCellClick}
          showXAxis
          showLegend={false}
          compact
          height={80}
          formatTooltip={() => ''}
          formatColumnLabel={formatColumnLabel}
        />
      </div>

      {/* Shared legend — rendered once below all mini-heatmaps */}
      <div className="flex items-center justify-end gap-3 text-xs text-muted-foreground mt-1 px-1" role="legend" aria-label="Status colour legend">
        {(['pass', 'warning', 'fail', 'error', 'invalidated'] as const).map(r => (
          <span key={r} className="flex items-center gap-1" aria-label={`${r} status`}>
            <span
              className="inline-block w-3 h-3 rounded-sm"
              style={{ backgroundColor: colours[r] }}
              aria-hidden="true"
            />
            {r}
          </span>
        ))}
      </div>
    </div>
  )
}
