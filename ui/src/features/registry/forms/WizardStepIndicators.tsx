import { Plus, Minus } from 'lucide-react'
import { StructuredCriteriaInput } from '@/components/shared/StructuredCriteriaInput'
import type { CriteriaParts } from './criteriaUtils'

export interface IndicatorRow {
  sli: string
  checked: boolean
  weight: number
  key_sli: boolean
  passCriteria: CriteriaParts[]
  warnCriteria: CriteriaParts[]
}

interface WizardStepIndicatorsProps {
  rows: IndicatorRow[]
  onChange: (rows: IndicatorRow[]) => void
}

const DEFAULT_CRITERIA: CriteriaParts = {
  operator: '<',
  sign: null,
  value: 0,
  percent: false,
}

export function WizardStepIndicators({ rows, onChange }: WizardStepIndicatorsProps) {
  function updateRow(index: number, patch: Partial<IndicatorRow>) {
    onChange(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  }

  function toggleCheck(index: number) {
    updateRow(index, { checked: !rows[index].checked })
  }

  function addCriterion(index: number) {
    const row = rows[index]
    updateRow(index, {
      passCriteria: [...row.passCriteria, { ...DEFAULT_CRITERIA }],
      warnCriteria: [...row.warnCriteria, { ...DEFAULT_CRITERIA }],
    })
  }

  function removeCriterion(rowIndex: number, criterionIndex: number) {
    const row = rows[rowIndex]
    if (row.passCriteria.length <= 1) return
    updateRow(rowIndex, {
      passCriteria: row.passCriteria.filter((_, i) => i !== criterionIndex),
      warnCriteria: row.warnCriteria.filter((_, i) => i !== criterionIndex),
    })
  }

  function updatePassCriteria(rowIndex: number, criterionIndex: number, parts: CriteriaParts) {
    const row = rows[rowIndex]
    const updated = row.passCriteria.map((c, i) => (i === criterionIndex ? parts : c))
    updateRow(rowIndex, { passCriteria: updated })
  }

  function updateWarnCriteria(rowIndex: number, criterionIndex: number, parts: CriteriaParts) {
    const row = rows[rowIndex]
    const updated = row.warnCriteria.map((c, i) => (i === criterionIndex ? parts : c))
    updateRow(rowIndex, { warnCriteria: updated })
  }

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Step 3 — Indicators & Criteria
        </h3>
        <p className="text-xs text-muted-foreground mt-1">
          Multiple criteria = AND logic. Use + to add.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-xs text-muted-foreground">
              <th className="py-2 px-2 text-left w-8" />
              <th className="py-2 px-2 text-left">Indicator</th>
              <th className="py-2 px-2 text-left w-14">Wt</th>
              <th className="py-2 px-2 text-left w-10">Key</th>
              <th className="py-2 px-2 text-left">PASS CRITERIA</th>
              <th className="py-2 px-2 text-left">WARNING CRITERIA</th>
              <th className="py-2 px-2 text-left w-8" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIdx) => (
              <IndicatorRowView
                key={row.sli}
                row={row}
                rowIndex={rowIdx}
                onToggle={() => toggleCheck(rowIdx)}
                onWeightChange={(w) => updateRow(rowIdx, { weight: w })}
                onKeyChange={(k) => updateRow(rowIdx, { key_sli: k })}
                onAddCriterion={() => addCriterion(rowIdx)}
                onRemoveCriterion={(ci) => removeCriterion(rowIdx, ci)}
                onPassChange={(ci, parts) => updatePassCriteria(rowIdx, ci, parts)}
                onWarnChange={(ci, parts) => updateWarnCriteria(rowIdx, ci, parts)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

interface IndicatorRowViewProps {
  row: IndicatorRow
  rowIndex: number
  onToggle: () => void
  onWeightChange: (weight: number) => void
  onKeyChange: (key: boolean) => void
  onAddCriterion: () => void
  onRemoveCriterion: (criterionIndex: number) => void
  onPassChange: (criterionIndex: number, parts: CriteriaParts) => void
  onWarnChange: (criterionIndex: number, parts: CriteriaParts) => void
}

function IndicatorRowView({
  row,
  onToggle,
  onWeightChange,
  onKeyChange,
  onAddCriterion,
  onRemoveCriterion,
  onPassChange,
  onWarnChange,
}: IndicatorRowViewProps) {
  if (!row.checked) {
    return (
      <tr className="border-b border-border/50 opacity-40">
        <td className="py-2 px-2">
          <input type="checkbox" checked={false} onChange={onToggle} />
        </td>
        <td className="py-2 px-2 font-mono text-xs">{row.sli}</td>
        <td colSpan={5} className="py-2 px-2 text-xs text-muted-foreground italic">
          (unchecked — will not be included)
        </td>
      </tr>
    )
  }

  const criteriaCount = row.passCriteria.length

  return (
    <>
      {row.passCriteria.map((passParts, ci) => (
        <tr
          key={`${row.sli}-${ci}`}
          className={ci === criteriaCount - 1 ? 'border-b border-border' : ''}
        >
          {ci === 0 && (
            <>
              <td className="py-2 px-2" rowSpan={criteriaCount}>
                <input type="checkbox" checked={true} onChange={onToggle} />
              </td>
              <td className="py-2 px-2 font-mono text-xs" rowSpan={criteriaCount}>
                {row.sli}
              </td>
              <td className="py-2 px-2" rowSpan={criteriaCount}>
                <input
                  type="number"
                  className="w-12 rounded border border-border bg-popover px-1 py-0.5 text-xs"
                  value={row.weight}
                  onChange={(e) => onWeightChange(parseFloat(e.target.value) || 1)}
                  min={0}
                  step={1}
                />
              </td>
              <td className="py-2 px-2" rowSpan={criteriaCount}>
                <input
                  type="checkbox"
                  checked={row.key_sli}
                  onChange={(e) => onKeyChange(e.target.checked)}
                />
              </td>
            </>
          )}

          <td className="py-1 px-2">
            {ci > 0 && (
              <span className="inline-block mr-2 text-[10px] font-bold text-muted-foreground uppercase">
                AND
              </span>
            )}
            <div className="inline-flex items-center gap-1">
              <StructuredCriteriaInput
                value={passParts}
                onChange={(parts) => onPassChange(ci, parts)}
                showPreview
              />
            </div>
          </td>

          <td className="py-1 px-2">
            {ci > 0 && (
              <span className="inline-block mr-2 text-[10px] font-bold text-muted-foreground uppercase">
                AND
              </span>
            )}
            <div className="inline-flex items-center gap-1">
              <StructuredCriteriaInput
                value={row.warnCriteria[ci] ?? { ...DEFAULT_CRITERIA }}
                onChange={(parts) => onWarnChange(ci, parts)}
                showPreview
              />
            </div>
          </td>

          <td className="py-1 px-2">
            {ci === 0 ? (
              <button
                type="button"
                aria-label="add criterion"
                onClick={onAddCriterion}
                className="text-muted-foreground hover:text-primary"
              >
                <Plus className="size-3.5" />
              </button>
            ) : (
              <button
                type="button"
                aria-label="remove criterion"
                onClick={() => onRemoveCriterion(ci)}
                className="text-muted-foreground hover:text-red-400"
              >
                <Minus className="size-3.5" />
              </button>
            )}
          </td>
        </tr>
      ))}
    </>
  )
}
