// src/lib/time-range-context.tsx
import { createContext, useContext, useState, useMemo, type ReactNode } from 'react'

export interface TimePreset {
  label: string
  days: number
}

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
const STORAGE_KEY = 'tropek-time-range-days'

/** Compute an ISO date string for midnight N days ago. */
export function computeFromDate(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  d.setHours(0, 0, 0, 0)
  return d.toISOString()
}

interface TimeRangeCtx {
  /** Currently selected preset */
  preset: TimePreset
  /** ISO string for the "from" date (midnight, N days ago) */
  from: string
  /** Update the selected preset by day count */
  setDays: (days: number) => void
}

const Ctx = createContext<TimeRangeCtx | null>(null)

function loadDays(): number {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (!stored) return DEFAULT_DAYS
  const n = Number(stored)
  return PRESETS.some(p => p.days === n) ? n : DEFAULT_DAYS
}

export function TimeRangeProvider({ children }: { children: ReactNode }) {
  const [days, _setDays] = useState(loadDays)

  function setDays(d: number) {
    _setDays(d)
    localStorage.setItem(STORAGE_KEY, String(d))
  }

  const preset = PRESETS.find(p => p.days === days) ?? PRESETS[2] // fallback: 30d
  const from = useMemo(() => computeFromDate(days), [days])

  return (
    <Ctx.Provider value={{ preset, from, setDays }}>
      {children}
    </Ctx.Provider>
  )
}

export function useTimeRange(): TimeRangeCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useTimeRange must be used inside TimeRangeProvider')
  return ctx
}
