// ui/src/lib/time-range-context.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { computeFromDate, toDateInputValue, PRESETS } from './time-range-context'

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
