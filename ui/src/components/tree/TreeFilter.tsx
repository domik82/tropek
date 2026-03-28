import { Search, X } from 'lucide-react'

interface TreeFilterProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  resultCount?: number
}

export function TreeFilter({ value, onChange, placeholder = 'Filter...', resultCount }: TreeFilterProps) {
  return (
    <div>
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
        <input
          type="text"
          placeholder={placeholder}
          value={value}
          onChange={e => onChange(e.target.value)}
          className="w-full bg-input border border-border rounded-md py-1.5 pl-8 pr-7 text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary/50"
        />
        {value && (
          <button
            onClick={() => onChange('')}
            aria-label="Clear filter"
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      {value && resultCount !== undefined && (
        <div className="text-[11px] text-muted-foreground px-1 pt-1">
          {resultCount} {resultCount === 1 ? 'result' : 'results'}
        </div>
      )}
    </div>
  )
}
