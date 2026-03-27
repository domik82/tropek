// ui/src/components/TimeRangePicker.tsx
import { useState } from 'react'
import { Calendar as CalendarIcon, ChevronDown } from 'lucide-react'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { Calendar } from '@/components/ui/calendar'
import { useTimeRange, PRESETS, toDateInputValue } from '@/lib/time-range-context'

const SANS = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

export function TimeRangePicker() {
  const { label, mode, preset, setDays, setAbsoluteRange } = useTimeRange()
  const [open, setOpen] = useState(false)

  // Which date field is being edited: null = show presets, 'from'/'to' = show calendar
  const [editing, setEditing] = useState<'from' | 'to' | null>(null)

  const [fromDate, setFromDate] = useState<Date | undefined>(() => {
    const d = new Date()
    d.setDate(d.getDate() - 30)
    return d
  })
  const [toDate, setToDate] = useState<Date | undefined>(undefined)

  function handlePreset(days: number) {
    setDays(days)
    setEditing(null)
    setOpen(false)
  }

  function handleApply() {
    if (!fromDate) return
    const fromIso = new Date(
      fromDate.getFullYear(), fromDate.getMonth(), fromDate.getDate()
    ).toISOString()
    const toIso = toDate
      ? new Date(
          toDate.getFullYear(), toDate.getMonth(), toDate.getDate(), 23, 59, 59
        ).toISOString()
      : undefined
    setAbsoluteRange(fromIso, toIso)
    setEditing(null)
    setOpen(false)
  }

  function handleFromSelect(day: Date | undefined) {
    if (day) {
      setFromDate(day)
      setEditing(null)
    }
  }

  function handleToSelect(day: Date | undefined) {
    if (day) {
      setToDate(day)
      setEditing(null)
    }
  }

  return (
    <Popover open={open} onOpenChange={(next) => { setOpen(next); if (!next) setEditing(null) }}>
      <PopoverTrigger
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border border-border bg-popover text-foreground hover:bg-muted transition-colors"
        style={{ fontFamily: SANS }}
      >
        <CalendarIcon size={14} className="text-muted-foreground" />
        {label}
        <ChevronDown size={12} className="text-muted-foreground" />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-auto p-0" style={{ fontFamily: SANS }}>
        <div className="flex">
          {/* Left — absolute date range */}
          <div className="p-4 border-r border-border" style={{ width: 230 }}>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              Absolute time range
            </h3>

            <label className="block text-xs text-muted-foreground mb-1">From</label>
            <button
              type="button"
              onClick={() => setEditing(editing === 'from' ? null : 'from')}
              className={`w-full flex items-center gap-2 px-2 py-1.5 text-xs rounded border bg-background text-foreground text-left mb-1 transition-colors ${
                editing === 'from' ? 'border-primary' : 'border-border'
              }`}
            >
              <CalendarIcon size={12} className="text-muted-foreground shrink-0" />
              {fromDate ? toDateInputValue(fromDate) : 'Select date'}
            </button>

            {editing === 'from' && (
              <div className="mb-2">
                <Calendar
                  mode="single"
                  selected={fromDate}
                  onSelect={handleFromSelect}
                  defaultMonth={fromDate}
                />
              </div>
            )}

            <label className="block text-xs text-muted-foreground mb-1 mt-2">To</label>
            <button
              type="button"
              onClick={() => setEditing(editing === 'to' ? null : 'to')}
              className={`w-full flex items-center gap-2 px-2 py-1.5 text-xs rounded border bg-background text-foreground text-left mb-1 transition-colors ${
                editing === 'to' ? 'border-primary' : 'border-border'
              }`}
            >
              <CalendarIcon size={12} className="text-muted-foreground shrink-0" />
              {toDate ? toDateInputValue(toDate) : 'now'}
            </button>

            {editing === 'to' && (
              <div className="mb-2">
                <Calendar
                  mode="single"
                  selected={toDate}
                  onSelect={handleToSelect}
                  defaultMonth={toDate ?? new Date()}
                />
              </div>
            )}

            <button
              onClick={handleApply}
              className="w-full mt-3 px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors font-medium"
            >
              Apply time range
            </button>
          </div>

          {/* Right — quick presets */}
          <div className="p-2" style={{ width: 170 }}>
            {PRESETS.map(p => (
              <button
                key={p.days}
                onClick={() => handlePreset(p.days)}
                className={`w-full text-left px-3 py-1.5 text-xs rounded transition-colors ${
                  mode === 'preset' && p.days === preset.days
                    ? 'bg-primary/15 text-primary'
                    : 'text-foreground hover:bg-muted'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
