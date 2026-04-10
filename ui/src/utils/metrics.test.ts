import { describe, it, expect } from 'vitest'
import { computeChangePct } from './metrics'

describe('computeChangePct', () => {
  it('returns null when baseline is null', () => {
    expect(computeChangePct(5, null)).toBeNull()
  })

  it('returns 0 when both value and baseline are 0', () => {
    expect(computeChangePct(0, 0)).toBe(0)
  })

  it('returns +200% when going from 0 to 2', () => {
    expect(computeChangePct(2, 0)).toBe(200)
  })

  it('returns +100% when going from 0 to 1', () => {
    expect(computeChangePct(1, 0)).toBe(100)
  })

  it('returns -100% when going from 0 to -1', () => {
    expect(computeChangePct(-1, 0)).toBe(-100)
  })

  it('returns 0% when value equals baseline', () => {
    expect(computeChangePct(120, 120)).toBe(0)
  })

  it('returns +20% for a 20% increase from non-zero baseline', () => {
    expect(computeChangePct(120, 100)).toBe(20)
  })

  it('returns -20% for a 20% decrease from non-zero baseline', () => {
    expect(computeChangePct(80, 100)).toBe(-20)
  })

  it('uses absolute value of baseline as denominator (negative baseline)', () => {
    // from -100 to -80: change = +20 / 100 = +20%
    expect(computeChangePct(-80, -100)).toBe(20)
  })

  it('rounds to 2 decimal places', () => {
    expect(computeChangePct(1, 3)).toBe(-66.67)
  })
})
