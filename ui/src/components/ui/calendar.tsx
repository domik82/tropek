// ui/src/components/ui/calendar.tsx
// Calendar using react-day-picker v9 with dropdown month/year navigation.

import { DayPicker, type DayPickerProps } from 'react-day-picker'
import { ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react'
import { getConfig } from '@/lib/config'
import 'react-day-picker/style.css'

export type CalendarProps = DayPickerProps

function CaptionChevron({ orientation }: { orientation?: string }) {
  if (orientation === 'left') return <ChevronLeft size={14} />
  if (orientation === 'right') return <ChevronRight size={14} />
  return <ChevronDown size={12} />
}

export function Calendar(props: CalendarProps) {
  const startDate = new Date(getConfig().dataStartDate)
  const startMonth = new Date(startDate.getFullYear(), startDate.getMonth())
  const endMonth = new Date(new Date().getFullYear(), new Date().getMonth())

  return (
    <div className="tropek-calendar">
      <DayPicker
        showOutsideDays
        captionLayout="dropdown"
        startMonth={startMonth}
        endMonth={endMonth}
        components={{ Chevron: CaptionChevron }}
        {...props}
      />
    </div>
  )
}
