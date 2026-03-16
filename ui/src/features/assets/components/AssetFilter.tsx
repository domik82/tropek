// src/features/assets/components/AssetFilter.tsx
interface Props {
  query: string
  onQueryChange: (v: string) => void
  onExpandAll: () => void
  onCollapseAll: () => void
}

export function AssetFilter({ query, onQueryChange, onExpandAll, onCollapseAll }: Props) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <input
        value={query}
        onChange={e => onQueryChange(e.target.value)}
        placeholder="Filter assets..."
        className="max-w-xs px-3 py-1.5 text-sm rounded border border-slate-700 bg-gray-800 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-slate-500"
      />
      <button onClick={onExpandAll} className="px-3 py-1.5 text-xs rounded border border-slate-700 text-slate-300 hover:bg-slate-800/50 hover:text-slate-200 transition-colors">Expand All</button>
      <button onClick={onCollapseAll} className="px-3 py-1.5 text-xs rounded border border-slate-700 text-slate-300 hover:bg-slate-800/50 hover:text-slate-200 transition-colors">Collapse All</button>
    </div>
  )
}
