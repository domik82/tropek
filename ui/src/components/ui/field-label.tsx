import { cn } from '@/lib/utils'

interface FieldLabelProps {
  children: React.ReactNode
  required?: boolean
  className?: string
}

export function FieldLabel({ children, required, className }: FieldLabelProps) {
  return (
    <label className={cn("text-xs uppercase text-muted-foreground block mb-1", className)}>
      {children}
      {required && <span className="text-destructive ml-0.5">*</span>}
    </label>
  )
}
