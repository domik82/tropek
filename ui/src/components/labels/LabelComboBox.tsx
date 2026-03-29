// ui/src/components/labels/LabelComboBox.tsx
import { useState, useRef, useEffect } from 'react'
import { SANS_SERIF } from '@/lib/fonts'

interface Suggestion {
  value: string
  count: number
}

interface Props {
  value: string
  onChange: (value: string) => void
  suggestions: Suggestion[]
  placeholder?: string
  isLoading?: boolean
}

export function LabelComboBox({ value, onChange, suggestions, placeholder, isLoading }: Props) {
  const [open, setOpen] = useState(false)
  const [focused, setFocused] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const filtered = suggestions.filter(s =>
    s.value.toLowerCase().includes(value.toLowerCase()),
  )
  const exactMatch = suggestions.some(s => s.value === value)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current && !inputRef.current.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div className="relative">
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={e => { onChange(e.target.value); setOpen(true) }}
        onFocus={() => { setFocused(true); setOpen(true) }}
        onBlur={() => setFocused(false)}
        placeholder={placeholder}
        className="w-full bg-black border border-border rounded px-3 py-2 text-sm text-foreground font-mono placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary/50"
      />

      {open && (focused || open) && (
        <div
          ref={dropdownRef}
          className="absolute z-50 top-full mt-1 w-full bg-popover border border-border rounded-lg shadow-lg max-h-[200px] overflow-y-auto py-1"
          style={{ fontFamily: SANS_SERIF }}
        >
          {isLoading && (
            <div className="px-3 py-2 text-xs text-muted-foreground">Loading...</div>
          )}

          {!isLoading && filtered.length > 0 && (
            <>
              <div className="px-3 py-1 text-[10px] uppercase text-muted-foreground font-semibold tracking-wide">
                Existing
              </div>
              {filtered.map(s => (
                <button
                  key={s.value}
                  type="button"
                  className="w-full px-3 py-1.5 text-sm flex items-center justify-between hover:bg-accent transition-colors text-foreground"
                  onMouseDown={e => {
                    e.preventDefault()
                    onChange(s.value)
                    setOpen(false)
                  }}
                >
                  <span className="font-mono">{s.value}</span>
                  <span className="text-xs text-muted-foreground">{s.count}</span>
                </button>
              ))}
            </>
          )}

          {!isLoading && value && !exactMatch && (
            <>
              <div className="mx-2 my-1 border-t border-border" />
              <button
                type="button"
                className="w-full px-3 py-1.5 text-sm text-primary hover:bg-accent transition-colors text-left"
                onMouseDown={e => {
                  e.preventDefault()
                  setOpen(false)
                }}
              >
                + Create &quot;{value}&quot; as new key
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
