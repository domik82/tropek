// src/pages/EvaluationDetailPage.tsx
import { useState, useMemo } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import { useEvaluationDetail, useInvalidateEvaluation } from '@/features/evaluations/hooks'
import { SLIBreakdownTable } from '@/features/evaluations/components/SLIBreakdownTable'
import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
import { ResultBadge } from '@/features/evaluations/components/ResultBadge'
import { EvaluationTabs, tabLabel } from '@/features/evaluations/components/EvaluationTabs'
import { AnnotationForm } from '@/features/evaluations/components/AnnotationForm'
import { RESULT_COLOUR } from '@/features/evaluations/constants'


function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export function EvaluationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const backLab = searchParams.get('lab')
  const backHref = backLab ? `/evaluations?lab=${backLab}` : '/evaluations'

  const { data: ev, isLoading } = useEvaluationDetail(id!)
  const invalidate = useInvalidateEvaluation(id!)

  const [activeTab, setActiveTab] = useState('all')
  const [showInvalidateForm, setShowInvalidateForm] = useState(false)
  const [pendingReason, setPendingReason] = useState('')

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
          ← Evaluations{backLab && <span className="text-slate-600"> ({backLab})</span>}
        </Link>
        <span>/</span>
        <span className="text-slate-200">{ev.name}</span>
      </div>

      {/* Header card */}
      <div className="bg-[#111827] border border-slate-700 rounded-xl p-5 flex flex-wrap gap-6 items-start">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold text-slate-100">{ev.name}</h1>
            <ResultBadge result={displayResult} />
            {ev.invalidated && ev.invalidation_note && (
              <span className="text-xs text-red-300 bg-red-900/30 border border-red-700/40 px-2 py-0.5 rounded">
                {ev.invalidation_note}
              </span>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-400">
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
        </div>

        {/* Score + invalidate */}
        <div className="flex flex-col items-center gap-3 shrink-0">
          <div className="text-center">
            <div className="text-4xl font-bold tabular-nums" style={{ color: RESULT_COLOUR[ev.result] ?? '#ccc' }}>
              {ev.score.toFixed(1)}%
            </div>
            <div className="text-xs text-slate-500 mt-0.5">total score</div>
          </div>
          {ev.invalidated ? (
            <span className="text-xs text-slate-500 italic">invalidated</span>
          ) : (
            <button
              onClick={() => setShowInvalidateForm(v => !v)}
              className="px-3 py-1 text-xs font-medium rounded border border-red-700/60 text-red-400 bg-red-900/20 hover:bg-red-900/40 transition-colors"
            >
              Invalidate
            </button>
          )}
        </div>
      </div>

      {/* Inline invalidate form */}
      {showInvalidateForm && !ev.invalidated && (
        <div className="bg-[#111827] border border-red-800/40 rounded-xl p-4 space-y-3">
          <p className="text-sm font-medium text-red-300">Reason for invalidation</p>
          <textarea
            value={pendingReason}
            onChange={e => setPendingReason(e.target.value)}
            placeholder="Describe why this evaluation result should be discarded…"
            rows={3}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-red-500 resize-none"
          />
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => { setShowInvalidateForm(false); setPendingReason('') }}
              className="px-3 py-1.5 text-xs rounded border border-slate-600 text-slate-400 hover:text-slate-200 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                invalidate.mutate(pendingReason, {
                  onSuccess: () => { setShowInvalidateForm(false); setPendingReason('') },
                })
              }}
              disabled={!pendingReason.trim() || invalidate.isPending}
              className="px-3 py-1.5 text-xs font-medium rounded bg-red-700 text-white hover:bg-red-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {invalidate.isPending ? 'Invalidating…' : 'Confirm invalidation'}
            </button>
          </div>
        </div>
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
