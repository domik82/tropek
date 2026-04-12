// ui/src/features/navigator/components/AssetPanel.tsx
import { useState, useMemo, useRef, useEffect } from 'react'
import { getConfig } from '@/lib/config'
import { useNavigate } from 'react-router-dom'
import { useAssetEvaluations, useMetricHeatmap, useEvaluationNames } from '../hooks'
import { useColumnAnnotations } from '@/features/evaluations/hooks'
import { useAssets } from '@/features/assets/hooks'
import { useSlos } from '@/features/slos/hooks'
import { EvaluationHeader } from '@/features/evaluations/components/EvaluationHeader'
import { AnnotationSection, type AnnotationSectionHandle } from '@/features/evaluations/components/AnnotationForm'
import { EvaluationActionsButton, EvaluationActionForm, NoteIconButton } from '@/features/evaluations/components/EvaluationActions'
import type { ActionKind } from '@/features/evaluations/types'
import type { TimeSlotSelection } from './AssetHeatmap'
import type { ViewMode } from '@/components/charts/ViewToggle'
import { EvaluationNameFilter } from './EvaluationNameFilter'
import { AssetPanelHeatmapView } from './AssetPanelHeatmapView'
import { AssetPanelChartView } from './AssetPanelChartView'
import { TruncationWarning } from '@/features/evaluations/components/TruncationWarning'
import { TimeRangePicker } from '@/components/TimeRangePicker'

interface Props {
  assetName: string
  initialEvalId?: string
}

export function AssetPanel({ assetName, initialEvalId }: Props) {
  const [mode, setMode] = useState<ViewMode>('heatmap')
  const [selectedEvalId, setSelectedEvalId] = useState<string | undefined>(initialEvalId)
  const [selectedSlot, setSelectedSlot] = useState<TimeSlotSelection | undefined>(undefined)
  const [activeAction, setActiveAction] = useState<ActionKind | null>(null)
  const [selectedNames, setSelectedNames] = useState<string[] | undefined>(undefined)
  const [sloExpandState, setSloExpandState] = useState<Map<string, boolean>>(() => new Map())

  // Reset local state when the asset changes (defense in depth alongside key= on parent)
  /* eslint-disable react-hooks/set-state-in-effect -- intentional reset on asset change */
  useEffect(() => {
    setSelectedEvalId(undefined)
    setSelectedSlot(undefined)
    setActiveAction(null)
    setSelectedNames(undefined)
    setSloExpandState(new Map())
  }, [assetName])
  /* eslint-enable react-hooks/set-state-in-effect */

  const notesRef = useRef<AnnotationSectionHandle>(null)
  const notesSectionRef = useRef<HTMLDivElement>(null)

  function handleAddNote() {
    notesRef.current?.openForm()
    notesSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const navigate = useNavigate()

  const explorerButton = (
    <button
      onClick={() => navigate(`/explorer?asset=${encodeURIComponent(assetName)}`)}
      className="p-1.5 rounded border border-border text-muted-foreground hover:text-foreground hover:bg-state-hover-bg transition-colors"
      title="Open Metric Explorer"
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
        <rect x="1" y="9" width="3" height="6" rx="0.5"/>
        <rect x="6" y="5" width="3" height="10" rx="0.5"/>
        <rect x="11" y="2" width="3" height="13" rx="0.5"/>
      </svg>
    </button>
  )

  const { data: evalNames = [] } = useEvaluationNames(assetName)

  const { data: evals = [], isLoading: evalsLoading, truncated, total } = useAssetEvaluations(assetName, selectedNames)
  const { data: heatmapData, isLoading: heatmapLoading } = useMetricHeatmap(assetName, selectedNames)

  // Live display name lookups
  const { data: assets } = useAssets()
  const { data: slos } = useSlos()
  const assetDisplayName = useMemo(() => {
    return assets?.find(a => a.name === assetName)?.display_name
  }, [assets, assetName])
  const sloDisplayNames = useMemo(() => {
    const m = new Map<string, string>()
    for (const s of slos ?? []) if (s.displayName) m.set(s.name, s.displayName)
    return m
  }, [slos])

  const defaultEvalId = useMemo(() => {
    if (!evals.length) return undefined
    const sorted = [...evals].sort((a, b) => b.period_start.localeCompare(a.period_start))
    return (sorted.find(e => !e.invalidated) ?? sorted[0]).id
  }, [evals])

  const earliestPeriodStart = useMemo(() => {
    if (!evals.length) return undefined
    return [...evals].sort((a, b) => a.period_start.localeCompare(b.period_start))[0].period_start
  }, [evals])

  const effectiveEvalId = selectedEvalId ?? defaultEvalId

  // Parent evaluation_id (column key) — set directly from slot click,
  // or derived from heatmap cells for the default/initial selection.
  const selectedColumnEvalId = useMemo(() => {
    // Prefer explicitly set column from slot click
    if (selectedSlot?.columnEvalId) return selectedSlot.columnEvalId
    // Fallback: derive from heatmap cells for the default eval
    if (!heatmapData || !effectiveEvalId) return undefined
    for (const g of heatmapData.groups) {
      for (const c of g.cells) {
        if (c.slo_evaluation_id === effectiveEvalId) return c.evaluation_id
      }
    }
    return undefined
  }, [selectedSlot, heatmapData, effectiveEvalId])

  // period_start of the currently selected column — either set explicitly via a
  // slot click or derived by looking up the effective eval in heatmap cells.
  const selectedPeriodStart = useMemo((): string | undefined => {
    if (selectedSlot?.periodStart) return selectedSlot.periodStart
    if (!heatmapData || !effectiveEvalId) return undefined
    for (const g of heatmapData.groups) {
      for (const c of g.cells) {
        if (c.slo_evaluation_id === effectiveEvalId) return c.period_start
      }
    }
    return undefined
  }, [selectedSlot, heatmapData, effectiveEvalId])

  // Exactly one slo_evaluation_id per SLO group for the selected column. The
  // preferred match is the cell whose parent evaluation_id equals the clicked
  // column (so SLOs evaluated under multiple evaluation_names still only light
  // up the dot for the clicked eval_name). If a group has no cell under the
  // clicked parent run — e.g. its SLO is bound to a different evaluation_name —
  // fall back to any cell at the same period_start so the trend chart for that
  // SLO still highlights its own timestamp-aligned point.
  const selectedColumnSloEvalIds = useMemo((): ReadonlySet<string> => {
    if (!heatmapData || !selectedPeriodStart) {
      return effectiveEvalId ? new Set([effectiveEvalId]) : new Set()
    }
    const ids = new Set<string>()
    for (const g of heatmapData.groups) {
      const byColumn = selectedColumnEvalId
        ? g.cells.find(c => c.evaluation_id === selectedColumnEvalId)
        : undefined
      const cell = byColumn ?? g.cells.find(c => c.period_start === selectedPeriodStart)
      if (cell) ids.add(cell.slo_evaluation_id)
    }
    if (effectiveEvalId) ids.add(effectiveEvalId)
    return ids
  }, [heatmapData, selectedColumnEvalId, selectedPeriodStart, effectiveEvalId])

  // Derive ev from evaluation list. Direct lookup by slo_evaluation_id first,
  // then fallback to any eval in the same column (parent run).
  const ev = useMemo(() => {
    if (!effectiveEvalId) return undefined
    const direct = evals.find(e => e.id === effectiveEvalId)
    if (direct) return direct
    if (selectedColumnEvalId) {
      return evals.find(e => e.evaluation_id === selectedColumnEvalId)
    }
    return undefined
  }, [evals, effectiveEvalId, selectedColumnEvalId])

  // Column annotations — fetched once per column, cached with staleTime: Infinity
  const { data: displayAnnotations = [] } = useColumnAnnotations(selectedColumnEvalId)

  // Derive column-level header data entirely from the enriched heatmap response.
  // This is the primary data source for the header — independent of the evals list.
  const columnInfo = useMemo(() => {
    if (!heatmapData || !selectedColumnEvalId) return undefined
    // Composite row gives column-level result/score
    const composite = heatmapData.composite.find(c => c.evaluation_id === selectedColumnEvalId)
    // First summary with thresholds
    let passPct: number | undefined
    let warningPct: number | undefined
    let invalidated = false
    for (const g of heatmapData.groups) {
      const summary = g.summary.find(s => s.evaluation_id === selectedColumnEvalId)
      if (summary?.invalidated) invalidated = true
      if (passPct == null && summary?.total_score_pass_threshold != null) {
        passPct = summary.total_score_pass_threshold
        warningPct = summary.total_score_warning_threshold ?? undefined
      }
    }
    // period_start from any cell in this column
    const firstCell = heatmapData.groups[0]?.cells.find(c => c.evaluation_id === selectedColumnEvalId)
    return {
      result: invalidated ? 'invalidated' as const : (composite?.result ?? 'error'),
      score: composite ? Math.round(composite.score) : undefined,
      invalidated,
      periodStart: firstCell?.period_start ?? composite?.period_start,
      passPct,
      warningPct,
    }
  }, [heatmapData, selectedColumnEvalId])

  // Initialise SLO expand state from config when heatmap data first arrives
  /* eslint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps -- intentional init from async data */
  useEffect(() => {
    if (!heatmapData || sloExpandState.size > 0) return
    const defaultExpanded = getConfig().heatmapSloGroupsExpandedByDefault
    const m = new Map<string, boolean>()
    for (const g of heatmapData.groups) m.set(g.slo_name, defaultExpanded)
    setSloExpandState(m)
  }, [heatmapData])

  // Auto-populate slot selection on initial load so the column is selected
  useEffect(() => {
    if (selectedSlot || !heatmapData || !effectiveEvalId) return
    // Find the column matching the default eval
    for (const g of heatmapData.groups) {
      for (const c of g.cells) {
        if (c.slo_evaluation_id === effectiveEvalId) {
          const evalIds = [...new Set(
            heatmapData.groups.flatMap(gr =>
              gr.cells
                .filter(cell => cell.evaluation_id === c.evaluation_id)
                .map(cell => cell.slo_evaluation_id)
            )
          )]
          if (evalIds.length > 1) {
            setSelectedSlot({ periodStart: c.period_start, evalIds, columnEvalId: c.evaluation_id })
          }
          return
        }
      }
    }
  }, [heatmapData, effectiveEvalId, selectedSlot])
  /* eslint-enable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */

  function handleSloToggle(sloName: string) {
    setSloExpandState(prev => {
      const next = new Map(prev)
      next.set(sloName, !prev.get(sloName))
      return next
    })
  }

  function handleSlotSelect(slot: TimeSlotSelection) {
    setSelectedSlot(slot)
    // Also set first eval as the selected one (for header display, actions, etc.)
    if (slot.evalIds.length > 0) {
      setSelectedEvalId(slot.evalIds[0])
    }
  }

  // Close any open action form when the user selects a different evaluation
  const prevEvalId = useRef(effectiveEvalId)
  /* eslint-disable react-hooks/set-state-in-effect -- intentional reset on eval change */
  useEffect(() => {
    if (prevEvalId.current !== effectiveEvalId) {
      setActiveAction(null)
      prevEvalId.current = effectiveEvalId
    }
  }, [effectiveEvalId])
  /* eslint-enable react-hooks/set-state-in-effect */

  const isLoading = evalsLoading || heatmapLoading

  const notedSlots = useMemo(() => {
    const slots = new Map<string, { evalId: string; count: number }>()
    if (!heatmapData) return slots
    for (const col of heatmapData.columns) {
      if (col.has_notes) {
        // Use period_start as the slot key (matches HeatmapChart column key) and
        // store the parent evaluation_id for hover-time annotation fetches.
        // count=0 because the actual number is loaded lazily on hover.
        slots.set(col.period_start, { evalId: col.evaluation_id, count: 0 })
      }
    }
    return slots
  }, [heatmapData])

  const hasColumn = columnInfo != null

  return (
    <div className="p-6 space-y-4">
      {/* Header card */}
      <EvaluationHeader
        title={assetName}
        titleMono
        result={hasColumn ? columnInfo.result : undefined}
        score={hasColumn ? columnInfo.score : undefined}
        passPct={columnInfo?.passPct}
        warningPct={columnInfo?.warningPct}
        toolbar={<TimeRangePicker />}
        metadata={hasColumn ? (
          <>
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
              <span>Asset: <span className="text-foreground">{ev?.asset_snapshot.display_name ?? assetDisplayName ?? ev?.asset_snapshot.name ?? assetName}</span></span>
              {ev && Object.entries(ev.asset_snapshot.tags ?? {}).map(([k, v]) => (
                <span key={k} className="text-muted-foreground text-xs">{k}: {v as string}</span>
              ))}
              {columnInfo.periodStart && (
                <span className="text-xs">
                  {columnInfo.periodStart.slice(0, 16).replace('T', ' ')}{ev ? ` → ${ev.period_end.slice(11, 16)}` : ''}
                </span>
              )}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {heatmapData && heatmapData.groups.length > 3 ? (
                <>SLOs: {heatmapData.groups.length} evaluated</>
              ) : heatmapData && heatmapData.groups.length > 1 ? (
                <>SLOs: {heatmapData.groups.map(g => g.slo_display_name ?? g.slo_name).join(', ')}</>
              ) : ev ? (
                <>SLO: {(ev.slo_name && sloDisplayNames.get(ev.slo_name)) ?? ev.slo_name ?? '—'}{ev.slo_version != null && ` v${ev.slo_version}`}</>
              ) : heatmapData && heatmapData.groups.length === 1 ? (
                <>SLO: {heatmapData.groups[0].slo_display_name ?? heatmapData.groups[0].slo_name}</>
              ) : null}
              {ev?.adapter_used && ` · adapter: ${ev.adapter_used}`}
              {ev?.asset_snapshot.build_ref && ` · build: ${ev.asset_snapshot.build_ref}`}
            </div>
          </>
        ) : undefined}
        noteButton={hasColumn && effectiveEvalId && !columnInfo.invalidated ? (
          <NoteIconButton onClick={handleAddNote} annotationCount={displayAnnotations.length} />
        ) : undefined}
        actions={hasColumn && effectiveEvalId ? (
          <EvaluationActionsButton
            currentResult={columnInfo.result === 'invalidated' ? (ev?.result ?? 'error') : columnInfo.result}
            invalidated={columnInfo.invalidated}
            activeAction={activeAction}
            onSelectAction={setActiveAction}
            onAddNote={handleAddNote}
          />
        ) : undefined}
      />

      {/* Action form — requires ev for sloName, falls back gracefully */}
      {hasColumn && activeAction && effectiveEvalId && (activeAction === 'restore' || !columnInfo.invalidated) && (
        <EvaluationActionForm
          evalId={effectiveEvalId}
          currentResult={ev?.result ?? 'error'}
          activeAction={activeAction}
          onClose={() => setActiveAction(null)}
          assetName={assetName}
          sloName={ev?.slo_name ?? heatmapData?.groups[0]?.slo_name ?? ''}
          defaultFromDate={earliestPeriodStart?.slice(0, 16)}
        />
      )}

      {evalNames.length >= 1 && (
        <EvaluationNameFilter
          names={evalNames}
          selected={selectedNames}
          onChange={setSelectedNames}
        />
      )}

      {truncated && <TruncationWarning total={total} />}

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {!isLoading && evals.length === 0 && (
        <p className="text-sm text-muted-foreground">No evaluations found in this time range.</p>
      )}

      {/* Notes */}
      {!isLoading && hasColumn && effectiveEvalId && (
        <div ref={notesSectionRef}>
          <AnnotationSection ref={notesRef} evalId={effectiveEvalId} annotations={displayAnnotations} />
        </div>
      )}

      {/* Heatmap mode */}
      {!isLoading && evals.length > 0 && mode === 'heatmap' && (
        <AssetPanelHeatmapView
          assetName={assetName}
          heatmapData={heatmapData}
          selectedColumnEvalId={selectedColumnEvalId}
          effectiveEvalId={effectiveEvalId}
          selectedColumnSloEvalIds={selectedColumnSloEvalIds}
          selectedPeriodStart={selectedPeriodStart}
          notedSlots={notedSlots}
          onEvalSelect={setSelectedEvalId}
          onSlotSelect={handleSlotSelect}
          mode={mode}
          setMode={setMode}
          explorerButton={explorerButton}
          sloExpandState={sloExpandState}
          onSloToggle={handleSloToggle}
        />
      )}

      {/* Charts mode */}
      {!isLoading && evals.length > 0 && mode === 'chart' && (
        <AssetPanelChartView
          assetName={assetName}
          effectiveEvalId={effectiveEvalId}
          selectedColumnSloEvalIds={selectedColumnSloEvalIds}
          selectedPeriodStart={selectedPeriodStart}
          evals={evals}
          heatmapData={heatmapData}
          onEvalSelect={setSelectedEvalId}
          onSlotSelect={handleSlotSelect}
          mode={mode}
          setMode={setMode}
          explorerButton={explorerButton}
        />
      )}

    </div>
  )
}
