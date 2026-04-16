import { useEffect, useRef } from 'react'
import { DataSet } from 'vis-data/esnext'
import type {
  DataItemCollectionType,
  DataGroupCollectionType,
  TimelineTooltipOption,
} from 'vis-timeline/esnext'
import { Timeline } from 'vis-timeline/esnext'
import 'vis-timeline/styles/vis-timeline-graph2d.min.css'
import './meta-timeline.css'
import { renderSpanTooltip } from './renderSpanTooltip'
import type { MetaTimelineGroup, MetaTimelineItem } from '../domain'

// vis-timeline's type declarations define setCustomTimeMarker on the interface
// but omit it from the Timeline class. It exists at runtime.
interface TimelineWithMarker extends Timeline {
  setCustomTimeMarker(title: string, id?: string, editable?: boolean): void
}

interface Props {
  groups: MetaTimelineGroup[]
  items: MetaTimelineItem[]
  focusTime: Date
  focusLabel: string
  windowStart: Date
  windowEnd: Date
}

export function MetaTimeline({
  groups,
  items,
  focusTime,
  focusLabel,
  windowStart,
  windowEnd,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const timelineRef = useRef<TimelineWithMarker | null>(null)
  const groupsDataSetRef = useRef<DataSet<MetaTimelineGroup> | null>(null)
  const itemsDataSetRef = useRef<DataSet<MetaTimelineItem> | null>(null)

  // Effect 1: Create the Timeline once on mount.
  useEffect(() => {
    if (!containerRef.current) return

    const groupsDataSet = new DataSet<MetaTimelineGroup>(groups)
    const itemsDataSet = new DataSet<MetaTimelineItem>(items)
    groupsDataSetRef.current = groupsDataSet
    itemsDataSetRef.current = itemsDataSet

    const timeline = new Timeline(
      containerRef.current,
      itemsDataSet as unknown as DataItemCollectionType,
      groupsDataSet as unknown as DataGroupCollectionType,
      {
        orientation: 'top',
        height: 340,
        start: windowStart,
        end: windowEnd,
        min: windowStart,
        max: windowEnd,
        zoomMin: 1000 * 60 * 60,
        zoomMax: windowEnd.getTime() - windowStart.getTime(),
        editable: false,
        selectable: false,
        moveable: true,
        zoomable: true,
        showCurrentTime: false,
        showTooltips: true,
        stack: false,
        groupHeightMode: 'fixed',
        margin: { axis: 12, item: { horizontal: 0, vertical: 4 } },
        tooltip: {
          followMouse: false,
          overflowMethod: 'flip',
          delay: 250,
          // renderSpanTooltip uses our narrower TooltipItem shape, which is a
          // runtime-compatible subset of vis-timeline's TimelineItem.
          template:
            renderSpanTooltip as unknown as NonNullable<TimelineTooltipOption['template']>,
        },
      },
    ) as TimelineWithMarker

    timeline.addCustomTime(focusTime, 'focus-eval')
    timeline.setCustomTimeMarker(focusLabel, 'focus-eval', false)
    timelineRef.current = timeline

    return () => {
      timeline.destroy()
      timelineRef.current = null
      groupsDataSetRef.current = null
      itemsDataSetRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // create-once

  // Effect 2: Update data sets on prop changes.
  useEffect(() => {
    if (groupsDataSetRef.current) {
      groupsDataSetRef.current.clear()
      groupsDataSetRef.current.add(groups)
    }
    if (itemsDataSetRef.current) {
      itemsDataSetRef.current.clear()
      itemsDataSetRef.current.add(items)
    }
  }, [groups, items])

  // Effect 3: Move the focus marker if the viewed eval changes.
  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.setCustomTime(focusTime, 'focus-eval')
    }
  }, [focusTime])

  return <div ref={containerRef} className="meta-timeline-container" />
}
