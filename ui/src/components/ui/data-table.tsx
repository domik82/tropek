import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface DataTableProps {
  children: ReactNode
  className?: string
  fixed?: boolean
}

export function DataTable({ children, className, fixed }: DataTableProps) {
  return (
    <div className={cn('overflow-hidden rounded-lg border border-border', className)}>
      <table className={cn('w-full text-sm text-left', fixed && 'table-fixed')}>{children}</table>
    </div>
  )
}

export function DataTableHeader({ children }: { children: ReactNode }) {
  return (
    <thead className="text-xs uppercase text-muted-foreground bg-table-header-bg border-b border-border">
      {children}
    </thead>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function dataTableRowClass(idx: number, isSelected?: boolean): string {
  const zebra = idx % 2 === 0 ? 'bg-table-row-bg' : 'bg-table-row-alt'
  const bg = isSelected ? 'bg-table-row-selected' : zebra
  return `transition-colors ${bg} hover:bg-table-row-hover border-b border-border/60 last:border-0`
}
