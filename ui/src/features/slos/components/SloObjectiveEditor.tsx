// src/features/slos/components/SloObjectiveEditor.tsx
import { useState } from 'react'
import { useFieldArray, useForm, Controller } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useCreateSlo, useSloValidation } from '../hooks'
import type { SloDefinition } from '../types'

const objectiveSchema = z.object({
  sli: z.string().min(1),
  display_name: z.string(),
  pass_criteria: z.string(),
  warning_criteria: z.string(),
  weight: z.coerce.number().min(0),
  key_sli: z.boolean(),
})

const formSchema = z.object({
  total_score_pass_pct: z.coerce.number().min(0).max(100),
  total_score_warning_pct: z.coerce.number().min(0).max(100),
  comparable_from_version: z.coerce.number().min(1).optional(),
  objectives: z.array(objectiveSchema),
})
type FormValues = z.infer<typeof formSchema>

interface Props {
  slo: SloDefinition
  onCancel: () => void
  onSaved: () => void
}

function IndicatorCombobox({
  value,
  onChange,
  indicators,
}: {
  value: string
  onChange: (v: string) => void
  indicators: string[]
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const filtered = indicators.filter(i => i.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="w-full text-left px-2 py-1.5 bg-surface-sunken border border-border rounded text-xs font-mono text-pass hover:border-border truncate"
      >
        {value || <span className="text-muted-foreground">Select indicator…</span>}
      </button>
      {open && (
        <div className="absolute z-10 mt-1 w-full bg-surface-sunken border border-border rounded shadow-lg max-h-48 overflow-y-auto">
          <input
            className="w-full px-2 py-1.5 bg-surface-sunken border-b border-border text-xs text-foreground placeholder:text-muted-foreground focus:outline-none"
            placeholder="Filter…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            autoFocus
          />
          {filtered.map(ind => (
            <button
              key={ind}
              type="button"
              className="w-full text-left px-2 py-1.5 text-xs font-mono text-pass hover:bg-state-hover-bg"
              onClick={() => { onChange(ind); setOpen(false); setSearch('') }}
            >
              {ind}
            </button>
          ))}
          {filtered.length === 0 && (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">No indicators found</p>
          )}
        </div>
      )}
    </div>
  )
}

export function SloObjectiveEditor({ slo, onCancel, onSaved }: Props) {
  const create = useCreateSlo()
  const validate = useSloValidation()
  const availableIndicators = slo.objectives.map(o => o.sli)

  const defaultObjectives = slo.objectives.map(obj => ({
    sli: obj.sli,
    display_name: obj.display_name,
    pass_criteria: obj.pass_criteria.join(', '),
    warning_criteria: obj.warning_criteria.join(', '),
    weight: obj.weight,
    key_sli: obj.key_sli,
  }))

  const { register, control, handleSubmit } = useForm<FormValues, unknown, FormValues>({
    resolver: zodResolver(formSchema) as import('react-hook-form').Resolver<FormValues>,
    defaultValues: {
      total_score_pass_pct: slo.total_score_pass_pct,
      total_score_warning_pct: slo.total_score_warning_pct,
      objectives: defaultObjectives,
    },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'objectives' })

  function buildPayload(values: FormValues) {
    return {
      objectives: values.objectives.map((obj, i) => ({
        sli: obj.sli,
        display_name: obj.display_name || obj.sli,
        pass_criteria: obj.pass_criteria ? obj.pass_criteria.split(',').map(s => s.trim()).filter(Boolean) : [],
        warning_criteria: obj.warning_criteria ? obj.warning_criteria.split(',').map(s => s.trim()).filter(Boolean) : [],
        weight: obj.weight,
        key_sli: obj.key_sli,
        sort_order: i,
      })),
      total_score_pass_pct: values.total_score_pass_pct,
      total_score_warning_pct: values.total_score_warning_pct,
      comparison: slo.comparison ?? {},
      comparable_from_version: values.comparable_from_version || undefined,
    }
  }

  function onSubmit(values: FormValues) {
    const payload = buildPayload(values)
    validate.mutate(payload, {
      onSuccess: (result) => {
        if (!result.valid) return
        create.mutate(
          {
            name: slo.name,
            display_name: slo.display_name ?? undefined,
            author: slo.author ?? undefined,
            notes: slo.notes ?? undefined,
            ...payload,
          },
          { onSuccess: () => onSaved() },
        )
      },
    })
  }

  const inp = 'w-full px-2 py-1.5 bg-surface-sunken border border-border rounded text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary'

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
      {/* Score thresholds */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Total Pass %</label>
          <input {...register('total_score_pass_pct')} type="number" min={0} max={100} className={inp} />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Total Warning %</label>
          <input {...register('total_score_warning_pct')} type="number" min={0} max={100} className={inp} />
        </div>
      </div>

      {/* Version compatibility */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[10px] text-muted-foreground mb-0.5">Comparable From Version</label>
          <input {...register('comparable_from_version')} type="number" min={1} className={inp} placeholder={`${slo.version}`} />
          <p className="text-[10px] text-muted-foreground/60 mt-0.5">Baselines from older versions are excluded</p>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="text-xs uppercase text-muted-foreground bg-table-header-bg border-b border-border">
            <tr>
              <th className="text-left px-2 py-2 min-w-[160px]">Indicator</th>
              <th className="text-left px-2 py-2 min-w-[140px]">Display Name</th>
              <th className="text-left px-2 py-2 min-w-[120px]">Pass Criteria</th>
              <th className="text-left px-2 py-2 min-w-[120px]">Warn Criteria</th>
              <th className="text-center px-2 py-2 w-16">Weight</th>
              <th className="text-center px-2 py-2 w-10">Key</th>
              <th className="w-8"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {fields.map((field, i) => (
              <tr key={field.id} className="hover:bg-state-hover-bg">
                <td className="px-2 py-1.5">
                  <Controller
                    control={control}
                    name={`objectives.${i}.sli`}
                    render={({ field: f }) => (
                      <IndicatorCombobox
                        value={f.value}
                        onChange={f.onChange}
                        indicators={availableIndicators}
                      />
                    )}
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    {...register(`objectives.${i}.display_name`)}
                    className="w-full px-2 py-1.5 bg-surface-sunken border border-border rounded text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                    placeholder="Human name"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    {...register(`objectives.${i}.pass_criteria`)}
                    className="w-full px-2 py-1.5 bg-surface-sunken border border-border rounded text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                    placeholder="e.g. <=+10%"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    {...register(`objectives.${i}.warning_criteria`)}
                    className="w-full px-2 py-1.5 bg-surface-sunken border border-border rounded text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                    placeholder="optional"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    {...register(`objectives.${i}.weight`)}
                    type="number"
                    className="w-full px-2 py-1.5 bg-surface-sunken border border-border rounded text-xs text-foreground text-center focus:outline-none focus:border-primary"
                  />
                </td>
                <td className="px-2 py-1.5 text-center">
                  <input
                    type="checkbox"
                    {...register(`objectives.${i}.key_sli`)}
                    className="accent-[var(--indicator-key-sli)]"
                  />
                </td>
                <td className="px-2 py-1.5 text-center">
                  <button type="button" onClick={() => remove(i)} className="text-action-destructive hover:text-action-destructive/80 text-xs">✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button
        type="button"
        onClick={() => append({
          sli: availableIndicators[0] ?? '',
          display_name: '',
          pass_criteria: '',
          warning_criteria: '',
          weight: 1,
          key_sli: false,
        })}
        className="px-3 py-1.5 text-xs rounded border border-border text-foreground hover:border-border hover:text-foreground transition-colors"
      >
        + Add Objective
      </button>

      {validate.data && !validate.data.valid && (
        <div className="text-xs text-destructive-form-text space-y-0.5">
          {validate.data.errors.map((e, i) => (
            <p key={i}>{e.field}: {e.message}</p>
          ))}
        </div>
      )}
      {create.isError && (
        <p className="text-xs text-destructive-form-text">Failed to save — please try again.</p>
      )}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:text-foreground transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={validate.isPending || create.isPending}
          className="px-3 py-1.5 text-xs font-medium rounded bg-primary text-primary-foreground hover:bg-primary/80 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {validate.isPending ? 'Validating…' : create.isPending ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </form>
  )
}
