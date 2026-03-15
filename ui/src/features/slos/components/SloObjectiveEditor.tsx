// src/features/slos/components/SloObjectiveEditor.tsx
import { useMemo, useState } from 'react'
import { useFieldArray, useForm, Controller } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { parseSloYaml } from '@/lib/parseSloYaml'
import { useSloValidation } from '../hooks'
import type { SloDefinition } from '../types'

const objectiveSchema = z.object({
  sli: z.string().min(1),
  display_name: z.string(),
  pass_criteria: z.string(),   // optional — an objective may have no pass criteria
  warning_criteria: z.string(),
  weight: z.coerce.number().min(0),
  key_sli: z.boolean(),
  tab_group: z.string(),
})

const formSchema = z.object({
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
        className="w-full text-left px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs font-mono text-[#7dc540] hover:border-slate-500 truncate"
      >
        {value || <span className="text-slate-500">Select indicator…</span>}
      </button>
      {open && (
        <div className="absolute z-10 mt-1 w-full bg-slate-800 border border-slate-600 rounded shadow-lg max-h-48 overflow-y-auto">
          <input
            className="w-full px-2 py-1.5 bg-slate-900 border-b border-slate-700 text-xs text-slate-200 placeholder-slate-500 focus:outline-none"
            placeholder="Filter…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            autoFocus
          />
          {filtered.map(ind => (
            <button
              key={ind}
              type="button"
              className="w-full text-left px-2 py-1.5 text-xs font-mono text-[#7dc540] hover:bg-slate-700"
              onClick={() => { onChange(ind); setOpen(false); setSearch('') }}
            >
              {ind}
            </button>
          ))}
          {filtered.length === 0 && (
            <p className="px-2 py-1.5 text-xs text-slate-500">No indicators found</p>
          )}
        </div>
      )}
    </div>
  )
}

export function SloObjectiveEditor({ slo, onCancel, onSaved }: Props) {
  const validation = useSloValidation()
  const availableIndicators = useMemo(() => {
    if (!slo.slo_yaml) return []
    const parsed = parseSloYaml(slo.slo_yaml)
    return parsed ? parsed.spec.objectives.map(o => o.sli_name) : []
  }, [slo.slo_yaml])

  const defaultObjectives = useMemo(() => {
    if (slo.slo_yaml) {
      const parsed = parseSloYaml(slo.slo_yaml)
      if (parsed) {
        return parsed.spec.objectives.map(obj => ({
          sli: obj.sli_name,
          display_name: obj.display_name,
          pass_criteria: obj.pass.join(', '),
          warning_criteria: obj.warning.join(', '),
          weight: obj.weight,
          key_sli: obj.key_sli,
          tab_group: obj.tab_group,
        }))
      }
    }
    return []
  }, [slo])

  const { register, control, handleSubmit } = useForm<FormValues, unknown, FormValues>({
    resolver: zodResolver(formSchema) as import('react-hook-form').Resolver<FormValues>,
    defaultValues: { objectives: defaultObjectives },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'objectives' })

  function onSubmit(values: FormValues) {
    const yaml = buildYamlFromObjectives(slo, values.objectives)
    validation.mutate(yaml, {
      onSuccess: (result) => {
        if (result.valid) onSaved()
      },
    })
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
      <div className="overflow-x-auto rounded-lg border border-slate-700">
        <table className="w-full text-sm">
          <thead className="text-xs uppercase text-slate-400 bg-slate-800/60 border-b border-slate-700">
            <tr>
              <th className="text-left px-2 py-2 min-w-[160px]">Indicator</th>
              <th className="text-left px-2 py-2 min-w-[140px]">Display Name</th>
              <th className="text-left px-2 py-2 min-w-[120px]">Pass Criteria</th>
              <th className="text-left px-2 py-2 min-w-[120px]">Warn Criteria</th>
              <th className="text-center px-2 py-2 w-16">Weight</th>
              <th className="text-left px-2 py-2 min-w-[100px]">Tab Group</th>
              <th className="text-center px-2 py-2 w-10">Key</th>
              <th className="w-8"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {fields.map((field, i) => (
              <tr key={field.id} className="hover:bg-slate-800/40">
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
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    placeholder="Human name"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    {...register(`objectives.${i}.pass_criteria`)}
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    placeholder="e.g. <=+10%"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    {...register(`objectives.${i}.warning_criteria`)}
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    placeholder="optional"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    {...register(`objectives.${i}.weight`)}
                    type="number"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs text-slate-200 text-center focus:outline-none focus:border-indigo-500"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    {...register(`objectives.${i}.tab_group`)}
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    placeholder="e.g. summary"
                  />
                </td>
                <td className="px-2 py-1.5 text-center">
                  <input
                    type="checkbox"
                    {...register(`objectives.${i}.key_sli`)}
                    className="accent-cyan-400"
                  />
                </td>
                <td className="px-2 py-1.5 text-center">
                  <button type="button" onClick={() => remove(i)} className="text-red-400 hover:text-red-300 text-xs">✕</button>
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
          tab_group: '',
        })}
        className="px-3 py-1.5 text-xs rounded border border-slate-600 text-slate-300 hover:border-slate-400 hover:text-slate-100 transition-colors"
      >
        + Add Objective
      </button>

      {validation.data && !validation.data.valid && (
        <div className="bg-red-900/20 border border-red-700/40 rounded p-3 text-xs space-y-1">
          <p className="text-red-400 font-semibold">Validation errors:</p>
          {validation.data.errors.map((e, idx) => (
            <p key={idx} className="text-red-300">{e.field}: {e.message}</p>
          ))}
        </div>
      )}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-xs rounded border border-slate-600 text-slate-400 hover:text-slate-200 transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={validation.isPending}
          className="px-3 py-1.5 text-xs font-medium rounded bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {validation.isPending ? 'Validating…' : 'Validate & Save'}
        </button>
      </div>
    </form>
  )
}

function buildYamlFromObjectives(slo: SloDefinition, objectives: FormValues['objectives']): string {
  const base = slo.slo_yaml ?? ''
  // Try to preserve metadata and comparison from existing YAML by rebuilding just spec.objectives
  const lines: string[] = [
    'api_version: tropek/v1',
    'kind: SLO',
    'metadata:',
    `  name: ${slo.name}`,
    'spec:',
    '  objectives:',
    ...objectives.flatMap(obj => [
      `    - sli_name: ${obj.sli}`,
      `      display_name: ${obj.display_name || obj.sli}`,
      ...(obj.pass_criteria ? [
        '      pass:',
        `        - criteria: ["${obj.pass_criteria}"]`,
      ] : []),
      ...(obj.warning_criteria ? [
        '      warning:',
        `        - criteria: ["${obj.warning_criteria}"]`,
      ] : []),
      `      weight: ${obj.weight}`,
      `      key_sli: ${obj.key_sli}`,
      ...(obj.tab_group ? [`      tab_group: ${obj.tab_group}`] : []),
    ]),
  ]

  const parsed = parseSloYaml(base)
  const totalScore = parsed?.spec.total_score
  if (totalScore?.pass || totalScore?.warning) {
    lines.push('  total_score:')
    if (totalScore.pass) lines.push(`    pass: "${totalScore.pass}"`)
    if (totalScore.warning) lines.push(`    warning: "${totalScore.warning}"`)
  }

  // Suppress unused var warning
  void base
  return lines.join('\n')
}
