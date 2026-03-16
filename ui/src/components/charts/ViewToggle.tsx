type ViewMode = 'heatmap' | 'chart'

interface ViewToggleProps {
  mode: ViewMode
  setMode: (m: ViewMode) => void
}

export type { ViewMode }

export function ViewToggle({ mode, setMode }: ViewToggleProps) {
  return (
    <div className="flex border border-slate-700 rounded overflow-hidden text-xs">
      <button
        onClick={() => setMode('heatmap')}
        className={`px-3 py-1.5 transition-colors ${mode === 'heatmap' ? 'bg-gray-800 text-slate-200' : 'text-slate-400 hover:bg-gray-800/50'}`}
      >
        Heatmap
      </button>
      <button
        onClick={() => setMode('chart')}
        className={`px-3 py-1.5 transition-colors ${mode === 'chart' ? 'bg-gray-800 text-slate-200' : 'text-slate-400 hover:bg-gray-800/50'}`}
      >
        Charts
      </button>
    </div>
  )
}
