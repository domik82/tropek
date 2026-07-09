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
const DATE_ONLY_PATTERN = /^\d{4}-\d{2}-\d{2}$/

/** Normalize one date token (full ISO or bare YYYY-MM-DD) to an ISO string, or null if invalid. */
function parseDateToken(token: string, endOfDay: boolean): string | null {
  if (DATE_ONLY_PATTERN.test(token)) {
    return endOfDay ? `${token}T23:59:59.999Z` : `${token}T00:00:00.000Z`
  }
  const parsed = new Date(token)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed.toISOString()
}

/**
 * Parse URL `from`/`to` search params into a StoredRange.
 * Returns null when `from` is absent or unparseable so the caller can fall back
 * to localStorage / the hardcoded default. Never throws.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function parseTimeParams(from: string | null, to?: string | null): StoredRange | null {
  if (!from) return null

  const presetMatch = PRESET_PATTERN.exec(from)
  if (presetMatch) {
    return { mode: 'preset', days: Number(presetMatch[1]) }
  }

  const fromIso = parseDateToken(from, false)
  if (!fromIso) return null

  const toIso = to ? parseDateToken(to, true) : null
  return { mode: 'absolute', from: fromIso, to: toIso ?? undefined }
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

/** Serialize a StoredRange to the URL params the provider writes. */
function rangeToParams(range: StoredRange): { from: string; to?: string } {
  if (range.mode === 'preset') {
    return { from: `now-${range.days ?? DEFAULT_DAYS}d` }
  }
  return { from: range.from ?? computeFromDate(DEFAULT_DAYS), to: range.to }
}

export function TimeRangeProvider({ children }: { children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const urlFrom = searchParams.get('from')
  const urlTo = searchParams.get('to')

  // URL is the source of truth; fall back to localStorage, then the hardcoded default.
  const range: StoredRange = useMemo(() => parseTimeParams(urlFrom, urlTo) ?? loadRange(), [urlFrom, urlTo])

  // When the URL has no `from`, seed it from the resolved fallback so the address bar
  // reflects the active range and is shareable. `replace` avoids a back-button trap.
  // Deps are honest: after seeding, `urlFrom` becomes set and the guard short-circuits,
  // so no loop; returning to a bare `/navigator` correctly re-seeds.
  useEffect(() => {
    if (urlFrom) return
    const params = rangeToParams(loadRange())
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.set('from', params.from)
      if (params.to) next.set('to', params.to)
      else next.delete('to')
      return next
    }, { replace: true })
  }, [urlFrom, setSearchParams])

  const setDays = useCallback((days: number) => {
    saveRange({ mode: 'preset', days })
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.set('from', `now-${days}d`)
      next.delete('to')
      return next
    })
  }, [setSearchParams])

  const setAbsoluteRange = useCallback((from: string, to: string | undefined) => {
    saveRange({ mode: 'absolute', from, to })
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.set('from', from)
      if (to) next.set('to', to)
      else next.delete('to')
      return next
    })
  }, [setSearchParams])

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
    return preset.label
  }, [range, preset])

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
