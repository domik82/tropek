import { useState } from 'react'
import { GitBranch, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DeletionConfirmForm } from '@/components/DeletionConfirmForm'
import { useSliDetail, useDeleteSli } from '@/features/slis/hooks'
import { useSlos } from '@/features/slos/hooks'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import type { SliDefinition } from '@/features/slis/types'
import type { SelectedNode } from '@/features/registry/types'

const VARIABLE_COLOR = '#FFA657'

interface SliDetailViewProps {
  name: string
  onNavigate: (node: SelectedNode) => void
  onNewVersion: (sli: SliDefinition) => void
}

function highlightVariables(query: string): React.ReactNode {
  // Split on $variableName tokens
  const parts = query.split(/(\$[a-zA-Z_][a-zA-Z0-9_]*)/)
  return parts.map((part, i) => {
    if (/^\$[a-zA-Z_][a-zA-Z0-9_]*$/.test(part)) {
      return (
        <span key={i} style={{ color: VARIABLE_COLOR }}>
          {part}
        </span>
      )
    }
    return part
  })
}

export function SliDetailView({ name, onNavigate, onNewVersion }: SliDetailViewProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const { data: sli, isLoading } = useSliDetail(name)
  const { data: slos } = useSlos()
  const deleteMutation = useDeleteSli()

  if (isLoading || !sli) {
    return (
      <div className="p-4 text-sm text-muted-foreground" style={{ fontFamily: SANS_SERIF }}>
        Loading...
      </div>
    )
  }

  // Find SLOs that reference this SLI in their objectives
  const usedBySlos = (slos ?? []).filter(s =>
    s.objectives.some(obj => obj.sli === sli.name)
  )

  function handleDeactivate(_reason: string, _author: string) {
    deleteMutation.mutate(sli!.name)
    setShowDeleteConfirm(false)
  }

  return (
    <div className="flex flex-col h-full overflow-auto" style={{ fontFamily: SANS_SERIF }}>
      {/* Accent strip */}
      <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.sli }} />

      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-foreground truncate">
              {sli.display_name ?? sli.name}
            </h2>
            <p className="text-xs font-mono text-muted-foreground mt-0.5">{sli.name}</p>
          </div>
          <div className="flex shrink-0 gap-1.5 items-center">
            <span
              className="px-2 py-0.5 text-xs rounded-full border border-border bg-muted/40 text-muted-foreground"
            >
              v{sli.version}
            </span>
            <span
              className="px-2 py-0.5 text-xs rounded-full border border-border bg-muted/40 text-muted-foreground"
            >
              {sli.adapter_type}
            </span>
            <span
              className={`px-2 py-0.5 text-xs rounded-full border ${
                sli.active
                  ? 'border-green-700/40 bg-green-950/20 text-green-400'
                  : 'border-border bg-muted/40 text-muted-foreground'
              }`}
            >
              {sli.active ? 'active' : 'inactive'}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2 mt-3">
          <Button size="xs" variant="outline" onClick={() => onNewVersion(sli)}>
            <GitBranch className="size-3" />
            New Version
          </Button>
          <Button
            size="xs"
            variant="outline"
            className="text-destructive-form-text border-destructive-form-border hover:bg-destructive-form-bg"
            onClick={() => setShowDeleteConfirm(true)}
          >
            <Trash2 className="size-3" />
            Deactivate
          </Button>
        </div>

        {showDeleteConfirm && (
          <div className="mt-3">
            <DeletionConfirmForm
              title={`Deactivate SLI "${sli.name}"?`}
              onConfirm={handleDeactivate}
              onCancel={() => setShowDeleteConfirm(false)}
              confirmLabel="Deactivate"
              pendingLabel="Deactivating…"
              isPending={deleteMutation.isPending}
              requireReason={false}
            />
          </div>
        )}
      </div>

      {/* Body */}
      <div className="p-4 space-y-4">
        {/* Indicators table */}
        <div>
          <p className="text-xs text-muted-foreground mb-2">Indicators</p>
          {Object.keys(sli.indicators).length === 0 ? (
            <p className="text-xs text-muted-foreground">No indicators defined.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-1.5 pr-3 text-muted-foreground font-medium w-1/3">
                      Name
                    </th>
                    <th className="text-left py-1.5 text-muted-foreground font-medium">
                      Query
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(sli.indicators).map(([metricName, query]) => (
                    <tr key={metricName} className="border-b border-border/40">
                      <td className="py-1.5 pr-3 font-mono align-top text-foreground">
                        {metricName}
                      </td>
                      <td className="py-1.5 font-mono text-muted-foreground break-all">
                        {highlightVariables(query)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Tags */}
        {Object.keys(sli.tags).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Tags</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(sli.tags).map(([k, v]) => (
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

        {/* Notes */}
        {sli.notes && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Notes</p>
            <p className="text-sm text-foreground">{sli.notes}</p>
          </div>
        )}

        {/* Author */}
        {sli.author && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Author</p>
            <p className="text-sm text-foreground">{sli.author}</p>
          </div>
        )}

        {/* Used by SLOs */}
        <div>
          <p className="text-xs text-muted-foreground mb-2">
            Used by ({usedBySlos.length} SLO{usedBySlos.length !== 1 ? 's' : ''})
          </p>
          {usedBySlos.length === 0 ? (
            <p className="text-xs text-muted-foreground">No SLOs use this SLI.</p>
          ) : (
            <ul className="space-y-1">
              {usedBySlos.map(s => (
                <li key={s.name}>
                  <button
                    type="button"
                    className="text-sm text-primary hover:underline cursor-pointer"
                    onClick={() => onNavigate({ type: 'slo', name: s.name })}
                  >
                    {s.name}
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
