import { describe, it, expect } from 'vitest'
import { getSpanColorIndex, META_SPAN_PALETTE_SIZE } from './spanColor'

describe('getSpanColorIndex', () => {
  it('is deterministic for the same value', () => {
    expect(getSpanColorIndex('v1.2.3')).toBe(getSpanColorIndex('v1.2.3'))
  })

  it('returns an index in [0, PALETTE_SIZE)', () => {
    for (const value of ['', 'a', 'v1.2.3', 'production', 'checkout-api', '42']) {
      const index = getSpanColorIndex(value)
      expect(index).toBeGreaterThanOrEqual(0)
      expect(index).toBeLessThan(META_SPAN_PALETTE_SIZE)
    }
  })

  it('produces at least two distinct indices across varied inputs', () => {
    const values = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'v1', 'v2']
    const indices = new Set(values.map(getSpanColorIndex))
    expect(indices.size).toBeGreaterThanOrEqual(2)
  })
})
