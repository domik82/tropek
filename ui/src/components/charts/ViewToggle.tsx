type ViewMode = 'heatmap' | 'chart'

interface ViewToggleProps {
  mode: ViewMode
  setMode: (m: ViewMode) => void
}

export type { ViewMode }

export function ViewToggle({ mode, setMode }: ViewToggleProps) {
  return (
    <div className="flex border border-border rounded overflow-hidden text-xs">
      <button
        onClick={() => setMode('heatmap')}
        className={`px-3 py-1.5 transition-colors ${mode === 'heatmap' ? 'bg-state-selected-bg text-foreground' : 'text-muted-foreground hover:bg-state-hover-bg'}`}
      >
        Heatmap
      </button>
      <button
        onClick={() => setMode('chart')}
        className={`px-3 py-1.5 transition-colors ${mode === 'chart' ? 'bg-state-selected-bg text-foreground' : 'text-muted-foreground hover:bg-state-hover-bg'}`}
      >
        Charts
      </button>
    </div>
  )
}
