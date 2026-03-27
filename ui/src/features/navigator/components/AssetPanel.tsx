// ui/src/features/navigator/components/AssetPanel.tsx
import { useState, useMemo, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAssetEvaluations, useMetricHeatmap, useEvaluationNames } from '../hooks'
import { useEvaluationDetail } from '@/features/evaluations/hooks'
import { useAssets } from '@/features/assets/hooks'
import { useSlos } from '@/features/slos/hooks'
import { useTabState } from '@/features/evaluations/hooks/useTabState'
import { EvaluationHeader } from '@/features/evaluations/components/EvaluationHeader'
import { AnnotationSection, type AnnotationSectionHandle } from '@/features/evaluations/components/AnnotationForm'
import { EvaluationActionsButton, EvaluationActionForm, NoteIconButton } from '@/features/evaluations/components/EvaluationActions'
import type { ActionKind } from '@/features/evaluations/types'
import type { ViewMode } from '@/components/charts/ViewToggle'
import { EvaluationNameFilter } from './EvaluationNameFilter'
import { AssetPanelHeatmapView } from './AssetPanelHeatmapView'
import { AssetPanelChartView } from './AssetPanelChartView'
import { TimeRangePicker } from '@/components/TimeRangePicker'

interface Props {
  assetName: string
  initialEvalId?: string
}

export function AssetPanel({ assetName, initialEvalId }: Props) {
  const [mode, setMode] = useState<ViewMode>('heatmap')
  const [selectedEvalId, setSelectedEvalId] = useState<string | undefined>(initialEvalId)
  const [activeAction, setActiveAction] = useState<ActionKind | null>(null)
  const [selectedNames, setSelectedNames] = useState<string[] | undefined>(undefined)
  const [namesInitialized, setNamesInitialized] = useState(false)

  // Reset local state when the asset changes (defense in depth alongside key= on parent)
  useEffect(() => {
    setSelectedEvalId(undefined)
    setActiveAction(null)
    setSelectedNames(undefined)
    setNamesInitialized(false)
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

  const { data: evalNames = [] } = useEvaluationNames(assetName)

  useEffect(() => {
    if (evalNames.length > 0 && !namesInitialized) {
      setSelectedNames([evalNames[0].name])
      setNamesInitialized(true)
    }
  }, [evalNames, namesInitialized])

  const { data: evals = [], isLoading: evalsLoading } = useAssetEvaluations(assetName, selectedNames)
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

  const { availableGroups, counts, activeTab, setActiveTab, tabIndicators } =
    useTabState(ev?.indicator_results)

  const isLoading = evalsLoading || heatmapLoading

  const notedSlots = useMemo(() => {
    if (!heatmapData) return new Map<string, { evalId: string; count: number }>()
    const notedEvals = new Map(
      evals
        .filter(e => (e.annotation_count ?? 0) > 0)
        .map(e => [e.id, e] as const),
    )
    const slots = new Map<string, { evalId: string; count: number }>()
    for (const c of heatmapData.cells) {
      if (c.eval_id && notedEvals.has(c.eval_id) && !slots.has(c.slot)) {
        const summary = notedEvals.get(c.eval_id)!
        slots.set(c.slot, {
          evalId: c.eval_id,
          count: summary.annotation_count ?? 0,
        })
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
        toolbar={<TimeRangePicker />}
        metadata={hasEvals && ev ? (
          <>
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-400">
              <span>Asset: <span className="text-slate-200">{ev.asset_snapshot.display_name ?? assetDisplayName ?? ev.asset_snapshot.name}</span></span>
              {Object.entries(ev.asset_snapshot.tags ?? {}).map(([k, v]) => (
                <span key={k} className="text-slate-500 text-xs">{k}: {v as string}</span>
              ))}
              <span className="text-xs">
                {ev.period_start.slice(0, 16).replace('T', ' ')} → {ev.period_end.slice(11, 16)}
              </span>
            </div>
            <div className="mt-1 text-xs text-slate-500">
              SLO: {(ev.slo_name && sloDisplayNames.get(ev.slo_name)) ?? ev.slo_name ?? '—'}{ev.slo_version != null && ` v${ev.slo_version}`}
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
      {evals.length > 0 && activeAction && effectiveEvalId && ev && !ev.invalidated && (
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

      {evalNames.length > 1 && (
        <EvaluationNameFilter
          names={evalNames}
          selected={selectedNames}
          onChange={setSelectedNames}
        />
      )}

      {isLoading && <p className="text-sm text-slate-400">Loading…</p>}
      {!isLoading && evals.length === 0 && (
        <p className="text-sm text-slate-400">No evaluations found in this time range.</p>
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
          ev={ev}
          effectiveEvalId={effectiveEvalId}
          notedSlots={notedSlots}
          onEvalSelect={setSelectedEvalId}
          mode={mode}
          setMode={setMode}
          explorerButton={explorerButton}
          availableGroups={availableGroups}
          counts={counts}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          tabIndicators={tabIndicators}
        />
      )}

      {/* Charts mode */}
      {!isLoading && evals.length > 0 && mode === 'chart' && (
        <AssetPanelChartView
          effectiveEvalId={effectiveEvalId}
          evals={evals}
          heatmapData={heatmapData}
          onEvalSelect={setSelectedEvalId}
          mode={mode}
          setMode={setMode}
          explorerButton={explorerButton}
        />
      )}
    </div>
  )
}
