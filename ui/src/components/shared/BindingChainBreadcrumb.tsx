import { ArrowRight } from 'lucide-react'

const SANS_SERIF = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

const ENTITY_COLORS = {
  slo: '#7dc540',
  sli: '#A371F7',
  ds: '#58A6FF',
} as const

interface BindingChainBreadcrumbProps {
  sloName: string
  sloVersion?: string
  sliName: string
  dsName: string
  onClickSlo: () => void
  onClickSli: () => void
  onClickDs: () => void
}

function Badge({
  label,
  version,
  color,
  onClick,
}: {
  label: string
  version?: string
  color: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-sm
        bg-popover hover:brightness-110 transition-colors cursor-pointer"
      style={{
        fontFamily: SANS_SERIF,
        border: `1.5px solid ${color}`,
        color: 'var(--foreground)',
      }}
    >
      <span>{label}</span>
      {version && (
        <span className="text-muted-foreground text-xs">v{version}</span>
      )}
    </button>
  )
}

export function BindingChainBreadcrumb({
  sloName,
  sloVersion,
  sliName,
  dsName,
  onClickSlo,
  onClickSli,
  onClickDs,
}: BindingChainBreadcrumbProps) {
  return (
    <div
      className="flex items-center gap-2"
      style={{ fontFamily: SANS_SERIF }}
    >
      <Badge
        label={sloName}
        version={sloVersion}
        color={ENTITY_COLORS.slo}
        onClick={onClickSlo}
      />
      <ArrowRight className="h-4 w-4 text-muted-foreground" />
      <Badge label={sliName} color={ENTITY_COLORS.sli} onClick={onClickSli} />
      <ArrowRight className="h-4 w-4 text-muted-foreground" />
      <Badge label={dsName} color={ENTITY_COLORS.ds} onClick={onClickDs} />
    </div>
  )
}
