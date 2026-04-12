import { useState, useMemo } from 'react'
import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { useAssets, useAddGroupMember, useAssetGroups } from '@/features/assets/hooks'
import { SANS_SERIF } from '@/lib/fonts'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  groupName: string | null
}

export function AddAssetToGroupDialog({ open, onOpenChange, groupName }: Props) {
  const [filter, setFilter] = useState('')
  const { data: assets } = useAssets()
  const { data: tree } = useAssetGroups()
  const addMember = useAddGroupMember()

  // Find current group members to exclude them from the list
  const currentMemberIds = useMemo(() => {
    if (!tree || !groupName) return new Set<string>()
    const group = tree.allGroups.find(g => g.name === groupName)
    if (!group) return new Set<string>()
    return new Set(group.members.map(m => m.assetId))
  }, [tree, groupName])

  const available = useMemo(() => {
    if (!assets) return []
    return assets
      .filter(a => !currentMemberIds.has(a.id))
      .filter(a => !filter || a.name.toLowerCase().includes(filter.toLowerCase())
        || (a.displayName ?? '').toLowerCase().includes(filter.toLowerCase()))
  }, [assets, currentMemberIds, filter])

  if (!open || !groupName) return null

  const handleAdd = (assetId: string) => {
    addMember.mutate({ groupName, assetId }, {
      onSuccess: () => {
        onOpenChange(false)
        setFilter('')
      },
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div
        className="bg-popover border border-border rounded-lg shadow-xl w-full max-w-sm mx-4"
        style={{ fontFamily: SANS_SERIF }}
      >
        <div className="px-4 pt-4 pb-3 border-b border-border">
          <h3 className="text-sm font-semibold text-foreground">
            Add asset to <span className="text-primary">{groupName}</span>
          </h3>
        </div>

        <div className="px-4 py-3">
          <div className="relative mb-3">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search assets..."
              value={filter}
              onChange={e => setFilter(e.target.value)}
              autoFocus
              className="pl-8"
            />
          </div>

          <div className="max-h-[280px] overflow-y-auto -mx-1">
            {available.length === 0 && (
              <p className="text-xs text-muted-foreground px-3 py-4 text-center">
                {filter ? 'No matching assets' : 'All assets are already in this group'}
              </p>
            )}
            {available.map(asset => (
              <button
                key={asset.id}
                className="w-full px-3 py-2 text-left text-sm hover:bg-accent rounded-md transition-colors flex items-center justify-between gap-2"
                onClick={() => handleAdd(asset.id)}
              >
                <span className="truncate text-foreground">{asset.displayName ?? asset.name}</span>
                <span className="text-[11px] text-muted-foreground shrink-0">{asset.typeName}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="px-4 py-3 border-t border-border flex justify-end">
          <button
            className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-accent transition-colors text-muted-foreground"
            onClick={() => { onOpenChange(false); setFilter('') }}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
