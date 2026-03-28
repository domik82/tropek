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
      // Clicking a chip when All is active → select just that one
      onChange([name])
      return
    }
    if (selected!.includes(name)) {
      // Don't deselect the last chip
      if (selected!.length <= 1) return
      onChange(selected!.filter(n => n !== name))
    } else {
      onChange([...selected!, name])
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
            ? 'bg-primary text-white border border-primary'
            : 'bg-gray-800/60 text-slate-500 border border-slate-700 hover:text-slate-300'
        }`}
      >
        All
      </button>
      {names.map(entry => {
        const active = !isAll && selected!.includes(entry.name)
        return (
          <button
            key={entry.name}
            onClick={() => handleToggle(entry.name)}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
              active
                ? 'bg-primary text-white border border-primary'
                : 'bg-gray-800/60 text-slate-500 border border-slate-700 hover:text-slate-300'
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
