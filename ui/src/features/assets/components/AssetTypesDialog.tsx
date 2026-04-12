// ui/src/features/assets/components/AssetTypesDialog.tsx
import { useState } from 'react'
import { Pencil, Star, Trash2, Check, X } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  useAssetTypes, useCreateAssetType, useRenameAssetType,
  useSetDefaultAssetType, useDeleteAssetType,
} from '../hooks'
import { SANS_SERIF } from '@/lib/fonts'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AssetTypesDialog({ open, onOpenChange }: Props) {
  const { data: types = [], isLoading } = useAssetTypes()
  const createType = useCreateAssetType()
  const renameType = useRenameAssetType()
  const setDefault = useSetDefaultAssetType()
  const deleteType = useDeleteAssetType()

  const [renamingName, setRenamingName] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [deletingName, setDeletingName] = useState<string | null>(null)
  const [addingNew, setAddingNew] = useState(false)
  const [newName, setNewName] = useState('')

  const startRename = (name: string) => {
    setRenamingName(name)
    setRenameValue(name)
    setDeletingName(null)
    setAddingNew(false)
  }

  const confirmRename = async () => {
    if (renamingName && renameValue && renameValue !== renamingName) {
      await renameType.mutateAsync({ oldName: renamingName, newName: renameValue })
    }
    setRenamingName(null)
  }

  const confirmDelete = async () => {
    if (deletingName) {
      await deleteType.mutateAsync(deletingName)
      setDeletingName(null)
    }
  }

  const handleAdd = async () => {
    if (newName) {
      await createType.mutateAsync(newName)
      setNewName('')
      setAddingNew(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-lg"
        style={{ fontFamily: SANS_SERIF }}
      >
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle>Asset Types</DialogTitle>
              <p className="text-sm text-muted-foreground">manage available types</p>
            </div>
            <button
              onClick={() => { setAddingNew(true); setRenamingName(null); setDeletingName(null) }}
              className="px-3 py-1.5 text-xs rounded border border-action-primary-border bg-action-primary-bg text-action-primary hover:bg-action-primary-hover"
            >
              + Add Type
            </button>
          </div>
        </DialogHeader>

        <div className="py-2">
          {/* Table header */}
          <div className="flex items-center gap-2 px-2 py-1.5 text-[10px] uppercase text-muted-foreground tracking-wide border-b border-border">
            <span className="flex-1">Type Name</span>
            <span className="w-[80px] text-center">Default</span>
            <span className="w-[60px] text-center">Assets</span>
            <span className="w-[100px] text-center">Actions</span>
          </div>

          {isLoading && (
            <div className="px-2 py-4 text-sm text-muted-foreground text-center">Loading…</div>
          )}

          {/* Type rows */}
          {types.map(type => {
            if (deletingName === type.name) {
              return (
                <div
                  key={type.name}
                  className="flex items-center gap-3 px-3 py-2 my-1 rounded bg-action-destructive-bg border border-action-destructive-border"
                >
                  <span className="flex-1 text-sm text-foreground">
                    Delete type &quot;{type.name}&quot;? This cannot be undone.
                  </span>
                  <button
                    onClick={() => setDeletingName(null)}
                    className="px-3 py-1 text-xs rounded bg-action-secondary-bg border border-action-secondary-border text-white"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={confirmDelete}
                    className="px-3 py-1 text-xs rounded bg-action-destructive-confirm text-white font-bold"
                  >
                    Delete
                  </button>
                </div>
              )
            }

            const canDelete = type.assetCount === 0 && !type.isDefault

            return (
              <div
                key={type.name}
                className="flex items-center gap-2 px-2 py-1.5 border-b border-border/50 hover:bg-muted/30 transition-colors"
              >
                {/* Name / Rename */}
                <div className="flex-1">
                  {renamingName === type.name ? (
                    <div className="flex items-center gap-1">
                      <Input
                        value={renameValue}
                        onChange={e => setRenameValue(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') void confirmRename()
                          if (e.key === 'Escape') setRenamingName(null)
                        }}
                        autoFocus
                        className="font-mono"
                      />
                      <button
                        onClick={() => void confirmRename()}
                        className="w-6 h-6 flex items-center justify-center rounded bg-action-primary-bg border border-action-primary-border text-action-primary"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => setRenamingName(null)}
                        className="w-6 h-6 flex items-center justify-center rounded bg-action-secondary-bg border border-action-secondary-border text-white"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ) : (
                    <span className="text-sm font-mono text-foreground">{type.name}</span>
                  )}
                </div>

                {/* Default indicator */}
                <div className="w-[80px] flex items-center justify-center">
                  {type.isDefault ? (
                    <span className="text-xs text-indicator-default font-medium">default</span>
                  ) : (
                    <span className="w-2.5 h-2.5 rounded-full border border-muted-foreground/40" />
                  )}
                </div>

                {/* Asset count */}
                <div className="w-[60px] text-center text-sm font-mono text-muted-foreground">
                  {type.assetCount}
                </div>

                {/* Actions */}
                <div className="w-[100px] flex items-center justify-center gap-1">
                  <button
                    onClick={() => startRename(type.name)}
                    className="w-7 h-6 flex items-center justify-center rounded-md border border-border text-action-primary hover:bg-action-primary-hover"
                    title="Rename"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => !type.isDefault && void setDefault.mutateAsync(type.name)}
                    disabled={type.isDefault}
                    className={`w-7 h-6 flex items-center justify-center rounded-md border ${
                      type.isDefault
                        ? 'border-border text-indicator-default'
                        : 'border-border text-muted-foreground hover:text-indicator-default hover:bg-muted/30'
                    }`}
                    title="Set as default"
                  >
                    <Star className={`w-3.5 h-3.5 ${type.isDefault ? 'fill-current' : ''}`} />
                  </button>
                  <button
                    onClick={() => canDelete && setDeletingName(type.name)}
                    disabled={!canDelete}
                    className={`w-7 h-6 flex items-center justify-center rounded-md border ${
                      canDelete
                        ? 'border-action-destructive-border text-action-destructive hover:bg-action-destructive-bg'
                        : 'border-border text-muted-foreground cursor-not-allowed'
                    }`}
                    title={canDelete ? 'Delete' : type.isDefault ? 'Cannot delete default type' : 'Cannot delete type with assets'}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )
          })}

          {/* Add new type form */}
          {addingNew && (
            <div className="flex items-center gap-2 px-2 py-2 mt-1">
              <Input
                value={newName}
                onChange={e => setNewName(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') void handleAdd()
                  if (e.key === 'Escape') setAddingNew(false)
                }}
                autoFocus
                placeholder="e.g. database"
                className="flex-1 font-mono"
              />
              <button
                onClick={() => void handleAdd()}
                disabled={!newName}
                className="px-3 py-1.5 text-xs rounded border border-action-primary-border bg-action-primary-bg text-action-primary disabled:opacity-40"
              >
                Save
              </button>
              <button
                onClick={() => { setAddingNew(false); setNewName('') }}
                className="px-3 py-1.5 text-xs rounded bg-action-secondary-bg border border-action-secondary-border text-white"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
