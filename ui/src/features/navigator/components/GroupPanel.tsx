// ui/src/features/navigator/components/GroupPanel.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useEvaluations } from '@/features/evaluations/hooks'
import { GroupHeatmap } from './GroupHeatmap'
import { GroupScoreChart } from './GroupScoreChart'

type ViewMode = 'heatmap' | 'chart'

interface Props {
  groupName: string
}

export function GroupPanel({ groupName }: Props) {
  const [mode, setMode] = useState<ViewMode>('heatmap')
  const navigate = useNavigate()
  const { data: evals = [], isLoading } = useEvaluations({ group_name: groupName })

  const latestScore = evals.length
    ? Math.round(evals.filter(e => !e.invalidated).slice(-1)[0]?.score ?? 0)
    : null

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">{groupName.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</h2>
          {evals.length > 0 && (
            <p className="text-xs text-muted-foreground mt-0.5">{evals.length} evaluations</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {latestScore != null && (
            <span className="text-2xl font-bold tabular-nums text-foreground">{latestScore}%</span>
          )}
          {/* View toggle */}
          <div className="flex border border-border rounded overflow-hidden text-xs">
            <button
              onClick={() => setMode('heatmap')}
              className={`px-3 py-1.5 transition-colors ${mode === 'heatmap' ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted/50'}`}
            >
              Heatmap
            </button>
            <button
              onClick={() => setMode('chart')}
              className={`px-3 py-1.5 transition-colors ${mode === 'chart' ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted/50'}`}
            >
              Chart
            </button>
          </div>
          {/* Explorer icon */}
          <button
            onClick={() => navigate(`/explorer?group=${encodeURIComponent(groupName)}`)}
            className="p-1.5 rounded border border-border text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            title="Open Metric Explorer"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <rect x="1" y="9" width="3" height="6" rx="0.5"/>
              <rect x="6" y="5" width="3" height="10" rx="0.5"/>
              <rect x="11" y="2" width="3" height="13" rx="0.5"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="rounded-lg border border-border bg-card p-4">
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!isLoading && evals.length === 0 && (
          <p className="text-sm text-muted-foreground">No evaluations found for this group.</p>
        )}
        {!isLoading && evals.length > 0 && mode === 'heatmap' && (
          <GroupHeatmap evaluations={evals} groupName={groupName} />
        )}
        {!isLoading && evals.length > 0 && mode === 'chart' && (
          <GroupScoreChart evaluations={evals} />
        )}
      </div>
    </div>
  )
}
