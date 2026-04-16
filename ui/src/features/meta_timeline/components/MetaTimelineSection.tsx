import { useMemo, useState } from 'react'
import { useMetaTimeline, useMetaTimelineSummary } from '../hooks'
import { useTimeRange } from '@/lib/time-range-context'
import { CollapsedStrip } from './CollapsedStrip'
import { MetaTimeline } from './MetaTimeline'

interface Props {
  assetId: string
  focusEval: { periodEnd: Date; id: string }
}

export function MetaTimelineSection({ assetId, focusEval }: Props) {
  const [isExpanded, setIsExpanded] = useState(false)
  const timeRange = useTimeRange()

  // Window is driven by the global TimeRangePicker so the timeline stays in
  // lockstep with the heatmap above it.
  const from = useMemo(() => new Date(timeRange.from), [timeRange.from])
  const to = useMemo(
    () => (timeRange.to ? new Date(timeRange.to) : new Date()),
    [timeRange.to],
  )

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
