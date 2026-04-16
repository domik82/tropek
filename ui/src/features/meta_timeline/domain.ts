// ui/src/features/meta_timeline/domain.ts
//
// Domain types for the meta timeline feature. Hand-written in UI vocabulary.
// Components import from here (via the barrel at './index.ts'), never from
// '@/generated/api'. DTO → domain conversion lives in './mappers.ts'.

export interface MetaTimelineGroup {
  id: string
  content: string
  nestedGroups?: string[]
  showNested?: boolean
}

export interface MetaTimelineItem {
  id: string
  group: string
  content: string
  start: Date
  end: Date
  type: 'range'
  className: string
  source: string
}

export interface MetaTimelineResponse {
  groups: MetaTimelineGroup[]
  items: MetaTimelineItem[]
}

export interface MetaTimelineSummary {
  itemCount: number
}
