// ui/src/features/evaluations/components/EvaluationSummaryCard.tsx
import { EvaluationHeader } from './EvaluationHeader'
import { NoteIconButton } from './EvaluationActions'
import type { EvaluationDetail } from '../domain'

interface Props {
  evaluation: EvaluationDetail
  onAddNote?: () => void
  actions?: React.ReactNode
  /** Fallback display name for the asset (when snapshot lacks displayName). */
  assetDisplayName?: string
  /** Fallback display name for the SLO. */
  sloDisplayName?: string
}

export function EvaluationSummaryCard({ evaluation: ev, onAddNote, actions, assetDisplayName, sloDisplayName }: Props) {
  return (
    <EvaluationHeader
      title={ev.evaluationName}
      result={ev.outcome}
      score={ev.score ?? undefined}
      passPct={ev.totalScorePassThreshold}
      warningPct={ev.totalScoreWarningThreshold}
      noteButton={
        onAddNote && !ev.invalidated ? (
          <NoteIconButton onClick={onAddNote} annotationCount={ev.annotations.length} />
        ) : undefined
      }
      metadata={
        <>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
            <span>Asset: <span className="text-foreground">{ev.assetSnapshot.displayName ?? assetDisplayName ?? ev.assetSnapshot.name}</span></span>
            {Object.entries(ev.assetSnapshot.tags ?? {}).map(([k, v]) => (
              <span key={k} className="text-muted-foreground text-xs">{k}: {v as string}</span>
            ))}
            <span className="text-xs">
              {ev.period.from.slice(0, 16).replace('T', ' ')} → {ev.period.to.slice(11, 16)}
            </span>
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            SLO: {sloDisplayName ?? ev.sloName ?? '—'}{ev.sloVersion != null && ` v${ev.sloVersion}`}
            {' · '}mode: {ev.ingestionMode}
            {ev.adapterUsed && ` · adapter: ${ev.adapterUsed}`}
            {ev.assetSnapshot.buildRef && ` · build: ${ev.assetSnapshot.buildRef}`}
          </div>
          {ev.invalidated && ev.invalidationNote && (
            <div className="mt-2">
              <span className="text-xs text-destructive-form-text bg-destructive-form-bg border border-destructive-form-border px-2 py-1 rounded inline-flex flex-wrap items-center gap-x-1.5">
                <span className="font-medium">Invalidated</span>
                <span className="text-destructive-form-text/80">— {ev.invalidationNote}</span>
              </span>
            </div>
          )}
          {ev.originalOutcome && ev.overrideAuthor && (
            <div className="mt-2 flex flex-col gap-1">
              <span className="text-xs text-amber-300 bg-amber-900/20 border border-amber-700/30 px-2 py-1 rounded inline-flex flex-wrap items-center gap-x-1.5">
                <span className="font-medium">Status overridden</span>
                <span className="text-amber-500">
                  {ev.originalOutcome} → {ev.outcome}
                </span>
                <span>by <span className="text-amber-200">{ev.overrideAuthor}</span></span>
                {ev.overrideReason && (
                  <span className="text-amber-400/80">— {ev.overrideReason}</span>
                )}
              </span>
            </div>
          )}
          {ev.originalOutcome && !ev.overrideAuthor && (
            <div className="mt-2 flex flex-col gap-1">
              <span className="text-xs text-entity-sli bg-entity-sli/10 border border-entity-sli/30 px-2 py-1 rounded inline-flex flex-wrap items-center gap-x-1.5">
                <span className="font-medium">Re-evaluated</span>
                <span className="text-entity-sli">
                  {ev.originalOutcome} → {ev.outcome}
                </span>
                {ev.originalScore != null && (
                  <span className="text-entity-sli/80">
                    ({ev.originalScore.toFixed(1)} → {ev.score?.toFixed(1) ?? '—'})
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
