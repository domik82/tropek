interface VariableResolutionPanelProps {
  assetVariables: Record<string, string>
  sloVariables: Record<string, string>
  reserved: Record<string, string>
}

const SECTIONS: {
  key: keyof VariableResolutionPanelProps
  label: string
}[] = [
  { key: 'assetVariables', label: 'asset.variables:' },
  { key: 'sloVariables', label: 'slo.variables:' },
  { key: 'reserved', label: 'reserved:' },
]

function VariableEntries({ vars }: { vars: Record<string, string> }) {
  return (
    <span className="ml-2">
      {Object.entries(vars).map(([k, v], i) => (
        <span key={k}>
          {i > 0 && '  '}
          <span style={{ color: 'var(--primary)' }}>${k}</span>
          <span className="text-muted-foreground">=</span>
          <span>{v}</span>
        </span>
      ))}
    </span>
  )
}

export function VariableResolutionPanel({
  assetVariables,
  sloVariables,
  reserved,
}: VariableResolutionPanelProps) {
  const data: VariableResolutionPanelProps = {
    assetVariables,
    sloVariables,
    reserved,
  }

  const visibleSections = SECTIONS.filter(
    (s) => Object.keys(data[s.key]).length > 0
  )

  if (visibleSections.length === 0) return null

  return (
    <div
      className="rounded-md border border-border bg-muted p-3 text-sm"
      style={{ fontFamily: 'monospace' }}
    >
      {visibleSections.map((section) => (
        <div key={section.key} className="leading-relaxed">
          <span className="text-muted-foreground">{section.label}</span>
          <VariableEntries vars={data[section.key]} />
        </div>
      ))}
    </div>
  )
}
