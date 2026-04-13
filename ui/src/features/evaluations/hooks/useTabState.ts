// ui/src/features/evaluations/hooks/useTabState.ts
import { useState, useMemo } from 'react'
import type { Indicator } from '../domain'

export interface TabState {
  availableGroups: string[]
  counts: Record<string, number>
  activeTab: string
  setActiveTab: (tab: string) => void
  tabIndicators: Indicator[]
}

export function useTabState(indicators: Indicator[] | undefined): TabState {
  const [activeTab, setActiveTab] = useState('all')

  const availableGroups = useMemo(
    () => [...new Set(indicators?.map(i => i.tabGroup).filter(Boolean) as string[])],
    [indicators],
  )

  const counts = useMemo(
    () => Object.fromEntries(
      availableGroups.map(g => [
        g,
        indicators?.filter(i => i.tabGroup === g).length ?? 0,
      ]),
    ),
    [indicators, availableGroups],
  )

  const resolvedTab = ['all', ...availableGroups].includes(activeTab) ? activeTab : 'all'

  const tabIndicators = useMemo(
    () => resolvedTab === 'all'
      ? (indicators ?? [])
      : (indicators?.filter(ind => ind.tabGroup === resolvedTab) ?? []),
    [indicators, resolvedTab],
  )

  return {
    availableGroups,
    counts,
    activeTab: resolvedTab,
    setActiveTab,
    tabIndicators,
  }
}
