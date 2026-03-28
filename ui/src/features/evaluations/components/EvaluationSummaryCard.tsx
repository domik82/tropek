// ui/src/features/evaluations/components/EvaluationSummaryCard.tsx
import { EvaluationHeader } from './EvaluationHeader'
import { NoteIconButton } from './EvaluationActions'
import type { EvaluationDetail } from '../types'

interface Props {
  evaluation: EvaluationDetail
  onAddNote?: () => void
  actions?: React.ReactNode
  /** Fallback display name for the asset (when snapshot lacks display_name). */
  assetDisplayName?: string
  /** Fallback display name for the SLO. */
  sloDisplayName?: string
}

export function EvaluationSummaryCard({ evaluation: ev, onAddNote, actions, assetDisplayName, sloDisplayName }: Props) {
  const displayResult = ev.invalidated ? 'invalidated' : ev.result

  return (
    <EvaluationHeader
      title={ev.evaluation_name}
      result={displayResult}
      score={ev.score}
      passPct={ev.total_score_pass_pct}
      warningPct={ev.total_score_warning_pct}
      noteButton={
        onAddNote && !ev.invalidated ? (
          <NoteIconButton onClick={onAddNote} annotationCount={ev.annotations.length} />
        ) : undefined
      }
      metadata={
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
            SLO: {sloDisplayName ?? ev.slo_name ?? '—'}{ev.slo_version != null && ` v${ev.slo_version}`}
            {' · '}mode: {ev.ingestion_mode}
            {ev.adapter_used && ` · adapter: ${ev.adapter_used}`}
            {ev.asset_snapshot.build_ref && ` · build: ${ev.asset_snapshot.build_ref}`}
          </div>
          {ev.invalidated && ev.invalidation_note && (
            <div className="mt-2">
              <span className="text-xs text-red-300 bg-red-900/30 border border-red-700/40 px-2 py-1 rounded inline-flex flex-wrap items-center gap-x-1.5">
                <span className="font-medium">Invalidated</span>
                <span className="text-red-400/80">— {ev.invalidation_note}</span>
              </span>
            </div>
          )}
          {ev.original_result && ev.override_author && (
            <div className="mt-2 flex flex-col gap-1">
              <span className="text-xs text-amber-300 bg-amber-900/20 border border-amber-700/30 px-2 py-1 rounded inline-flex flex-wrap items-center gap-x-1.5">
                <span className="font-medium">Status overridden</span>
                <span className="text-amber-500">
                  {ev.original_result} → {ev.result}
                </span>
                <span>by <span className="text-amber-200">{ev.override_author}</span></span>
                {ev.override_reason && (
                  <span className="text-amber-400/80">— {ev.override_reason}</span>
                )}
              </span>
            </div>
          )}
          {ev.original_result && !ev.override_author && (
            <div className="mt-2 flex flex-col gap-1">
              <span className="text-xs text-purple-300 bg-purple-900/20 border border-purple-700/30 px-2 py-1 rounded inline-flex flex-wrap items-center gap-x-1.5">
                <span className="font-medium">Re-evaluated</span>
                <span className="text-purple-400">
                  {ev.original_result} → {ev.result}
                </span>
                {ev.original_score != null && (
                  <span className="text-purple-500">
                    ({ev.original_score.toFixed(1)} → {ev.score.toFixed(1)})
                  </span>
                )}
              </span>
            </div>
          )}
        </>
      }
      actions={actions}
    />
  )
}
