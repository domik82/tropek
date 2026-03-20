// ui/src/features/evaluations/hooks/useTabState.ts
import { useState, useMemo } from 'react'
import type { IndicatorResult } from '../types'

export interface TabState {
  availableGroups: string[]
  counts: Record<string, number>
  activeTab: string
  setActiveTab: (tab: string) => void
  tabIndicators: IndicatorResult[]
}

export function useTabState(indicatorResults: IndicatorResult[] | undefined): TabState {
  const [activeTab, setActiveTab] = useState('all')

  const availableGroups = useMemo(
    () => [...new Set(indicatorResults?.map(i => i.tab_group).filter(Boolean) as string[])],
    [indicatorResults],
  )

  const counts = useMemo(
    () => Object.fromEntries(
      availableGroups.map(g => [
        g,
        indicatorResults?.filter(i => i.tab_group === g).length ?? 0,
      ]),
    ),
    [indicatorResults, availableGroups],
  )

  const resolvedTab = ['all', ...availableGroups].includes(activeTab) ? activeTab : 'all'

  const tabIndicators = useMemo(
    () => resolvedTab === 'all'
      ? (indicatorResults ?? [])
      : (indicatorResults?.filter(ind => ind.tab_group === resolvedTab) ?? []),
    [indicatorResults, resolvedTab],
  )

  return {
    availableGroups,
    counts,
    activeTab: resolvedTab,
    setActiveTab,
    tabIndicators,
  }
}
