// src/features/slos/components/SloCreateForm.tsx
import { useForm, useFieldArray } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useCreateSlo } from '../hooks'

// ── Schema ─────────────────────────────────────────────────────────────────────

const objSchema = z.object({
  sli: z.string().min(1),
  display_name: z.string(),
  pass_criteria: z.string(),
  warning_criteria: z.string(),
  weight: z.coerce.number().min(0),
  key_sli: z.boolean(),
})

const labelSchema = z.object({
  key: z.string().min(1),
  value: z.string(),
})

const formSchema = z.object({
  name: z.string().min(1, 'Required').regex(/^[a-z0-9-]+$/, 'Lowercase, numbers and hyphens only'),
  display_name: z.string(),
  author: z.string(),
  notes: z.string(),
  compare_with: z.string(),
  number_of_comparison_results: z.coerce.number().min(1),
  include_result_with_score: z.string(),
  aggregate_function: z.string(),
  total_score_pass_pct: z.coerce.number().min(0).max(100),
  total_score_warning_pct: z.coerce.number().min(0).max(100),
  comparable_from_version: z.coerce.number().min(1).optional(),
  objectives: z.array(objSchema),
  labels: z.array(labelSchema),
})

type FormValues = z.infer<typeof formSchema>

const DEFAULTS: FormValues = {
  name: '', display_name: '', author: '', notes: '',
  compare_with: 'several_results',
  number_of_comparison_results: 3,
  include_result_with_score: 'pass_or_warn',
  aggregate_function: 'avg',
  total_score_pass_pct: 90,
  total_score_warning_pct: 75,
  objectives: [],
  labels: [],
}

// ── Shared styles ──────────────────────────────────────────────────────────────

const inp = 'w-full px-2 py-1.5 bg-surface-sunken border border-border rounded text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary'
const sel = inp + ' cursor-pointer'

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{children}</h3>
}

// ── Main component ─────────────────────────────────────────────────────────────

interface Props {
  onCancel: () => void
  onSaved: () => void
}

export function SloCreateForm({ onCancel, onSaved }: Props) {
  const create = useCreateSlo()

  const { register, control, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(formSchema) as import('react-hook-form').Resolver<FormValues>,
    defaultValues: DEFAULTS,
  })

  const objectives = useFieldArray({ control, name: 'objectives' })
  const labels = useFieldArray({ control, name: 'labels' })

  function onSubmit(values: FormValues) {
    create.mutate(
      {
        name: values.name,
        display_name: values.display_name || undefined,
        notes: values.notes || undefined,
        author: values.author || undefined,
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
        comparison: {
          compare_with: values.compare_with,
          number_of_comparison_results: values.number_of_comparison_results,
          include_result_with_score: values.include_result_with_score,
          aggregate_function: values.aggregate_function,
        },
        tags: Object.fromEntries(
          values.labels.filter(l => l.key).map(l => [l.key, l.value])
        ),
        comparable_from_version: values.comparable_from_version || undefined,
      },
      { onSuccess: () => onSaved() },
    )
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">

      {/* Basic info */}
      <div className="space-y-3">
        <SectionLabel>Basic Info</SectionLabel>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Name <span className="text-destructive-form-text">*</span></label>
            <input {...register('name')} className={inp} placeholder="my-slo-name" />
            {errors.name && <p className="text-xs text-destructive-form-text mt-0.5">{errors.name.message}</p>}
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Display Name</label>
            <input {...register('display_name')} className={inp} placeholder="My SLO" />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Author</label>
            <input {...register('author')} className={inp} placeholder="jane.doe" autoComplete="name" />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Notes</label>
            <input {...register('notes')} className={inp} placeholder="What changed in this version…" />
          </div>
        </div>
      </div>

      {/* Comparison */}
      <div className="space-y-3">
        <SectionLabel>Comparison</SectionLabel>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Compare With</label>
            <select {...register('compare_with')} className={sel}>
              <option value="single_result">single_result</option>
              <option value="several_results">several_results</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1"># Comparison Results</label>
            <input {...register('number_of_comparison_results')} type="number" min={1} className={inp} />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Include Results With Score</label>
            <select {...register('include_result_with_score')} className={sel}>
              <option value="pass">pass</option>
              <option value="pass_or_warn">pass_or_warn</option>
              <option value="all">all</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Aggregate Function</label>
            <select {...register('aggregate_function')} className={sel}>
              <option value="avg">avg</option>
              <option value="p50">p50</option>
              <option value="p90">p90</option>
              <option value="p95">p95</option>
              <option value="p99">p99</option>
            </select>
          </div>
        </div>
      </div>

      {/* Score thresholds */}
      <div className="space-y-3">
        <SectionLabel>Score Thresholds</SectionLabel>
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
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Comparable From Version</label>
          <input {...register('comparable_from_version')} type="number" min={1} className={inp} placeholder="defaults to previous" />
          <p className="text-[10px] text-muted-foreground/60 mt-0.5">Baselines from versions before this are excluded</p>
        </div>
      </div>

      {/* Labels */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <SectionLabel>Labels</SectionLabel>
          <button
            type="button"
            onClick={() => labels.append({ key: '', value: '' })}
            className="px-3 py-1.5 text-xs font-medium rounded border bg-primary border-primary text-primary-foreground hover:bg-primary/80 transition-colors"
          >
            + Add label
          </button>
        </div>
        {labels.fields.length === 0 && (
          <p className="text-xs text-muted-foreground/60 italic">No labels yet.</p>
        )}
        {labels.fields.length > 0 && (
          <div className="rounded-lg border border-border overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-surface-sunken/60 border-b border-border text-muted-foreground uppercase">
                <tr>
                  <th className="text-left px-2 py-2">Key</th>
                  <th className="text-left px-2 py-2">Value</th>
                  <th className="w-8"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {labels.fields.map((f, i) => (
                  <tr key={f.id} className="hover:bg-state-hover-bg">
                    <td className="px-2 py-1.5">
                      <input {...register(`labels.${i}.key`)} className={inp + ' font-mono'} placeholder="env" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input {...register(`labels.${i}.value`)} className={inp} placeholder="production" />
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      <button type="button" onClick={() => labels.remove(i)} className="text-destructive-form-text hover:text-action-destructive">✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Objectives */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <SectionLabel>Objectives</SectionLabel>
          <button
            type="button"
            onClick={() => objectives.append({
              sli: '', display_name: '', pass_criteria: '', warning_criteria: '',
              weight: 1, key_sli: false,
            })}
            className="px-3 py-1.5 text-xs font-medium rounded border bg-primary border-primary text-primary-foreground hover:bg-primary/80 transition-colors"
          >
            + Add objective
          </button>
        </div>
        {objectives.fields.length === 0 && (
          <p className="text-xs text-muted-foreground/60 italic">No objectives yet.</p>
        )}
        {objectives.fields.length > 0 && (
          <div className="rounded-lg border border-border overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-surface-sunken/60 border-b border-border text-muted-foreground uppercase">
                <tr>
                  <th className="text-left px-2 py-2 min-w-[140px]">Indicator</th>
                  <th className="text-left px-2 py-2 min-w-[120px]">Display Name</th>
                  <th className="text-left px-2 py-2 min-w-[110px]">Pass</th>
                  <th className="text-left px-2 py-2 min-w-[110px]">Warning</th>
                  <th className="text-center px-2 py-2 w-14">Weight</th>
                  <th className="text-center px-2 py-2 w-10">Key</th>
                  <th className="w-8"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {objectives.fields.map((f, i) => (
                  <tr key={f.id} className="hover:bg-state-hover-bg">
                    <td className="px-2 py-1.5">
                      <input {...register(`objectives.${i}.sli`)} className={inp + ' font-mono text-pass'} placeholder="indicator" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input {...register(`objectives.${i}.display_name`)} className={inp} placeholder="Human name" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input {...register(`objectives.${i}.pass_criteria`)} className={inp} placeholder="<=+10%" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input {...register(`objectives.${i}.warning_criteria`)} className={inp} placeholder="optional" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input {...register(`objectives.${i}.weight`)} type="number" className={inp + ' text-center'} />
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      <input type="checkbox" {...register(`objectives.${i}.key_sli`)} className="accent-[var(--indicator-key-sli)]" />
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      <button type="button" onClick={() => objectives.remove(i)} className="text-destructive-form-text hover:text-action-destructive">✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {create.isError && (
        <p className="text-xs text-destructive-form-text">Failed to save — please try again.</p>
      )}

      <div className="flex justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:text-foreground transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={create.isPending}
          className="px-3 py-1.5 text-xs font-medium rounded bg-primary text-primary-foreground hover:bg-primary/80 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {create.isPending ? 'Saving…' : 'Create SLO'}
        </button>
      </div>
    </form>
  )
}
