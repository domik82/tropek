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
import { EvaluationActionsButton, NoteIconButton } from '@/features/evaluations/components/EvaluationActions'
import { ActionPopover } from '@/features/evaluations/components/ActionPopover'
import { OverrideForm } from '@/features/evaluations/components/actions/OverrideForm'
import { InvalidateForm } from '@/features/evaluations/components/actions/InvalidateForm'
import { RestoreForm } from '@/features/evaluations/components/actions/RestoreForm'
import { BaselineForm } from '@/features/evaluations/components/actions/BaselineForm'
import { ReEvaluateForm } from '@/features/evaluations/components/actions/ReEvaluateForm'
import { useSloScope } from '@/features/evaluations/components/actions/slo-scope/useSloScope'
import type { SloScopeInitialMode } from '@/features/evaluations/components/actions/slo-scope/types'
import type { ActionKind, Outcome } from '@/features/evaluations'
import type { TimeSlotSelection } from './AssetHeatmap'
import type {
  GroupedMetricHeatmap,
  HeatmapResult,
  HeatmapSloGroup,
  HeatmapIndicatorCell,
  HeatmapSummaryCell,
  EvaluationColumn,
} from '../domain'
import type { ViewMode } from '@/components/charts/ViewToggle'
import { EvaluationNameFilter } from './EvaluationNameFilter'
import { AssetPanelHeatmapView } from './AssetPanelHeatmapView'
import { AssetPanelChartView } from './AssetPanelChartView'
import { TruncationWarning } from '@/features/evaluations/components/TruncationWarning'
import { TimeRangePicker } from '@/components/TimeRangePicker'
import { ChartViewControls } from '@/components/charts/ChartViewControls'

interface Props {
  assetName: string
  initialEvalId?: string
}

export function AssetPanel({ assetName, initialEvalId }: Props) {
  const [mode, setMode] = useState<ViewMode>('heatmap')
  const [selectedEvalId, setSelectedEvalId] = useState<string | undefined>(initialEvalId)
  const [selectedSlot, setSelectedSlot] = useState<TimeSlotSelection | undefined>(undefined)
  const [selectedSingleSloEvalId, setSelectedSingleSloEvalId] = useState<string | undefined>(undefined)
  const [activeAction, setActiveAction] = useState<ActionKind | null>(null)
  const [selectedNames, setSelectedNames] = useState<string[] | undefined>(undefined)
  const [sloExpandState, setSloExpandState] = useState<Map<string, boolean>>(() => new Map())

  // Reset local state when the asset changes (defense in depth alongside key= on parent)
  /* eslint-disable react-hooks/set-state-in-effect -- intentional reset on asset change */
  useEffect(() => {
    setSelectedEvalId(undefined)
    setSelectedSlot(undefined)
    setSelectedSingleSloEvalId(undefined)
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
    return assets?.find(a => a.name === assetName)?.displayName
  }, [assets, assetName])
  const assetId = useMemo(() => {
    return assets?.find(a => a.name === assetName)?.id
  }, [assets, assetName])
  const sloDisplayNames = useMemo(() => {
    const m = new Map<string, string>()
    for (const s of slos ?? []) if (s.displayName) m.set(s.name, s.displayName)
    return m
  }, [slos])

  const defaultEvalId = useMemo(() => {
    if (!evals.length) return undefined
    const sorted = [...evals].sort((a, b) => b.period.from.localeCompare(a.period.from))
    return (sorted.find(e => !e.invalidated) ?? sorted[0]).id
  }, [evals])

  const earliestPeriodStart = useMemo(() => {
    if (!evals.length) return undefined
    return [...evals].sort((a, b) => a.period.from.localeCompare(b.period.from))[0].period.from
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

  // period_end of the currently selected column — used as focus marker for the
  // asset meta timeline. Derived from the heatmap columns index.
  const selectedPeriodEnd = useMemo((): string | undefined => {
    if (!heatmapData || !selectedColumnEvalId) return undefined
    return heatmapData.columns.find(c => c.evaluation_id === selectedColumnEvalId)?.period_end
  }, [heatmapData, selectedColumnEvalId])

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
      return evals.find(e => e.evaluationId === selectedColumnEvalId)
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
    const compositeResult: Outcome = (() => {
      const raw = composite?.result
      if (raw === 'pass' || raw === 'warning' || raw === 'fail' || raw === 'error' || raw === 'invalidated') {
        return raw
      }
      return 'error'
    })()
    return {
      result: (invalidated ? 'invalidated' : compositeResult) as Outcome,
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
    // A per-SLO indicator click seeds single-SLO scoping; column-level or
    // composite clicks clear it so the scope picker defaults back to ALL.
    setSelectedSingleSloEvalId(slot.specificSloEvalId)
  }

  // Close any open action form when the user selects a different evaluation
  const prevEvalId = useRef(effectiveEvalId)
  useEffect(() => {
    if (prevEvalId.current !== effectiveEvalId) {
      // TODO: eslint reports the disable below as unused under the current eslint-plugin-react-hooks
      // version (the rule no longer fires here). Reconcile — drop the directive or restore the rule — when versions settle.
      setActiveAction(null) // eslint-disable-line react-hooks/set-state-in-effect -- intentional reset on eval change
      prevEvalId.current = effectiveEvalId
    }
  }, [effectiveEvalId])

  const isLoading = evalsLoading || heatmapLoading

  const notedSlots = useMemo(() => {
    // Keyed by evaluation_id (unique per EvaluationRun) — matches the slot
    // key used by the mapper. Two runs sharing a period_start (e.g. load-test
    // and prod-validation at the same 16:00) stay as distinct slots so their
    // notes do not bleed across columns.
    const slots = new Map<string, { evalId: string; count: number }>()
    if (!heatmapData) return slots
    for (const col of heatmapData.columns) {
      if (col.has_notes) {
        slots.set(col.evaluation_id, { evalId: col.evaluation_id, count: 0 })
      }
    }
    return slots
  }, [heatmapData])

  const hasColumn = columnInfo != null

  // The useSloScope hook consumes the camelCase navigator domain shape, but
  // useMetricHeatmap still returns the DTO (snake_case) because the navigator
  // migration is incomplete. Do a narrow, local DTO→domain mapping here so
  // scope derivation works without touching the heatmap fetch boundary.
  const scopeHeatmapData = useMemo<GroupedMetricHeatmap | undefined>(() => {
    if (!heatmapData) return undefined
    const normaliseResult = (raw: string | null | undefined, invalidated: boolean): HeatmapResult => {
      if (invalidated) return 'invalidated'
      switch (raw) {
        case 'pass':
        case 'warning':
        case 'fail':
        case 'error':
        case 'invalidated':
          return raw
        case null:
        case undefined:
        case '':
          return 'none'
        default:
          return 'error'
      }
    }
    const columns: EvaluationColumn[] = heatmapData.columns.map(column => ({
      evaluationId: column.evaluation_id,
      periodStart: column.period_start,
      periodEnd: column.period_end ?? column.period_start,
      evalName: column.eval_name,
      hasNotes: column.has_notes,
    }))
    const groups: HeatmapSloGroup[] = heatmapData.groups.map(group => {
      const cells: HeatmapIndicatorCell[] = group.cells.map(cell => ({
        evaluationId: cell.evaluation_id,
        sloEvaluationId: cell.slo_evaluation_id,
        periodStart: cell.period_start,
        metric: cell.metric,
        displayName: cell.display_name,
        result: normaliseResult(cell.result, false),
        score: cell.score,
        value: cell.value ?? null,
        comparedValue: cell.compared_value ?? null,
        changeRelativePct: cell.change_relative_pct ?? null,
        weight: cell.weight ?? 1,
        keySli: cell.key_sli ?? false,
        passTargets: cell.pass_targets ?? null,
        warningTargets: cell.warning_targets ?? null,
        tabGroup: cell.tab_group ?? null,
        aggregation: cell.aggregation ?? null,
        changePoint: cell.change_point
          ? {
              direction: cell.change_point.direction as 'regression' | 'improvement',
              changeRelativePct: cell.change_point.change_relative_pct ?? null,
              transition: cell.change_point.transition ?? null,
            }
          : null,
      }))
      const summary: HeatmapSummaryCell[] = group.summary.map(summaryCell => ({
        evaluationId: summaryCell.evaluation_id,
        periodStart: summaryCell.period_start,
        result: normaliseResult(summaryCell.result, summaryCell.invalidated ?? false),
        score: summaryCell.score ?? 0,
        totalScorePassThreshold: summaryCell.total_score_pass_threshold ?? null,
        totalScoreWarningThreshold: summaryCell.total_score_warning_threshold ?? null,
        sliMetadata: summaryCell.sli_metadata ?? null,
        invalidationNote: summaryCell.invalidation_note ?? null,
      }))
      return {
        sloName: group.slo_name,
        sloDisplayName: group.slo_display_name ?? null,
        metrics: group.metrics.map(metric => ({
          name: metric.name,
          displayName: metric.display_name,
        })),
        cells,
        summary,
      }
    })
    const composite: HeatmapSummaryCell[] = heatmapData.composite.map(compositeCell => ({
      evaluationId: compositeCell.evaluation_id,
      periodStart: compositeCell.period_start,
      result: normaliseResult(compositeCell.result, compositeCell.invalidated ?? false),
      score: compositeCell.score ?? 0,
      totalScorePassThreshold: compositeCell.total_score_pass_threshold ?? null,
      totalScoreWarningThreshold: compositeCell.total_score_warning_threshold ?? null,
      sliMetadata: compositeCell.sli_metadata ?? null,
      invalidationNote: compositeCell.invalidation_note ?? null,
    }))
    return {
      assetName: heatmapData.asset_name,
      columns,
      groups,
      composite,
    }
  }, [heatmapData])

  // Resolve the specific cell click to a SLO name so the scope picker can
  // default to just that SLO. Composite/column clicks leave the cell id
  // unset and the picker defaults to ALL.
  function resolveScopeInitialMode(): SloScopeInitialMode {
    if (!selectedSingleSloEvalId || !scopeHeatmapData) return 'all'
    for (const group of scopeHeatmapData.groups) {
      if (group.cells.some(cell => cell.sloEvaluationId === selectedSingleSloEvalId)) {
        return { singleSlo: group.sloName }
      }
    }
    return 'all'
  }
  const scopeInitialMode = resolveScopeInitialMode()

  const scope = useSloScope({
    heatmapData: scopeHeatmapData,
    columnEvalId: selectedColumnEvalId,
    initialMode: scopeInitialMode,
  })

  // useSloScope only re-seeds its selection when columnEvalId / filter /
  // row set changes — not when initialMode swings between 'all' and
  // { singleSlo }. Re-apply the default whenever the clicked cell seeds
  // a different scope hint so cell-click vs column-click defaults behave
  // correctly within a single column.
  const lastSingleSloRef = useRef<string | undefined>(undefined)
  const { setSelected: setScopeSelected, availableSlos: scopeAvailableSlos } = scope
  useEffect(() => {
    if (lastSingleSloRef.current === selectedSingleSloEvalId) return
    lastSingleSloRef.current = selectedSingleSloEvalId
    if (scopeInitialMode === 'all') {
      setScopeSelected(new Set(scopeAvailableSlos.map(option => option.sloName)))
      return
    }
    const targetName = scopeInitialMode.singleSlo
    if (scopeAvailableSlos.some(option => option.sloName === targetName)) {
      setScopeSelected(new Set([targetName]))
    }
  }, [selectedSingleSloEvalId, scopeInitialMode, scopeAvailableSlos, setScopeSelected])

  // Menu availability derives from the per-SLO summary rows under the
  // clicked column. allRowsInvalidated hides Invalidate; noRowsInvalidated
  // hides Restore. Uses the collapsed result union (no separate invalidated
  // boolean) because scopeHeatmapData has already folded it in.
  const menuAvailability = useMemo(() => {
    if (!scopeHeatmapData || !selectedColumnEvalId) {
      return { allRowsInvalidated: false, noRowsInvalidated: true }
    }
    const summaryRows = scopeHeatmapData.groups.flatMap(group =>
      group.summary.filter(summaryCell => summaryCell.evaluationId === selectedColumnEvalId),
    )
    if (summaryRows.length === 0) {
      return { allRowsInvalidated: false, noRowsInvalidated: true }
    }
    return {
      allRowsInvalidated: summaryRows.every(summaryCell => summaryCell.result === 'invalidated'),
      noRowsInvalidated: summaryRows.every(summaryCell => summaryCell.result !== 'invalidated'),
    }
  }, [scopeHeatmapData, selectedColumnEvalId])

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
        toolbar={
          <div className="flex items-start gap-2">
            {!isLoading && evals.length > 0 && <ChartViewControls variant="panel" />}
            <TimeRangePicker />
          </div>
        }
        metadata={hasColumn ? (
          <>
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
              <span>Asset: <span className="text-foreground">{ev?.assetSnapshot.displayName ?? assetDisplayName ?? ev?.assetSnapshot.name ?? assetName}</span></span>
              {ev && Object.entries(ev.assetSnapshot.tags ?? {}).map(([k, v]) => (
                <span key={k} className="text-muted-foreground text-xs">{k}: {v as string}</span>
              ))}
              {columnInfo.periodStart && (
                <span className="text-xs">
                  {columnInfo.periodStart.slice(0, 16).replace('T', ' ')}{ev ? ` → ${ev.period.to.slice(11, 16)}` : ''}
                </span>
              )}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {heatmapData && heatmapData.groups.length > 3 ? (
                <>SLOs: {heatmapData.groups.length} evaluated</>
              ) : heatmapData && heatmapData.groups.length > 1 ? (
                <>SLOs: {heatmapData.groups.map(g => g.slo_display_name ?? g.slo_name).join(', ')}</>
              ) : ev ? (
                <>SLO: {(ev.sloName && sloDisplayNames.get(ev.sloName)) ?? ev.sloName ?? '—'}{ev.sloVersion != null && ` v${ev.sloVersion}`}</>
              ) : heatmapData && heatmapData.groups.length === 1 ? (
                <>SLO: {heatmapData.groups[0].slo_display_name ?? heatmapData.groups[0].slo_name}</>
              ) : null}
              {ev?.adapterUsed && ` · adapter: ${ev.adapterUsed}`}
              {ev?.assetSnapshot.buildRef && ` · build: ${ev.assetSnapshot.buildRef}`}
            </div>
          </>
        ) : undefined}
        noteButton={hasColumn && effectiveEvalId && !columnInfo.invalidated ? (
          <NoteIconButton onClick={handleAddNote} annotationCount={displayAnnotations.length} />
        ) : undefined}
        actions={hasColumn && effectiveEvalId && selectedColumnEvalId ? (
          <div className='relative'>
            <EvaluationActionsButton
              currentResult={columnInfo.result === 'invalidated' ? (ev?.outcome ?? 'error') : columnInfo.result}
              allRowsInvalidated={menuAvailability.allRowsInvalidated}
              noRowsInvalidated={menuAvailability.noRowsInvalidated}
              activeAction={activeAction}
              onSelectAction={setActiveAction}
              onAddNote={handleAddNote}
            />
            <ActionPopover open={activeAction !== null} onClose={() => setActiveAction(null)}>
              {activeAction === 'override' && (
                <OverrideForm
                  scope={scope}
                  columnEvalId={selectedColumnEvalId}
                  onComplete={() => setActiveAction(null)}
                />
              )}
              {activeAction === 'invalidate' && (
                <InvalidateForm
                  scope={scope}
                  columnEvalId={selectedColumnEvalId}
                  onComplete={() => setActiveAction(null)}
                />
              )}
              {activeAction === 'restore' && (
                <RestoreForm
                  scope={scope}
                  columnEvalId={selectedColumnEvalId}
                  onComplete={() => setActiveAction(null)}
                />
              )}
              {activeAction === 'baseline' && (
                <BaselineForm
                  scope={scope}
                  columnEvalId={selectedColumnEvalId}
                  onComplete={() => setActiveAction(null)}
                />
              )}
              {activeAction === 're-evaluate' && (
                <ReEvaluateForm
                  scope={scope}
                  columnEvalId={selectedColumnEvalId}
                  assetName={assetName}
                  defaultFromDate={earliestPeriodStart?.slice(0, 16)}
                  onComplete={() => setActiveAction(null)}
                />
              )}
            </ActionPopover>
          </div>
        ) : undefined}
      />

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
      {!isLoading && hasColumn && selectedColumnEvalId && (
        <div ref={notesSectionRef}>
          <AnnotationSection ref={notesRef} runId={selectedColumnEvalId} annotations={displayAnnotations} />
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
          assetId={assetId}
          focusPeriodEnd={selectedPeriodEnd}
          focusEvalId={selectedColumnEvalId}
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
