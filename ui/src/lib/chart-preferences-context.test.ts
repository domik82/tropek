import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { ChartPreferencesProvider, useChartPreferences } from './chart-preferences-context'

function useCtx() {
  return useChartPreferences()
}

describe('chart-preferences-context', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('defaults to 1 column, notes on, line charts', () => {
    const { result } = renderHook(useCtx, { wrapper: ChartPreferencesProvider })
    expect(result.current.columns).toBe(1)
    expect(result.current.notesMaster).toBe(true)
    expect(result.current.chartTypeMaster).toBe('line')
  })

  it('persists columns to localStorage', () => {
    const { result } = renderHook(useCtx, { wrapper: ChartPreferencesProvider })
    act(() => result.current.setColumns(2))
    expect(result.current.columns).toBe(2)
    expect(localStorage.getItem('tropek.chartColumns')).toBe('2')
  })

  it('reads persisted columns on mount', () => {
    localStorage.setItem('tropek.chartColumns', '2')
    const { result } = renderHook(useCtx, { wrapper: ChartPreferencesProvider })
    expect(result.current.columns).toBe(2)
  })

  it('toggles notesMaster, persists it, and bumps notesGeneration', () => {
    const { result } = renderHook(useCtx, { wrapper: ChartPreferencesProvider })
    const before = result.current.notesGeneration
    act(() => result.current.toggleNotesMaster())
    expect(result.current.notesMaster).toBe(false)
    expect(localStorage.getItem('tropek.notesMaster')).toBe('false')
    expect(result.current.notesGeneration).toBe(before + 1)
  })

  it('toggles chartTypeMaster, persists it, and bumps chartTypeGeneration independently', () => {
    const { result } = renderHook(useCtx, { wrapper: ChartPreferencesProvider })
    const notesGenBefore = result.current.notesGeneration
    act(() => result.current.toggleChartType())
    expect(result.current.chartTypeMaster).toBe('bar')
    expect(localStorage.getItem('tropek.chartType')).toBe('bar')
    expect(result.current.chartTypeGeneration).toBe(1)
    // toggling chart type must NOT bump the notes generation
    expect(result.current.notesGeneration).toBe(notesGenBefore)
  })

  it('throws when used outside the provider', () => {
    expect(() => renderHook(useCtx)).toThrow('useChartPreferences must be used inside ChartPreferencesProvider')
  })
})
