import { useCallback, useMemo, useState } from 'react'
import type { GroupedMetricHeatmap, HeatmapResult } from '@/features/navigator/domain'
import type {
  SloScopeFilter,
  SloScopeInitialMode,
  SloScopeOption,
  SloScopeOutcome,
  SloScopeResult,
} from './types'

interface UseSloScopeArgs {
  heatmapData: GroupedMetricHeatmap | undefined
  columnEvalId: string | undefined
  initialMode: SloScopeInitialMode
  filter?: SloScopeFilter
}

// The navigator domain's HeatmapResult union already folds 'invalidated' and
// 'none' into the single field. SloScopeOutcome drops 'none' (no data for the
// column means the SLO is skipped entirely) and keeps the rest verbatim.
function outcomeFromHeatmapResult(result: HeatmapResult): SloScopeOutcome | null {
  switch (result) {
    case 'pass':
    case 'warning':
    case 'fail':
    case 'error':
    case 'invalidated':
      return result
    case 'none':
      return null
  }
}

export function useSloScope({
  heatmapData,
  columnEvalId,
  initialMode,
  filter = 'all',
}: UseSloScopeArgs): SloScopeResult {
  const availableSlos = useMemo<SloScopeOption[]>(() => {
    if (!heatmapData || !columnEvalId) return []
    const options: SloScopeOption[] = []
    for (const group of heatmapData.groups) {
      // Per-SLO outcome for this column lives on the summary row; the
      // sloEvaluationId is only emitted on indicator cells, so we pick any
      // indicator in this group that matches the column to recover it.
      const summaryCell = group.summary.find(cell => cell.evaluationId === columnEvalId)
      if (!summaryCell) continue
      const outcome = outcomeFromHeatmapResult(summaryCell.result)
      if (outcome === null) continue

      if (filter === 'invalidated-only' && outcome !== 'invalidated') continue
      if (filter === 'not-invalidated' && outcome === 'invalidated') continue

      const indicatorCell = group.cells.find(cell => cell.evaluationId === columnEvalId)
      if (!indicatorCell) continue

      options.push({
        sloName: group.sloName,
        displayName: group.sloDisplayName ?? group.sloName,
        sloEvaluationId: indicatorCell.sloEvaluationId,
        currentResult: outcome,
      })
    }
    return options
  }, [heatmapData, columnEvalId, filter])

  const defaultSelection = useMemo<Set<string>>(() => {
    const allSloNames = new Set(availableSlos.map(option => option.sloName))
    if (initialMode === 'all') return allSloNames
    if (allSloNames.has(initialMode.singleSlo)) {
      return new Set([initialMode.singleSlo])
    }
    return allSloNames
  }, [availableSlos, initialMode])

  const [selected, setSelected] = useState<Set<string>>(defaultSelection)

  // Re-seed the selection whenever the backing key set changes — column
  // switch, filter change, or heatmap refetch producing different rows.
  const selectionKey = `${columnEvalId ?? ''}:${filter}:${availableSlos
    .map(option => option.sloName)
    .join(',')}`
  const [lastSelectionKey, setLastSelectionKey] = useState(selectionKey)
  if (selectionKey !== lastSelectionKey) {
    setLastSelectionKey(selectionKey)
    setSelected(defaultSelection)
  }

  const reset = useCallback(() => {
    setSelected(new Set(availableSlos.map(option => option.sloName)))
  }, [availableSlos])

  const lookupEvalId = useCallback(
    (sloName: string) =>
      availableSlos.find(option => option.sloName === sloName)?.sloEvaluationId,
    [availableSlos],
  )

  return { availableSlos, selected, setSelected, reset, lookupEvalId }
}
