import { MessageSquareWarning, LineChart, BarChart3 } from 'lucide-react'
import { useChartPreferences } from '@/lib/chart-preferences-context'

/** Cross-chart controls: columns layout, master notes switch, master chart type.
 * Reads the shared ChartPreferences context; drop it into any trend-grid header. */
export function ChartViewControls() {
  const {
    columns,
    setColumns,
    notesMaster,
    toggleNotesMaster,
    chartTypeMaster,
    toggleChartType,
  } = useChartPreferences()

  return (
    <div className="flex items-center gap-2 text-xs">
      {/* Columns: 1 / row vs 2 / row */}
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

      {/* Master notes switch */}
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

      {/* Master chart type: line vs bar */}
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
    </div>
  )
}
