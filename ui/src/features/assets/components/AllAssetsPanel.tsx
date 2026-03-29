// ui/src/features/assets/components/AllAssetsPanel.tsx
import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { LabelChips } from '@/components/labels/LabelChips'
import { useAssets, useAssetTypes, useDeleteAsset } from '../hooks'

export function AllAssetsPanel() {
  const { data: assets = [], isLoading } = useAssets()
  const { data: types = [] } = useAssetTypes()
  const deleteAsset = useDeleteAsset()
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  if (isLoading) {
    return <div className="p-6 text-muted-foreground">Loading…</div>
  }

  return (
    <div
      className="p-6 space-y-4"
      style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
    >
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-foreground">All Assets</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          {assets.length} assets · {types.length} types
        </p>
      </div>

      {/* Table */}
      {assets.length === 0 && (
        <p className="text-sm text-muted-foreground italic">No assets yet</p>
      )}
      {assets.length > 0 && (
        <div className="border border-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-table-header-bg">
                <th className="text-left px-3 py-2 text-xs uppercase text-muted-foreground font-medium">Name</th>
                <th className="text-left px-3 py-2 text-xs uppercase text-muted-foreground font-medium w-[100px]">Type</th>
                <th className="text-left px-3 py-2 text-xs uppercase text-muted-foreground font-medium min-w-[200px]">Labels</th>
                <th className="text-center px-3 py-2 text-xs uppercase text-muted-foreground font-medium w-[60px]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset, idx) => (
                <tr key={asset.id} className={`border-b border-border/60 last:border-0 hover:bg-table-row-hover transition-colors ${idx % 2 === 0 ? 'bg-table-row-bg' : 'bg-table-row-alt'}`}>
                  <td className="px-3 py-2">
                    <span className="font-mono text-foreground">{asset.display_name ?? asset.name}</span>
                    {asset.display_name && (
                      <span className="text-xs text-muted-foreground ml-1.5">{asset.name}</span>
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono text-muted-foreground">
                    {asset.type_name}
                  </td>
                  <td className="px-3 py-2">
                    <LabelChips labels={asset.tags} maxVisible={3} size="small" />
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center justify-center">
                      {confirmDelete === asset.name ? (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => {
                              void deleteAsset.mutateAsync(asset.name)
                              setConfirmDelete(null)
                            }}
                            className="px-2 py-0.5 text-xs rounded bg-action-destructive-confirm text-white font-bold"
                          >
                            Delete
                          </button>
                          <button
                            onClick={() => setConfirmDelete(null)}
                            className="px-2 py-0.5 text-xs rounded bg-action-secondary-bg border border-action-secondary-border text-white"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmDelete(asset.name)}
                          className="p-1 text-action-destructive hover:bg-action-destructive-confirm-bg/50 rounded transition-colors"
                          title="Delete asset"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
