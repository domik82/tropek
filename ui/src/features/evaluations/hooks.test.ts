// src/features/evaluations/hooks.test.ts
import { describe, it, expect } from 'vitest'
import { toggleColumnKey } from './hooks'
import type { ColumnDef } from './types'

const col = (key: string, required = false): ColumnDef => ({ key, label: key, required })

describe('toggleColumnKey', () => {
  it('adds a key that is not yet visible', () => {
    const result = toggleColumnKey(new Set(['a']), 'b', [col('a'), col('b')])
    expect(result).toEqual(new Set(['a', 'b']))
  })

  it('removes a key that is already visible', () => {
    const result = toggleColumnKey(new Set(['a', 'b']), 'b', [col('a'), col('b')])
    expect(result).toEqual(new Set(['a']))
  })

  it('does not remove a required column', () => {
    const result = toggleColumnKey(new Set(['a', 'b']), 'a', [col('a', true), col('b')])
    expect(result).toEqual(new Set(['a', 'b']))
  })

  it('returns the same Set when toggling an unknown key', () => {
    const prev = new Set(['a'])
    const result = toggleColumnKey(prev, 'unknown', [col('a')])
    expect(result).toEqual(new Set(['a']))
  })
})
