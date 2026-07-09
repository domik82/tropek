// src/lib/time-range-context.tsx
import { createContext, useContext, useMemo, useCallback, useEffect, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'

export interface TimePreset {
  label: string
  days: number
}

// eslint-disable-next-line react-refresh/only-export-components
export const PRESETS: TimePreset[] = [
  { label: 'Last 7 days', days: 7 },
  { label: 'Last 14 days', days: 14 },
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 60 days', days: 60 },
  { label: 'Last 90 days', days: 90 },
  { label: 'Last 6 months', days: 180 },
  { label: 'Last 1 year', days: 365 },
]

const DEFAULT_DAYS = 30
const STORAGE_KEY = 'tropek-time-range'

/** Compute an ISO date string for midnight N days ago. */
// eslint-disable-next-line react-refresh/only-export-components
export function computeFromDate(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  d.setHours(0, 0, 0, 0)
  return d.toISOString()
}

/** Format a Date to YYYY-MM-DD for date inputs. */
// eslint-disable-next-line react-refresh/only-export-components
export function toDateInputValue(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

type RangeMode = 'preset' | 'absolute'

interface StoredRange {
  mode: RangeMode
  days?: number
  from?: string
  to?: string
}

const PRESET_PATTERN = /^now-(\d+)d$/
// Grafana absolute URL formats (packages/grafana-data, Apache-2.0): compact date, compact
// date-time, and epoch millis. We copy the format contract, not the moment.js-coupled code.
const DATE_ONLY_PATTERN = /^(\d{4})(\d{2})(\d{2})$/
const DATE_TIME_PATTERN = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$/
const EPOCH_MILLIS_PATTERN = /^\d+$/

/** Validate a constructed ISO string, returning the normalized ISO or null if the date is invalid. */
function isoOrNull(iso: string): string | null {
  const parsed = new Date(iso)
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString()
}

/**
 * Resolve one Grafana absolute time token to an ISO string, or null if unrecognized.
 * Accepts compact date-time (YYYYMMDDTHHmmss), date-only (YYYYMMDD), and epoch millis.
 * The compact date patterns are checked before the plain-digit epoch pattern so an 8-digit
 * YYYYMMDD is never mistaken for an epoch value. `endOfDay` applies only to date-only tokens.
 */
function parseAbsoluteToken(token: string, endOfDay: boolean): string | null {
  const dateTimeMatch = DATE_TIME_PATTERN.exec(token)
  if (dateTimeMatch) {
    const [, year, month, day, hour, minute, second] = dateTimeMatch
    return isoOrNull(`${year}-${month}-${day}T${hour}:${minute}:${second}.000Z`)
  }
  const dateOnlyMatch = DATE_ONLY_PATTERN.exec(token)
  if (dateOnlyMatch) {
    const [, year, month, day] = dateOnlyMatch
    return isoOrNull(endOfDay ? `${year}-${month}-${day}T23:59:59.999Z` : `${year}-${month}-${day}T00:00:00.000Z`)
  }
  if (EPOCH_MILLIS_PATTERN.test(token)) {
    const parsed = new Date(Number(token))
    if (Number.isNaN(parsed.getTime())) return null
    return parsed.toISOString()
  }
  return null
}

/**
 * Parse URL `from`/`to` search params into a StoredRange whose `from`/`to` are ISO strings.
 * Accepts Grafana's URL formats (relative `now-Nd`, epoch millis, YYYYMMDD, YYYYMMDDTHHmmss).
 * Returns null when `from` is absent or unparseable so the caller can fall back to
 * localStorage / the hardcoded default. Never throws.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function parseTimeParams(from: string | null, to?: string | null): StoredRange | null {
  if (!from) return null

  const presetMatch = PRESET_PATTERN.exec(from)
  if (presetMatch) {
    return { mode: 'preset', days: Number(presetMatch[1]) }
  }

  const fromIso = parseAbsoluteToken(from, false)
  if (!fromIso) return null

  const toIso = to ? (parseAbsoluteToken(to, true) ?? undefined) : undefined
  return { mode: 'absolute', from: fromIso, to: toIso }
}

interface TimeRangeCtx {
  mode: RangeMode
  /** Currently selected preset (only meaningful when mode === 'preset') */
  preset: TimePreset
  /** Display label for the trigger button */
  label: string
  /** ISO string for the "from" date */
  from: string
  /** ISO string for the "to" date (undefined = now) */
  to: string | undefined
  /** Select a preset by day count */
  setDays: (days: number) => void
  /** Set an absolute date range */
  setAbsoluteRange: (from: string, to: string | undefined) => void
}

const Ctx = createContext<TimeRangeCtx | null>(null)

function loadRange(): StoredRange {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) return JSON.parse(stored) as StoredRange
  } catch { /* ignore */ }
  return { mode: 'preset', days: DEFAULT_DAYS }
}

function saveRange(range: StoredRange) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(range))
}

/**
 * Serialize a StoredRange to Grafana-style URL params: presets stay relative (`now-Nd`),
 * absolute ranges become epoch-millisecond strings (no colons, so no `%3A` in the URL).
 */
function rangeToParams(range: StoredRange): { from: string; to?: string } {
  if (range.mode === 'preset') {
    return { from: `now-${range.days ?? DEFAULT_DAYS}d` }
  }
  const fromIso = range.from ?? computeFromDate(DEFAULT_DAYS)
  const fromEpoch = String(new Date(fromIso).getTime())
  const toEpoch = range.to ? String(new Date(range.to).getTime()) : undefined
  return { from: fromEpoch, to: toEpoch }
}

export function TimeRangeProvider({ children }: { children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const urlFrom = searchParams.get('from')
  const urlTo = searchParams.get('to')

  // URL is the source of truth; fall back to localStorage, then the hardcoded default.
  const range: StoredRange = useMemo(() => parseTimeParams(urlFrom, urlTo) ?? loadRange(), [urlFrom, urlTo])

  // Write a range to the URL through the one place that knows the wire format (rangeToParams).
  const writeRange = useCallback((next: StoredRange, options?: { replace?: boolean }) => {
    const params = rangeToParams(next)
    setSearchParams(prev => {
      const search = new URLSearchParams(prev)
      search.set('from', params.from)
      if (params.to) search.set('to', params.to)
      else search.delete('to')
      return search
    }, options)
  }, [setSearchParams])

  // When the URL has no `from`, seed it from the resolved fallback so the address bar reflects
  // the active range and is shareable. When a range arrives FROM the URL (e.g. a shared link),
  // mirror it into localStorage so returning to a bare path re-seeds this range, not the
  // viewer's previous one. Deps are honest: after seeding, `urlFrom` becomes set and the guard
  // short-circuits, so no loop.
  useEffect(() => {
    if (urlFrom) {
      saveRange(range)
      return
    }
    writeRange(range, { replace: true })
  }, [urlFrom, range, writeRange])

  const setDays = useCallback((days: number) => {
    const next: StoredRange = { mode: 'preset', days }
    saveRange(next)
    writeRange(next)
  }, [writeRange])

  const setAbsoluteRange = useCallback((from: string, to: string | undefined) => {
    const next: StoredRange = { mode: 'absolute', from, to }
    saveRange(next)
    writeRange(next)
  }, [writeRange])

  const preset = PRESETS.find(candidate => candidate.days === range.days) ?? PRESETS[2]

  const from = useMemo(() => {
    if (range.mode === 'absolute' && range.from) return range.from
    return computeFromDate(range.days ?? DEFAULT_DAYS)
  }, [range])

  const to = range.mode === 'absolute' ? range.to : undefined

  const label = useMemo(() => {
    if (range.mode === 'absolute' && range.from) {
      const fromLabel = range.from.slice(0, 10)
      const toLabel = range.to ? range.to.slice(0, 10) : 'now'
      return `${fromLabel} to ${toLabel}`
    }
    const days = range.days ?? DEFAULT_DAYS
    const knownPreset = PRESETS.find(candidate => candidate.days === days)
    return knownPreset ? knownPreset.label : `Last ${days} days`
  }, [range])

  return (
    <Ctx.Provider value={{ mode: range.mode, preset, label, from, to, setDays, setAbsoluteRange }}>
      {children}
    </Ctx.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTimeRange(): TimeRangeCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useTimeRange must be used inside TimeRangeProvider')
  return ctx
}
