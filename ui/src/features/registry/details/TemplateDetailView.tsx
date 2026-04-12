import { GitBranch } from 'lucide-react'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import { SloObjectiveTable } from '@/features/slos/components/SloObjectiveTable'
import { useSloDetail } from '@/features/slos/hooks'
import { useSloGroups } from '@/features/slo-groups'
import { Button } from '@/components/ui/button'
import type { Slo } from '@/features/slos'
import type { SelectedNode } from '@/features/registry/ui-types'

interface Props {
  name: string
  onNavigate: (node: SelectedNode) => void
  onNewVersion: (slo: Slo) => void
}

export function TemplateDetailView({ name, onNavigate, onNewVersion }: Props) {
  const { data: slo, isLoading } = useSloDetail(name)
  const { data: groups } = useSloGroups()

  if (isLoading || !slo) {
    return (
      <div className="p-4 text-sm text-muted-foreground" style={{ fontFamily: SANS_SERIF }}>
        Loading...
      </div>
    )
  }

  const referencingGroups = (groups ?? []).filter(
    g => g.templateSloName === slo.name && g.active,
  )

  return (
    <div className="overflow-auto h-full" style={{ fontFamily: SANS_SERIF }}>
      <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.template }} />
      <div className="p-6 space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h2 className="text-xl font-semibold text-foreground truncate">
                {slo.displayName ?? slo.name}
              </h2>
              <p className="text-xs font-mono text-muted-foreground mt-0.5">{slo.name}</p>
            </div>
            <div className="flex shrink-0 gap-1.5 items-center">
              <span className="px-2 py-0.5 text-xs rounded-full border border-border bg-muted/40 text-muted-foreground">
                v{slo.version}
              </span>
              <span
                className="px-2 py-0.5 text-xs rounded-full border"
                style={{
                  borderColor: `${ENTITY_COLORS.template}40`,
                  backgroundColor: `${ENTITY_COLORS.template}15`,
                  color: ENTITY_COLORS.template,
                }}
              >
                template
              </span>
            </div>
          </div>

          <div className="flex gap-2 mt-3">
            <Button size="sm" variant="outline" onClick={() => onNewVersion(slo)}>
              <GitBranch className="size-3.5" />
              New Version
            </Button>
          </div>
        </div>

        {/* SLI link */}
        {slo.sliName && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">SLI Definition</p>
            <button
              type="button"
              className="text-sm text-primary hover:underline cursor-pointer"
              onClick={() => onNavigate({ type: 'sli', name: slo.sliName! })}
            >
              {slo.sliName} v{slo.sliVersion}
            </button>
          </div>
        )}

        {/* Objectives */}
        {slo.objectives.length > 0 && (
          <div>
            <SloObjectiveTable slo={slo} />
          </div>
        )}

        {/* Variables — highlight $__gen_ placeholders */}
        {Object.keys(slo.variables).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Variables</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(slo.variables).map(([k, v]) => {
                const isGen = v.includes('$__gen_')
                return (
                  <span
                    key={k}
                    className={`px-2 py-0.5 text-xs rounded-full border ${
                      isGen
                        ? 'border-amber-600/30 bg-amber-950/20 text-amber-400'
                        : 'border-border bg-muted/40 text-muted-foreground'
                    }`}
                  >
                    {k}={v}
                  </span>
                )
              })}
            </div>
          </div>
        )}

        {/* Referencing groups */}
        <div>
          <p className="text-xs text-muted-foreground mb-2">
            Groups ({referencingGroups.length})
          </p>
          {referencingGroups.length === 0 ? (
            <p className="text-xs text-muted-foreground">No groups use this template</p>
          ) : (
            <ul className="space-y-1">
              {referencingGroups.map(g => (
                <li key={g.name}>
                  <button
                    type="button"
                    className="text-sm text-primary hover:underline cursor-pointer"
                    onClick={() => onNavigate({ type: 'slo-group', name: g.name })}
                  >
                    {g.displayName ?? g.name}
                  </button>
                  <span className="text-xs text-muted-foreground ml-2">
                    {g.generatedSloCount} SLOs
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

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
      </div>
    </div>
  )
}
