// ui/src/features/meta_timeline/mappers.ts
//
// Sync mappers for the meta timeline feature. Run inside fetch functions
// in api.ts, once per network call. React Query cache stores domain types.

import type { components } from '@/generated/api'
import { getSpanColorIndex } from './components/spanColor'
import type {
  MetaTimelineGroup,
  MetaTimelineItem,
  MetaTimelineResponse,
  MetaTimelineSummary,
} from './domain'

type TimelineResponseDto = components['schemas']['TimelineResponse']
type TimelineGroupDto = components['schemas']['TimelineGroup']
type TimelineItemDto = components['schemas']['TimelineItem']
type TimelineSummaryDto = components['schemas']['TimelineSummaryResponse']

function dtoToGroup(dto: TimelineGroupDto): MetaTimelineGroup {
  const group: MetaTimelineGroup = {
    id: dto.id,
    content: dto.content,
  }
  if (dto.nestedGroups) {
    group.nestedGroups = dto.nestedGroups
  }
  if (dto.showNested !== undefined && dto.showNested !== null) {
    group.showNested = dto.showNested
  }
  return group
}

function dtoToItem(dto: TimelineItemDto): MetaTimelineItem {
  const colorClass = `meta-span-color-${getSpanColorIndex(dto.content)}`
  const className = dto.className ? `${dto.className} ${colorClass}` : colorClass
  return {
    id: dto.id,
    group: dto.group,
    content: dto.content,
    start: new Date(dto.start),
    end: new Date(dto.end),
    type: 'range',
    className,
    source: dto.source,
  }
}

export function dtoToMetaTimelineResponse(dto: TimelineResponseDto): MetaTimelineResponse {
  return {
    groups: dto.groups.map(dtoToGroup),
    items: dto.items.map(dtoToItem),
  }
}

export function dtoToMetaTimelineSummary(dto: TimelineSummaryDto): MetaTimelineSummary {
  return {
    itemCount: dto.itemCount,
  }
}
