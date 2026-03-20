import { Plus, PackagePlus } from 'lucide-react'
import type { TreeMode } from './types'

interface Props {
  mode: TreeMode
  onCreateGroup: () => void
  onAddAsset?: () => void
}

export function AssetTreeFooter({ mode, onCreateGroup, onAddAsset }: Props) {
  return (
    <div className="border-t border-border px-2 py-2 flex gap-2">
      <button
        onClick={onCreateGroup}
        className="flex-1 text-xs border border-border rounded py-1.5 text-primary hover:bg-primary/10 transition-colors flex items-center justify-center gap-1"
      >
        <Plus className="w-3.5 h-3.5" />
        New Group
      </button>
      {(mode === 'navigator' || mode === 'assets') && onAddAsset && (
        <button
          onClick={onAddAsset}
          className="flex-1 text-xs border border-[#58A6FF] rounded py-1.5 text-[#58A6FF] hover:bg-[#0D2847]/50 transition-colors flex items-center justify-center gap-1"
        >
          <PackagePlus className="w-3.5 h-3.5" />
          Add Asset
        </button>
      )}
    </div>
  )
}
