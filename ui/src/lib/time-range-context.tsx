// src/lib/time-range-context.tsx
import { createContext, useContext, useState, useMemo, useCallback, type ReactNode } from 'react'

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

export function TimeRangeProvider({ children }: { children: ReactNode }) {
  const [range, setRange] = useState<StoredRange>(loadRange)

  const setDays = useCallback((d: number) => {
    const next: StoredRange = { mode: 'preset', days: d }
    setRange(next)
    saveRange(next)
  }, [])

  const setAbsoluteRange = useCallback((from: string, to: string | undefined) => {
    const next: StoredRange = { mode: 'absolute', from, to }
    setRange(next)
    saveRange(next)
  }, [])

  const preset = PRESETS.find(p => p.days === range.days) ?? PRESETS[2]

  const from = useMemo(() => {
    if (range.mode === 'absolute' && range.from) return range.from
    return computeFromDate(range.days ?? DEFAULT_DAYS)
  }, [range])

  const to = range.mode === 'absolute' ? range.to : undefined

  const label = useMemo(() => {
    if (range.mode === 'absolute' && range.from) {
      const f = range.from.slice(0, 10)
      const t = range.to ? range.to.slice(0, 10) : 'now'
      return `${f} to ${t}`
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
