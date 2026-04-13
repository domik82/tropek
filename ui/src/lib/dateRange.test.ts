import { describe, it, expect } from 'vitest'
import { makeDateRange, type DateRange } from './dateRange'

describe('makeDateRange', () => {
  it('wraps two ISO strings into a DateRange struct', () => {
    const range: DateRange = makeDateRange('2026-03-15T10:00:00Z', '2026-03-15T10:30:00Z')
    expect(range.from).toBe('2026-03-15T10:00:00Z')
    expect(range.to).toBe('2026-03-15T10:30:00Z')
  })
})
