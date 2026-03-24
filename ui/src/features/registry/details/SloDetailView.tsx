import { useState, useMemo } from 'react'
import { useQueries } from '@tanstack/react-query'
import { GitBranch, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DeletionConfirmForm } from '@/components/DeletionConfirmForm'
import { SloObjectiveTable } from '@/features/slos/components/SloObjectiveTable'
import { useSloDetail, useSloVersions, useDeleteSlo, useGroupTree } from '@/features/slos/hooks'
import { fetchGroupSloLinks } from '@/features/slos/api'
import { groupKeys } from '@/lib/queryKeys'
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

  // Fetch linked groups: query each group's links and filter to this SLO
  const { data: tree } = useGroupTree()
  const groupNames = useMemo(
    () => (tree?.all_groups ?? []).map(g => g.name).filter(n => n !== '__ungrouped__'),
    [tree],
  )
  const linkQueries = useQueries({
    queries: groupNames.map(gn => ({
      queryKey: groupKeys.links(gn),
      queryFn: () => fetchGroupSloLinks(gn),
    })),
  })
  const linkedGroups = useMemo(
    () => groupNames.filter((_, i) => (linkQueries[i]?.data ?? []).some(l => l.slo_name === name)),
    [groupNames, linkQueries, name],
  )

  if (isLoading || !slo) {
    return (
      <div className="p-4 text-sm text-muted-foreground" style={{ fontFamily: SANS_SERIF }}>
        Loading...
      </div>
    )
  }

  const comparison = slo.comparison

  function handleDeactivate(_reason: string, _author: string) {
    deleteMutation.mutate(slo!.name)
    setShowDeleteConfirm(false)
  }

  return (
    <div className="overflow-auto h-full" style={{ fontFamily: SANS_SERIF }}>
      {/* Accent strip */}
      <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.slo }} />

      <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h2 className="text-xl font-semibold text-foreground truncate">
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

        {/* Objectives table — reuse Navigator's shared component */}
        <div>
          <SloObjectiveTable slo={slo} />
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

        {/* Linked Groups */}
        <div>
          <p className="text-xs text-muted-foreground mb-2">
            Linked Groups ({(linkedGroups ?? []).length})
          </p>
          {(linkedGroups ?? []).length === 0 ? (
            <p className="text-xs text-muted-foreground">No groups linked to this SLO</p>
          ) : (
            <ul className="space-y-1">
              {(linkedGroups ?? []).map(gn => (
                <li key={gn}>
                  <button
                    type="button"
                    className="text-sm text-primary hover:underline cursor-pointer"
                    onClick={() => onNavigate({ type: 'group', name: gn })}
                  >
                    {gn}
                  </button>
                </li>
              ))}
            </ul>
          )}
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
