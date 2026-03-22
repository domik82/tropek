import { Plus, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import type { TagRow } from './tagUtils'

export interface ComparisonData {
  baseline_mode: 'previous' | 'manual'
  compare_count: number
  aggregate_function: string
  include_result_with_score: string
  pass_pct: number
  warn_pct: number
  tags: TagRow[]
  variables: { key: string; value: string }[]
}

interface WizardStepComparisonProps {
  data: ComparisonData
  onChange: (data: ComparisonData) => void
}

const AGGREGATE_OPTIONS = ['avg', 'p50', 'p90', 'p95', 'p99']
const INCLUDE_SCORE_OPTIONS = [
  { value: 'pass_or_warn', label: 'Pass or Warning' },
  { value: 'pass', label: 'Pass only' },
  { value: 'all', label: 'All results' },
]

export function WizardStepComparison({ data, onChange }: WizardStepComparisonProps) {
  function update<K extends keyof ComparisonData>(field: K, value: ComparisonData[K]) {
    onChange({ ...data, [field]: value })
  }

  function updateTag(index: number, field: 'key' | 'value', val: string) {
    const tags = data.tags.map((t, i) => (i === index ? { ...t, [field]: val } : t))
    update('tags', tags)
  }

  function updateVariable(index: number, field: 'key' | 'value', val: string) {
    const vars = data.variables.map((v, i) => (i === index ? { ...v, [field]: val } : v))
    update('variables', vars)
  }

  const passPct = Math.max(0, Math.min(100, data.pass_pct))
  const warnPct = Math.max(0, Math.min(passPct, data.warn_pct))

  return (
    <div className="space-y-4">
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        Step 4 — Comparison & Scoring
      </h3>

      <div className="grid grid-cols-2 gap-6">
        {/* Left column — Comparison Settings */}
        <div className="space-y-3">
          <span className="text-xs font-medium text-muted-foreground">Comparison Settings</span>

          <div>
            <label htmlFor="baseline-mode" className="block text-xs text-muted-foreground mb-1">
              Baseline Mode
            </label>
            <select
              id="baseline-mode"
              className="w-full rounded border border-border bg-popover px-2 py-1.5 text-sm"
              value={data.baseline_mode}
              onChange={(e) => update('baseline_mode', e.target.value as 'previous' | 'manual')}
            >
              <option value="previous">Previous evaluations</option>
              <option value="manual">Manual</option>
            </select>
          </div>

          <div>
            <label htmlFor="compare-count" className="block text-xs text-muted-foreground mb-1">
              Compare against last
            </label>
            <div className="flex items-center gap-2">
              <Input
                id="compare-count"
                type="number"
                className="w-20"
                value={data.compare_count}
                onChange={(e) => update('compare_count', parseInt(e.target.value) || 1)}
                min={1}
              />
              <span className="text-xs text-muted-foreground">evaluations</span>
            </div>
          </div>

          <div>
            <label htmlFor="agg-function" className="block text-xs text-muted-foreground mb-1">
              Aggregate Function
            </label>
            <select
              id="agg-function"
              className="w-full rounded border border-border bg-popover px-2 py-1.5 text-sm"
              value={data.aggregate_function}
              onChange={(e) => update('aggregate_function', e.target.value)}
            >
              {AGGREGATE_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="include-score" className="block text-xs text-muted-foreground mb-1">
              Include Result With Score
            </label>
            <select
              id="include-score"
              className="w-full rounded border border-border bg-popover px-2 py-1.5 text-sm"
              value={data.include_result_with_score}
              onChange={(e) => update('include_result_with_score', e.target.value)}
            >
              {INCLUDE_SCORE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Right column — Score Thresholds */}
        <div className="space-y-3">
          <span className="text-xs font-medium text-muted-foreground">Score Thresholds</span>

          <div>
            <label htmlFor="pass-pct" className="block text-xs text-muted-foreground mb-1">
              Pass &ge;
            </label>
            <div className="flex items-center gap-1">
              <Input
                id="pass-pct"
                type="number"
                className="w-20"
                value={data.pass_pct}
                onChange={(e) => update('pass_pct', parseInt(e.target.value) || 0)}
                min={0}
                max={100}
              />
              <span className="text-xs text-muted-foreground">%</span>
            </div>
          </div>

          <div>
            <label htmlFor="warn-pct" className="block text-xs text-muted-foreground mb-1">
              Warning &ge;
            </label>
            <div className="flex items-center gap-1">
              <Input
                id="warn-pct"
                type="number"
                className="w-20"
                value={data.warn_pct}
                onChange={(e) => update('warn_pct', parseInt(e.target.value) || 0)}
                min={0}
                max={100}
              />
              <span className="text-xs text-muted-foreground">%</span>
            </div>
          </div>

          {/* Threshold bar */}
          <div className="mt-2">
            <div className="flex h-4 w-full rounded overflow-hidden text-[9px] font-bold text-white">
              <div
                className="flex items-center justify-center"
                style={{ width: `${warnPct}%`, backgroundColor: '#e5484d' }}
              >
                {warnPct > 10 && 'Fail'}
              </div>
              <div
                className="flex items-center justify-center"
                style={{ width: `${passPct - warnPct}%`, backgroundColor: '#f5a623' }}
              >
                {(passPct - warnPct) > 10 && 'Warn'}
              </div>
              <div
                className="flex items-center justify-center"
                style={{ width: `${100 - passPct}%`, backgroundColor: '#30a14e' }}
              >
                {(100 - passPct) > 10 && 'Pass'}
              </div>
            </div>
            <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
              <span>0%</span>
              <span>100%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tags */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-muted-foreground">Tags</span>
          <button
            type="button"
            onClick={() => update('tags', [...data.tags, { key: '', value: '' }])}
            className="inline-flex items-center gap-1 text-xs hover:text-primary"
            style={{ color: ENTITY_COLORS.slo }}
          >
            <Plus className="size-3" /> Add
          </button>
        </div>
        <div className="space-y-1.5">
          {data.tags.map((tag, i) => (
            <div key={i} className="flex gap-1.5 items-center">
              <Input
                value={tag.key}
                onChange={(e) => updateTag(i, 'key', e.target.value)}
                placeholder="key"
                className="flex-1"
              />
              <Input
                value={tag.value}
                onChange={(e) => updateTag(i, 'value', e.target.value)}
                placeholder="value"
                className="flex-1"
              />
              <button
                type="button"
                aria-label="remove tag"
                onClick={() => update('tags', data.tags.filter((_, j) => j !== i))}
                className="text-muted-foreground hover:text-red-400"
              >
                <X className="size-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Variables */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-muted-foreground">Variables</span>
          <button
            type="button"
            onClick={() => update('variables', [...data.variables, { key: '', value: '' }])}
            className="inline-flex items-center gap-1 text-xs hover:text-primary"
            style={{ color: ENTITY_COLORS.slo }}
          >
            <Plus className="size-3" /> Add
          </button>
        </div>
        <div className="space-y-1.5">
          {data.variables.map((v, i) => (
            <div key={i} className="flex gap-1.5 items-center">
              <Input
                value={v.key}
                onChange={(e) => updateVariable(i, 'key', e.target.value)}
                placeholder="key"
                className="flex-1"
              />
              <Input
                value={v.value}
                onChange={(e) => updateVariable(i, 'value', e.target.value)}
                placeholder="value"
                className="flex-1"
              />
              <button
                type="button"
                aria-label="remove variable"
                onClick={() => update('variables', data.variables.filter((_, j) => j !== i))}
                className="text-muted-foreground hover:text-red-400"
              >
                <X className="size-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
