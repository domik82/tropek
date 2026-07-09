// src/lib/format.test.ts
import { describe, it, expect } from 'vitest'
import { fmt, fmtPct, fmtSlot, fmtDateTime, fmtDate, formatChangePointPct } from './format'

describe('fmt', () => {
  it('returns em-dash for null', () => expect(fmt(null)).toBe('—'))
  it('returns em-dash for undefined', () => expect(fmt(undefined as unknown as null)).toBe('—'))
  it('formats integer', () => expect(fmt(42)).toBe('42.00'))
  it('formats float', () => expect(fmt(3.14159)).toBe('3.14'))
  it('formats zero', () => expect(fmt(0)).toBe('0'))
  it('formats negative', () => expect(fmt(-5.5)).toBe('-5.50'))
  it('formats millions', () => expect(fmt(4620532)).toBe('4.62M'))
  it('formats negative millions', () => expect(fmt(-4620532)).toBe('-4.62M'))
  it('formats thousands', () => expect(fmt(12345)).toBe('12.35K'))
  it('formats negative thousands', () => expect(fmt(-1500)).toBe('-1.50K'))
  it('preserves precision for small values', () => expect(fmt(0.000023)).toBe('0.000023'))
  it('preserves precision for very small values', () => expect(fmt(0.0001)).toBe('0.0001'))
  it('uses 2 decimals for values >= 0.01', () => expect(fmt(0.42)).toBe('0.42'))
})

describe('fmtPct', () => {
  it('returns em-dash for null', () => expect(fmtPct(null)).toBe('—'))
  it('appends percent sign', () => expect(fmtPct(99.9)).toBe('99.9%'))
  it('formats to one decimal', () => expect(fmtPct(0.123)).toBe('0.1%'))
})

describe('formatChangePointPct', () => {
  it('formats a positive pct with a leading plus sign, no absolute', () => {
    expect(formatChangePointPct(15.7, null, null)).toBe('+15.7%')
  })
  it('formats a negative pct without an extra sign, no absolute', () => {
    expect(formatChangePointPct(-2.9, null, null)).toBe('-2.9%')
  })
  it('rounds to one decimal place', () => {
    expect(formatChangePointPct(15.749, null, null)).toBe('+15.7%')
  })
  it('returns "appeared" when transition is appeared, ignoring pct, no absolute', () => {
    expect(formatChangePointPct(null, 'appeared', null)).toBe('appeared')
  })
  it('returns "vanished" when transition is vanished, ignoring pct, no absolute', () => {
    expect(formatChangePointPct(null, 'vanished', null)).toBe('vanished')
  })
  it('returns em-dash when pct, transition, and absolute are all null', () => {
    expect(formatChangePointPct(null, null, null)).toBe('—')
  })
  it('formats zero without a leading plus sign', () => {
    expect(formatChangePointPct(0, null, null)).toBe('0.0%')
  })
  it('appends the absolute change for a transition', () => {
    expect(formatChangePointPct(null, 'appeared', 500)).toBe('appeared, +500.00')
  })
  it('appends a negative compact absolute change for a transition', () => {
    expect(formatChangePointPct(null, 'vanished', -13_300_000)).toBe('vanished, -13.30M')
  })
  it('appends the absolute change for a non-transition point', () => {
    expect(formatChangePointPct(15.7, null, 1_800_000)).toBe('+15.7%, +1.80M')
  })
  it('falls back to percent-only when absolute is null', () => {
    expect(formatChangePointPct(15.7, null, null)).toBe('+15.7%')
  })
  it('falls back to word-only for a transition when absolute is null', () => {
    expect(formatChangePointPct(null, 'appeared', null)).toBe('appeared')
  })
})

describe('fmtSlot', () => {
  it('formats ISO timestamp to MM-DD HH:MM', () => {
    expect(fmtSlot('2026-03-14T06:00:00Z')).toBe('03-14 06:00')
  })
  it('returns em-dash for empty string', () => {
    expect(fmtSlot('')).toBe('—')
  })
})

describe('fmtDateTime', () => {
  it('formats ISO timestamp to YYYY-MM-DD HH:MM', () => {
    expect(fmtDateTime('2026-03-14T06:00:00Z')).toBe('2026-03-14 06:00')
  })
  it('returns em-dash for empty string', () => {
    expect(fmtDateTime('')).toBe('—')
  })
})

describe('fmtDate', () => {
  it('formats ISO to YYYY-MM-DD', () => {
    expect(fmtDate('2026-03-14T06:00:00Z')).toBe('2026-03-14')
  })
  it('returns em-dash for empty string', () => {
    expect(fmtDate('')).toBe('—')
  })
})
