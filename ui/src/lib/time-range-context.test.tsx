// ui/src/lib/time-range-context.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { computeFromDate, toDateInputValue, PRESETS, parseTimeParams, TimeRangeProvider, useTimeRange } from './time-range-context'

describe('computeFromDate', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-23T14:30:00Z'))
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns midnight 7 days ago for 7-day preset', () => {
    const result = computeFromDate(7)
    const d = new Date(result)
    expect(d.getHours()).toBe(0)
    expect(d.getMinutes()).toBe(0)
    expect(d.getSeconds()).toBe(0)
    expect(d.getMilliseconds()).toBe(0)
  })

  it('returns midnight 30 days ago for 30-day preset', () => {
    const result = computeFromDate(30)
    const d = new Date(result)
    expect(d.getHours()).toBe(0)
    expect(d.getMinutes()).toBe(0)
    expect(d.getDate()).toBe(21)
    expect(d.getMonth()).toBe(1) // February = 1
  })

  it('returns midnight ~6 months ago for 180-day preset', () => {
    const result = computeFromDate(180)
    const d = new Date(result)
    expect(d.getHours()).toBe(0)
    expect(d.getFullYear()).toBe(2025)
  })
})

describe('toDateInputValue', () => {
  it('formats a date as YYYY-MM-DD', () => {
    expect(toDateInputValue(new Date(2026, 2, 23))).toBe('2026-03-23')
  })

  it('zero-pads single-digit months and days', () => {
    expect(toDateInputValue(new Date(2026, 0, 5))).toBe('2026-01-05')
  })
})

describe('PRESETS', () => {
  it('contains expected preset options', () => {
    const labels = PRESETS.map(p => p.label)
    expect(labels).toEqual([
      'Last 7 days',
      'Last 14 days',
      'Last 30 days',
      'Last 60 days',
      'Last 90 days',
      'Last 6 months',
      'Last 1 year',
    ])
  })

  it('all presets have positive day values', () => {
    for (const p of PRESETS) {
      expect(p.days).toBeGreaterThan(0)
    }
  })
})

describe('parseTimeParams', () => {
  it('returns null when from is absent or empty', () => {
    expect(parseTimeParams(null)).toBeNull()
    expect(parseTimeParams('')).toBeNull()
  })

  it('parses a preset expression', () => {
    expect(parseTimeParams('now-30d')).toEqual({ mode: 'preset', days: 30 })
  })

  it('parses a full ISO absolute range', () => {
    expect(parseTimeParams('2026-04-01T00:00:00.000Z', '2026-04-25T23:59:59.999Z')).toEqual({
      mode: 'absolute',
      from: '2026-04-01T00:00:00.000Z',
      to: '2026-04-25T23:59:59.999Z',
    })
  })

  it('parses an open-ended absolute range (no to)', () => {
    expect(parseTimeParams('2026-04-01T00:00:00.000Z')).toEqual({
      mode: 'absolute',
      from: '2026-04-01T00:00:00.000Z',
      to: undefined,
    })
  })

  it('expands a date-only from to midnight UTC', () => {
    expect(parseTimeParams('2026-04-01')).toEqual({
      mode: 'absolute',
      from: '2026-04-01T00:00:00.000Z',
      to: undefined,
    })
  })

  it('expands a date-only to to end-of-day UTC', () => {
    expect(parseTimeParams('2026-04-01', '2026-04-25')).toEqual({
      mode: 'absolute',
      from: '2026-04-01T00:00:00.000Z',
      to: '2026-04-25T23:59:59.999Z',
    })
  })

  it('returns null for unparseable from', () => {
    expect(parseTimeParams('not-a-date')).toBeNull()
  })

  it('drops an unparseable to and stays open-ended', () => {
    expect(parseTimeParams('2026-04-01', 'garbage')).toEqual({
      mode: 'absolute',
      from: '2026-04-01T00:00:00.000Z',
      to: undefined,
    })
  })
})

function Probe() {
  const { mode, from, to, label } = useTimeRange()
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <span data-testid="from">{from}</span>
      <span data-testid="to">{to ?? 'now'}</span>
      <span data-testid="label">{label}</span>
    </div>
  )
}

function LocationProbe() {
  const location = useLocation()
  return <span data-testid="search">{location.search}</span>
}

function SetterButtons() {
  const { setDays, setAbsoluteRange } = useTimeRange()
  return (
    <div>
      <button onClick={() => setDays(7)}>set-7d</button>
      <button onClick={() => setAbsoluteRange('2026-04-01T00:00:00.000Z', '2026-04-25T23:59:59.999Z')}>set-abs</button>
    </div>
  )
}

function renderProvider(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <TimeRangeProvider>
        <Probe />
        <LocationProbe />
        <SetterButtons />
      </TimeRangeProvider>
    </MemoryRouter>,
  )
}

describe('TimeRangeProvider URL persistence', () => {
  beforeEach(() => localStorage.clear())

  it('reads a preset from the URL', () => {
    renderProvider('/?from=now-90d')
    expect(screen.getByTestId('mode')).toHaveTextContent('preset')
    expect(screen.getByTestId('label')).toHaveTextContent('Last 90 days')
  })

  it('reads an absolute range from the URL', () => {
    renderProvider('/?from=2026-04-01T00:00:00.000Z&to=2026-04-25T23:59:59.999Z')
    expect(screen.getByTestId('mode')).toHaveTextContent('absolute')
    expect(screen.getByTestId('from')).toHaveTextContent('2026-04-01T00:00:00.000Z')
    expect(screen.getByTestId('to')).toHaveTextContent('2026-04-25T23:59:59.999Z')
  })

  it('lets the URL win over localStorage', () => {
    localStorage.setItem('tropek-time-range', JSON.stringify({ mode: 'preset', days: 7 }))
    renderProvider('/?from=now-90d')
    expect(screen.getByTestId('label')).toHaveTextContent('Last 90 days')
  })

  it('falls back to localStorage and seeds the URL when from is absent', () => {
    localStorage.setItem('tropek-time-range', JSON.stringify({ mode: 'preset', days: 14 }))
    renderProvider('/')
    expect(screen.getByTestId('label')).toHaveTextContent('Last 14 days')
    expect(screen.getByTestId('search')).toHaveTextContent('from=now-14d')
  })

  it('writes a relative preset to the URL on setDays', () => {
    renderProvider('/?from=now-30d')
    fireEvent.click(screen.getByText('set-7d'))
    const search = screen.getByTestId('search').textContent ?? ''
    expect(search).toContain('from=now-7d')
    expect(search).not.toContain('to=')
  })

  it('writes an absolute range to the URL on setAbsoluteRange', () => {
    renderProvider('/?from=now-30d')
    fireEvent.click(screen.getByText('set-abs'))
    const search = screen.getByTestId('search').textContent ?? ''
    expect(search).toContain('from=2026-04-01')
    expect(search).toContain('to=2026-04-25')
  })
})
