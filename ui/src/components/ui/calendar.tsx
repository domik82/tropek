// ui/src/components/ui/calendar.tsx
// Minimal shadcn-style calendar using react-day-picker v9.

import { DayPicker, type DayPickerProps } from 'react-day-picker'
import { ChevronLeft, ChevronRight } from 'lucide-react'

export type CalendarProps = DayPickerProps

export function Calendar(props: CalendarProps) {
  return (
    <DayPicker
      showOutsideDays
      components={{
        Chevron: ({ orientation }) =>
          orientation === 'left'
            ? <ChevronLeft size={14} />
            : <ChevronRight size={14} />,
      }}
      classNames={{
        root: 'p-2',
        months: 'flex gap-4',
        month: 'space-y-2',
        month_caption: 'flex justify-center items-center h-7',
        caption_label: 'text-xs font-medium text-foreground',
        nav: 'flex items-center gap-1',
        button_previous: 'absolute left-1 top-1 inline-flex items-center justify-center w-6 h-6 rounded text-muted-foreground hover:bg-muted hover:text-foreground transition-colors',
        button_next: 'absolute right-1 top-1 inline-flex items-center justify-center w-6 h-6 rounded text-muted-foreground hover:bg-muted hover:text-foreground transition-colors',
        month_grid: 'w-full border-collapse',
        weekdays: '',
        weekday: 'text-muted-foreground text-[0.65rem] font-normal w-7 text-center',
        week: '',
        day: 'text-center p-0',
        day_button: 'inline-flex items-center justify-center w-7 h-7 text-[0.7rem] rounded hover:bg-muted transition-colors text-foreground',
        selected: '!bg-primary !text-primary-foreground hover:!bg-primary/90',
        today: 'font-bold text-primary',
        outside: 'text-muted-foreground/40',
        range_start: 'rounded-l-md',
        range_end: 'rounded-r-md',
        range_middle: 'bg-primary/10',
      }}
      {...props}
    />
  )
}
