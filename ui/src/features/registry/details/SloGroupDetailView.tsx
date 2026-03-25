import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DeletionConfirmForm } from '@/components/DeletionConfirmForm'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import { useSloGroupDetail, useDeleteSloGroup } from '@/features/slo-groups/hooks'
import type { SelectedNode } from '@/features/registry/types'

interface Props {
  name: string
  onNavigate: (node: SelectedNode) => void
}

export function SloGroupDetailView({ name, onNavigate }: Props) {
  const [showDelete, setShowDelete] = useState(false)
  const { data: group, isLoading } = useSloGroupDetail(name)
  const deleteMutation = useDeleteSloGroup()

  if (isLoading || !group) {
    return (
      <div className="p-4 text-sm text-muted-foreground" style={{ fontFamily: SANS_SERIF }}>
        Loading...
      </div>
    )
  }

  function handleDelete(_reason: string, _author: string) {
    deleteMutation.mutate(group!.name)
    setShowDelete(false)
  }

  // Compute variable rows: transpose gen_variables map into row-oriented data
  const varKeys = Object.keys(group.gen_variables)
  const rowCount = Math.max(0, ...varKeys.map(k => group.gen_variables[k].length))
  const rows = Array.from({ length: rowCount }, (_, i) =>
    varKeys.map(k => group.gen_variables[k][i] ?? ''),
  )

  return (
    <div className="overflow-auto h-full" style={{ fontFamily: SANS_SERIF }}>
      <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.sloGroup }} />
      <div className="p-6 space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h2 className="text-xl font-semibold text-foreground truncate">
                {group.display_name ?? group.name}
              </h2>
              <p className="text-xs font-mono text-muted-foreground mt-0.5">{group.name}</p>
            </div>
            <span className="px-2 py-0.5 text-xs rounded-full border border-border bg-muted/40 text-muted-foreground shrink-0">
              v{group.version}
            </span>
          </div>

          <div className="flex gap-2 mt-3">
            <Button
              size="xs"
              variant="outline"
              className="text-red-400 border-red-700/40 hover:bg-red-950/20"
              onClick={() => setShowDelete(true)}
            >
              <Trash2 className="size-3" />
              Delete Group
            </Button>
          </div>

          {showDelete && (
            <div className="mt-3">
              <DeletionConfirmForm
                title={`Delete group "${group.name}"?`}
                onConfirm={handleDelete}
                onCancel={() => setShowDelete(false)}
                confirmLabel="Delete"
                pendingLabel="Deleting…"
                isPending={deleteMutation.isPending}
                requireReason={false}
              />
            </div>
          )}
        </div>

        {/* Template link */}
        <div>
          <p className="text-xs text-muted-foreground mb-1">Template SLO</p>
          <button
            className="text-sm text-primary hover:underline"
            onClick={() => onNavigate({ type: 'template', name: group.template_slo_name })}
          >
            {group.template_slo_name} v{group.template_slo_version}
          </button>
        </div>

        {/* Generated count */}
        <div>
          <p className="text-sm text-foreground">{group.generated_slo_count} SLOs generated</p>
        </div>

        {/* Gen variables table */}
        {varKeys.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Generator Variables</p>
            <div className="border border-border rounded overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-muted/30">
                    {varKeys.map(k => (
                      <th
                        key={k}
                        className="text-left px-3 py-1.5 text-muted-foreground font-medium"
                      >
                        {k}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={i} className="border-t border-border/50">
                      {row.map((val, j) => (
                        <td key={j} className="px-3 py-1.5 text-foreground font-mono">
                          {val}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tags */}
        {Object.keys(group.tags).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Tags</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(group.tags).map(([k, v]) => (
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

        {/* Author */}
        {group.author && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Author</p>
            <p className="text-sm text-foreground">{group.author}</p>
          </div>
        )}
      </div>
    </div>
  )
}
