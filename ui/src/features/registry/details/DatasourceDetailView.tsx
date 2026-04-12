import { useState } from 'react'
import { Pencil, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DeletionConfirmForm } from '@/components/DeletionConfirmForm'
import { useDatasource, useDeleteDatasource } from '@/features/datasources'
import { useSliDefinitions } from '@/features/slis'
import type { SelectedNode } from '@/features/registry'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'

interface DatasourceDetailViewProps {
  name: string
  onNavigate: (node: SelectedNode) => void
  onEdit: () => void
}

export function DatasourceDetailView({ name, onNavigate, onEdit }: DatasourceDetailViewProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const { data: ds, isLoading } = useDatasource(name)
  const { data: slis } = useSliDefinitions()
  const deleteMutation = useDeleteDatasource()

  if (isLoading || !ds) {
    return (
      <div className="p-4 text-sm text-muted-foreground" style={{ fontFamily: SANS_SERIF }}>
        Loading...
      </div>
    )
  }

  const usedBySlis = (slis ?? []).filter(s => s.adapterType === ds.adapterType)

  function handleDelete() {
    deleteMutation.mutate(ds!.name)
    setShowDeleteConfirm(false)
  }

  return (
    <div className="overflow-auto h-full" style={{ fontFamily: SANS_SERIF }}>
      {/* Accent strip */}
      <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.ds }} />

      <div className="p-6 space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h2 className="text-xl font-semibold text-foreground truncate">
                {ds.displayName ?? ds.name}
              </h2>
              <p className="text-xs font-mono text-muted-foreground mt-0.5">{ds.name}</p>
            </div>
            <span
              className="shrink-0 px-2 py-0.5 text-xs rounded-full border border-border bg-muted/40 text-muted-foreground"
            >
              {ds.adapterType}
            </span>
          </div>

          {/* Actions */}
          <div className="flex gap-2 mt-3">
            <Button size="xs" variant="outline" onClick={onEdit}>
              <Pencil className="size-3" />
              Edit
            </Button>
            <Button
              size="xs"
              variant="outline"
              className="text-destructive-form-text border-destructive-form-border hover:bg-destructive-form-bg"
              onClick={() => setShowDeleteConfirm(true)}
            >
              <Trash2 className="size-3" />
              Delete
            </Button>
          </div>

          {showDeleteConfirm && (
            <div className="mt-3">
              <DeletionConfirmForm
                title={`Delete datasource "${ds.name}"?`}
                onConfirm={handleDelete}
                onCancel={() => setShowDeleteConfirm(false)}
                confirmLabel="Delete"
                pendingLabel="Deleting…"
                isPending={deleteMutation.isPending}
                requireReason={false}
              />
            </div>
          )}
        </div>
        {/* Adapter URL */}
        <div>
          <p className="text-xs text-muted-foreground mb-1">Adapter URL</p>
          <p className="text-sm font-mono break-all">{ds.adapterUrl}</p>
        </div>

        {/* Token */}
        <div>
          <p className="text-xs text-muted-foreground mb-1">Token</p>
          <p className="text-sm">{ds.hasToken ? '••••••••' : 'None'}</p>
        </div>

        {/* Tags */}
        {Object.keys(ds.tags).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Tags</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(ds.tags).map(([k, v]) => (
                <span
                  key={k}
                  className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary border border-primary/20"
                >
                  {k}: {v}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Used by SLIs */}
        <div>
          <p className="text-xs text-muted-foreground mb-2">
            Used by ({usedBySlis.length} SLI{usedBySlis.length !== 1 ? 's' : ''})
          </p>
          {usedBySlis.length === 0 ? (
            <p className="text-xs text-muted-foreground">No SLIs use this datasource type.</p>
          ) : (
            <ul className="space-y-1">
              {usedBySlis.map(sli => (
                <li key={sli.name}>
                  <button
                    type="button"
                    className="text-sm text-primary hover:underline cursor-pointer"
                    onClick={() => onNavigate({ type: 'sli', name: sli.name })}
                  >
                    {sli.displayName ?? sli.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
