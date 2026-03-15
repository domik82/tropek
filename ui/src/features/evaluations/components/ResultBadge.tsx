// src/features/evaluations/components/ResultBadge.tsx
const BADGE_CLS: Record<string, string> = {
  pass:        'bg-[#7dc540]/20 text-[#7dc540] border border-[#7dc540]/40',
  warning:     'bg-[#e6be00]/20 text-[#e6be00] border border-[#e6be00]/40',
  fail:        'bg-[#dc172a]/20 text-[#dc172a] border border-[#dc172a]/40',
  invalidated: 'bg-slate-700/40 text-slate-400 border border-slate-600/40',
}

export function ResultBadge({ result }: { result: string }) {
  const cls = BADGE_CLS[result] ?? BADGE_CLS.pass
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wide ${cls}`}>
      {result}
    </span>
  )
}
