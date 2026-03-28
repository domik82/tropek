import { getConfig } from '@/lib/config'

interface Props {
  total: number
}

export function TruncationWarning({ total }: Props) {
  const max = getConfig().maxEvaluations
  return (
    <div className="rounded-md border border-amber-600/40 bg-amber-950/30 px-4 py-2 text-sm text-amber-400">
      Showing {max.toLocaleString()} of {total.toLocaleString()} evaluations.
      Narrow the time range or filter by evaluation name to see all results.
    </div>
  )
}
