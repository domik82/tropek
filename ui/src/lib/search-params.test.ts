import { describe, it, expect } from 'vitest'
import { withTimeParamsLast } from './search-params'

describe('withTimeParamsLast', () => {
  it('moves from/to to the end after other params', () => {
    const result = withTimeParamsLast(new URLSearchParams('from=1&to=2&group=g'))
    expect([...result.keys()]).toEqual(['group', 'from', 'to'])
    expect(result.toString()).toBe('group=g&from=1&to=2')
  })

  it('preserves the order of non-time params', () => {
    const result = withTimeParamsLast(new URLSearchParams('a=1&from=2&b=3&to=4&c=5'))
    expect([...result.keys()]).toEqual(['a', 'b', 'c', 'from', 'to'])
  })

  it('handles an open-ended range (from but no to)', () => {
    const result = withTimeParamsLast(new URLSearchParams('group=g&from=1'))
    expect([...result.keys()]).toEqual(['group', 'from'])
  })

  it('leaves params without from/to untouched in order', () => {
    const result = withTimeParamsLast(new URLSearchParams('group=g&asset=a'))
    expect([...result.keys()]).toEqual(['group', 'asset'])
  })
})
