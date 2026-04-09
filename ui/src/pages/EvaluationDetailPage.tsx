// src/pages/EvaluationDetailPage.tsx
import { useState, useMemo } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import { useEvaluationDetail, EvaluationSummaryCard } from '@/features/evaluations'
import type { ActionKind } from '@/features/evaluations'
import { useAssets } from '@/features/assets'
import { useSlos } from '@/features/slos'
import { EvaluationIndicatorSection } from '@/features/evaluations/components/EvaluationIndicatorSection'
import { EvaluationNotesSection, useNotesActions } from '@/features/evaluations/components/EvaluationNotesSection'
import { EvaluationActionsButton, EvaluationActionForm } from '@/features/evaluations/components/EvaluationActions'

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
    if (!ev || ev.asset_snapshot.display_name) return undefined
    return assets?.find(a => a.name === ev.asset_snapshot.name)?.display_name ?? undefined
  }, [assets, ev])
  const sloDisplayName = useMemo(() => {
    if (!ev?.slo_name) return undefined
    return slos?.find(s => s.name === ev.slo_name)?.display_name ?? undefined
  }, [slos, ev])

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
        <span className="text-foreground">{ev.evaluation_name}</span>
      </div>

      <EvaluationSummaryCard
        evaluation={ev}
        onAddNote={handleAddNote}
        assetDisplayName={assetDisplayName}
        sloDisplayName={sloDisplayName}
        actions={
          <EvaluationActionsButton
            currentResult={ev.result ?? 'error'}
            invalidated={ev.invalidated}
            activeAction={activeAction}
            onSelectAction={setActiveAction}
            onAddNote={handleAddNote}
          />
        }
      />

      {/* Action form */}
      {activeAction && (activeAction === 'restore' || !ev.invalidated) && (
        <EvaluationActionForm
          evalId={id!}
          currentResult={ev.result ?? 'error'}
          activeAction={activeAction}
          onClose={() => setActiveAction(null)}
          assetName={ev.asset_snapshot.name}
          sloName={ev.slo_name ?? ''}
          defaultFromDate={ev.period_start.slice(0, 16)}
        />
      )}

      <EvaluationNotesSection ref={notesSectionRef} evaluationId={id!} annotations={ev.annotations} />

      <EvaluationIndicatorSection evaluation={ev} assetDisplayName={assetDisplayName} sloDisplayName={sloDisplayName} />
    </div>
  )
}
