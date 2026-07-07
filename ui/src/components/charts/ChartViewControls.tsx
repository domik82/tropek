import { MessageSquareWarning, LineChart, BarChart3 } from 'lucide-react'
import { useChartPreferences } from '@/lib/chart-preferences-context'

interface Props {
  /**
   * `inline` (default) renders a single compact row — drop it into a trend-grid
   * header, next to the first chart. `panel` renders a labelled box (controls on
   * top, columns toggle below) that reads clearly as a global control — use it in
   * the asset header next to the time range / actions.
   */
  variant?: 'inline' | 'panel'
}

/** Cross-chart controls: columns layout, master notes switch, master chart type.
 * Reads the shared ChartPreferences context; every instance mirrors the same state. */
export function ChartViewControls({ variant = 'inline' }: Props) {
  const {
    columns,
    setColumns,
    notesMaster,
    toggleNotesMaster,
    chartTypeMaster,
    toggleChartType,
  } = useChartPreferences()

  const columnsToggle = (
    <div className="flex border border-border rounded overflow-hidden">
      <button
        type="button"
        onClick={() => setColumns(1)}
        className={`px-2 py-1 transition-colors ${columns === 1 ? 'bg-state-selected-bg text-foreground' : 'text-muted-foreground'}`}
      >
        1 / row
      </button>
      <button
        type="button"
        onClick={() => setColumns(2)}
        className={`px-2 py-1 transition-colors ${columns === 2 ? 'bg-state-selected-bg text-foreground' : 'text-muted-foreground'}`}
      >
        2 / row
      </button>
    </div>
  )

  const notesButton = (
    <button
      type="button"
      onClick={toggleNotesMaster}
      className={`p-1 rounded border transition-colors ${
        notesMaster ? 'border-primary/40 text-primary' : 'border-border text-muted-foreground/60'
      }`}
      title="Show or hide notes on all charts"
      aria-label="Toggle notes on all charts"
    >
      <MessageSquareWarning className="size-3.5" />
    </button>
  )

  const chartTypeToggle = (
    <div className="flex border border-border rounded overflow-hidden">
      <button
        type="button"
        onClick={() => { if (chartTypeMaster !== 'line') toggleChartType() }}
        className={`px-2 py-1 transition-colors ${chartTypeMaster === 'line' ? 'bg-state-selected-bg text-foreground' : 'text-muted-foreground'}`}
        title="Show all charts as lines"
        aria-label="Show all charts as lines"
      >
        <LineChart className="size-3.5" />
      </button>
      <button
        type="button"
        onClick={() => { if (chartTypeMaster !== 'bar') toggleChartType() }}
        className={`px-2 py-1 transition-colors ${chartTypeMaster === 'bar' ? 'bg-state-selected-bg text-foreground' : 'text-muted-foreground'}`}
        title="Show all charts as bars"
        aria-label="Show all charts as bars"
      >
        <BarChart3 className="size-3.5" />
      </button>
    </div>
  )

  if (variant === 'panel') {
    return (
      <div className="flex flex-col gap-1.5 border border-border rounded-lg px-2.5 py-1.5 text-xs">
        <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Graphs</span>
        <div className="flex items-center justify-between gap-3">
          {notesButton}
          {chartTypeToggle}
        </div>
        {columnsToggle}
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 text-xs">
      {columnsToggle}
      {notesButton}
      {chartTypeToggle}
    </div>
  )
}
