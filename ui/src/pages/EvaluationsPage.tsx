// src/pages/EvaluationsPage.tsx
// Thin shell — reads URL params, calls hook, composes feature components.

import { useState, useMemo, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useEvaluations, useColumnVisibility } from '@/features/evaluations/hooks'
import { useAssetGroups } from '@/features/assets/hooks'
import { EvaluationHeatmap } from '@/features/evaluations/components/EvaluationHeatmap'
import { EvaluationTable } from '@/features/evaluations/components/EvaluationTable'
import { TriggerEvaluationModal } from '@/features/evaluations/components/TriggerEvaluationModal'
import { Button } from '@/components/ui/button'
import type { ColumnDef } from '@/features/evaluations/types'

export function EvaluationsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const lab = searchParams.get('group_name') ?? undefined
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null)
  const [triggerOpen, setTriggerOpen] = useState(false)

  const { data: groupTree } = useAssetGroups()
  const groups = groupTree?.top_level ?? []

  const { data: allEvals = [], isError: allError } = useEvaluations({ group_name: lab })
  const { data: slotEvals = [], isError: slotError } = useEvaluations({
    group_name: lab,
    from: selectedSlot ?? undefined,
    to: selectedSlot ? new Date(new Date(selectedSlot).getTime() + 1000).toISOString().slice(0, 19) + 'Z' : undefined,
  })

  // Latest slot across all evaluations in the current view
  const latestSlot = useMemo(() => {
    if (!allEvals.length) return null
    return allEvals.map(e => e.period_start).sort().at(-1) ?? null
  }, [allEvals])

  // Auto-select the latest slot when a specific lab is chosen.
  // Reset to null when switching to "All Labs" (lab undefined).
  useEffect(() => {
    if (lab && latestSlot) {
      setSelectedSlot(latestSlot)
    } else if (!lab) {
      setSelectedSlot(null)
    }
  }, [lab, latestSlot])

  // Date range in days
  const dateRange = useMemo(() => {
    if (!allEvals.length) return null
    const dates = allEvals.map(e => e.period_start).sort()
    return Math.round(
      (new Date(dates[dates.length - 1]).getTime() - new Date(dates[0]).getTime()) /
      (1000 * 60 * 60 * 24)
    ) + 1
  }, [allEvals])

  const selectedGroup = groups.find(g => g.name === lab)

  const dynamicCols: ColumnDef[] = Array.from(
    new Set(allEvals.flatMap(e => Object.keys(e.asset_snapshot.tags ?? {})))
  )
    .filter(k => !['os', 'arch', 'lab'].includes(k))
    .map(key => ({ key, label: key, required: false }))

  const colVis = useColumnVisibility(dynamicCols)
  const tableEvals = selectedSlot ? slotEvals : allEvals

  function selectLab(name: string | undefined) {
    setSelectedSlot(null)
    if (name) setSearchParams({ group_name: name })
    else setSearchParams({})
  }

  if (allError || slotError) return <p className="p-6 text-red-400">Failed to load data.</p>

  return (
    <div className="p-6 space-y-4">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold">Evaluations</h1>
          {allEvals.length > 0 && dateRange != null && (
            <p className="text-sm text-gray-400 mt-0.5">
              {allEvals.length} runs · {dateRange} days
            </p>
          )}
        </div>
        <Button onClick={() => setTriggerOpen(true)}>Trigger Evaluation</Button>
      </div>

      {/* Lab filter tabs */}
      {groups.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => selectLab(undefined)}
            className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
              !lab ? 'bg-gray-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            All Labs
          </button>
          {groups.map(g => (
            <button
              key={g.name}
              onClick={() => selectLab(g.name)}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                lab === g.name ? 'bg-gray-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
              }`}
            >
              {g.display_name ?? g.name}
            </button>
          ))}
        </div>
      )}

      {/* Lab description */}
      {selectedGroup?.description && (
        <p className="text-xs text-gray-400">{selectedGroup.description}</p>
      )}

      {/* Heatmap card */}
      <div className="rounded-lg border border-gray-700 bg-gray-900 p-4">
        <EvaluationHeatmap
          evaluations={allEvals}
          selectedDate={selectedSlot}
          onDateSelect={setSelectedSlot}
        />
      </div>

      {/* Slot selection indicator */}
      {selectedSlot ? (
        <p className="text-sm text-gray-300 flex items-center gap-2">
          <strong>{selectedSlot.slice(0, 16).replace('T', ' ')}</strong>
          {selectedSlot === latestSlot && (
            <span className="text-xs bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded">latest</span>
          )}
          <span className="text-gray-400">
            {tableEvals.length} run{tableEvals.length !== 1 ? 's' : ''}
          </span>
          <button className="text-gray-500 hover:text-white text-xs" onClick={() => setSelectedSlot(null)}>
            ✕ clear
          </button>
        </p>
      ) : (
        <p className="text-xs text-gray-500">
          Showing all {tableEvals.length} runs. Click a heatmap cell to filter by time slot.
        </p>
      )}

      {/* Table card */}
      <div className="rounded-lg border border-gray-700 bg-gray-900 p-4">
        <EvaluationTable evaluations={tableEvals} dynamicCols={dynamicCols} {...colVis} />
      </div>

      <TriggerEvaluationModal open={triggerOpen} onClose={() => setTriggerOpen(false)} />
    </div>
  )
}
