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

  it('parses epoch milliseconds to an absolute ISO range', () => {
    const fromEpoch = Date.UTC(2025, 1, 28, 23, 0, 0)
    const toEpoch = Date.UTC(2026, 6, 31, 21, 59, 59)
    expect(parseTimeParams(String(fromEpoch), String(toEpoch))).toEqual({
      mode: 'absolute',
      from: new Date(fromEpoch).toISOString(),
      to: new Date(toEpoch).toISOString(),
    })
  })

  it('parses an open-ended epoch range (no to)', () => {
    const fromEpoch = Date.UTC(2025, 1, 28, 23, 0, 0)
    expect(parseTimeParams(String(fromEpoch))).toEqual({
      mode: 'absolute',
      from: new Date(fromEpoch).toISOString(),
      to: undefined,
    })
  })

  it('parses a compact date-only token (YYYYMMDD)', () => {
    expect(parseTimeParams('20250228')).toEqual({
      mode: 'absolute',
      from: '2025-02-28T00:00:00.000Z',
      to: undefined,
    })
  })

  it('expands a date-only to to end-of-day', () => {
    expect(parseTimeParams('20250228', '20250425')).toEqual({
      mode: 'absolute',
      from: '2025-02-28T00:00:00.000Z',
      to: '2025-04-25T23:59:59.999Z',
    })
  })

  it('parses a compact date-time token (YYYYMMDDTHHmmss)', () => {
    expect(parseTimeParams('20250228T230000')).toEqual({
      mode: 'absolute',
      from: '2025-02-28T23:00:00.000Z',
      to: undefined,
    })
  })

  it('does not accept ISO-with-separators (Grafana parity)', () => {
    expect(parseTimeParams('2025-02-28T23:00:00.000Z')).toBeNull()
  })

  it('returns null for unparseable from', () => {
    expect(parseTimeParams('not-a-date')).toBeNull()
  })

  it('drops an unparseable to and stays open-ended', () => {
    expect(parseTimeParams('20250228', 'garbage')).toEqual({
      mode: 'absolute',
      from: '2025-02-28T00:00:00.000Z',
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

  it('reads an absolute epoch range from the URL', () => {
    const fromEpoch = Date.UTC(2026, 3, 1, 0, 0, 0)
    const toEpoch = Date.UTC(2026, 3, 25, 23, 59, 59)
    renderProvider(`/?from=${fromEpoch}&to=${toEpoch}`)
    expect(screen.getByTestId('mode')).toHaveTextContent('absolute')
    expect(screen.getByTestId('from')).toHaveTextContent(new Date(fromEpoch).toISOString())
    expect(screen.getByTestId('to')).toHaveTextContent(new Date(toEpoch).toISOString())
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

  it('writes an absolute range to the URL as epoch millis', () => {
    renderProvider('/?from=now-30d')
    fireEvent.click(screen.getByText('set-abs'))
    const search = screen.getByTestId('search').textContent ?? ''
    const fromEpoch = new Date('2026-04-01T00:00:00.000Z').getTime()
    const toEpoch = new Date('2026-04-25T23:59:59.999Z').getTime()
    expect(search).toContain(`from=${fromEpoch}`)
    expect(search).toContain(`to=${toEpoch}`)
  })

  it('mirrors a URL-supplied absolute range into localStorage (shared link survives navigation)', () => {
    const fromEpoch = Date.UTC(2026, 0, 1, 0, 0, 0)
    const toEpoch = Date.UTC(2026, 1, 1, 23, 59, 59)
    renderProvider(`/?from=${fromEpoch}&to=${toEpoch}`)
    const stored = JSON.parse(localStorage.getItem('tropek-time-range') ?? '{}')
    expect(stored.mode).toBe('absolute')
    expect(stored.from).toBe(new Date(fromEpoch).toISOString())
    expect(stored.to).toBe(new Date(toEpoch).toISOString())
  })

  it('re-seeds a bare URL from the mirrored range as epoch', () => {
    localStorage.setItem(
      'tropek-time-range',
      JSON.stringify({ mode: 'absolute', from: '2026-01-01T00:00:00.000Z', to: '2026-02-01T23:59:59.999Z' }),
    )
    renderProvider('/')
    const search = screen.getByTestId('search').textContent ?? ''
    const fromEpoch = new Date('2026-01-01T00:00:00.000Z').getTime()
    expect(search).toContain(`from=${fromEpoch}`)
  })

  it('labels an unknown preset-day URL with the actual day count', () => {
    renderProvider('/?from=now-45d')
    expect(screen.getByTestId('label')).toHaveTextContent('Last 45 days')
  })
})
