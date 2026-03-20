// src/pages/EvaluationDetailPage.tsx
import { useState } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import { useEvaluationDetail } from '@/features/evaluations/hooks'
import { EvaluationSummaryCard } from '@/features/evaluations/components/EvaluationSummaryCard'
import { EvaluationIndicatorSection } from '@/features/evaluations/components/EvaluationIndicatorSection'
import { EvaluationNotesSection, useNotesActions } from '@/features/evaluations/components/EvaluationNotesSection'
import { EvaluationActionsButton, EvaluationActionForm } from '@/features/evaluations/components/EvaluationActions'
import type { ActionKind } from '@/features/evaluations/types'

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

  if (isLoading) return <div className="p-6 text-slate-400">Loading…</div>
  if (!ev) return <div className="p-6 text-red-400">Evaluation not found.</div>

  return (
    <div className="p-6 space-y-6">
      {/* Breadcrumb */}
      <div className="text-sm text-slate-400 flex items-center gap-2">
        <Link to={backHref} className="hover:text-indigo-400 flex items-center gap-1">
          ← Navigator{backGroup && <span className="text-slate-600"> ({backGroup})</span>}{backAsset && <span className="text-slate-600"> ({backAsset})</span>}
        </Link>
        <span>/</span>
        <span className="text-slate-200">{ev.evaluation_name}</span>
      </div>

      <EvaluationSummaryCard
        evaluation={ev}
        onAddNote={handleAddNote}
        actions={
          <EvaluationActionsButton
            currentResult={ev.result}
            invalidated={ev.invalidated}
            activeAction={activeAction}
            onSelectAction={setActiveAction}
            onAddNote={handleAddNote}
          />
        }
      />

      {/* Action form */}
      {activeAction && !ev.invalidated && (
        <EvaluationActionForm
          evalId={id!}
          currentResult={ev.result}
          activeAction={activeAction}
          onClose={() => setActiveAction(null)}
          assetName={ev.asset_snapshot.name}
          sloName={ev.slo_name ?? ''}
          defaultFromDate={ev.period_start.slice(0, 16)}
        />
      )}

      <EvaluationNotesSection ref={notesSectionRef} evaluationId={id!} annotations={ev.annotations} />

      <EvaluationIndicatorSection evaluation={ev} />
    </div>
  )
}
