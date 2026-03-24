import { useState, useEffect, useRef } from 'react'
import { SANS_SERIF } from '@/lib/fonts'
import { useCreateSlo } from '@/features/slos/hooks'
import { useSliDetail } from '@/features/slis/hooks'
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
      ? { sliName: editSlo.sli_name ?? '', sliVersion: editSlo.sli_version ?? null, indicators: Object.fromEntries(editSlo.objectives.map((o) => [o.sli, ''])) }
      : { sliName: '', sliVersion: null, indicators: {} },
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

  // In edit mode, fetch the full SLI definition to show ALL indicators
  // (not just the subset used by the current SLO objectives)
  const { data: fullSli } = useSliDetail(editSlo?.sli_name ?? '')
  const sliMergedRef = useRef(false)
  useEffect(() => {
    if (sliMergedRef.current || !fullSli || !isEdit) return
    sliMergedRef.current = true
    // Update pickSli with full indicators from the SLI definition
    setPickSli((prev) => ({
      ...prev,
      sliVersion: fullSli.version,
      indicators: fullSli.indicators,
    }))
    // Merge full SLI indicators into indicator rows — existing objectives
    // keep their checked=true + criteria, new ones get checked=false
    const allNames = Object.keys(fullSli.indicators)
    setIndicatorRows((prev) =>
      allNames.map((name) => {
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
  }, [fullSli, isEdit])

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
        sli_name: pickSli.sliName || undefined,
        sli_version: pickSli.sliVersion ?? undefined,
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
    <div className="p-6 space-y-6" style={{ fontFamily: SANS_SERIF }}>
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-foreground">{title}</h1>
        {subtitle && <p className="text-sm text-muted-foreground mt-0.5">{subtitle}</p>}
      </div>

      {/* Steps in card wrappers */}
      <section className="border border-slate-700 rounded-lg p-5">
        <WizardStepIdentity data={identity} onChange={setIdentity} nameReadOnly={isEdit} />
      </section>

      {showStep2 && (
        <section className="border border-slate-700 rounded-lg p-5">
          <WizardStepPickSli
            data={pickSli}
            onChange={handlePickSliChange}
            editIndicatorNames={editSlo ? editSlo.objectives.map((o) => o.sli) : undefined}
          />
        </section>
      )}

      {showStep3 && (
        <section className="border border-slate-700 rounded-lg p-5">
          <WizardStepIndicators rows={indicatorRows} onChange={setIndicatorRows} />
        </section>
      )}

      {showStep4 && (
        <section className="border border-slate-700 rounded-lg p-5">
          <WizardStepComparison data={comparison} onChange={setComparison} />
        </section>
      )}

      {/* Mutation error banner */}
      {createMutation.isError && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          <p className="font-medium">Save failed</p>
          <p className="mt-0.5 text-xs opacity-80">
            {createMutation.error instanceof Error ? createMutation.error.message : 'Unknown error'}
          </p>
        </div>
      )}

      {/* Submit buttons — inline at bottom of scroll, not fixed */}
      <div className="flex justify-end gap-2 pt-2 border-t border-slate-700">
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:text-foreground transition-colors"
          >
            Cancel
          </button>
        )}
        <button
          type="button"
          disabled={!isValid || createMutation.isPending}
          onClick={handleSubmit}
          className="px-3 py-1.5 text-xs font-medium rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {submitLabel}
        </button>
      </div>
    </div>
  )
}
