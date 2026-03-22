import type { CriteriaParts, Operator, Sign } from '@/features/registry/forms/criteriaUtils'
import { serializeCriteria } from '@/features/registry/forms/criteriaUtils'

const OPERATORS: Operator[] = ['<', '<=', '>', '>=', '=']
const SIGNS: Array<{ label: string; value: Sign | null }> = [
  { label: '\u2014', value: null },
  { label: '+', value: '+' },
  { label: '-', value: '-' },
]

const sansSerif = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

interface StructuredCriteriaInputProps {
  value: CriteriaParts
  onChange: (parts: CriteriaParts) => void
  showPreview?: boolean
}

export function StructuredCriteriaInput({
  value,
  onChange,
  showPreview,
}: StructuredCriteriaInputProps) {
  return (
    <div className="flex items-center gap-1.5" style={{ fontFamily: sansSerif }}>
      <select
        className="rounded border border-border bg-popover px-1.5 py-1 text-sm"
        value={value.operator}
        onChange={(e) => onChange({ ...value, operator: e.target.value as Operator })}
      >
        {OPERATORS.map((op) => (
          <option key={op} value={op}>
            {op}
          </option>
        ))}
      </select>

      <select
        className="rounded border border-border bg-popover px-1.5 py-1 text-sm"
        value={value.sign ?? ''}
        onChange={(e) =>
          onChange({ ...value, sign: (e.target.value || null) as Sign | null })
        }
      >
        {SIGNS.map((s) => (
          <option key={s.label} value={s.value ?? ''}>
            {s.label}
          </option>
        ))}
      </select>

      <input
        type="number"
        className="w-20 rounded border border-border bg-popover px-1.5 py-1 text-sm"
        value={value.value}
        onChange={(e) => onChange({ ...value, value: parseFloat(e.target.value) || 0 })}
      />

      <button
        type="button"
        className={`rounded px-2 py-1 text-sm font-medium ${
          value.percent
            ? 'bg-primary text-primary-foreground'
            : 'border border-border bg-popover text-muted-foreground'
        }`}
        onClick={() => onChange({ ...value, percent: !value.percent })}
      >
        %
      </button>

      {showPreview && (
        <span className="ml-2 text-sm text-muted-foreground font-mono">
          {serializeCriteria(value)}
        </span>
      )}
    </div>
  )
}
