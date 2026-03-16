// ui/src/features/navigator/components/GroupPanel.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useEvaluations, useColumnVisibility } from '@/features/evaluations/hooks'
import { EvaluationHeatmap } from '@/features/evaluations/components/EvaluationHeatmap'
import { EvaluationTable } from '@/features/evaluations/components/EvaluationTable'
import { EvaluationHeader } from '@/features/evaluations/components/EvaluationHeader'
import { GroupScoreChart } from './GroupScoreChart'

type ViewMode = 'heatmap' | 'chart'

function ViewToggle({ mode, setMode }: { mode: ViewMode; setMode: (m: ViewMode) => void }) {
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
        Chart
      </button>
    </div>
  )
}

interface Props {
  groupName: string
  onSelectAsset: (name: string, evalId?: string) => void
}

function prettyGroupName(name: string) {
  return name.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export function GroupPanel({ groupName, onSelectAsset }: Props) {
  const [mode, setMode] = useState<ViewMode>('heatmap')
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const navigate = useNavigate()

  const { data: evals = [], isLoading } = useEvaluations({ group_name: groupName })

  const colVis = useColumnVisibility([])
  const tableEvals = selectedDate
    ? evals.filter(e => e.period_start === selectedDate)
    : evals

  const explorerButton = (
    <button
      onClick={() => navigate(`/explorer?group=${encodeURIComponent(groupName)}`)}
      className="p-1.5 rounded border border-slate-600 text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors"
      title="Open Metric Explorer"
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
        <rect x="1" y="9" width="3" height="6" rx="0.5"/>
        <rect x="6" y="5" width="3" height="10" rx="0.5"/>
        <rect x="11" y="2" width="3" height="13" rx="0.5"/>
      </svg>
    </button>
  )

  return (
    <div className="p-6 space-y-4">
      {/* Header card — group name only */}
      <EvaluationHeader
        title={prettyGroupName(groupName)}
        subtitle={evals.length > 0 ? `${evals.length} evaluations` : undefined}
      />

      {/* Content */}
      {isLoading && <p className="text-sm text-slate-400">Loading…</p>}
      {!isLoading && evals.length === 0 && (
        <p className="text-sm text-slate-400">No evaluations found for this group.</p>
      )}

      {!isLoading && evals.length > 0 && mode === 'heatmap' && (
        <>
          <div className="rounded-lg border border-slate-700 bg-gray-900 p-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Evaluation Heatmap</h2>
              <div className="flex items-center gap-3">
                <ViewToggle mode={mode} setMode={setMode} />
                {explorerButton}
              </div>
            </div>
            <EvaluationHeatmap
              evaluations={evals}
              selectedDate={selectedDate}
              onDateSelect={setSelectedDate}
              onAssetSelect={(assetName) => {
                const match = selectedDate
                  ? evals.find(e => e.asset_snapshot.name === assetName && e.period_start === selectedDate)
                  : undefined
                onSelectAsset(assetName, match?.id)
              }}
            />
          </div>
          <EvaluationTable evaluations={tableEvals} dynamicCols={[]} {...colVis} onAssetSelect={onSelectAsset} onEvalClick={ev => onSelectAsset(ev.asset_snapshot.name, ev.id)} />
        </>
      )}

      {!isLoading && evals.length > 0 && mode === 'chart' && (
        <>
          <div className="flex justify-end">
            <div className="flex items-center gap-3">
              <ViewToggle mode={mode} setMode={setMode} />
              {explorerButton}
            </div>
          </div>
          <div className="rounded-lg border border-slate-700 bg-gray-900 p-4">
            <GroupScoreChart evaluations={evals} />
          </div>
        </>
      )}
    </div>
  )
}
