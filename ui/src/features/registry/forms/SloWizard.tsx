import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import { useCreateSlo } from '@/features/slos/hooks'
import { serializeCriteria, parseCriteria, DEFAULT_CRITERIA } from './criteriaUtils'
import { tagsToRows, rowsToTags } from './tagUtils'
import { WizardStepIdentity } from './WizardStepIdentity'
import { WizardStepPickSli } from './WizardStepPickSli'
import { WizardStepIndicators } from './WizardStepIndicators'
import { WizardStepComparison } from './WizardStepComparison'
import type { IdentityData } from './WizardStepIdentity'
import type { PickSliData } from './WizardStepPickSli'
import type { IndicatorRow } from './WizardStepIndicators'
import type { ComparisonData } from './WizardStepComparison'
import type { SloDefinition } from '@/features/slos/types'

interface SloWizardProps {
  editSlo?: SloDefinition
  onClose?: () => void
}

function buildIdentityFromEdit(slo: SloDefinition): IdentityData {
  return {
    name: slo.name,
    display_name: slo.display_name ?? '',
    author: slo.author ?? '',
    notes: slo.notes ?? '',
  }
}

function buildIndicatorRowsFromEdit(slo: SloDefinition): IndicatorRow[] {
  return slo.objectives.map((obj) => ({
    sli: obj.sli,
    checked: true,
    weight: obj.weight,
    key_sli: obj.key_sli,
    passCriteria: obj.pass_criteria.length > 0
      ? obj.pass_criteria.map((c) => parseCriteria(c) ?? { ...DEFAULT_CRITERIA })
      : [{ ...DEFAULT_CRITERIA }],
    warnCriteria: obj.warning_criteria.length > 0
      ? obj.warning_criteria.map((c) => parseCriteria(c) ?? { ...DEFAULT_CRITERIA })
      : [{ ...DEFAULT_CRITERIA }],
  }))
}

function buildComparisonFromEdit(slo: SloDefinition): ComparisonData {
  const comp = slo.comparison
  return {
    baseline_mode: comp.baseline_mode === 'manual' ? 'manual' : 'previous',
    compare_count: comp.number_of_comparison_results ?? 3,
    aggregate_function: comp.aggregate_function ?? 'avg',
    include_result_with_score: comp.include_result_with_score ?? 'pass_or_warn',
    pass_pct: slo.total_score_pass_pct,
    warn_pct: slo.total_score_warning_pct,
    tags: tagsToRows(slo.tags),
    variables: Object.entries(slo.variables).map(([key, value]) => ({ key, value })),
  }
}

export function SloWizard({ editSlo, onClose }: SloWizardProps) {
  const isEdit = !!editSlo

  const [identity, setIdentity] = useState<IdentityData>(
    editSlo ? buildIdentityFromEdit(editSlo) : { name: '', display_name: '', author: '', notes: '' },
  )

  const [pickSli, setPickSli] = useState<PickSliData>(
    editSlo
      ? { datasource: '', sliName: '', indicators: Object.fromEntries(editSlo.objectives.map((o) => [o.sli, ''])) }
      : { datasource: '', sliName: '', indicators: {} },
  )

  const [indicatorRows, setIndicatorRows] = useState<IndicatorRow[]>(
    editSlo ? buildIndicatorRowsFromEdit(editSlo) : [],
  )

  const [comparison, setComparison] = useState<ComparisonData>(
    editSlo
      ? buildComparisonFromEdit(editSlo)
      : {
          baseline_mode: 'previous',
          compare_count: 3,
          aggregate_function: 'avg',
          include_result_with_score: 'pass_or_warn',
          pass_pct: 90,
          warn_pct: 75,
          tags: [],
          variables: [],
        },
  )

  // Edit mode also calls POST — backend auto-increments version
  const createMutation = useCreateSlo()

  // Progressive disclosure: compute which steps are visible
  const showStep2 = identity.name.trim().length > 0
  const showStep3 = isEdit
    ? indicatorRows.length > 0
    : Object.keys(pickSli.indicators).length > 0
  const showStep4 = indicatorRows.some(
    (r) => r.checked && r.passCriteria.some((c) => c.value !== 0),
  )

  // When SLI selection changes, rebuild indicator rows
  function handlePickSliChange(data: PickSliData) {
    setPickSli(data)
    const names = Object.keys(data.indicators)
    if (names.length > 0) {
      setIndicatorRows((prev) =>
        names.map((name) => {
          const existing = prev.find((r) => r.sli === name)
          if (existing) return existing
          return {
            sli: name,
            checked: false,
            weight: 1,
            key_sli: false,
            passCriteria: [{ ...DEFAULT_CRITERIA }],
            warnCriteria: [{ ...DEFAULT_CRITERIA }],
          }
        }),
      )
    }
  }

  // Compute whether form is valid for submission
  const checkedRows = indicatorRows.filter((r) => r.checked)
  const isValid =
    identity.name.trim().length > 0 &&
    checkedRows.length > 0 &&
    checkedRows.every((r) => r.passCriteria.length > 0)

  function handleSubmit() {
    if (!isValid) return

    const objectives = checkedRows.map((row, idx) => ({
      sli: row.sli,
      display_name: row.sli,
      pass_criteria: row.passCriteria.map(serializeCriteria),
      warning_criteria: row.warnCriteria.map(serializeCriteria),
      weight: row.weight,
      key_sli: row.key_sli,
      sort_order: idx,
    }))

    const tags = rowsToTags(comparison.tags)
    const variables: Record<string, string> = {}
    for (const v of comparison.variables) {
      if (v.key.trim()) variables[v.key.trim()] = v.value
    }

    createMutation.mutate(
      {
        name: identity.name,
        display_name: identity.display_name || undefined,
        author: identity.author || undefined,
        notes: identity.notes || undefined,
        objectives,
        total_score_pass_pct: comparison.pass_pct,
        total_score_warning_pct: comparison.warn_pct,
        comparison: {
          baseline_mode: comparison.baseline_mode,
          number_of_comparison_results: comparison.compare_count,
          aggregate_function: comparison.aggregate_function,
          include_result_with_score: comparison.include_result_with_score,
        },
        tags: Object.keys(tags).length > 0 ? tags : undefined,
        variables: Object.keys(variables).length > 0 ? variables : undefined,
      },
      { onSuccess: () => onClose?.() },
    )
  }

  const title = isEdit
    ? `${editSlo!.name} \u00b7 New Version`
    : 'New SLO Definition'
  const subtitle = isEdit
    ? `Editing creates version ${editSlo!.version + 1} \u00b7 All fields pre-filled from v${editSlo!.version}`
    : undefined
  const submitLabel = createMutation.isPending
    ? 'Saving\u2026'
    : isEdit
      ? 'Create Version'
      : 'Create SLO'

  return (
    <div className="flex flex-col h-full bg-background" style={{ fontFamily: SANS_SERIF }}>
      {/* Accent strip */}
      <div className="h-[3px] shrink-0" style={{ backgroundColor: ENTITY_COLORS.slo }} />

      {/* Header */}
      <div className="px-6 py-4 border-b border-border shrink-0">
        <h1 className="text-lg font-semibold text-foreground">{title}</h1>
        {subtitle && (
          <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
        )}
      </div>

      {/* Wizard body — scrollable */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-8 max-w-5xl">
        {/* Step 1 — always visible */}
        <section>
          <WizardStepIdentity
            data={identity}
            onChange={setIdentity}
            nameReadOnly={isEdit}
          />
        </section>

        {/* Step 2 — when name filled */}
        {showStep2 && (
          <section>
            <WizardStepPickSli
              data={pickSli}
              onChange={handlePickSliChange}
              editIndicatorNames={editSlo ? editSlo.objectives.map((o) => o.sli) : undefined}
            />
          </section>
        )}

        {/* Step 3 — when SLI selected */}
        {showStep3 && (
          <section>
            <WizardStepIndicators rows={indicatorRows} onChange={setIndicatorRows} />
          </section>
        )}

        {/* Step 4 — when any indicator has pass criteria with value */}
        {showStep4 && (
          <section>
            <WizardStepComparison data={comparison} onChange={setComparison} />
          </section>
        )}
      </div>

      {/* Footer — sticky within wizard container */}
      <div className="shrink-0 flex justify-end gap-2 px-6 py-3 border-t border-border bg-background">
        {onClose && (
          <Button size="xs" variant="outline" type="button" onClick={onClose}>
            Cancel
          </Button>
        )}
        <Button
          size="xs"
          type="button"
          disabled={!isValid || createMutation.isPending}
          onClick={handleSubmit}
        >
          {submitLabel}
        </Button>
      </div>
    </div>
  )
}
