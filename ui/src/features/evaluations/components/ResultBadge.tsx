// src/features/evaluations/components/ResultBadge.tsx
const BADGE_CLS: Record<string, string> = {
  pass:        'bg-pass/20 text-pass border border-pass/40',
  warning:     'bg-warning/20 text-warning border border-warning/40',
  fail:        'bg-fail/20 text-fail border border-fail/40',
  invalidated: 'bg-slate-700/40 text-slate-400 border border-slate-600/40',
}

export function ResultBadge({ result }: { result: string }) {
  const cls = BADGE_CLS[result] ?? BADGE_CLS.pass
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wide ${cls}`} role="status">
      {result}
    </span>
  )
}
