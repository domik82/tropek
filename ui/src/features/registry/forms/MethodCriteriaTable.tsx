import type { MethodCriteriaOverride } from '@/features/slos/types'

interface MethodCriteriaTableProps {
  methods: string[]
  criteria: Record<string, MethodCriteriaOverride>
  blueprintPassCriteria: string[]
  blueprintWeight: number
  onChange: (criteria: Record<string, MethodCriteriaOverride>) => void
}

export function MethodCriteriaTable({
  methods,
  criteria,
  blueprintPassCriteria,
  blueprintWeight,
  onChange,
}: MethodCriteriaTableProps) {
  const blueprintPass = blueprintPassCriteria[0] ?? ''

  function getEffective(method: string) {
    const override = criteria[method]
    return {
      pass: override?.pass_threshold?.[0] ?? blueprintPass,
      weight: override?.weight ?? blueprintWeight,
      key_sli: override?.key_sli ?? false,
      hasPassOverride: override?.pass_threshold != null,
      hasWeightOverride: override?.weight != null,
      hasKeySliOverride: override?.key_sli != null,
    }
  }

  function updateMethod(method: string, patch: Partial<MethodCriteriaOverride>) {
    const prev = criteria[method] ?? {}
    const merged = { ...prev, ...patch }

    const cleaned: MethodCriteriaOverride = {}
    if (merged.pass_threshold && merged.pass_threshold[0] !== blueprintPass) {
      cleaned.pass_threshold = merged.pass_threshold
    }
    if (merged.weight != null && merged.weight !== blueprintWeight) {
      cleaned.weight = merged.weight
    }
    if (merged.key_sli != null && merged.key_sli !== false) {
      cleaned.key_sli = merged.key_sli
    }

    const next = { ...criteria }
    if (Object.keys(cleaned).length > 0) {
      next[method] = cleaned
    } else {
      delete next[method]
    }
    onChange(next)
  }

  return (
    <div>
      <p className="text-xs text-muted-foreground mb-2">
        Method Criteria — overrides per aggregation method
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="py-2 px-2 text-left">Method</th>
              <th className="py-2 px-2 text-left">Pass Criteria</th>
              <th className="py-2 px-2 text-left w-16">Weight</th>
              <th className="py-2 px-2 text-left w-12">Key</th>
            </tr>
          </thead>
          <tbody>
            {methods.map(method => {
              const eff = getEffective(method)
              return (
                <tr key={method} className="border-b border-border/50">
                  <td className="py-2 px-2 font-mono text-foreground">{method}</td>
                  <td className="py-2 px-2">
                    <input
                      type="text"
                      value={eff.pass}
                      onChange={e => updateMethod(method, { pass_threshold: [e.target.value] })}
                      className={`w-24 rounded border border-border bg-popover px-1.5 py-0.5 text-xs font-mono ${
                        eff.hasPassOverride ? 'text-foreground' : 'text-muted-foreground italic'
                      }`}
                    />
                  </td>
                  <td className="py-2 px-2">
                    <input
                      type="number"
                      value={eff.weight}
                      onChange={e =>
                        updateMethod(method, { weight: parseFloat(e.target.value) || 1 })
                      }
                      className={`w-14 rounded border border-border bg-popover px-1.5 py-0.5 text-xs ${
                        eff.hasWeightOverride ? 'text-foreground' : 'text-muted-foreground italic'
                      }`}
                      min={0}
                      step={1}
                    />
                  </td>
                  <td className="py-2 px-2">
                    <input
                      type="checkbox"
                      checked={eff.key_sli}
                      onChange={e => updateMethod(method, { key_sli: e.target.checked })}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
