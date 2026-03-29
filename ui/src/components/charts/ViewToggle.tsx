import { Button } from '@/components/ui/button'

type ViewMode = 'heatmap' | 'chart'

interface ViewToggleProps {
  mode: ViewMode
  setMode: (m: ViewMode) => void
}

export type { ViewMode }

export function ViewToggle({ mode, setMode }: ViewToggleProps) {
  return (
    <div className="flex border border-border rounded overflow-hidden text-xs">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setMode('heatmap')}
        className={`rounded-none ${mode === 'heatmap' ? 'bg-state-selected-bg text-foreground' : 'text-muted-foreground'}`}
      >
        Heatmap
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setMode('chart')}
        className={`rounded-none ${mode === 'chart' ? 'bg-state-selected-bg text-foreground' : 'text-muted-foreground'}`}
      >
        Charts
      </Button>
    </div>
  )
}
