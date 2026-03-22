import { Link2, Unlink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { BindingChainBreadcrumb } from '@/components/shared/BindingChainBreadcrumb'
import { useGroupSloLinks, useDeleteGroupSloLink } from '@/features/slos/hooks'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import type { SelectedNode } from '@/features/registry/types'

interface AssetBindingViewProps {
  assetName: string
  groupName: string
  onNavigate: (node: SelectedNode) => void
  onLinkSlo: () => void
}

export function AssetBindingView({
  assetName,
  groupName,
  onNavigate,
  onLinkSlo,
}: AssetBindingViewProps) {
  const { data: links, isLoading } = useGroupSloLinks(groupName)
  const deleteMutation = useDeleteGroupSloLink()

  if (isLoading) {
    return (
      <div className="p-4 text-sm text-muted-foreground" style={{ fontFamily: SANS_SERIF }}>
        Loading...
      </div>
    )
  }

  const bindings = links ?? []

  return (
    <div className="flex flex-col h-full overflow-auto" style={{ fontFamily: SANS_SERIF }}>
      {/* Accent strip */}
      <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.group }} />

      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-foreground truncate">{assetName}</h2>
            <p className="text-xs text-muted-foreground mt-0.5">SLO Bindings</p>
          </div>
          <Button size="xs" variant="outline" onClick={onLinkSlo}>
            <Link2 className="size-3" />
            Link SLO
          </Button>
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {bindings.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-8 text-center">
            <p className="text-sm text-muted-foreground">No SLO bindings</p>
            <Button size="xs" variant="outline" onClick={onLinkSlo}>
              <Link2 className="size-3" />
              Link an SLO
            </Button>
          </div>
        ) : (
          bindings.map(link => (
            <div
              key={link.id}
              className="rounded-md border border-border bg-popover p-3 space-y-2"
            >
              <BindingChainBreadcrumb
                sloName={link.slo_name}
                sliName={link.sli_name}
                dsName={link.data_source_name}
                onClickSlo={() => onNavigate({ type: 'slo', name: link.slo_name })}
                onClickSli={() => onNavigate({ type: 'sli', name: link.sli_name })}
                onClickDs={() => onNavigate({ type: 'datasource', name: link.data_source_name })}
              />
              <div className="flex justify-end">
                <Button
                  size="xs"
                  variant="outline"
                  className="text-red-400 border-red-700/40 hover:bg-red-950/20"
                  onClick={() =>
                    deleteMutation.mutate({ groupName, linkName: link.link_name })
                  }
                >
                  <Unlink className="size-3" />
                  Unlink
                </Button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
