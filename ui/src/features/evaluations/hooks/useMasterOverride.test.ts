import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useMasterOverride } from './useMasterOverride'

describe('useMasterOverride', () => {
  it('follows the master value until an override is set', () => {
    const { result } = renderHook(({ master, generation }) => useMasterOverride(master, generation), {
      initialProps: { master: true, generation: 0 },
    })
    expect(result.current[0]).toBe(true)
  })

  it('applies an override over the master value', () => {
    const { result } = renderHook(({ master, generation }) => useMasterOverride(master, generation), {
      initialProps: { master: true, generation: 0 },
    })
    act(() => result.current[1](false))
    expect(result.current[0]).toBe(false)
  })

  it('clears the override when the generation bumps (re-follows master)', () => {
    const { result, rerender } = renderHook(
      ({ master, generation }) => useMasterOverride(master, generation),
      { initialProps: { master: true, generation: 0 } },
    )
    act(() => result.current[1](false))
    expect(result.current[0]).toBe(false)
    rerender({ master: true, generation: 1 })
    expect(result.current[0]).toBe(true)
  })

  it('does not reset the override when master changes but generation does not', () => {
    const { result, rerender } = renderHook(
      ({ master, generation }) => useMasterOverride(master, generation),
      { initialProps: { master: true, generation: 0 } },
    )
    act(() => result.current[1](false))
    rerender({ master: false, generation: 0 })
    expect(result.current[0]).toBe(false) // still following the override
  })

  it('works with a string union (chart type)', () => {
    const { result } = renderHook(
      ({ master, generation }) => useMasterOverride<'line' | 'bar'>(master, generation),
      { initialProps: { master: 'line' as 'line' | 'bar', generation: 0 } },
    )
    act(() => result.current[1]('bar'))
    expect(result.current[0]).toBe('bar')
  })
})
