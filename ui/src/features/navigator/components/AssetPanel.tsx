// ui/src/features/navigator/components/AssetPanel.tsx
import { useState, useMemo, useRef, useEffect } from 'react'
import { getConfig } from '@/lib/config'
import { useNavigate } from 'react-router-dom'
import { useQueries } from '@tanstack/react-query'
import { useAssetEvaluations, useMetricHeatmap, useEvaluationNames } from '../hooks'
import { useEvaluationDetail } from '@/features/evaluations/hooks'
import { fetchEvaluationDetail } from '@/features/evaluations/api'
import { evaluationKeys } from '@/lib/queryKeys'
import { useAssets } from '@/features/assets/hooks'
import { useSlos } from '@/features/slos/hooks'
import { EvaluationHeader } from '@/features/evaluations/components/EvaluationHeader'
import { AnnotationSection, type AnnotationSectionHandle } from '@/features/evaluations/components/AnnotationForm'
import { EvaluationActionsButton, EvaluationActionForm, NoteIconButton } from '@/features/evaluations/components/EvaluationActions'
import type { ActionKind, SliMetadata } from '@/features/evaluations/types'
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
  useEffect(() => {
    setSelectedEvalId(undefined)
    setSelectedSlot(undefined)
    setActiveAction(null)
    setSelectedNames(undefined)
    setSloExpandState(new Map())
  }, [assetName])

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
    for (const s of slos ?? []) if (s.display_name) m.set(s.name, s.display_name)
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
  const { data: ev } = useEvaluationDetail(effectiveEvalId)

  // Multi-eval fetching for time slot selection (shows all SLOs together)
  const slotEvalQueries = useQueries({
    queries: (selectedSlot?.evalIds ?? []).map(id => ({
      queryKey: evaluationKeys.detail(id),
      queryFn: () => fetchEvaluationDetail(id),
      enabled: !!id,
    })),
  })
  const allSlotEvals = useMemo(
    () => slotEvalQueries.filter(q => q.data != null).map(q => q.data!),
    [slotEvalQueries],
  )

  // Map each metric to the eval ID that owns it (for multi-SLO trend charts)
  const metricEvalMap = useMemo((): Map<string, string> | undefined => {
    if (allSlotEvals.length <= 1) return undefined
    const m = new Map<string, string>()
    for (const e of allSlotEvals) {
      for (const ind of e.indicator_results) {
        m.set(ind.metric, e.id)
      }
    }
    return m
  }, [allSlotEvals])

  const mergedSliMetadata = useMemo((): Record<string, SliMetadata> | undefined => {
    if (allSlotEvals.length > 0) {
      const meta: Record<string, SliMetadata> = {}
      for (const e of allSlotEvals) {
        if (e.sli_metadata) Object.assign(meta, e.sli_metadata)
      }
      return Object.keys(meta).length > 0 ? meta : undefined
    }
    return ev?.sli_metadata
  }, [allSlotEvals, ev])

  // Initialise SLO expand state from config when heatmap data first arrives
  useEffect(() => {
    if (!heatmapData || sloExpandState.size > 0) return
    const defaultExpanded = getConfig().heatmapSloGroupsExpandedByDefault
    const m = new Map<string, boolean>()
    for (const g of heatmapData.groups) m.set(g.slo_name, defaultExpanded)
    setSloExpandState(m)
  }, [heatmapData])

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
  useEffect(() => {
    if (prevEvalId.current !== effectiveEvalId) {
      setActiveAction(null)
      prevEvalId.current = effectiveEvalId
    }
  }, [effectiveEvalId])

  const isLoading = evalsLoading || heatmapLoading

  const notedSlots = useMemo(() => {
    if (!heatmapData) return new Map<string, { evalId: string; count: number }>()
    const notedEvals = new Map(
      evals
        .filter(e => (e.annotation_count ?? 0) > 0)
        .map(e => [e.id, e] as const),
    )
    const slots = new Map<string, { evalId: string; count: number }>()
    for (const group of heatmapData.groups) {
      for (const c of group.cells) {
        if (notedEvals.has(c.slo_evaluation_id) && !slots.has(c.period_start)) {
          const summary = notedEvals.get(c.slo_evaluation_id)!
          slots.set(c.period_start, {
            evalId: c.slo_evaluation_id,
            count: summary.annotation_count ?? 0,
          })
        }
      }
    }
    return slots
  }, [evals, heatmapData])

  const hasEvals = evals.length > 0
  const displayResult = hasEvals && ev ? (ev.invalidated ? 'invalidated' : ev.result) : undefined
  const score = hasEvals && ev ? Math.round(ev.score) : undefined

  return (
    <div className="p-6 space-y-4">
      {/* Header card */}
      <EvaluationHeader
        title={assetName}
        titleMono
        result={displayResult}
        score={score}
        passPct={ev?.total_score_pass_threshold}
        warningPct={ev?.total_score_warning_threshold}
        toolbar={<TimeRangePicker />}
        metadata={hasEvals && ev ? (
          <>
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
              <span>Asset: <span className="text-foreground">{ev.asset_snapshot.display_name ?? assetDisplayName ?? ev.asset_snapshot.name}</span></span>
              {Object.entries(ev.asset_snapshot.tags ?? {}).map(([k, v]) => (
                <span key={k} className="text-muted-foreground text-xs">{k}: {v as string}</span>
              ))}
              <span className="text-xs">
                {ev.period_start.slice(0, 16).replace('T', ' ')} → {ev.period_end.slice(11, 16)}
              </span>
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {allSlotEvals.length > 1 ? (
                <>SLOs: {allSlotEvals.map(e => (e.slo_name && sloDisplayNames.get(e.slo_name)) ?? e.slo_name ?? '—').join(', ')}</>
              ) : (
                <>SLO: {(ev.slo_name && sloDisplayNames.get(ev.slo_name)) ?? ev.slo_name ?? '—'}{ev.slo_version != null && ` v${ev.slo_version}`}</>
              )}
              {ev.adapter_used && ` · adapter: ${ev.adapter_used}`}
              {ev.asset_snapshot.build_ref && ` · build: ${ev.asset_snapshot.build_ref}`}
            </div>
          </>
        ) : undefined}
        noteButton={hasEvals && effectiveEvalId && ev && !ev.invalidated ? (
          <NoteIconButton onClick={handleAddNote} annotationCount={(ev.annotations ?? []).length} />
        ) : undefined}
        actions={hasEvals && effectiveEvalId && ev ? (
          <EvaluationActionsButton
            currentResult={ev.result}
            invalidated={ev.invalidated}
            activeAction={activeAction}
            onSelectAction={setActiveAction}
            onAddNote={handleAddNote}
          />
        ) : undefined}
      />

      {/* Action form */}
      {evals.length > 0 && activeAction && effectiveEvalId && ev && (activeAction === 'restore' || !ev.invalidated) && (
        <EvaluationActionForm
          evalId={effectiveEvalId}
          currentResult={ev.result}
          activeAction={activeAction}
          onClose={() => setActiveAction(null)}
          assetName={assetName}
          sloName={ev.slo_name ?? ''}
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
      {!isLoading && evals.length > 0 && effectiveEvalId && ev && (
        <div ref={notesSectionRef}>
          <AnnotationSection ref={notesRef} evalId={effectiveEvalId} annotations={ev.annotations ?? []} />
        </div>
      )}

      {/* Heatmap mode */}
      {!isLoading && evals.length > 0 && mode === 'heatmap' && (
        <AssetPanelHeatmapView
          assetName={assetName}
          heatmapData={heatmapData}
          allSlotEvals={allSlotEvals.length > 0 ? allSlotEvals : (ev ? [ev] : [])}
          effectiveEvalId={effectiveEvalId}
          notedSlots={notedSlots}
          onEvalSelect={setSelectedEvalId}
          onSlotSelect={handleSlotSelect}
          sliMetadata={mergedSliMetadata}
          mode={mode}
          setMode={setMode}
          explorerButton={explorerButton}
          metricEvalMap={metricEvalMap}
          sloExpandState={sloExpandState}
          onSloToggle={handleSloToggle}
        />
      )}

      {/* Charts mode */}
      {!isLoading && evals.length > 0 && mode === 'chart' && (
        <AssetPanelChartView
          effectiveEvalId={effectiveEvalId}
          evals={evals}
          heatmapData={heatmapData}
          onEvalSelect={setSelectedEvalId}
          onSlotSelect={handleSlotSelect}
          metricEvalMap={metricEvalMap}
          mode={mode}
          setMode={setMode}
          explorerButton={explorerButton}
        />
      )}
    </div>
  )
}
