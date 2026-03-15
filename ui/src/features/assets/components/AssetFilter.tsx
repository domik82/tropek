// src/features/assets/components/AssetFilter.tsx
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

interface Props {
  query: string
  onQueryChange: (v: string) => void
  onExpandAll: () => void
  onCollapseAll: () => void
}

export function AssetFilter({ query, onQueryChange, onExpandAll, onCollapseAll }: Props) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <Input
        value={query}
        onChange={e => onQueryChange(e.target.value)}
        placeholder="Filter assets..."
        className="max-w-xs"
      />
      <Button variant="outline" size="sm" onClick={onExpandAll}>Expand All</Button>
      <Button variant="outline" size="sm" onClick={onCollapseAll}>Collapse All</Button>
    </div>
  )
}
