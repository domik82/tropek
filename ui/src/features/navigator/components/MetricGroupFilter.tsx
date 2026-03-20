// ui/src/features/navigator/components/MetricGroupFilter.tsx
import type { IndicatorResult } from '@/features/evaluations/types'

interface Props {
  allIndicators: IndicatorResult[]
  metricGroups: string[]
  activeFilter: string
  onFilterChange: (group: string) => void
}

export function MetricGroupFilter({ allIndicators, metricGroups, activeFilter, onFilterChange }: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      <button
        onClick={() => onFilterChange('all')}
        className={`px-3 py-1.5 rounded text-sm transition-colors ${
          activeFilter === 'all' ? 'bg-gray-800 text-slate-200' : 'text-slate-400 hover:text-slate-200'
        }`}
      >
        All ({allIndicators.length})
      </button>
      {metricGroups.map(g => (
        <button
          key={g}
          onClick={() => onFilterChange(g)}
          className={`px-3 py-1.5 rounded text-sm transition-colors ${
            activeFilter === g ? 'bg-gray-800 text-slate-200' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          {g} ({allIndicators.filter(i => i.tab_group === g).length})
        </button>
      ))}
    </div>
  )
}
