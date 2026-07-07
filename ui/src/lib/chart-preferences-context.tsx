// src/lib/chart-preferences-context.tsx
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

export type ChartColumns = 1 | 2
export type ChartType = 'line' | 'bar'

const COLUMNS_KEY = 'tropek.chartColumns'
const NOTES_KEY = 'tropek.notesMaster'
const CHART_TYPE_KEY = 'tropek.chartType'

interface ChartPreferencesCtx {
  columns: ChartColumns
  setColumns: (n: ChartColumns) => void
  notesMaster: boolean
  toggleNotesMaster: () => void
  /** Bumped on each master notes flip; used by charts to clear per-chart overrides. */
  notesGeneration: number
  chartTypeMaster: ChartType
  toggleChartType: () => void
  /** Bumped on each master chart-type flip; independent of notesGeneration. */
  chartTypeGeneration: number
}

const Ctx = createContext<ChartPreferencesCtx | null>(null)

function loadColumns(): ChartColumns {
  // default: 1 chart per row (full-width, more legible); opt into 2-up explicitly
  return localStorage.getItem(COLUMNS_KEY) === '2' ? 2 : 1
}

function loadNotesMaster(): boolean {
  // default ON: anything other than the explicit string 'false' is treated as true
  return localStorage.getItem(NOTES_KEY) !== 'false'
}

function loadChartType(): ChartType {
  return localStorage.getItem(CHART_TYPE_KEY) === 'bar' ? 'bar' : 'line'
}

export function ChartPreferencesProvider({ children }: { children: ReactNode }) {
  const [columns, setColumnsState] = useState<ChartColumns>(loadColumns)
  const [notesMaster, setNotesMaster] = useState<boolean>(loadNotesMaster)
  const [notesGeneration, setNotesGeneration] = useState(0)
  const [chartTypeMaster, setChartTypeMaster] = useState<ChartType>(loadChartType)
  const [chartTypeGeneration, setChartTypeGeneration] = useState(0)

  const setColumns = useCallback((n: ChartColumns) => {
    setColumnsState(n)
    localStorage.setItem(COLUMNS_KEY, String(n))
  }, [])

  const toggleNotesMaster = useCallback(() => {
    setNotesMaster(previous => {
      const next = !previous
      localStorage.setItem(NOTES_KEY, String(next))
      return next
    })
    setNotesGeneration(generation => generation + 1)
  }, [])

  const toggleChartType = useCallback(() => {
    setChartTypeMaster(previous => {
      const next = previous === 'line' ? 'bar' : 'line'
      localStorage.setItem(CHART_TYPE_KEY, next)
      return next
    })
    setChartTypeGeneration(generation => generation + 1)
  }, [])

  return (
    <Ctx.Provider
      value={{
        columns,
        setColumns,
        notesMaster,
        toggleNotesMaster,
        notesGeneration,
        chartTypeMaster,
        toggleChartType,
        chartTypeGeneration,
      }}
    >
      {children}
    </Ctx.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useChartPreferences(): ChartPreferencesCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useChartPreferences must be used inside ChartPreferencesProvider')
  return ctx
}
