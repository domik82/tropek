// src/pages/EvaluationDetailPage.tsx
import { useState, useMemo } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import { useEvaluationDetail } from '@/features/evaluations/hooks'
import { SLIBreakdownTable } from '@/features/evaluations/components/SLIBreakdownTable'
import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
import { EvaluationHeader } from '@/features/evaluations/components/EvaluationHeader'
import { EvaluationTabs, tabLabel } from '@/features/evaluations/components/EvaluationTabs'
import { AnnotationForm } from '@/features/evaluations/components/AnnotationForm'
import { EvaluationActionsButton, EvaluationActionForm } from '@/features/evaluations/components/EvaluationActions'
import { ReEvaluateModal } from '@/features/evaluations/components/ReEvaluateModal'
import type { ActionKind } from '@/features/evaluations/components/EvaluationActions'

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
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

  const [activeTab, setActiveTab] = useState('all')
  const [activeAction, setActiveAction] = useState<ActionKind | null>(null)

  const availableGroups = useMemo(() =>
    [...new Set(ev?.indicator_results.map(i => i.tab_group).filter(Boolean) as string[])],
    [ev]
  )

  const counts = useMemo(() =>
    Object.fromEntries(
      availableGroups.map(g => [g, ev?.indicator_results.filter(i => i.tab_group === g).length ?? 0])
    ),
    [ev, availableGroups]
  )

  const resolvedTab = ['all', ...availableGroups].includes(activeTab) ? activeTab : 'all'

  const tabIndicators = useMemo(
    () => resolvedTab === 'all'
      ? (ev?.indicator_results ?? [])
      : (ev?.indicator_results.filter(ind => ind.tab_group === resolvedTab) ?? []),
    [ev, resolvedTab]
  )

  if (isLoading) return <div className="p-6 text-slate-400">Loading…</div>
  if (!ev) return <div className="p-6 text-red-400">Evaluation not found.</div>

  const displayResult = ev.invalidated ? 'invalidated' : ev.result

  return (
    <div className="p-6 space-y-6">

      {/* Breadcrumb */}
      <div className="text-sm text-slate-400 flex items-center gap-2">
        <Link to={backHref} className="hover:text-indigo-400 flex items-center gap-1">
          ← Navigator{backGroup && <span className="text-slate-600"> ({backGroup})</span>}{backAsset && <span className="text-slate-600"> ({backAsset})</span>}
        </Link>
        <span>/</span>
        <span className="text-slate-200">{ev.name}</span>
      </div>

      {/* Header card */}
      <EvaluationHeader
        title={ev.name}
        result={displayResult}
        score={ev.score}
        metadata={
          <>
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-400">
              <span>Asset: <span className="text-slate-200">{ev.asset_snapshot.name}</span></span>
              {Object.entries(ev.asset_snapshot.tags ?? {}).map(([k, v]) => (
                <span key={k} className="text-slate-500 text-xs">{k}: {v as string}</span>
              ))}
              <span className="text-xs">
                {ev.period_start.slice(0, 16).replace('T', ' ')} → {ev.period_end.slice(11, 16)}
              </span>
            </div>
            <div className="mt-1 text-xs text-slate-500">
              SLO: {ev.slo_name ?? '—'}{ev.slo_version != null && ` v${ev.slo_version}`}
              {' · '}mode: {ev.ingestion_mode}
              {ev.adapter_used && ` · adapter: ${ev.adapter_used}`}
              {ev.asset_snapshot.build_ref && ` · build: ${ev.asset_snapshot.build_ref}`}
            </div>
            {ev.invalidated && ev.invalidation_note && (
              <div className="mt-2">
                <span className="text-xs text-red-300 bg-red-900/30 border border-red-700/40 px-2 py-0.5 rounded">
                  {ev.invalidation_note}
                </span>
              </div>
            )}
            {ev.original_result && (
              <div className="mt-2 flex flex-col gap-1">
                <span className="text-xs text-amber-300 bg-amber-900/20 border border-amber-700/30 px-2 py-1 rounded inline-flex flex-wrap items-center gap-x-1.5">
                  <span className="font-medium">Status overridden</span>
                  <span className="text-amber-500">
                    {ev.original_result} → {ev.result}
                  </span>
                  {ev.override_author && (
                    <span>by <span className="text-amber-200">{ev.override_author}</span></span>
                  )}
                  {ev.override_reason && (
                    <span className="text-amber-400/80">— {ev.override_reason}</span>
                  )}
                </span>
              </div>
            )}
          </>
        }
        actions={
          <EvaluationActionsButton
            currentResult={ev.result}
            invalidated={ev.invalidated}
            activeAction={activeAction}
            onSelectAction={setActiveAction}
          />
        }
      />

      {/* Action form */}
      {activeAction === 're-evaluate' && (
        <ReEvaluateModal
          assetName={ev.asset_snapshot.name}
          sloName={ev.slo_name ?? ''}
          onClose={() => setActiveAction(null)}
        />
      )}
      {activeAction && activeAction !== 're-evaluate' && !ev.invalidated && (
        <EvaluationActionForm
          evalId={id!}
          currentResult={ev.result}
          activeAction={activeAction}
          onClose={() => setActiveAction(null)}
        />
      )}

      {/* Notes — at top, before the table */}
      <AnnotationForm evalId={id!} annotations={ev.annotations} />

      {/* SLI breakdown — tab bar + table */}
      <div id="sli-table" className="space-y-0 scroll-mt-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">SLI Breakdown</h2>
        </div>

        <EvaluationTabs
          availableGroups={availableGroups}
          allCount={ev.indicator_results.length}
          counts={counts}
          activeTab={resolvedTab}
          onTabChange={setActiveTab}
        />

        <SLIBreakdownTable
          indicators={tabIndicators}
          onIndicatorClick={(metric, tabGroup) => {
            if (resolvedTab !== 'all') setActiveTab(tabGroup)
            setTimeout(() => scrollTo(`trend-${metric}`), 50)
          }}
        />
      </div>

      {/* Trend charts */}
      <div className="space-y-4">
        <p className="text-xs text-slate-500">
          30-day trend for{' '}
          <strong className="text-slate-300">{resolvedTab === 'all' ? 'All' : tabLabel(resolvedTab)}</strong>{' '}
          metrics on <strong className="text-slate-300">{ev.asset_snapshot.name}</strong>.
          Dot colour reflects each metric's own pass/warn/fail result.
        </p>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {tabIndicators.map(ind => (
            <MetricTrendBlock key={ind.metric} evalId={id!} indicator={ind} />
          ))}
        </div>
      </div>

    </div>
  )
}
