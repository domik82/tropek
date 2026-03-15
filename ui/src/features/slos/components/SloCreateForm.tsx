// src/features/slos/components/SloCreateForm.tsx
// Structured form for creating a new SLO from scratch.
// YAML tab lets user paste/upload raw YAML to pre-fill the form.

import { useState } from 'react'
import { useForm, useFieldArray } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { parseSloYaml } from '@/lib/parseSloYaml'
import { useUploadSlo } from '../hooks'

// ── Schema ─────────────────────────────────────────────────────────────────────

const labelSchema = z.object({ key: z.string().min(1), value: z.string() })
const querySchema  = z.object({ indicator: z.string().min(1), query: z.string() })
const objSchema    = z.object({
  sli:              z.string().min(1),
  display_name:     z.string(),
  pass_criteria:    z.string(),
  warning_criteria: z.string(),
  weight:           z.coerce.number().min(0),
  key_sli:          z.boolean(),
  tab_group:        z.string(),
})

const formSchema = z.object({
  name:          z.string().min(1, 'Required').regex(/^[a-z0-9-]+$/, 'Lowercase, numbers and hyphens only'),
  display_name:  z.string(),
  author:        z.string(),
  notes:         z.string(),
  labels:        z.array(labelSchema),
  // comparison
  compare_with:                    z.string(),
  number_of_comparison_results:    z.coerce.number().min(1),
  include_result_with_score:       z.string(),
  aggregate_function:              z.string(),
  // score
  total_pass:    z.string(),
  total_warning: z.string(),
  // SLI queries + objectives
  sli_queries:  z.array(querySchema),
  objectives:   z.array(objSchema),
})

type FormValues = z.infer<typeof formSchema>

const DEFAULTS: FormValues = {
  name: '', display_name: '', author: '', notes: '',
  labels: [],
  compare_with: 'several_results',
  number_of_comparison_results: 3,
  include_result_with_score: 'pass_or_warn',
  aggregate_function: 'avg',
  total_pass: '90%', total_warning: '75%',
  sli_queries: [],
  objectives: [],
}

// ── YAML builder ───────────────────────────────────────────────────────────────

function buildYaml(v: FormValues): string {
  const lines: string[] = [
    'api_version: tropek/v1',
    'kind: SLO',
    'metadata:',
    `  name: ${v.name}`,
  ]
  if (v.labels.length > 0) {
    lines.push('  labels:')
    v.labels.forEach(l => lines.push(`    ${l.key}: ${l.value}`))
  }
  lines.push('spec:')
  lines.push('  comparison:')
  lines.push(`    compare_with: ${v.compare_with}`)
  lines.push(`    number_of_comparison_results: ${v.number_of_comparison_results}`)
  lines.push(`    include_result_with_score: ${v.include_result_with_score}`)
  lines.push(`    aggregate_function: ${v.aggregate_function}`)
  if (v.sli_queries.length > 0) {
    lines.push('  indicators:')
    v.sli_queries.forEach(q => {
      lines.push(`    ${q.indicator}: "${q.query}"`)
    })
  }
  if (v.objectives.length > 0) {
    lines.push('  objectives:')
    v.objectives.forEach(obj => {
      lines.push(`    - sli_name: ${obj.sli}`)
      lines.push(`      display_name: ${obj.display_name || obj.sli}`)
      if (obj.pass_criteria) {
        lines.push('      pass:')
        lines.push(`        - criteria: ["${obj.pass_criteria}"]`)
      }
      if (obj.warning_criteria) {
        lines.push('      warning:')
        lines.push(`        - criteria: ["${obj.warning_criteria}"]`)
      }
      lines.push(`      weight: ${obj.weight}`)
      lines.push(`      key_sli: ${obj.key_sli}`)
      if (obj.tab_group) lines.push(`      tab_group: ${obj.tab_group}`)
    })
  }
  if (v.total_pass || v.total_warning) {
    lines.push('  total_score:')
    if (v.total_pass)    lines.push(`    pass: "${v.total_pass}"`)
    if (v.total_warning) lines.push(`    warning: "${v.total_warning}"`)
  }
  return lines.join('\n')
}

// ── Small shared input styles ──────────────────────────────────────────────────

const inp = 'w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500'
const sel = inp + ' cursor-pointer'

// ── Sub-section label ──────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">{children}</h3>
}

// ── Main component ─────────────────────────────────────────────────────────────

interface Props {
  onCancel: () => void
  onSaved:  () => void
}

export function SloCreateForm({ onCancel, onSaved }: Props) {
  const [tab, setTab] = useState<'form' | 'yaml'>('form')
  const [rawYaml, setRawYaml] = useState('')
  const [yamlError, setYamlError] = useState<string | null>(null)
  const upload = useUploadSlo()

  const { register, control, handleSubmit, reset, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(formSchema) as import('react-hook-form').Resolver<FormValues>,
    defaultValues: DEFAULTS,
  })

  const labels    = useFieldArray({ control, name: 'labels' })
  const queries   = useFieldArray({ control, name: 'sli_queries' })
  const objectives = useFieldArray({ control, name: 'objectives' })

  // Populate form from pasted/parsed YAML
  function parseAndFill() {
    const parsed = parseSloYaml(rawYaml)
    if (!parsed) { setYamlError('Could not parse — check format is tropek/v1 SLO'); return }
    setYamlError(null)
    reset({
      name:          parsed.metadata.name,
      display_name:  '',
      author:        '',
      notes:         '',
      labels:        Object.entries(parsed.metadata.labels).map(([key, value]) => ({ key, value })),
      compare_with:  parsed.spec.comparison.compare_with ?? 'several_results',
      number_of_comparison_results: parseInt(parsed.spec.comparison.number_of_comparison_results ?? '3') || 3,
      include_result_with_score:    parsed.spec.comparison.include_result_with_score ?? 'pass_or_warn',
      aggregate_function:           parsed.spec.comparison.aggregate_function ?? 'avg',
      total_pass:    parsed.spec.total_score.pass,
      total_warning: parsed.spec.total_score.warning,
      sli_queries:   [],
      objectives:    parsed.spec.objectives.map(obj => ({
        sli:              obj.sli_name,
        display_name:     obj.display_name,
        pass_criteria:    obj.pass.join(', '),
        warning_criteria: obj.warning.join(', '),
        weight:           obj.weight,
        key_sli:          obj.key_sli,
        tab_group:        obj.tab_group,
      })),
    })
    setTab('form')
  }

  function onSubmit(values: FormValues) {
    const yaml = buildYaml(values)
    upload.mutate(
      {
        name: values.name,
        slo_yaml: yaml,
        display_name: values.display_name || undefined,
        notes: values.notes || undefined,
        author: values.author || undefined,
      },
      { onSuccess: () => onSaved() }
    )
  }

  // Live indicator list for objectives combobox
  function getIndicators() {
    // read from the field array via react-hook-form control would need watch;
    // pass a plain read from the DOM is complex — use a simple workaround
    return queries.fields.map(f => f.indicator).filter(Boolean)
  }

  return (
    <div className="space-y-4">
      {/* Tab switcher */}
      <div className="flex gap-1 border-b border-slate-700 pb-0">
        {(['form', 'yaml'] as const).map(t => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? 'border-indigo-400 text-indigo-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            {t === 'form' ? 'Build Form' : 'Paste YAML'}
          </button>
        ))}
      </div>

      {/* ── YAML tab ── */}
      {tab === 'yaml' && (
        <div className="space-y-3">
          <p className="text-xs text-slate-500">Paste a tropek/v1 SLO YAML to pre-fill the form, or use Upload YAML to submit directly.</p>
          <textarea
            value={rawYaml}
            onChange={e => { setRawYaml(e.target.value); setYamlError(null) }}
            className="w-full h-72 bg-slate-900 border border-slate-700 rounded-lg p-3 font-mono text-xs text-slate-200 resize-y focus:outline-none focus:border-indigo-500"
            placeholder="api_version: tropek/v1&#10;kind: SLO&#10;..."
            spellCheck={false}
          />
          {yamlError && <p className="text-xs text-red-400">{yamlError}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={parseAndFill}
              disabled={!rawYaml.trim()}
              className="px-3 py-1.5 text-xs font-medium rounded bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Parse &amp; fill form →
            </button>
          </div>
        </div>
      )}

      {/* ── Form tab ── */}
      {tab === 'form' && (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">

          {/* Basic info */}
          <div className="space-y-3">
            <SectionLabel>Basic Info</SectionLabel>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">Name <span className="text-red-400">*</span></label>
                <input {...register('name')} className={inp} placeholder="my-slo-name" />
                {errors.name && <p className="text-xs text-red-400 mt-0.5">{errors.name.message}</p>}
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Display Name</label>
                <input {...register('display_name')} className={inp} placeholder="My SLO" />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Author</label>
                <input {...register('author')} className={inp} placeholder="jane.doe" />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Notes</label>
                <input {...register('notes')} className={inp} placeholder="What changed in this version…" />
              </div>
            </div>

            {/* Labels */}
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Labels</span>
                <button
                  type="button"
                  onClick={() => labels.append({ key: '', value: '' })}
                  className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
                >
                  + Add label
                </button>
              </div>
              {labels.fields.map((f, i) => (
                <div key={f.id} className="flex gap-2 items-center">
                  <input {...register(`labels.${i}.key`)}   className={inp} placeholder="key" />
                  <span className="text-slate-600 text-xs">:</span>
                  <input {...register(`labels.${i}.value`)} className={inp} placeholder="value" />
                  <button type="button" onClick={() => labels.remove(i)} className="text-red-400 hover:text-red-300 text-xs shrink-0">✕</button>
                </div>
              ))}
            </div>
          </div>

          {/* Comparison */}
          <div className="space-y-3">
            <SectionLabel>Comparison</SectionLabel>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">Compare With</label>
                <select {...register('compare_with')} className={sel}>
                  <option value="single_result">single_result</option>
                  <option value="several_results">several_results</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1"># Comparison Results</label>
                <input {...register('number_of_comparison_results')} type="number" min={1} className={inp} />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Include Results With Score</label>
                <select {...register('include_result_with_score')} className={sel}>
                  <option value="pass">pass</option>
                  <option value="pass_or_warn">pass_or_warn</option>
                  <option value="all">all</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Aggregate Function</label>
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
                <label className="block text-xs text-slate-500 mb-1">Total Pass</label>
                <input {...register('total_pass')} className={inp} placeholder='e.g. "90%"' />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Total Warning</label>
                <input {...register('total_warning')} className={inp} placeholder='e.g. "75%"' />
              </div>
            </div>
          </div>

          {/* SLI Queries */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <SectionLabel>SLI Queries</SectionLabel>
              <button
                type="button"
                onClick={() => queries.append({ indicator: '', query: '' })}
                className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
              >
                + Add query
              </button>
            </div>
            {queries.fields.length === 0 && (
              <p className="text-xs text-slate-600 italic">No SLI queries yet — add at least one before defining objectives.</p>
            )}
            {queries.fields.length > 0 && (
              <div className="rounded-lg border border-slate-700 overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-slate-800/60 border-b border-slate-700">
                    <tr>
                      <th className="text-left px-3 py-2 text-slate-400 uppercase w-48">Indicator</th>
                      <th className="text-left px-3 py-2 text-slate-400 uppercase">PromQL / Query</th>
                      <th className="w-8"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {queries.fields.map((f, i) => (
                      <tr key={f.id}>
                        <td className="px-2 py-1.5">
                          <input {...register(`sli_queries.${i}.indicator`)} className={inp + ' font-mono text-[#7dc540]'} placeholder="error_rate" />
                        </td>
                        <td className="px-2 py-1.5">
                          <input {...register(`sli_queries.${i}.query`)} className={inp + ' font-mono'} placeholder='rate(errors_total{job="$SERVICE"}[5m])' />
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          <button type="button" onClick={() => queries.remove(i)} className="text-red-400 hover:text-red-300">✕</button>
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
            <div className="flex items-center justify-between">
              <SectionLabel>Objectives</SectionLabel>
              <button
                type="button"
                onClick={() => objectives.append({
                  sli: getIndicators()[0] ?? '',
                  display_name: '', pass_criteria: '', warning_criteria: '',
                  weight: 1, key_sli: false, tab_group: '',
                })}
                className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
              >
                + Add objective
              </button>
            </div>
            {objectives.fields.length === 0 && (
              <p className="text-xs text-slate-600 italic">No objectives yet.</p>
            )}
            {objectives.fields.length > 0 && (
              <div className="rounded-lg border border-slate-700 overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-slate-800/60 border-b border-slate-700 text-slate-400 uppercase">
                    <tr>
                      <th className="text-left px-2 py-2 min-w-[140px]">Indicator</th>
                      <th className="text-left px-2 py-2 min-w-[120px]">Display Name</th>
                      <th className="text-left px-2 py-2 min-w-[110px]">Pass</th>
                      <th className="text-left px-2 py-2 min-w-[110px]">Warning</th>
                      <th className="text-center px-2 py-2 w-14">Weight</th>
                      <th className="text-left px-2 py-2 min-w-[90px]">Group</th>
                      <th className="text-center px-2 py-2 w-10">Key</th>
                      <th className="w-8"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {objectives.fields.map((f, i) => (
                      <tr key={f.id} className="hover:bg-slate-800/30">
                        <td className="px-2 py-1.5">
                          <input
                            {...register(`objectives.${i}.sli`)}
                            className={inp + ' font-mono text-[#7dc540]'}
                            placeholder="indicator"
                            list={`indicators-${i}`}
                          />
                          <datalist id={`indicators-${i}`}>
                            {getIndicators().map(ind => <option key={ind} value={ind} />)}
                          </datalist>
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
                        <td className="px-2 py-1.5">
                          <input {...register(`objectives.${i}.tab_group`)} className={inp} placeholder="summary" />
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          <input type="checkbox" {...register(`objectives.${i}.key_sli`)} className="accent-cyan-400" />
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          <button type="button" onClick={() => objectives.remove(i)} className="text-red-400 hover:text-red-300">✕</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {upload.isError && (
            <p className="text-xs text-red-400">Failed to save — please try again.</p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onCancel}
              className="px-3 py-1.5 text-xs rounded border border-slate-600 text-slate-400 hover:text-slate-200 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={upload.isPending}
              className="px-3 py-1.5 text-xs font-medium rounded bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {upload.isPending ? 'Saving…' : 'Create SLO'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
