import { useMemo, useState } from 'react'
import { addDays, subDays } from 'date-fns'
import { useMetaTimeline, useMetaTimelineSummary } from '../hooks'
import { CollapsedStrip } from './CollapsedStrip'
import { MetaTimeline } from './MetaTimeline'

interface Props {
  assetId: string
  focusEval: { periodEnd: Date; id: string }
}

export function MetaTimelineSection({ assetId, focusEval }: Props) {
  const [isExpanded, setIsExpanded] = useState(false)

  const from = useMemo(() => subDays(focusEval.periodEnd, 30), [focusEval.periodEnd])
  const to = useMemo(() => addDays(focusEval.periodEnd, 7), [focusEval.periodEnd])

  const { data: summary } = useMetaTimelineSummary(assetId, from, to)

  const { data, isLoading, error } = useMetaTimeline(assetId, from, to, {
    enabled: isExpanded,
  })

  return (
    <div>
      <CollapsedStrip
        itemCount={summary?.itemCount ?? 0}
        expanded={isExpanded}
        onToggle={() => setIsExpanded((prev) => !prev)}
      />
      {isExpanded && (
        <div className="mt-2">
          {isLoading && (
            <div className="p-4 text-sm text-muted-foreground">Loading timeline…</div>
          )}
          {error && (
            <div className="p-4 text-sm text-destructive">
              Failed to load timeline: {error.message}
            </div>
          )}
          {data && data.items.length === 0 && (
            <div className="p-4 text-sm text-muted-foreground">
              No meta data recorded for this asset yet.
            </div>
          )}
          {data && data.items.length > 0 && (
            <MetaTimeline
              groups={data.groups}
              items={data.items}
              focusTime={focusEval.periodEnd}
              focusLabel="This evaluation"
              windowStart={from}
              windowEnd={to}
            />
          )}
        </div>
      )}
    </div>
  )
}
