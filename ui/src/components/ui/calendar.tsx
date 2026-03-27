// ui/src/components/ui/calendar.tsx
// Calendar using react-day-picker v9 with inline styles for reliable dark-theme rendering.

import { DayPicker, type DayPickerProps } from 'react-day-picker'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import 'react-day-picker/style.css'

export type CalendarProps = DayPickerProps

export function Calendar(props: CalendarProps) {
  return (
    <div className="tropek-calendar">
      <DayPicker
        showOutsideDays
        components={{
          Chevron: ({ orientation }) =>
            orientation === 'left'
              ? <ChevronLeft size={14} />
              : <ChevronRight size={14} />,
        }}
        {...props}
      />
    </div>
  )
}
