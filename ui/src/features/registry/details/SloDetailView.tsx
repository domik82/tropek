import { useState } from 'react'
import { GitBranch, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DeletionConfirmForm } from '@/components/DeletionConfirmForm'
import { useSloDetail, useSloVersions, useDeleteSlo } from '@/features/slos/hooks'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import type { SloDefinition } from '@/features/slos/types'
import type { SelectedNode } from '@/features/registry/types'

interface SloDetailViewProps {
  name: string
  onNavigate: (node: SelectedNode) => void
  onNewVersion: (slo: SloDefinition) => void
}

export function SloDetailView({ name, onNavigate, onNewVersion }: SloDetailViewProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const { data: slo, isLoading } = useSloDetail(name)
  const { data: versions } = useSloVersions(name, true)
  const deleteMutation = useDeleteSlo()

  if (isLoading || !slo) {
    return (
      <div className="p-4 text-sm text-muted-foreground" style={{ fontFamily: SANS_SERIF }}>
        Loading...
      </div>
    )
  }

  const comparison = slo.comparison as {
    compare_with?: string
    number_of_comparison_results?: number
    include_result_with_score?: string
    aggregate_function?: string
  }

  function handleDeactivate(_reason: string, _author: string) {
    deleteMutation.mutate(slo!.name)
    setShowDeleteConfirm(false)
  }

  return (
    <div className="flex flex-col h-full overflow-auto" style={{ fontFamily: SANS_SERIF }}>
      {/* Accent strip */}
      <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.slo }} />

      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-foreground truncate">
              {slo.display_name ?? slo.name}
            </h2>
            <p className="text-xs font-mono text-muted-foreground mt-0.5">{slo.name}</p>
          </div>
          <div className="flex shrink-0 gap-1.5 items-center">
            <span
              className="px-2 py-0.5 text-xs rounded-full border border-border bg-muted/40 text-muted-foreground"
            >
              v{slo.version}
            </span>
            <span
              className={`px-2 py-0.5 text-xs rounded-full border ${
                slo.active
                  ? 'border-green-700/40 bg-green-950/20 text-green-400'
                  : 'border-border bg-muted/40 text-muted-foreground'
              }`}
            >
              {slo.active ? 'active' : 'inactive'}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2 mt-3">
          <Button size="xs" variant="outline" onClick={() => onNewVersion(slo)}>
            <GitBranch className="size-3" />
            New Version
          </Button>
          <Button
            size="xs"
            variant="outline"
            className="text-red-400 border-red-700/40 hover:bg-red-950/20"
            onClick={() => setShowDeleteConfirm(true)}
          >
            <Trash2 className="size-3" />
            Deactivate
          </Button>
        </div>

        {showDeleteConfirm && (
          <div className="mt-3">
            <DeletionConfirmForm
              title={`Deactivate SLO "${slo.name}"?`}
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
        {/* Objectives table */}
        <div>
          <p className="text-xs text-muted-foreground mb-2">Objectives</p>
          {slo.objectives.length === 0 ? (
            <p className="text-xs text-muted-foreground">No objectives defined.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-1.5 pr-3 text-muted-foreground font-medium">SLI</th>
                    <th className="text-left py-1.5 pr-3 text-muted-foreground font-medium">Weight</th>
                    <th className="text-left py-1.5 pr-3 text-muted-foreground font-medium">Key</th>
                    <th className="text-left py-1.5 pr-3 text-muted-foreground font-medium">Pass Criteria</th>
                    <th className="text-left py-1.5 text-muted-foreground font-medium">Warning Criteria</th>
                  </tr>
                </thead>
                <tbody>
                  {slo.objectives.map((obj, i) => (
                    <tr key={i} className="border-b border-border/40">
                      <td className="py-1.5 pr-3 font-mono align-top">
                        <button
                          type="button"
                          className="text-foreground hover:text-primary underline-offset-2 hover:underline"
                          onClick={() => onNavigate({ type: 'sli', name: obj.sli })}
                        >
                          {obj.sli}
                        </button>
                      </td>
                      <td className="py-1.5 pr-3 align-top text-foreground">{obj.weight}</td>
                      <td className="py-1.5 pr-3 align-top text-foreground">
                        {obj.key_sli ? (
                          <span style={{ color: ENTITY_COLORS.slo }}>★</span>
                        ) : null}
                      </td>
                      <td className="py-1.5 pr-3 align-top font-mono text-muted-foreground">
                        {obj.pass_criteria.join(' AND ')}
                      </td>
                      <td className="py-1.5 align-top font-mono text-muted-foreground">
                        {obj.warning_criteria.join(' AND ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Score thresholds */}
        <div>
          <p className="text-xs text-muted-foreground mb-1">Score Thresholds</p>
          <p className="text-sm text-foreground">
            Pass ≥ {slo.total_score_pass_pct}% · Warning ≥ {slo.total_score_warning_pct}%
          </p>
        </div>

        {/* Comparison summary */}
        {Object.keys(comparison).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Comparison</p>
            <p className="text-sm text-foreground font-mono">
              {[
                comparison.compare_with,
                comparison.number_of_comparison_results != null
                  ? `(${comparison.number_of_comparison_results})`
                  : undefined,
                comparison.include_result_with_score
                  ? `include: ${comparison.include_result_with_score}`
                  : undefined,
                comparison.aggregate_function
                  ? `aggregate: ${comparison.aggregate_function}`
                  : undefined,
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </div>
        )}

        {/* Tags */}
        {Object.keys(slo.tags).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Tags</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(slo.tags).map(([k, v]) => (
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

        {/* Variables */}
        {Object.keys(slo.variables).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Variables</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(slo.variables).map(([k, v]) => (
                <span
                  key={k}
                  className="px-2 py-0.5 text-xs rounded-full bg-muted/40 text-muted-foreground border border-border"
                >
                  {k}={v}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Notes */}
        {slo.notes && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Notes</p>
            <p className="text-sm text-foreground">{slo.notes}</p>
          </div>
        )}

        {/* Author */}
        {slo.author && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Author</p>
            <p className="text-sm text-foreground">{slo.author}</p>
          </div>
        )}

        {/* Linked Assets — placeholder */}
        <div>
          <p className="text-xs text-muted-foreground mb-2">Linked Assets</p>
          <p className="text-xs text-muted-foreground">No linked assets</p>
        </div>

        {/* Version history */}
        {versions && versions.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">
              Version History ({versions.length})
            </p>
            <ul className="space-y-1">
              {versions.map(v => (
                <li key={v.version} className="flex items-center gap-2 text-xs">
                  <span
                    className="px-1.5 py-0.5 rounded border border-border bg-muted/40 text-muted-foreground font-mono"
                  >
                    v{v.version}
                  </span>
                  <span className="text-muted-foreground">
                    {new Date(v.created_at).toLocaleDateString()}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
