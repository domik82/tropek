import { describe, it, expect } from 'vitest'
import { clampFontSize } from './theme-utils'

describe('clampFontSize', () => {
  it('clamps below minimum to 12', () => {
    expect(clampFontSize(10)).toBe(12)
    expect(clampFontSize(0)).toBe(12)
  })
  it('clamps above maximum to 24', () => {
    expect(clampFontSize(26)).toBe(24)
    expect(clampFontSize(100)).toBe(24)
  })
  it('passes through values in range', () => {
    expect(clampFontSize(12)).toBe(12)
    expect(clampFontSize(14)).toBe(14)
    expect(clampFontSize(24)).toBe(24)
  })
})
