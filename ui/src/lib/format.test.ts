// src/lib/format.test.ts
import { describe, it, expect } from 'vitest'
import { fmt, fmtPct, fmtSlot, fmtDateTime, fmtDate } from './format'

describe('fmt', () => {
  it('returns em-dash for null', () => expect(fmt(null)).toBe('—'))
  it('returns em-dash for undefined', () => expect(fmt(undefined as unknown as null)).toBe('—'))
  it('formats integer', () => expect(fmt(42)).toBe('42.00'))
  it('formats float', () => expect(fmt(3.14159)).toBe('3.14'))
  it('formats zero', () => expect(fmt(0)).toBe('0'))
  it('formats negative', () => expect(fmt(-5.5)).toBe('-5.50'))
  it('preserves precision for small values', () => expect(fmt(0.000023)).toBe('0.000023'))
  it('preserves precision for very small values', () => expect(fmt(0.0001)).toBe('0.0001'))
  it('uses 2 decimals for values >= 0.01', () => expect(fmt(0.42)).toBe('0.42'))
})

describe('fmtPct', () => {
  it('returns em-dash for null', () => expect(fmtPct(null)).toBe('—'))
  it('appends percent sign', () => expect(fmtPct(99.9)).toBe('99.9%'))
  it('formats to one decimal', () => expect(fmtPct(0.123)).toBe('0.1%'))
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
