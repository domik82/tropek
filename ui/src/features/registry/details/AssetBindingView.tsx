import { Link, Unlink, Pencil } from 'lucide-react'
import { BindingChainBreadcrumb } from '@/components/shared/BindingChainBreadcrumb'
import { VariableResolutionPanel } from '@/components/shared/VariableResolutionPanel'
import { SloObjectiveTable, useGroupSloBindings, useDeleteGroupSloBinding, useSloDetail } from '@/features/slos'
import type { SloBinding } from '@/features/slos'
import { useSliDetail } from '@/features/slis'
import { useAsset } from '@/features/assets'
import type { Asset } from '@/features/assets'
import type { SelectedNode } from '@/features/registry'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'

interface AssetBindingViewProps {
  assetName: string
  groupName: string
  /** true when a group node (not an asset) is selected */
  isGroup?: boolean
  onNavigate: (node: SelectedNode) => void
  onLinkSlo: () => void
}

export function AssetBindingView({
  assetName,
  groupName,
  isGroup,
  onNavigate,
  onLinkSlo,
}: AssetBindingViewProps) {
  // Only fetch asset details for actual asset nodes, not group nodes
  const { data: asset, isLoading: assetLoading } = useAsset(isGroup ? null : assetName)
  const { data: links, isLoading: linksLoading } = useGroupSloBindings(groupName)

  if ((!isGroup && assetLoading) || linksLoading) {
    return (
      <div className="p-6 text-sm text-muted-foreground" style={{ fontFamily: SANS_SERIF }}>
        Loading…
      </div>
    )
  }

  const bindings = links ?? []
  const varCount = Object.keys(asset?.variables ?? {}).length
  const tagCount = Object.keys(asset?.tags ?? {}).length
  const statsLine = isGroup
    ? `group · ${bindings.length} bindings`
    : [
        asset?.type_name ?? 'asset',
        varCount > 0 ? `${varCount} variables` : null,
        tagCount > 0 ? `${tagCount} tags` : null,
      ].filter(Boolean).join(' · ')

  return (
    <div className="overflow-auto h-full" style={{ fontFamily: SANS_SERIF }}>
      {/* Entity accent strip — group color */}
      <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.group }} />

      <div className="p-6 space-y-6">
      {/* Header — matches GroupDetailPanel layout */}
      <div>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold text-foreground">
              {asset?.display_name ?? assetName}
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">{statsLine}</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onLinkSlo}
              className="px-3 py-1.5 text-xs rounded bg-action-primary-bg border border-action-primary-border text-action-primary hover:bg-action-primary-hover transition-colors flex items-center gap-1.5"
            >
              <Link className="w-3.5 h-3.5" />
              Link SLO
            </button>
          </div>
        </div>

        {/* Variables row — monospace like GroupDetailPanel metadata */}
        {varCount > 0 && (
          <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
            {Object.entries(asset!.variables).map(([k, v]) => (
              <span key={k} className="font-mono">
                <span className="text-chip-var-key">{`$${k}`}</span>{` = ${v}`}
              </span>
            ))}
          </div>
        )}

        {/* Tag chips */}
        {tagCount > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {Object.entries(asset!.tags).map(([k, v]) => (
              <span
                key={k}
                className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary border border-primary/20"
              >
                {k}: {v}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* SLO Bindings section */}
      <div>
        <h3 className="text-sm font-semibold text-foreground mb-3">
          SLO Bindings ({bindings.length})
        </h3>

        {bindings.length === 0 ? (
          <p className="text-sm text-muted-foreground italic">No SLO bindings</p>
        ) : (
          <div className="space-y-4">
            {bindings.map(link => (
              <BindingCard
                key={link.id}
                link={link}
                asset={asset ?? null}
                groupName={groupName}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        )}
      </div>
    </div>{/* close p-6 wrapper */}
    </div>
  )
}

function BindingCard({
  link,
  asset,
  groupName,
  onNavigate,
}: {
  link: SloBinding
  asset: Asset | null
  groupName: string
  onNavigate: (node: SelectedNode) => void
}) {
  const { data: slo } = useSloDetail(link.slo_name)
  const sliName = slo?.sli_name ?? null
  const { data: sli } = useSliDetail(sliName ?? '')
  const deleteMutation = useDeleteGroupSloBinding()
  const assetVars = asset?.variables ?? {}
  const sloVars = slo?.variables ?? {}
  const reserved: Record<string, string> = {}

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      {/* Binding header — dark bg like table headers */}
      <div className="flex items-center justify-between gap-2 px-3 py-2.5 bg-table-header-bg border-b border-border">
        <BindingChainBreadcrumb
          sloName={link.slo_name}
          sloVersion={slo ? String(slo.version) : undefined}
          sliName={sliName ?? undefined}
          dsName={link.data_source_name}
          onClickSlo={() => onNavigate({ type: 'slo', name: link.slo_name })}
          onClickSli={sliName ? () => onNavigate({ type: 'sli', name: sliName }) : undefined}
          onClickDs={() => onNavigate({ type: 'datasource', name: link.data_source_name })}
        />
        <div className="flex shrink-0 gap-2">
          <button
            onClick={() => onNavigate({ type: 'slo', name: link.slo_name })}
            className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5"
          >
            <Pencil className="w-3.5 h-3.5" />
            Edit
          </button>
          <button
            onClick={() => deleteMutation.mutate({ groupName, sloName: link.slo_name })}
            className="px-3 py-1.5 text-xs rounded bg-action-destructive-bg border border-action-destructive-border text-action-destructive hover:bg-action-destructive-bg transition-colors flex items-center gap-1.5"
          >
            <Unlink className="w-3.5 h-3.5" />
            Unlink
          </button>
        </div>
      </div>

      {/* Variable resolution */}
      {(Object.keys(assetVars).length > 0 || Object.keys(sloVars).length > 0 || Object.keys(reserved).length > 0) && (
        <div className="px-3 pt-3">
          <VariableResolutionPanel
            assetVariables={assetVars}
            sloVariables={sloVars}
            reserved={reserved}
          />
        </div>
      )}

      {/* Objectives — REUSE SloObjectiveTable */}
      {slo && slo.objectives.length > 0 && (
        <div className="p-3">
          <SloObjectiveTable slo={slo} indicators={sli?.indicators} />
        </div>
      )}

      {/* Loading state */}
      {!slo && (
        <div className="p-3 text-sm text-muted-foreground">Loading SLO details…</div>
      )}
    </div>
  )
}
