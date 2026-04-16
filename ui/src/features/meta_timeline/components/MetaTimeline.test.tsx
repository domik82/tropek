import { cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MetaTimeline } from './MetaTimeline'

// Stub the vis-timeline and vis-data modules.
// vi.fn() arrow mocks are not valid constructors — use function expressions.
const destroySpy = vi.fn()
const addCustomTimeSpy = vi.fn()
const setCustomTimeSpy = vi.fn()
const setCustomTimeMarkerSpy = vi.fn()

const dataSetClearSpy = vi.fn()
const dataSetAddSpy = vi.fn()

vi.mock('vis-data/esnext', () => ({
  DataSet: vi.fn().mockImplementation(function () {
    return { clear: dataSetClearSpy, add: dataSetAddSpy }
  }),
}))

vi.mock('vis-timeline/esnext', () => ({
  Timeline: vi.fn().mockImplementation(function () {
    return {
      destroy: destroySpy,
      addCustomTime: addCustomTimeSpy,
      setCustomTime: setCustomTimeSpy,
      setCustomTimeMarker: setCustomTimeMarkerSpy,
    }
  }),
}))

// Stub CSS imports
vi.mock('vis-timeline/styles/vis-timeline-graph2d.min.css', () => ({}))
vi.mock('./meta-timeline.css', () => ({}))

const defaultProps = {
  groups: [{ id: '["app"]', content: 'app' }],
  items: [
    {
      id: 's0',
      group: '["app"]',
      content: '1.0',
      start: new Date('2026-04-01'),
      end: new Date('2026-04-30'),
      type: 'range' as const,
      className: 'meta-span',
      source: 'cicd',
    },
  ],
  focusTime: new Date('2026-04-16'),
  focusLabel: 'eval-1',
  windowStart: new Date('2026-03-01'),
  windowEnd: new Date('2026-05-01'),
}

describe('MetaTimeline', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    cleanup()
  })

  it('renders a container div with meta-timeline-container class', () => {
    const { container } = render(<MetaTimeline {...defaultProps} />)
    expect(container.querySelector('.meta-timeline-container')).not.toBeNull()
  })

  it('does not throw when re-rendered with different items', () => {
    const { rerender } = render(<MetaTimeline {...defaultProps} />)
    expect(() =>
      rerender(
        <MetaTimeline
          {...defaultProps}
          items={[
            ...defaultProps.items,
            {
              id: 's1',
              group: '["app"]',
              content: '2.0',
              start: new Date('2026-04-10'),
              end: new Date('2026-04-20'),
              type: 'range' as const,
              className: 'meta-span',
              source: 'cicd',
            },
          ]}
        />,
      ),
    ).not.toThrow()
  })

  it('calls destroy on unmount', () => {
    const { unmount } = render(<MetaTimeline {...defaultProps} />)
    unmount()
    expect(destroySpy).toHaveBeenCalledOnce()
  })

  // §10.3 case 3: "Do NOT assert pixel-level rendering. Add an explicit
  // comment citing §10.3 case 3 explaining why."
  // vis-timeline renders into the DOM imperatively, and happy-dom cannot
  // faithfully reproduce its behavior. All assertions above verify the
  // wrapper lifecycle (mount, data update, unmount) via stubs, not visual output.
})
