// ui/src/components/TimeRangePicker.tsx
import { useState } from 'react'
import { Calendar, ChevronDown } from 'lucide-react'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { useTimeRange, PRESETS, toDateInputValue } from '@/lib/time-range-context'

const SANS = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

export function TimeRangePicker() {
  const { label, mode, preset, setDays, setAbsoluteRange } = useTimeRange()
  const [open, setOpen] = useState(false)

  // Local state for the absolute date inputs (only committed on Apply)
  const [fromInput, setFromInput] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() - 30)
    return toDateInputValue(d)
  })
  const [toInput, setToInput] = useState('')

  function handlePreset(days: number) {
    setDays(days)
    setOpen(false)
  }

  function handleApply() {
    const fromIso = new Date(fromInput + 'T00:00:00').toISOString()
    const toIso = toInput ? new Date(toInput + 'T23:59:59').toISOString() : undefined
    setAbsoluteRange(fromIso, toIso)
    setOpen(false)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border border-border bg-popover text-foreground hover:bg-muted transition-colors"
        style={{ fontFamily: SANS }}
      >
        <Calendar size={14} className="text-muted-foreground" />
        {label}
        <ChevronDown size={12} className="text-muted-foreground" />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-auto p-0" style={{ fontFamily: SANS }}>
        <div className="flex">
          {/* Left — absolute date range */}
          <div className="p-4 border-r border-border" style={{ width: 220 }}>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              Absolute time range
            </h3>
            <label className="block text-xs text-muted-foreground mb-1">From</label>
            <input
              type="date"
              value={fromInput}
              onChange={e => setFromInput(e.target.value)}
              className="w-full px-2 py-1.5 text-xs rounded border border-border bg-background text-foreground mb-3"
            />
            <label className="block text-xs text-muted-foreground mb-1">To</label>
            <input
              type="date"
              value={toInput}
              onChange={e => setToInput(e.target.value)}
              placeholder="now"
              className="w-full px-2 py-1.5 text-xs rounded border border-border bg-background text-foreground mb-3"
            />
            <button
              onClick={handleApply}
              className="w-full px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors font-medium"
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
