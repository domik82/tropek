// ui/src/lib/time-range-context.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { computeFromDate, toDateInputValue, PRESETS, parseTimeParams } from './time-range-context'

describe('computeFromDate', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-23T14:30:00Z'))
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns midnight 7 days ago for 7-day preset', () => {
    const result = computeFromDate(7)
    const d = new Date(result)
    expect(d.getHours()).toBe(0)
    expect(d.getMinutes()).toBe(0)
    expect(d.getSeconds()).toBe(0)
    expect(d.getMilliseconds()).toBe(0)
  })

  it('returns midnight 30 days ago for 30-day preset', () => {
    const result = computeFromDate(30)
    const d = new Date(result)
    expect(d.getHours()).toBe(0)
    expect(d.getMinutes()).toBe(0)
    expect(d.getDate()).toBe(21)
    expect(d.getMonth()).toBe(1) // February = 1
  })

  it('returns midnight ~6 months ago for 180-day preset', () => {
    const result = computeFromDate(180)
    const d = new Date(result)
    expect(d.getHours()).toBe(0)
    expect(d.getFullYear()).toBe(2025)
  })
})

describe('toDateInputValue', () => {
  it('formats a date as YYYY-MM-DD', () => {
    expect(toDateInputValue(new Date(2026, 2, 23))).toBe('2026-03-23')
  })

  it('zero-pads single-digit months and days', () => {
    expect(toDateInputValue(new Date(2026, 0, 5))).toBe('2026-01-05')
  })
})

describe('PRESETS', () => {
  it('contains expected preset options', () => {
    const labels = PRESETS.map(p => p.label)
    expect(labels).toEqual([
      'Last 7 days',
      'Last 14 days',
      'Last 30 days',
      'Last 60 days',
      'Last 90 days',
      'Last 6 months',
      'Last 1 year',
    ])
  })

  it('all presets have positive day values', () => {
    for (const p of PRESETS) {
      expect(p.days).toBeGreaterThan(0)
    }
  })
})

describe('parseTimeParams', () => {
  it('returns null when from is absent or empty', () => {
    expect(parseTimeParams(null)).toBeNull()
    expect(parseTimeParams('')).toBeNull()
  })

  it('parses a preset expression', () => {
    expect(parseTimeParams('now-30d')).toEqual({ mode: 'preset', days: 30 })
  })

  it('parses a full ISO absolute range', () => {
    expect(parseTimeParams('2026-04-01T00:00:00.000Z', '2026-04-25T23:59:59.999Z')).toEqual({
      mode: 'absolute',
      from: '2026-04-01T00:00:00.000Z',
      to: '2026-04-25T23:59:59.999Z',
    })
  })

  it('parses an open-ended absolute range (no to)', () => {
    expect(parseTimeParams('2026-04-01T00:00:00.000Z')).toEqual({
      mode: 'absolute',
      from: '2026-04-01T00:00:00.000Z',
      to: undefined,
    })
  })

  it('expands a date-only from to midnight UTC', () => {
    expect(parseTimeParams('2026-04-01')).toEqual({
      mode: 'absolute',
      from: '2026-04-01T00:00:00.000Z',
      to: undefined,
    })
  })

  it('expands a date-only to to end-of-day UTC', () => {
    expect(parseTimeParams('2026-04-01', '2026-04-25')).toEqual({
      mode: 'absolute',
      from: '2026-04-01T00:00:00.000Z',
      to: '2026-04-25T23:59:59.999Z',
    })
  })

  it('returns null for unparseable from', () => {
    expect(parseTimeParams('not-a-date')).toBeNull()
  })

  it('drops an unparseable to and stays open-ended', () => {
    expect(parseTimeParams('2026-04-01', 'garbage')).toEqual({
      mode: 'absolute',
      from: '2026-04-01T00:00:00.000Z',
      to: undefined,
    })
  })
})
