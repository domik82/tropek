import { useState, useRef, useEffect } from 'react'
import { ChevronDown, Search } from 'lucide-react'

const SANS_SERIF = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

interface ComboBoxItem {
  value: string
  label: string
  badge?: string
}

interface SearchableComboBoxProps {
  value: string
  items: ComboBoxItem[]
  onSelect: (value: string) => void
  placeholder?: string
}

export function SearchableComboBox({
  value,
  items,
  onSelect,
  placeholder = 'Select...',
}: SearchableComboBoxProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)

  const selectedItem = items.find((item) => item.value === value)

  const filteredItems = items.filter((item) => {
    if (!search) return true
    const q = search.toLowerCase()
    return item.label.toLowerCase().includes(q) || item.value.toLowerCase().includes(q)
  })

  useEffect(() => {
    if (open && searchInputRef.current) {
      searchInputRef.current.focus()
    }
  }, [open])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
        setSearch('')
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  function handleToggle() {
    setOpen(!open)
    if (open) {
      setSearch('')
    }
  }

  function handleSelect(itemValue: string) {
    onSelect(itemValue)
    setOpen(false)
    setSearch('')
  }

  return (
    <div ref={containerRef} className="relative" style={{ fontFamily: SANS_SERIF }}>
      <button
        type="button"
        onClick={handleToggle}
        className="flex w-full items-center justify-between gap-2 rounded border
          border-[var(--border)] bg-[var(--popover)] px-3 py-2 text-sm
          hover:border-[var(--primary)] focus:outline-none focus:ring-1
          focus:ring-[var(--primary)]"
      >
        <span className={selectedItem ? 'text-[var(--foreground)]' : 'text-[var(--muted-foreground)]'}>
          {selectedItem ? selectedItem.label : placeholder}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]" />
      </button>

      {open && (
        <div
          className="absolute z-50 mt-1 w-full rounded border border-[var(--border)]
            bg-[var(--popover)] shadow-lg"
        >
          <div className="flex items-center gap-2 border-b border-[var(--border)] px-3 py-2">
            <Search className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]" />
            <input
              ref={searchInputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search..."
              className="w-full bg-transparent text-sm text-[var(--foreground)]
                placeholder:text-[var(--muted-foreground)] focus:outline-none"
            />
          </div>

          <div className="max-h-60 overflow-y-auto py-1">
            {filteredItems.length === 0 ? (
              <div className="px-3 py-2 text-sm text-[var(--muted-foreground)]">No results</div>
            ) : (
              filteredItems.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => handleSelect(item.value)}
                  className="flex w-full items-center justify-between px-3 py-2 text-sm
                    text-[var(--foreground)] hover:bg-[var(--accent)]"
                >
                  <span>{item.label}</span>
                  {item.badge && (
                    <span
                      className="ml-2 rounded-full bg-[var(--muted)] px-2 py-0.5 text-xs
                        text-[var(--muted-foreground)]"
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
