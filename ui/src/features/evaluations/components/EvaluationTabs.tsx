// src/features/evaluations/components/EvaluationTabs.tsx

// eslint-disable-next-line react-refresh/only-export-components
export function tabLabel(group: string): string {
  if (group === 'all') return 'All'
  return group.charAt(0).toUpperCase() + group.slice(1).replace(/_/g, ' ')
}

interface Props {
  availableGroups: string[]
  allCount: number
  counts: Record<string, number>
  activeTab: string
  onTabChange: (tab: string) => void
}

export function EvaluationTabs({ availableGroups, allCount, counts, activeTab, onTabChange }: Props) {
  const tabs = ['all', ...availableGroups]
  return (
    <div className="flex items-center gap-0 border-b border-border mx-3">
      {tabs.map(tab => (
        <button
          key={tab}
          onClick={() => onTabChange(tab)}
          className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === tab
              ? 'border-pass text-pass'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          {tabLabel(tab)}
          <span className="ml-1.5 text-xs opacity-60">
            {tab === 'all' ? allCount : (counts[tab] ?? 0)}
          </span>
        </button>
      ))}
    </div>
  )
}
