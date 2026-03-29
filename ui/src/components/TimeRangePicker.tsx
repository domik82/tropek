// ui/src/components/TimeRangePicker.tsx
import { useState } from 'react'
import { Calendar as CalendarIcon, ChevronDown } from 'lucide-react'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { useTimeRange, PRESETS, toDateInputValue } from '@/lib/time-range-context'
import { SANS_SERIF } from '@/lib/fonts'

function presetFromDate(days: number): Date {
  const d = new Date()
  d.setDate(d.getDate() - days)
  d.setHours(0, 0, 0, 0)
  return d
}

export function TimeRangePicker() {
  const { label, mode, preset, setDays, setAbsoluteRange } = useTimeRange()
  const [open, setOpen] = useState(false)

  // Which date field is being edited: null = collapsed, 'from'/'to' = show calendar
  const [editing, setEditing] = useState<'from' | 'to' | null>(null)

  const [fromDate, setFromDate] = useState<Date | undefined>(() => presetFromDate(30))
  const [toDate, setToDate] = useState<Date | undefined>(undefined)

  function handlePreset(days: number) {
    setDays(days)
    // Sync the absolute inputs to match the preset so they're not stale
    setFromDate(presetFromDate(days))
    setToDate(undefined)
    setEditing(null)
    setOpen(false)
  }

  const rangeInvalid = !!(fromDate && toDate && fromDate > toDate)

  function handleApply() {
    if (!fromDate || rangeInvalid) return
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
    if (!day) return
    setFromDate(day)
    // If from is now after to, clamp to = from
    if (toDate && day > toDate) setToDate(day)
    setEditing(null)
  }

  function handleToSelect(day: Date | undefined) {
    if (!day) return
    setToDate(day)
    // If to is now before from, clamp from = to
    if (fromDate && day < fromDate) setFromDate(day)
    setEditing(null)
  }

  return (
    <Popover open={open} onOpenChange={(next) => { setOpen(next); if (!next) setEditing(null) }}>
      <PopoverTrigger
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-border bg-popover text-foreground hover:bg-muted transition-colors"
        style={{ fontFamily: SANS_SERIF }}
      >
        <CalendarIcon size={15} className="text-muted-foreground" />
        {label}
        <ChevronDown size={13} className="text-muted-foreground" />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-auto p-0 z-[100]" style={{ fontFamily: SANS_SERIF }}>
        <div className="flex">
          {/* Left — absolute date range */}
          <div className="p-4 border-r border-border" style={{ width: 260 }}>
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
                  disabled={toDate ? { after: toDate } : undefined}
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
                  disabled={fromDate ? { before: fromDate } : undefined}
                />
              </div>
            )}

            <Button
              variant="default"
              size="sm"
              onClick={handleApply}
              disabled={!fromDate || rangeInvalid}
              className="w-full mt-3"
            >
              Apply time range
            </Button>
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
