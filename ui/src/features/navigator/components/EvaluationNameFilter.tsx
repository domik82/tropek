import type { EvaluationNameEntry } from '@/features/evaluations/api'

interface Props {
  names: EvaluationNameEntry[]
  /** Selected names, or undefined = "All" (no filter). */
  selected: string[] | undefined
  onChange: (names: string[] | undefined) => void
}

export function EvaluationNameFilter({ names, selected, onChange }: Props) {
  if (names.length === 0) return null

  const isAll = selected === undefined

  function handleToggle(name: string) {
    if (isAll) {
      // Clicking a chip when All is active → deselect that one (select everything else)
      onChange(names.map(n => n.name).filter(n => n !== name))
      return
    }
    if (selected!.includes(name)) {
      const remaining = selected!.filter(n => n !== name)
      // Deselecting the last one → back to All
      onChange(remaining.length === 0 ? undefined : remaining)
    } else {
      const next = [...selected!, name]
      // Selecting all individually → collapse to All
      onChange(next.length === names.length ? undefined : next)
    }
  }

  function handleAll() {
    onChange(undefined)
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span
        className="text-xs uppercase tracking-wide text-slate-500 mr-1"
        style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
      >
        Eval name
      </span>
      <button
        onClick={handleAll}
        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
          isAll
            ? 'bg-primary/20 text-primary border border-primary/40'
            : 'bg-gray-800 text-slate-400 border border-slate-700 hover:text-slate-200'
        }`}
      >
        All
      </button>
      {names.map(entry => {
        // Active = included in results: either All is on, or explicitly selected
        const active = isAll || selected!.includes(entry.name)
        return (
          <button
            key={entry.name}
            onClick={() => handleToggle(entry.name)}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
              active
                ? 'bg-primary/20 text-primary border border-primary/40'
                : 'bg-gray-800 text-slate-400 border border-slate-700 hover:text-slate-200'
            }`}
          >
            {entry.name}
            <span className="text-[10px] opacity-60">{entry.count}</span>
          </button>
        )
      })}
    </div>
  )
}
