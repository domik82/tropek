// ui/src/components/TimeRangePicker.tsx
import { useState } from 'react'
import { Calendar, ChevronDown } from 'lucide-react'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { useTimeRange, PRESETS } from '@/lib/time-range-context'

export function TimeRangePicker() {
  const { preset, setDays } = useTimeRange()
  const [open, setOpen] = useState(false)

  return (
    <Popover open={open} onOpenChange={(nextOpen) => setOpen(nextOpen)}>
      <PopoverTrigger
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border border-border bg-popover text-foreground hover:bg-muted transition-colors"
        style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
      >
        <Calendar size={14} className="text-muted-foreground" />
        {preset.label}
        <ChevronDown size={12} className="text-muted-foreground" />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-44 p-1">
        {PRESETS.map(p => (
          <button
            key={p.days}
            onClick={() => { setDays(p.days); setOpen(false) }}
            className={`w-full text-left px-3 py-1.5 text-xs rounded transition-colors ${
              p.days === preset.days
                ? 'bg-primary/15 text-primary'
                : 'text-foreground hover:bg-muted'
            }`}
            style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
          >
            {p.label}
          </button>
        ))}
      </PopoverContent>
    </Popover>
  )
}
