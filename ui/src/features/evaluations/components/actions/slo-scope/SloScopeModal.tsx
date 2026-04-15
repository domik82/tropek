import { useState, useEffect, useMemo } from 'react'
import type { SloScopeOption, SloScopeOutcome } from './types'

interface Props {
  open: boolean
  availableSlos: SloScopeOption[]
  initialSelected: Set<string>
  onConfirm: (selected: Set<string>) => void
  onCancel: () => void
}

const RESULT_BADGE_CLASS: Record<SloScopeOutcome, string> = {
  pass: 'text-pass bg-pass/10 border-pass/30',
  warning: 'text-warning bg-warning/10 border-warning/30',
  fail: 'text-fail bg-fail/10 border-fail/30',
  invalidated: 'text-muted-foreground bg-muted/20 border-border',
  error: 'text-muted-foreground bg-muted/20 border-border',
}

export function SloScopeModal({
  open,
  availableSlos,
  initialSelected,
  onConfirm,
  onCancel,
}: Props) {
  const [draft, setDraft] = useState<Set<string>>(new Set(initialSelected))
  const [query, setQuery] = useState('')

  /* eslint-disable react-hooks/set-state-in-effect -- intentional reset on reopen */
  useEffect(() => {
    if (open) {
      setDraft(new Set(initialSelected))
      setQuery('')
    }
  }, [open, initialSelected])
  /* eslint-enable react-hooks/set-state-in-effect */

  const filtered = useMemo(() => {
    const trimmedQuery = query.trim().toLowerCase()
    if (!trimmedQuery) return availableSlos
    return availableSlos.filter(
      slo =>
        slo.displayName.toLowerCase().includes(trimmedQuery) ||
        slo.sloName.toLowerCase().includes(trimmedQuery),
    )
  }, [availableSlos, query])

  if (!open) return null

  function toggle(sloName: string) {
    setDraft(prev => {
      const next = new Set(prev)
      if (next.has(sloName)) next.delete(sloName)
      else next.add(sloName)
      return next
    })
  }

  function selectAll() {
    setDraft(new Set(availableSlos.map(slo => slo.sloName)))
  }

  function clearAll() {
    setDraft(new Set())
  }

  return (
    <div
      className='fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm'
      role='dialog'
      aria-modal='true'
      aria-label='Select SLOs'
    >
      <div className='w-full max-w-md bg-popover border border-border rounded-xl shadow-2xl p-4 space-y-3'>
        <div className='flex items-center justify-between'>
          <h2 className='text-sm font-semibold text-foreground'>Select SLOs</h2>
          <span className='text-xs text-muted-foreground'>
            {draft.size} of {availableSlos.length} selected
          </span>
        </div>

        <input
          type='text'
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder='Search SLOs…'
          className='w-full px-2 py-1.5 text-sm bg-background border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-primary'
        />

        <div className='flex gap-2'>
          <button
            type='button'
            onClick={selectAll}
            className='text-xs px-2 py-1 rounded border border-border text-muted-foreground hover:text-foreground'
          >
            Select all
          </button>
          <button
            type='button'
            onClick={clearAll}
            className='text-xs px-2 py-1 rounded border border-border text-muted-foreground hover:text-foreground'
          >
            Clear
          </button>
        </div>

        <ul className='max-h-[50vh] overflow-y-auto space-y-1'>
          {filtered.length === 0 && (
            <li className='text-xs text-muted-foreground px-2 py-4 text-center'>No matches.</li>
          )}
          {filtered.map(slo => {
            const checked = draft.has(slo.sloName)
            return (
              <li key={slo.sloName}>
                <label className='flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted/40 cursor-pointer'>
                  <input
                    type='checkbox'
                    checked={checked}
                    onChange={() => toggle(slo.sloName)}
                    className='rounded border-border accent-primary'
                  />
                  <span className='flex-1 text-sm text-foreground'>{slo.displayName}</span>
                  <span
                    className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${
                      RESULT_BADGE_CLASS[slo.currentResult]
                    }`}
                  >
                    {slo.currentResult}
                  </span>
                </label>
              </li>
            )
          })}
        </ul>

        <div className='flex justify-end gap-2 pt-2 border-t border-border'>
          <button
            type='button'
            onClick={onCancel}
            className='px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:text-foreground'
          >
            Cancel
          </button>
          <button
            type='button'
            onClick={() => onConfirm(draft)}
            className='px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/80'
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  )
}
