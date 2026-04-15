// src/pages/EvaluationDetailPage.tsx
import { useState, useMemo } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import { useEvaluationDetail, EvaluationSummaryCard } from '@/features/evaluations'
import type { ActionKind, EvaluationDetail } from '@/features/evaluations'
import { useAssets } from '@/features/assets'
import { useSlos } from '@/features/slos'
import { EvaluationIndicatorSection } from '@/features/evaluations/components/EvaluationIndicatorSection'
import { EvaluationNotesSection, useNotesActions } from '@/features/evaluations/components/EvaluationNotesSection'
import { EvaluationActionsButton } from '@/features/evaluations/components/EvaluationActions'
import { ActionPopover } from '@/features/evaluations/components/ActionPopover'
import { OverrideForm } from '@/features/evaluations/components/actions/OverrideForm'
import { InvalidateForm } from '@/features/evaluations/components/actions/InvalidateForm'
import { RestoreForm } from '@/features/evaluations/components/actions/RestoreForm'
import { BaselineForm } from '@/features/evaluations/components/actions/BaselineForm'
import { ReEvaluateForm } from '@/features/evaluations/components/actions/ReEvaluateForm'
import { useSloScope } from '@/features/evaluations/components/actions/slo-scope/useSloScope'
import type { GroupedMetricHeatmap, HeatmapResult } from '@/features/navigator/domain'

function evaluationOutcomeToHeatmapResult(ev: EvaluationDetail): HeatmapResult {
  if (ev.invalidated) return 'invalidated'
  const outcome = ev.outcome
  if (outcome === 'pass' || outcome === 'warning' || outcome === 'fail' || outcome === 'error') {
    return outcome
  }
  return 'error'
}

// Build a one-column, one-group GroupedMetricHeatmap that represents the
// single EvaluationDetail the page is viewing. Enough shape for useSloScope
// to surface a single SLO row in the picker.
function buildSingleSloScopeHeatmap(ev: EvaluationDetail): GroupedMetricHeatmap {
  const result = evaluationOutcomeToHeatmapResult(ev)
  const sloName = ev.sloName ?? ''
  return {
    assetName: ev.assetSnapshot.name,
    columns: [
      {
        evaluationId: ev.evaluationId,
        periodStart: ev.period.from,
        periodEnd: ev.period.to,
        evalName: ev.evaluationName,
      },
    ],
    groups: [
      {
        sloName,
        sloDisplayName: null,
        metrics: [],
        cells: [
          {
            evaluationId: ev.evaluationId,
            sloEvaluationId: ev.id,
            periodStart: ev.period.from,
            metric: '',
            displayName: '',
            result,
            score: ev.score ?? 0,
            value: null,
            comparedValue: null,
            changeRelativePct: null,
            weight: 1,
            keySli: false,
            passTargets: null,
            warningTargets: null,
            tabGroup: null,
            aggregation: null,
          },
        ],
        summary: [
          {
            evaluationId: ev.evaluationId,
            periodStart: ev.period.from,
            result,
            score: ev.score ?? 0,
            totalScorePassThreshold: null,
            totalScoreWarningThreshold: null,
            sliMetadata: null,
            invalidationNote: ev.invalidationNote,
          },
        ],
      },
    ],
    composite: [],
  }
}

export function EvaluationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const backGroup = searchParams.get('group_name')
  const backAsset = searchParams.get('asset_name')
  const backHref = backAsset
    ? `/navigator?asset=${encodeURIComponent(backAsset)}`
    : backGroup
      ? `/navigator?group=${encodeURIComponent(backGroup)}`
      : '/navigator'

  const { data: ev, isLoading } = useEvaluationDetail(id!)
  const [activeAction, setActiveAction] = useState<ActionKind | null>(null)
  const { notesSectionRef, handleAddNote } = useNotesActions()

  // Live display name lookups
  const { data: assets } = useAssets()
  const { data: slos } = useSlos()
  const assetDisplayName = useMemo(() => {
    if (!ev || ev.assetSnapshot.displayName) return undefined
    return assets?.find(a => a.name === ev.assetSnapshot.name)?.displayName ?? undefined
  }, [assets, ev])
  const sloDisplayName = useMemo(() => {
    if (!ev?.sloName) return undefined
    return slos?.find(s => s.name === ev.sloName)?.displayName ?? undefined
  }, [slos, ev])

  // Detail page is single-SLO by URL: synthesize a minimal one-group
  // GroupedMetricHeatmap so useSloScope has the shape it expects. The
  // picker will list exactly one SLO — the one this detail page is for.
  const syntheticHeatmap = useMemo<GroupedMetricHeatmap | undefined>(() => {
    if (!ev || !ev.sloName) return undefined
    return buildSingleSloScopeHeatmap(ev)
  }, [ev])

  const scope = useSloScope({
    heatmapData: syntheticHeatmap,
    columnEvalId: ev?.evaluationId,
    initialMode: ev?.sloName ? { singleSlo: ev.sloName } : 'all',
  })

  if (isLoading) return <div className="p-6 text-muted-foreground">Loading…</div>
  if (!ev) return <div className="p-6 text-destructive-form-text">Evaluation not found.</div>

  return (
    <div className="p-6 space-y-6">
      {/* Breadcrumb */}
      <div className="text-sm text-muted-foreground flex items-center gap-2">
        <Link to={backHref} className="hover:text-link-hover flex items-center gap-1">
          ← Navigator{backGroup && <span className="text-muted-foreground/60"> ({backGroup})</span>}{backAsset && <span className="text-muted-foreground/60"> ({backAsset})</span>}
        </Link>
        <span>/</span>
        <span className="text-foreground">{ev.evaluationName}</span>
      </div>

      <EvaluationSummaryCard
        evaluation={ev}
        onAddNote={handleAddNote}
        assetDisplayName={assetDisplayName}
        sloDisplayName={sloDisplayName}
        actions={
          <div className='relative'>
            <EvaluationActionsButton
              currentResult={ev.outcome ?? 'error'}
              allRowsInvalidated={ev.invalidated}
              noRowsInvalidated={!ev.invalidated}
              activeAction={activeAction}
              onSelectAction={setActiveAction}
              onAddNote={handleAddNote}
            />
            <ActionPopover open={activeAction !== null} onClose={() => setActiveAction(null)}>
              {activeAction === 'override' && (
                <OverrideForm
                  scope={scope}
                  columnEvalId={ev.evaluationId}
                  onComplete={() => setActiveAction(null)}
                />
              )}
              {activeAction === 'invalidate' && (
                <InvalidateForm
                  scope={scope}
                  columnEvalId={ev.evaluationId}
                  onComplete={() => setActiveAction(null)}
                />
              )}
              {activeAction === 'restore' && (
                <RestoreForm
                  scope={scope}
                  columnEvalId={ev.evaluationId}
                  onComplete={() => setActiveAction(null)}
                />
              )}
              {activeAction === 'baseline' && (
                <BaselineForm
                  scope={scope}
                  columnEvalId={ev.evaluationId}
                  onComplete={() => setActiveAction(null)}
                />
              )}
              {activeAction === 're-evaluate' && (
                <ReEvaluateForm
                  scope={scope}
                  columnEvalId={ev.evaluationId}
                  assetName={ev.assetSnapshot.name}
                  defaultFromDate={ev.period.from.slice(0, 16)}
                  onComplete={() => setActiveAction(null)}
                />
              )}
            </ActionPopover>
          </div>
        }
      />

      <EvaluationNotesSection ref={notesSectionRef} runId={ev.evaluationId} annotations={ev.annotations} />

      <EvaluationIndicatorSection evaluation={ev} assetDisplayName={assetDisplayName} sloDisplayName={sloDisplayName} />
    </div>
  )
}
