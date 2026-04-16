import { describe, expect, it } from 'vitest'
import { dtoToMetaTimelineResponse, dtoToMetaTimelineSummary } from './mappers'

describe('dtoToMetaTimelineResponse', () => {
  it('converts items start/end to Date objects', () => {
    const dto = {
      groups: [
        { id: '["app"]', content: 'app', nestedGroups: ['["app","plug"]'], showNested: false },
        { id: '["app","plug"]', content: 'plug' },
      ],
      items: [
        { id: 's0', group: '["app"]', content: '1.0', start: '2026-04-01T00:00:00Z', end: '2026-04-30T00:00:00Z', type: 'range', className: 'meta-span', source: 'cicd' },
        { id: 's1', group: '["app","plug"]', content: '2.0', start: '2026-04-10T00:00:00Z', end: '2026-04-20T00:00:00Z', type: 'range', className: 'meta-span meta-span-open', source: 'deploy' },
        { id: 's2', group: '["app"]', content: '1.1', start: '2026-04-15T00:00:00Z', end: '2026-04-25T00:00:00Z', type: 'range', className: 'meta-span meta-span-closed', source: 'cicd' },
      ],
    }
    const result = dtoToMetaTimelineResponse(dto)

    // Groups pass through
    expect(result.groups).toHaveLength(2)
    expect(result.groups[0].nestedGroups).toEqual(['["app","plug"]'])
    expect(result.groups[0].showNested).toBe(false)
    expect(result.groups[1].nestedGroups).toBeUndefined()

    // Items have Date objects
    expect(result.items).toHaveLength(3)
    expect(result.items[0].start).toBeInstanceOf(Date)
    expect(result.items[0].end).toBeInstanceOf(Date)
    expect(result.items[1].className).toBe('meta-span meta-span-open')
  })

  it('handles empty input', () => {
    const result = dtoToMetaTimelineResponse({ groups: [], items: [] })
    expect(result.groups).toEqual([])
    expect(result.items).toEqual([])
  })
})

describe('dtoToMetaTimelineSummary', () => {
  it('maps itemCount', () => {
    const result = dtoToMetaTimelineSummary({ itemCount: 7 })
    expect(result.itemCount).toBe(7)
  })
})
