# Phase 1b — Aggregated-Mode UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add UI support for creating/editing aggregated-mode SLI definitions, SLO templates with method criteria, and grouped evaluation display — completing the user-facing surface for the aggregated query mode added in Phase 1a.

**Architecture:** Extend existing SLI form with a mode toggle that conditionally renders raw-mode fields (indicators table) or aggregated-mode fields (query template, interval, methods). Extend SLO wizard to show a method criteria table when the linked SLI is aggregated. Extend the SLI breakdown table to group rows by SLI prefix and show sample-count metadata. All new UI values are driven by backend API fields added in Phase 1a.

**Tech Stack:** React 19, TypeScript 5.9, React Hook Form + Zod, React Query, Vitest + RTL + happy-dom, Tailwind CSS v4

---

## Prerequisites

Phase 1a must be merged. The following backend fields exist on `feat/prometheus-adapter-phase1a`:

- **SLI API:** `mode`, `query_template`, `interval`, `methods` on create/read schemas (verified: `api/app/modules/sli_registry/schemas.py`)
- **SLO API:** `method_criteria` on create/read schemas (verified: `api/app/modules/slo_registry/schemas.py:50,73`)
- **Worker:** `sli_metadata` stored in `Evaluation.job_stats` (verified: `api/app/modules/quality_gate/worker.py:388`)
- **DB migration:** Run `./scripts/db-regen-migrations.sh` after Phase 1a merge to include `method_criteria` column

### Backend gap discovered during validation

The presenter (`api/app/modules/quality_gate/presenter.py:96-108`) builds the evaluation detail response but does NOT pass `sli_metadata` from `job_stats` to the API response. Task 9a below fixes this before the UI can consume it.

## File Map

### Types (modify)
- `ui/src/features/slis/types.ts` — Add `mode`, `query_template`, `interval`, `methods` to `SliDefinition` and `SliDefinitionCreate`
- `ui/src/features/slos/types.ts` — Add `method_criteria` to `SloDefinition`
- `ui/src/features/evaluations/types.ts` — Add `SliMetadata` type, add `sli_metadata` to `EvaluationDetail.job_stats`
- `ui/src/lib/aggregation-methods.ts` — New: `AGGREGATION_METHODS` constant array and `AggregationMethod` type

### SLI Form (modify + new)
- `ui/src/features/registry/forms/SliForm.tsx` — Add mode toggle, conditionally render raw vs aggregated fields
- `ui/src/features/registry/forms/SliForm.test.tsx` — Add tests for mode toggle, aggregated form, validation
- `ui/src/features/registry/forms/AggregatedModeFields.tsx` — New: query template, interval selector, methods multi-select
- `ui/src/features/registry/forms/AggregatedModeFields.test.tsx` — New: unit tests

### SLI Detail View (modify)
- `ui/src/features/registry/details/SliDetailView.tsx` — Show mode badge, aggregated fields when mode=aggregated

### SLO Wizard (modify + new)
- `ui/src/features/registry/forms/WizardStepIndicators.tsx` — Detect aggregated SLI, render method criteria table
- `ui/src/features/registry/forms/MethodCriteriaTable.tsx` — New: method criteria editor table
- `ui/src/features/registry/forms/MethodCriteriaTable.test.tsx` — New: unit tests
- `ui/src/features/registry/forms/SloWizard.tsx` — Wire method_criteria into submit payload

### SLO Detail View (modify)
- `ui/src/features/registry/details/SloDetailView.tsx` — Show method_criteria when present

### Evaluation Breakdown (modify)
- `ui/src/features/evaluations/components/SLIBreakdownTable.tsx` — Group aggregated rows, show sample-count header
- `ui/src/features/evaluations/components/SLIBreakdownTable.test.tsx` — Add grouping + metadata tests

### Backend Presenter Fix (modify)
- `api/app/modules/quality_gate/presenter.py` — Pass `sli_metadata` from `job_stats` into evaluation detail response
- `api/app/modules/quality_gate/schemas.py` — Add `sli_metadata` field to `EvaluationDetail`
- `api/tests/services/test_presenter.py` �� Test that `sli_metadata` round-trips through presenter

### Multi-SLO Evaluation Column Fix (modify)
- `ui/src/features/navigator/components/AssetPanel.tsx` — Change from single evalId to time-slot selection; fetch all evals for slot
- `ui/src/features/navigator/components/AssetHeatmap.tsx` — Emit time slot + eval IDs on cell click instead of single eval ID
- `ui/src/features/navigator/components/AssetPanelHeatmapView.tsx` — Pass new callback shape through
- `ui/src/features/evaluations/components/EvaluationIndicatorSection.tsx` — Accept merged indicator data from multiple evaluations

### Bootstrap Data (modify)
- `bootstrap_mock/manifests/sli-definitions.yaml` — Add aggregated-mode SLI definition
- `bootstrap_mock/manifests/slo-definitions.yaml` — Add SLO template with method_criteria
- `clients/python/tropek_client/manifest.py` — Pass mode/query_template/interval/methods through for SLI manifests, method_criteria for SLO manifests

---

## Task 1: Aggregation Method Constants

**Files:**
- Create: `ui/src/lib/aggregation-methods.ts`

- [ ] **Step 1: Create the constants file**

```ts
// ui/src/lib/aggregation-methods.ts

export const AGGREGATION_METHODS = [
  'min', 'mean', 'max', 'std', 'sum', 'median', 'p75', 'p90', 'p95', 'p99',
] as const

export type AggregationMethod = typeof AGGREGATION_METHODS[number]

export const METHOD_LABELS: Record<AggregationMethod, string> = {
  min: 'Min',
  mean: 'Mean',
  max: 'Max',
  std: 'Std Dev',
  sum: 'Sum',
  median: 'Median',
  p75: 'P75',
  p90: 'P90',
  p95: 'P95',
  p99: 'P99',
}

export const INTERVAL_PRESETS = ['1m', '5m', '15m'] as const
```

- [ ] **Step 2: Commit**

```
feat(ui): add aggregation method constants
```

---

## Task 2: Update TypeScript Types

**Files:**
- Modify: `ui/src/features/slis/types.ts`
- Modify: `ui/src/features/slos/types.ts`
- Modify: `ui/src/features/evaluations/types.ts`

- [ ] **Step 1: Update SLI types**

In `ui/src/features/slis/types.ts`, add mode and aggregated fields to both interfaces:

```ts
// src/features/slis/types.ts

export interface SliDefinition {
  id: string
  name: string
  display_name: string | null
  adapter_type: string
  version: number
  comparable_from_version: number
  indicators: Record<string, string>  // metric_name → query_string
  mode: 'raw' | 'aggregated'
  query_template: string | null
  interval: string | null
  methods: string[] | null
  notes: string | null
  author: string | null
  tags: Record<string, string>
  active: boolean
  created_at: string
}

export interface SliDefinitionCreate {
  name: string
  display_name?: string
  adapter_type: string
  indicators?: Record<string, string>
  mode?: 'raw' | 'aggregated'
  query_template?: string
  interval?: string
  methods?: string[]
  comparable_from_version?: number
  notes?: string
  author?: string
  tags?: Record<string, string>
}
```

- [ ] **Step 2: Update SLO types**

In `ui/src/features/slos/types.ts`, add `method_criteria` to `SloDefinition`:

```ts
// Add to SloDefinition interface, after the `comparison` field:
  method_criteria: Record<string, MethodCriteriaOverride> | null
```

Add the helper type at the top of the file:

```ts
export interface MethodCriteriaOverride {
  pass_threshold?: string[]
  warning_threshold?: string[]
  weight?: number
  key_sli?: boolean
}
```

- [ ] **Step 3: Update evaluation types**

In `ui/src/features/evaluations/types.ts`, add `SliMetadata` interface and update `EvaluationDetail`:

```ts
export interface SliMetadata {
  mode: 'aggregated'
  expected_samples: number
  actual_samples: number
  missing_pct: number
  chunks_failed: number
}

// Update EvaluationDetail — add after compared_evaluation_ids:
  sli_metadata?: Record<string, SliMetadata>
```

- [ ] **Step 4: Commit**

```
feat(ui): add aggregated-mode fields to SLI, SLO, evaluation types
```

---

## Task 3: AggregatedModeFields Component

**Files:**
- Create: `ui/src/features/registry/forms/AggregatedModeFields.tsx`
- Create: `ui/src/features/registry/forms/AggregatedModeFields.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// ui/src/features/registry/forms/AggregatedModeFields.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AggregatedModeFields } from './AggregatedModeFields'

const defaultProps = {
  queryTemplate: '',
  interval: '1m',
  methods: [] as string[],
  onQueryTemplateChange: vi.fn(),
  onIntervalChange: vi.fn(),
  onMethodsChange: vi.fn(),
}

describe('AggregatedModeFields', () => {
  it('renders query template input', () => {
    render(<AggregatedModeFields {...defaultProps} />)
    expect(screen.getByLabelText('Query Template')).toBeInTheDocument()
  })

  it('renders interval selector with presets', () => {
    render(<AggregatedModeFields {...defaultProps} />)
    expect(screen.getByLabelText('Interval')).toBeInTheDocument()
    expect(screen.getByText('1m')).toBeInTheDocument()
    expect(screen.getByText('5m')).toBeInTheDocument()
    expect(screen.getByText('15m')).toBeInTheDocument()
  })

  it('renders method checkboxes', () => {
    render(<AggregatedModeFields {...defaultProps} />)
    expect(screen.getByLabelText('Mean')).toBeInTheDocument()
    expect(screen.getByLabelText('P99')).toBeInTheDocument()
    expect(screen.getByLabelText('Max')).toBeInTheDocument()
  })

  it('calls onQueryTemplateChange when template is typed', () => {
    const onChange = vi.fn()
    render(<AggregatedModeFields {...defaultProps} onQueryTemplateChange={onChange} />)
    fireEvent.change(screen.getByLabelText('Query Template'), {
      target: { value: 'rate(cpu[$interval])' },
    })
    expect(onChange).toHaveBeenCalledWith('rate(cpu[$interval])')
  })

  it('calls onMethodsChange when a method is toggled on', () => {
    const onChange = vi.fn()
    render(<AggregatedModeFields {...defaultProps} onMethodsChange={onChange} />)
    fireEvent.click(screen.getByLabelText('Mean'))
    expect(onChange).toHaveBeenCalledWith(['mean'])
  })

  it('calls onMethodsChange when a method is toggled off', () => {
    const onChange = vi.fn()
    render(<AggregatedModeFields {...defaultProps} methods={['mean', 'p99']} onMethodsChange={onChange} />)
    fireEvent.click(screen.getByLabelText('Mean'))
    expect(onChange).toHaveBeenCalledWith(['p99'])
  })

  it('shows pre-selected methods as checked', () => {
    render(<AggregatedModeFields {...defaultProps} methods={['mean', 'max']} />)
    expect(screen.getByLabelText('Mean')).toBeChecked()
    expect(screen.getByLabelText('Max')).toBeChecked()
    expect(screen.getByLabelText('P99')).not.toBeChecked()
  })

  it('interval preset buttons update the interval value', () => {
    const onChange = vi.fn()
    render(<AggregatedModeFields {...defaultProps} onIntervalChange={onChange} />)
    fireEvent.click(screen.getByText('5m'))
    expect(onChange).toHaveBeenCalledWith('5m')
  })

  it('supports custom interval via text input', () => {
    const onChange = vi.fn()
    render(<AggregatedModeFields {...defaultProps} onIntervalChange={onChange} />)
    fireEvent.change(screen.getByLabelText('Interval'), {
      target: { value: '30s' },
    })
    expect(onChange).toHaveBeenCalledWith('30s')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/ui-test.sh --tail 15 src/features/registry/forms/AggregatedModeFields.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement the component**

```tsx
// ui/src/features/registry/forms/AggregatedModeFields.tsx
import { AGGREGATION_METHODS, METHOD_LABELS, INTERVAL_PRESETS } from '@/lib/aggregation-methods'
import { Input } from '@/components/ui/input'

interface AggregatedModeFieldsProps {
  queryTemplate: string
  interval: string
  methods: string[]
  onQueryTemplateChange: (value: string) => void
  onIntervalChange: (value: string) => void
  onMethodsChange: (methods: string[]) => void
}

export function AggregatedModeFields({
  queryTemplate,
  interval,
  methods,
  onQueryTemplateChange,
  onIntervalChange,
  onMethodsChange,
}: AggregatedModeFieldsProps) {
  function toggleMethod(method: string) {
    if (methods.includes(method)) {
      onMethodsChange(methods.filter(m => m !== method))
    } else {
      onMethodsChange([...methods, method])
    }
  }

  return (
    <div className="space-y-3">
      {/* Query Template */}
      <div>
        <label htmlFor="sli-query-template" className="block text-xs text-muted-foreground mb-1">
          Query Template
        </label>
        <Input
          id="sli-query-template"
          value={queryTemplate}
          onChange={e => onQueryTemplateChange(e.target.value)}
          placeholder="rate(metric{job=&quot;$job&quot;}[$interval])"
          className="font-mono text-xs"
        />
        <p className="text-[10px] text-muted-foreground mt-0.5">
          Use $variable placeholders. $interval is reserved for the step value.
        </p>
      </div>

      {/* Interval */}
      <div>
        <label htmlFor="sli-interval" className="block text-xs text-muted-foreground mb-1">
          Interval
        </label>
        <div className="flex items-center gap-2">
          <Input
            id="sli-interval"
            value={interval}
            onChange={e => onIntervalChange(e.target.value)}
            placeholder="1m"
            className="w-20 font-mono text-xs"
          />
          <div className="flex gap-1">
            {INTERVAL_PRESETS.map(preset => (
              <button
                key={preset}
                type="button"
                onClick={() => onIntervalChange(preset)}
                className={`px-2 py-0.5 text-xs rounded border transition-colors ${
                  interval === preset
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:text-foreground'
                }`}
              >
                {preset}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Methods */}
      <div>
        <span className="block text-xs text-muted-foreground mb-1">
          Aggregation Methods
        </span>
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {AGGREGATION_METHODS.map(method => (
            <label key={method} className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={methods.includes(method)}
                onChange={() => toggleMethod(method)}
                aria-label={METHOD_LABELS[method]}
              />
              <span className="text-foreground">{METHOD_LABELS[method]}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 15 src/features/registry/forms/AggregatedModeFields.test.tsx`
Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```
feat(ui): add AggregatedModeFields component with query template, interval, methods
```

---

## Task 4: SLI Form — Mode Toggle + Aggregated Fields

**Files:**
- Modify: `ui/src/features/registry/forms/SliForm.tsx`
- Modify: `ui/src/features/registry/forms/SliForm.test.tsx`

- [ ] **Step 1: Add tests for mode toggle behavior**

Append these tests to the existing `describe('SliForm', ...)` block in `SliForm.test.tsx`:

```tsx
  it('shows mode toggle with Raw selected by default', () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )
    expect(screen.getByRole('radio', { name: 'Raw' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Aggregated' })).not.toBeChecked()
  })

  it('shows indicator fields in raw mode', () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )
    expect(screen.getByText('Indicators')).toBeInTheDocument()
    expect(screen.queryByLabelText('Query Template')).not.toBeInTheDocument()
  })

  it('shows aggregated fields when Aggregated mode is selected', () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )
    fireEvent.click(screen.getByRole('radio', { name: 'Aggregated' }))
    expect(screen.getByLabelText('Query Template')).toBeInTheDocument()
    expect(screen.getByLabelText('Interval')).toBeInTheDocument()
    expect(screen.getByLabelText('Mean')).toBeInTheDocument()
    expect(screen.queryByText('Indicators')).not.toBeInTheDocument()
  })

  it('edit mode pre-fills aggregated fields', () => {
    const aggSli: SliDefinition = {
      ...mockSli,
      mode: 'aggregated',
      indicators: {},
      query_template: 'rate(cpu[$interval])',
      interval: '5m',
      methods: ['mean', 'p99'],
    }
    render(
      <SliForm open={true} onOpenChange={vi.fn()} editFrom={aggSli} />,
      { wrapper: Wrapper },
    )
    expect(screen.getByRole('radio', { name: 'Aggregated' })).toBeChecked()
    expect(screen.getByLabelText('Query Template')).toHaveValue('rate(cpu[$interval])')
    expect(screen.getByLabelText('Interval')).toHaveValue('5m')
    expect(screen.getByLabelText('Mean')).toBeChecked()
    expect(screen.getByLabelText('P99')).toBeChecked()
    expect(screen.getByLabelText('Max')).not.toBeChecked()
  })

  it('submits aggregated-mode SLI with correct payload', async () => {
    render(
      <SliForm open={true} onOpenChange={vi.fn()} />,
      { wrapper: Wrapper },
    )
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'agg-sli' } })
    fireEvent.change(screen.getByLabelText('Adapter Type'), { target: { value: 'prometheus' } })
    fireEvent.click(screen.getByRole('radio', { name: 'Aggregated' }))
    fireEvent.change(screen.getByLabelText('Query Template'), {
      target: { value: 'rate(cpu[$interval])' },
    })
    fireEvent.click(screen.getByLabelText('Mean'))
    fireEvent.click(screen.getByLabelText('P99'))

    fireEvent.click(screen.getByRole('button', { name: /create/i }))

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'agg-sli',
          adapter_type: 'prometheus',
          mode: 'aggregated',
          query_template: 'rate(cpu[$interval])',
          interval: '1m',
          methods: ['mean', 'p99'],
        }),
        expect.anything(),
      )
    })
  })
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/forms/SliForm.test.tsx`
Expected: new tests FAIL (no radio buttons, no aggregated fields)

- [ ] **Step 3: Update SliForm to support both modes**

Replace the content of `ui/src/features/registry/forms/SliForm.tsx` with:

```tsx
import { useState, useEffect } from 'react'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useCreateSli } from '@/features/slis/hooks'
import { AggregatedModeFields } from './AggregatedModeFields'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import { tagsToRows, rowsToTags } from './tagUtils'
import type { TagRow } from './tagUtils'
import type { SliDefinition } from '@/features/slis/types'

const rawSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  display_name: z.string().optional(),
  adapter_type: z.string().min(1, 'Adapter type is required'),
  author: z.string().optional(),
  notes: z.string().optional(),
  indicators: z.array(z.object({
    name: z.string().min(1, 'Indicator name is required'),
    query: z.string().min(1, 'Query is required'),
  })).min(1, 'At least one indicator is required'),
})

const aggregatedSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  display_name: z.string().optional(),
  adapter_type: z.string().min(1, 'Adapter type is required'),
  author: z.string().optional(),
  notes: z.string().optional(),
  indicators: z.array(z.object({
    name: z.string(),
    query: z.string(),
  })),
})

type FormValues = z.infer<typeof rawSchema>

interface SliFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  editFrom?: SliDefinition
  defaultAdapterType?: string
}

function indicatorsToRows(indicators: Record<string, string>): { name: string; query: string }[] {
  return Object.entries(indicators).map(([name, query]) => ({ name, query }))
}

function rowsToIndicators(rows: { name: string; query: string }[]): Record<string, string> {
  const result: Record<string, string> = {}
  for (const row of rows) {
    if (row.name.trim()) {
      result[row.name.trim()] = row.query
    }
  }
  return result
}

export function SliForm({ open, onOpenChange, editFrom, defaultAdapterType }: SliFormProps) {
  const isNewVersion = !!editFrom
  const initialMode = editFrom?.mode ?? 'raw'

  const [mode, setMode] = useState<'raw' | 'aggregated'>(initialMode)
  const [queryTemplate, setQueryTemplate] = useState(editFrom?.query_template ?? '')
  const [interval, setInterval] = useState(editFrom?.interval ?? '1m')
  const [methods, setMethods] = useState<string[]>(editFrom?.methods ?? [])

  const schema = mode === 'raw' ? rawSchema : aggregatedSchema

  const { register, handleSubmit, control, formState: { errors }, reset } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: editFrom?.name ?? '',
      display_name: editFrom?.display_name ?? '',
      adapter_type: editFrom?.adapter_type ?? defaultAdapterType ?? '',
      author: editFrom?.author ?? '',
      notes: editFrom?.notes ?? '',
      indicators: editFrom?.indicators ? indicatorsToRows(editFrom.indicators) : [],
    },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'indicators' })

  const [tagRows, setTagRows] = useState<TagRow[]>(
    editFrom?.tags ? tagsToRows(editFrom.tags) : [],
  )

  useEffect(() => {
    if (editFrom) {
      reset({
        name: editFrom.name,
        display_name: editFrom.display_name ?? '',
        adapter_type: editFrom.adapter_type,
        author: editFrom.author ?? '',
        notes: editFrom.notes ?? '',
        indicators: indicatorsToRows(editFrom.indicators),
      })
      setMode(editFrom.mode ?? 'raw')
      setQueryTemplate(editFrom.query_template ?? '')
      setInterval(editFrom.interval ?? '1m')
      setMethods(editFrom.methods ?? [])
      setTagRows(tagsToRows(editFrom.tags))
    }
  }, [editFrom, reset])

  const createMutation = useCreateSli()
  const isPending = createMutation.isPending

  if (!open) return null

  function onSubmit(values: FormValues) {
    const tags = rowsToTags(tagRows)
    const base = {
      name: values.name,
      display_name: values.display_name || undefined,
      adapter_type: values.adapter_type,
      notes: values.notes || undefined,
      author: values.author || undefined,
      tags: Object.keys(tags).length > 0 ? tags : undefined,
    }

    if (mode === 'raw') {
      createMutation.mutate(
        { ...base, mode: 'raw', indicators: rowsToIndicators(values.indicators) },
        { onSuccess: () => { reset(); onOpenChange(false) } },
      )
    } else {
      createMutation.mutate(
        {
          ...base,
          mode: 'aggregated',
          query_template: queryTemplate,
          interval,
          methods,
        },
        { onSuccess: () => { reset(); onOpenChange(false) } },
      )
    }
  }

  const title = isNewVersion ? `New Version of: ${editFrom!.name}` : 'New SLI'
  const submitLabel = isPending ? 'Saving…' : isNewVersion ? 'Create Version' : 'Create'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-lg bg-popover border border-border rounded-xl overflow-hidden shadow-xl"
        style={{ fontFamily: SANS_SERIF }}
      >
        {/* Accent strip */}
        <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.sli }} />

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-foreground">{title}</h2>
          <button
            type="button"
            aria-label="Close"
            className="text-muted-foreground hover:text-foreground"
            onClick={() => onOpenChange(false)}
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Form body (scrollable) */}
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="p-4 space-y-3 max-h-[70vh] overflow-y-auto">
            {/* Name */}
            <div>
              <label htmlFor="sli-name" className="block text-xs text-muted-foreground mb-1">
                Name
              </label>
              <Input
                id="sli-name"
                {...register('name')}
                disabled={isNewVersion}
                placeholder="my-sli"
              />
              {errors.name && (
                <p className="text-xs text-destructive-form-text mt-0.5">{errors.name.message}</p>
              )}
            </div>

            {/* Display Name */}
            <div>
              <label htmlFor="sli-display-name" className="block text-xs text-muted-foreground mb-1">
                Display Name
              </label>
              <Input id="sli-display-name" {...register('display_name')} placeholder="My SLI" />
            </div>

            {/* Adapter Type */}
            <div>
              <label htmlFor="sli-adapter-type" className="block text-xs text-muted-foreground mb-1">
                Adapter Type
              </label>
              <Input
                id="sli-adapter-type"
                {...register('adapter_type')}
                placeholder="prometheus"
              />
              {errors.adapter_type && (
                <p className="text-xs text-destructive-form-text mt-0.5">{errors.adapter_type.message}</p>
              )}
            </div>

            {/* Mode toggle */}
            <div>
              <span className="block text-xs text-muted-foreground mb-1">Mode</span>
              <div className="flex gap-4">
                <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
                  <input
                    type="radio"
                    name="sli-mode"
                    value="raw"
                    checked={mode === 'raw'}
                    onChange={() => setMode('raw')}
                  />
                  <span className="text-foreground">Raw</span>
                </label>
                <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
                  <input
                    type="radio"
                    name="sli-mode"
                    value="aggregated"
                    checked={mode === 'aggregated'}
                    onChange={() => setMode('aggregated')}
                  />
                  <span className="text-foreground">Aggregated</span>
                </label>
              </div>
            </div>

            {/* Mode-specific fields */}
            {mode === 'raw' ? (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-muted-foreground">Indicators</span>
                  <button
                    type="button"
                    aria-label="Add indicator"
                    onClick={() => append({ name: '', query: '' })}
                    className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary"
                  >
                    <Plus className="size-3" /> Add indicator
                  </button>
                </div>
                {errors.indicators?.root && (
                  <p className="text-xs text-destructive-form-text mb-1">{errors.indicators.root.message}</p>
                )}
                <div className="space-y-1.5">
                  {fields.map((field, i) => (
                    <div key={field.id} className="flex gap-1.5 items-center">
                      <Input
                        {...register(`indicators.${i}.name`)}
                        placeholder="metric_name"
                        className="w-1/3 font-mono text-xs"
                      />
                      <Input
                        {...register(`indicators.${i}.query`)}
                        placeholder="rate(metric[5m])"
                        className="flex-1 font-mono text-xs"
                      />
                      <button
                        type="button"
                        aria-label="remove indicator"
                        onClick={() => remove(i)}
                        className="text-muted-foreground hover:text-action-destructive"
                      >
                        <X className="size-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <AggregatedModeFields
                queryTemplate={queryTemplate}
                interval={interval}
                methods={methods}
                onQueryTemplateChange={setQueryTemplate}
                onIntervalChange={setInterval}
                onMethodsChange={setMethods}
              />
            )}

            {/* Author */}
            <div>
              <label htmlFor="sli-author" className="block text-xs text-muted-foreground mb-1">
                Author
              </label>
              <Input id="sli-author" {...register('author')} placeholder="your-name" />
            </div>

            {/* Notes */}
            <div>
              <label htmlFor="sli-notes" className="block text-xs text-muted-foreground mb-1">
                Notes
              </label>
              <Input id="sli-notes" {...register('notes')} placeholder="Optional notes" />
            </div>

            {/* Tags */}
            <TagRowEditor rows={tagRows} onChange={setTagRows} />
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-2 px-4 py-3 border-t border-border bg-muted/20">
            <Button size="xs" variant="outline" type="button" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button size="xs" type="submit" disabled={isPending}>
              {submitLabel}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

function TagRowEditor({ rows, onChange }: { rows: TagRow[]; onChange: (rows: TagRow[]) => void }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-muted-foreground">Tags</span>
        <button
          type="button"
          onClick={() => onChange([...rows, { key: '', value: '' }])}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary"
        >
          <Plus className="size-3" /> Add
        </button>
      </div>
      <div className="space-y-1.5">
        {rows.map((row, i) => (
          <div key={i} className="flex gap-1.5 items-center">
            <Input
              value={row.key}
              onChange={e => onChange(rows.map((r, j) => (j === i ? { ...r, key: e.target.value } : r)))}
              placeholder="key"
              className="flex-1"
            />
            <Input
              value={row.value}
              onChange={e => onChange(rows.map((r, j) => (j === i ? { ...r, value: e.target.value } : r)))}
              placeholder="value"
              className="flex-1"
            />
            <button
              type="button"
              aria-label="remove tag"
              onClick={() => onChange(rows.filter((_, j) => j !== i))}
              className="text-muted-foreground hover:text-action-destructive"
            >
              <X className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run all SLI form tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/forms/SliForm.test.tsx`
Expected: all tests PASS (existing + new)

- [ ] **Step 5: Commit**

```
feat(ui): add mode toggle to SLI form with aggregated field support
```

---

## Task 5: SLI Detail View — Aggregated Mode Display

**Files:**
- Modify: `ui/src/features/registry/details/SliDetailView.tsx`

- [ ] **Step 1: Update SliDetailView to show aggregated-mode fields**

In `SliDetailView.tsx`, replace the `{/* Body */}` section's indicators block (the `<div>` containing "Indicators" heading and the indicators table) with a conditional that shows either the indicators table (raw) or the aggregated-mode fields:

Replace the block starting at `{/* Indicators table */}` (approximately lines 132–164) with:

```tsx
        {/* Mode-specific content */}
        {(sli.mode ?? 'raw') === 'raw' ? (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Indicators</p>
            {Object.keys(sli.indicators).length === 0 ? (
              <p className="text-xs text-muted-foreground">No indicators defined.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-1.5 pr-3 text-muted-foreground font-medium w-1/3">
                        Name
                      </th>
                      <th className="text-left py-1.5 text-muted-foreground font-medium">
                        Query
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(sli.indicators).map(([metricName, query]) => (
                      <tr key={metricName} className="border-b border-border/40">
                        <td className="py-1.5 pr-3 font-mono align-top text-foreground">
                          {metricName}
                        </td>
                        <td className="py-1.5 font-mono text-muted-foreground break-all">
                          {highlightVariables(query)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Query Template</p>
              <p className="text-sm font-mono text-foreground break-all">
                {sli.query_template ? highlightVariables(sli.query_template) : '—'}
              </p>
            </div>
            <div className="flex gap-6">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Interval</p>
                <p className="text-sm font-mono text-foreground">{sli.interval ?? '—'}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Methods</p>
                <div className="flex flex-wrap gap-1.5">
                  {(sli.methods ?? []).map(m => (
                    <span
                      key={m}
                      className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary border border-primary/20 font-mono"
                    >
                      {m}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
```

Also add a mode badge to the header badges section. After the `adapter_type` badge span, add:

```tsx
            {(sli.mode ?? 'raw') === 'aggregated' && (
              <span
                className="px-2 py-0.5 text-xs rounded-full border border-primary/40 bg-primary/10 text-primary"
              >
                aggregated
              </span>
            )}
```

- [ ] **Step 2: Commit**

```
feat(ui): show aggregated-mode fields in SLI detail view
```

---

## Task 6: Method Criteria Table Component

**Files:**
- Create: `ui/src/features/registry/forms/MethodCriteriaTable.tsx`
- Create: `ui/src/features/registry/forms/MethodCriteriaTable.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// ui/src/features/registry/forms/MethodCriteriaTable.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MethodCriteriaTable } from './MethodCriteriaTable'
import type { MethodCriteriaOverride } from '@/features/slos/types'

const methods = ['mean', 'p99', 'max']
const defaultBlueprintPass = ['<10']
const defaultBlueprintWeight = 1

describe('MethodCriteriaTable', () => {
  it('renders a row for each method', () => {
    render(
      <MethodCriteriaTable
        methods={methods}
        criteria={{}}
        blueprintPassCriteria={defaultBlueprintPass}
        blueprintWeight={defaultBlueprintWeight}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByText('mean')).toBeInTheDocument()
    expect(screen.getByText('p99')).toBeInTheDocument()
    expect(screen.getByText('max')).toBeInTheDocument()
  })

  it('shows inherited values in muted style when no override exists', () => {
    render(
      <MethodCriteriaTable
        methods={methods}
        criteria={{}}
        blueprintPassCriteria={defaultBlueprintPass}
        blueprintWeight={defaultBlueprintWeight}
        onChange={vi.fn()}
      />,
    )
    // All pass criteria inputs should show the blueprint default
    const passInputs = screen.getAllByDisplayValue('<10')
    expect(passInputs.length).toBe(3)
    // Inherited values have italic styling — check via class
    passInputs.forEach(input => {
      expect(input).toHaveClass('italic')
    })
  })

  it('shows override values without muted style', () => {
    const criteria: Record<string, MethodCriteriaOverride> = {
      p99: { pass_threshold: ['<25'], weight: 2 },
    }
    render(
      <MethodCriteriaTable
        methods={methods}
        criteria={criteria}
        blueprintPassCriteria={defaultBlueprintPass}
        blueprintWeight={defaultBlueprintWeight}
        onChange={vi.fn()}
      />,
    )
    const p99Input = screen.getByDisplayValue('<25')
    expect(p99Input).not.toHaveClass('italic')
  })

  it('calls onChange when pass criteria is edited', () => {
    const onChange = vi.fn()
    render(
      <MethodCriteriaTable
        methods={methods}
        criteria={{}}
        blueprintPassCriteria={defaultBlueprintPass}
        blueprintWeight={defaultBlueprintWeight}
        onChange={onChange}
      />,
    )
    const passInputs = screen.getAllByDisplayValue('<10')
    fireEvent.change(passInputs[1], { target: { value: '<25' } })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        p99: expect.objectContaining({ pass_threshold: ['<25'] }),
      }),
    )
  })

  it('calls onChange when weight is edited', () => {
    const onChange = vi.fn()
    render(
      <MethodCriteriaTable
        methods={methods}
        criteria={{}}
        blueprintPassCriteria={defaultBlueprintPass}
        blueprintWeight={defaultBlueprintWeight}
        onChange={onChange}
      />,
    )
    const weightInputs = screen.getAllByDisplayValue('1')
    fireEvent.change(weightInputs[1], { target: { value: '3' } })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        p99: expect.objectContaining({ weight: 3 }),
      }),
    )
  })

  it('calls onChange when key_sli is toggled', () => {
    const onChange = vi.fn()
    render(
      <MethodCriteriaTable
        methods={methods}
        criteria={{}}
        blueprintPassCriteria={defaultBlueprintPass}
        blueprintWeight={defaultBlueprintWeight}
        onChange={onChange}
      />,
    )
    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0]) // Toggle key_sli for first method (mean)
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        mean: expect.objectContaining({ key_sli: true }),
      }),
    )
  })

  it('removes override when value is reset to blueprint default', () => {
    const criteria: Record<string, MethodCriteriaOverride> = {
      p99: { pass_threshold: ['<25'], weight: 2 },
    }
    const onChange = vi.fn()
    render(
      <MethodCriteriaTable
        methods={methods}
        criteria={criteria}
        blueprintPassCriteria={defaultBlueprintPass}
        blueprintWeight={defaultBlueprintWeight}
        onChange={onChange}
      />,
    )
    const p99Input = screen.getByDisplayValue('<25')
    fireEvent.change(p99Input, { target: { value: '<10' } })
    // When pass goes back to default AND weight was 2 (not default), only pass is removed
    const call = onChange.mock.calls[0][0]
    expect(call.p99.pass_threshold).toBeUndefined()
    expect(call.p99.weight).toBe(2)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/ui-test.sh --tail 15 src/features/registry/forms/MethodCriteriaTable.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement the component**

```tsx
// ui/src/features/registry/forms/MethodCriteriaTable.tsx
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

    // Remove fields that match blueprint defaults
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
                      onChange={e => updateMethod(method, { weight: parseFloat(e.target.value) || 1 })}
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 15 src/features/registry/forms/MethodCriteriaTable.test.tsx`
Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```
feat(ui): add MethodCriteriaTable component for SLO template method overrides
```

---

## Task 7: SLO Wizard — Method Criteria Integration

**Files:**
- Modify: `ui/src/features/registry/forms/SloWizard.tsx`
- Modify: `ui/src/features/registry/forms/WizardStepIndicators.tsx`

This task wires the `MethodCriteriaTable` into the SLO wizard. When the selected SLI has `mode === 'aggregated'`, the wizard shows the method criteria table instead of the per-indicator criteria rows.

- [ ] **Step 1: Update WizardStepIndicators to accept and display a method criteria section**

In `WizardStepIndicators.tsx`, add a prop for aggregated mode and render the MethodCriteriaTable when applicable:

```tsx
// At the top of WizardStepIndicators.tsx, add import:
import { MethodCriteriaTable } from './MethodCriteriaTable'
import type { MethodCriteriaOverride } from '@/features/slos/types'
```

Add new props to the interface:

```tsx
interface WizardStepIndicatorsProps {
  rows: IndicatorRow[]
  onChange: (rows: IndicatorRow[]) => void
  // Aggregated mode support
  aggregatedMode?: boolean
  aggregatedMethods?: string[]
  methodCriteria?: Record<string, MethodCriteriaOverride>
  onMethodCriteriaChange?: (criteria: Record<string, MethodCriteriaOverride>) => void
  blueprintPassCriteria?: string[]
  blueprintWeight?: number
}
```

At the start of the `WizardStepIndicators` function body, add an early return for aggregated mode:

```tsx
  if (aggregatedMode && aggregatedMethods && aggregatedMethods.length > 0) {
    return (
      <div className="space-y-3">
        <div>
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-[10px] font-bold">3</span>
            <h3 className="text-sm font-semibold text-foreground">Method Criteria</h3>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            The linked SLI uses aggregated mode. Set criteria per method — inherited values shown in <span className="italic">italic</span>.
          </p>
        </div>
        <MethodCriteriaTable
          methods={aggregatedMethods}
          criteria={methodCriteria ?? {}}
          blueprintPassCriteria={blueprintPassCriteria ?? ['<100']}
          blueprintWeight={blueprintWeight ?? 1}
          onChange={onMethodCriteriaChange ?? (() => {})}
        />
      </div>
    )
  }
```

- [ ] **Step 2: Update SloWizard to detect aggregated SLI and pass method criteria**

In `SloWizard.tsx`, add state for method criteria and detect aggregated SLI mode:

Add import at the top:

```tsx
import type { MethodCriteriaOverride } from '@/features/slos/types'
```

Add state after the `comparison` state declaration:

```tsx
  const [methodCriteria, setMethodCriteria] = useState<Record<string, MethodCriteriaOverride>>(
    editSlo?.method_criteria ?? {},
  )
```

Add detection logic after the `useSliDetail` call. The `fullSli` variable already exists:

```tsx
  const isAggregatedSli = fullSli?.mode === 'aggregated'
  const aggregatedMethods = fullSli?.methods ?? []
```

Update the `WizardStepIndicators` render in the JSX (the `{showStep3 && ...}` block):

Replace the `<WizardStepIndicators ...>` call with:

```tsx
          <WizardStepIndicators
            rows={indicatorRows}
            onChange={setIndicatorRows}
            aggregatedMode={isAggregatedSli}
            aggregatedMethods={aggregatedMethods}
            methodCriteria={methodCriteria}
            onMethodCriteriaChange={setMethodCriteria}
            blueprintPassCriteria={
              indicatorRows.find(r => r.checked)?.passCriteria.map(c =>
                `${c.operator}${c.value}${c.suffix}`,
              ) ?? ['<100']
            }
            blueprintWeight={indicatorRows.find(r => r.checked)?.weight ?? 1}
          />
```

Update the `handleSubmit` function to include `method_criteria` in the payload:

After `variables` computation but before `createMutation.mutate(...)`:

```tsx
    const mc = Object.keys(methodCriteria).length > 0 ? methodCriteria : undefined
```

In the `createMutation.mutate(...)` call, add `method_criteria: mc` to the payload object.

Update the `showStep4` condition to also consider aggregated mode:

```tsx
  const showStep4 = isAggregatedSli
    ? Object.keys(methodCriteria).length >= 0  // always show comparison for aggregated
    : indicatorRows.some(
        (r) => r.checked && r.passCriteria.some((c) => c.value !== 0),
      )
```

- [ ] **Step 3: Commit**

```
feat(ui): integrate method criteria table into SLO wizard for aggregated SLIs
```

---

## Task 8: SLO Detail View — Method Criteria Display

**Files:**
- Modify: `ui/src/features/registry/details/SloDetailView.tsx`

- [ ] **Step 1: Add method criteria display to SloDetailView**

In `SloDetailView.tsx`, add a section after the `{/* Objectives table */}` block to show method_criteria when present:

```tsx
        {/* Method criteria overrides (aggregated-mode SLO templates) */}
        {slo.method_criteria && Object.keys(slo.method_criteria).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Method Criteria Overrides</p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-1.5 pr-3 text-muted-foreground font-medium">Method</th>
                    <th className="text-left py-1.5 pr-3 text-muted-foreground font-medium">Pass</th>
                    <th className="text-left py-1.5 pr-3 text-muted-foreground font-medium">Weight</th>
                    <th className="text-left py-1.5 text-muted-foreground font-medium">Key SLI</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(slo.method_criteria).map(([method, override]) => (
                    <tr key={method} className="border-b border-border/40">
                      <td className="py-1.5 pr-3 font-mono text-foreground">{method}</td>
                      <td className="py-1.5 pr-3 font-mono text-muted-foreground">
                        {override.pass_threshold?.join(', ') ?? '—'}
                      </td>
                      <td className="py-1.5 pr-3 text-muted-foreground">
                        {override.weight ?? '—'}
                      </td>
                      <td className="py-1.5 text-muted-foreground">
                        {override.key_sli ? '◆' : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
```

- [ ] **Step 2: Commit**

```
feat(ui): show method criteria overrides in SLO detail view
```

---

## Task 9: SLI Breakdown Table — Grouped Aggregated Display

**Files:**
- Modify: `ui/src/features/evaluations/components/SLIBreakdownTable.tsx`
- Modify: `ui/src/features/evaluations/components/SLIBreakdownTable.test.tsx`

- [ ] **Step 1: Write the failing tests for grouped display**

Append these tests to `SLIBreakdownTable.test.tsx`:

```tsx
const aggregatedIndicators: IndicatorResult[] = [
  {
    metric: 'cpu.mean',
    display_name: 'cpu.mean',
    value: 4.3,
    compared_value: 4.1,
    change_absolute: 0.2,
    change_relative_pct: 4.88,
    aggregation: 'mean',
    status: 'pass',
    score: 1,
    weight: 1,
    key_sli: false,
    pass_targets: [{ criteria: '<10', target_value: 10, violated: false }],
    warning_targets: null,
  },
  {
    metric: 'cpu.p99',
    display_name: 'cpu.p99',
    value: 18.7,
    compared_value: 17.0,
    change_absolute: 1.7,
    change_relative_pct: 10.0,
    aggregation: 'p99',
    status: 'pass',
    score: 1,
    weight: 2,
    key_sli: true,
    pass_targets: [{ criteria: '<25', target_value: 25, violated: false }],
    warning_targets: null,
  },
  {
    metric: 'cpu.max',
    display_name: 'cpu.max',
    value: 31.2,
    compared_value: 28.0,
    change_absolute: 3.2,
    change_relative_pct: 11.43,
    aggregation: 'max',
    status: 'pass',
    score: 1,
    weight: 1,
    key_sli: false,
    pass_targets: [{ criteria: '<40', target_value: 40, violated: false }],
    warning_targets: null,
  },
  {
    metric: 'error_rate',
    display_name: 'Error Rate',
    value: 0.02,
    compared_value: 0.01,
    change_absolute: 0.01,
    change_relative_pct: 100.0,
    aggregation: 'avg',
    status: 'pass',
    score: 1,
    weight: 3,
    key_sli: false,
    pass_targets: [{ criteria: '<0.05', target_value: 0.05, violated: false }],
    warning_targets: null,
  },
]

const sliMetadata: Record<string, { mode: 'aggregated'; expected_samples: number; actual_samples: number; missing_pct: number; chunks_failed: number }> = {
  cpu: {
    mode: 'aggregated',
    expected_samples: 1440,
    actual_samples: 1387,
    missing_pct: 3.7,
    chunks_failed: 0,
  },
}

describe('SLIBreakdownTable grouped display', () => {
  it('renders a group header for aggregated SLI metrics', () => {
    render(
      <SLIBreakdownTable
        indicators={aggregatedIndicators}
        sliMetadata={sliMetadata}
      />,
    )
    expect(screen.getByText(/cpu/)).toBeInTheDocument()
    expect(screen.getByText(/1387.*1440/)).toBeInTheDocument()
  })

  it('renders ungrouped rows for non-aggregated metrics', () => {
    render(
      <SLIBreakdownTable
        indicators={aggregatedIndicators}
        sliMetadata={sliMetadata}
      />,
    )
    expect(screen.getByText('Error Rate')).toBeInTheDocument()
  })

  it('shows method suffix in grouped rows instead of full metric name', () => {
    render(
      <SLIBreakdownTable
        indicators={aggregatedIndicators}
        sliMetadata={sliMetadata}
      />,
    )
    // Within the group, should show just the method part
    expect(screen.getByText('mean')).toBeInTheDocument()
    expect(screen.getByText('p99')).toBeInTheDocument()
    expect(screen.getByText('max')).toBeInTheDocument()
  })

  it('shows low-confidence warning when missing_pct exceeds threshold', () => {
    const highMissing = {
      cpu: { ...sliMetadata.cpu, missing_pct: 25.0 },
    }
    render(
      <SLIBreakdownTable
        indicators={aggregatedIndicators}
        sliMetadata={highMissing}
      />,
    )
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument()
  })

  it('works without sliMetadata (backward compatible)', () => {
    render(<SLIBreakdownTable indicators={aggregatedIndicators} />)
    // Should still render all rows, just without group headers
    expect(screen.getByText('cpu.mean')).toBeInTheDocument()
    expect(screen.getByText('Error Rate')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/components/SLIBreakdownTable.test.tsx`
Expected: new tests FAIL (sliMetadata prop doesn't exist)

- [ ] **Step 3: Implement grouped display**

Replace the content of `SLIBreakdownTable.tsx` with:

```tsx
// src/features/evaluations/components/SLIBreakdownTable.tsx
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { fmt } from '@/lib/format'
import { STATUS_TEXT } from '@/lib/status'
import type { IndicatorResult } from '../types'
import type { SliMetadata } from '../types'

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}%`
}

const LOW_CONFIDENCE_THRESHOLD = 20

interface SliGroup {
  prefix: string
  indicators: IndicatorResult[]
  metadata?: SliMetadata
}

function groupIndicators(
  indicators: IndicatorResult[],
  sliMetadata?: Record<string, SliMetadata>,
): (IndicatorResult | SliGroup)[] {
  if (!sliMetadata || Object.keys(sliMetadata).length === 0) {
    return indicators
  }

  const result: (IndicatorResult | SliGroup)[] = []
  const grouped = new Set<string>()

  // Build groups from metadata keys
  const prefixMap = new Map<string, IndicatorResult[]>()
  for (const ind of indicators) {
    const dotIdx = ind.metric.lastIndexOf('.')
    if (dotIdx > 0) {
      const prefix = ind.metric.substring(0, dotIdx)
      if (sliMetadata[prefix]) {
        if (!prefixMap.has(prefix)) prefixMap.set(prefix, [])
        prefixMap.get(prefix)!.push(ind)
        grouped.add(ind.metric)
      }
    }
  }

  // Emit items in original order, replacing first member of each group with the group
  const emittedGroups = new Set<string>()
  for (const ind of indicators) {
    if (grouped.has(ind.metric)) {
      const dotIdx = ind.metric.lastIndexOf('.')
      const prefix = ind.metric.substring(0, dotIdx)
      if (!emittedGroups.has(prefix)) {
        emittedGroups.add(prefix)
        result.push({
          prefix,
          indicators: prefixMap.get(prefix)!,
          metadata: sliMetadata[prefix],
        })
      }
    } else {
      result.push(ind)
    }
  }

  return result
}

function isGroup(item: IndicatorResult | SliGroup): item is SliGroup {
  return 'prefix' in item && 'indicators' in item
}

interface Props {
  indicators: IndicatorResult[]
  sliMetadata?: Record<string, SliMetadata>
  onIndicatorClick?: (metric: string, tabGroup: string) => void
}

export function SLIBreakdownTable({ indicators, sliMetadata, onIndicatorClick }: Props) {
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())

  const items = groupIndicators(indicators, sliMetadata)

  function handleRowClick(metric: string, tabGroup: string) {
    setSelectedMetric(metric)
    onIndicatorClick?.(metric, tabGroup)
  }

  function toggleGroup(prefix: string) {
    setCollapsedGroups(prev => {
      const next = new Set(prev)
      if (next.has(prefix)) next.delete(prefix)
      else next.add(prefix)
      return next
    })
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-table-row-bg">
      <table className="w-full text-sm text-left">
        <thead className="text-xs uppercase text-muted-foreground bg-table-header-bg border-b border-border">
          <tr>
            <th className="px-2 py-3 text-center w-6 text-indicator-key-sli" title="Key SLI">◆</th>
            <th className="px-4 py-3">Indicator</th>
            <th className="px-4 py-3 text-right">Value</th>
            <th className="px-4 py-3 text-right">Baseline</th>
            <th className="px-4 py-3 text-right">Δ</th>
            <th className="px-4 py-3 text-right">Weight</th>
            <th className="px-4 py-3 text-right">Score</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Pass criteria</th>
            <th className="px-4 py-3">Warn criteria</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => {
            if (isGroup(item)) {
              const collapsed = collapsedGroups.has(item.prefix)
              const meta = item.metadata
              const lowConfidence = meta && meta.missing_pct > LOW_CONFIDENCE_THRESHOLD
              return (
                <GroupRows
                  key={item.prefix}
                  group={item}
                  collapsed={collapsed}
                  lowConfidence={!!lowConfidence}
                  onToggle={() => toggleGroup(item.prefix)}
                  selectedMetric={selectedMetric}
                  onRowClick={handleRowClick}
                  onIndicatorClick={onIndicatorClick}
                  startIdx={idx}
                />
              )
            }
            return (
              <IndicatorRow
                key={item.metric}
                ind={item}
                idx={idx}
                isSelected={item.metric === selectedMetric}
                onClick={handleRowClick}
                onIndicatorClick={onIndicatorClick}
              />
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

interface GroupRowsProps {
  group: SliGroup
  collapsed: boolean
  lowConfidence: boolean
  onToggle: () => void
  selectedMetric: string | null
  onRowClick: (metric: string, tabGroup: string) => void
  onIndicatorClick?: (metric: string, tabGroup: string) => void
  startIdx: number
}

function GroupRows({ group, collapsed, lowConfidence, onToggle, selectedMetric, onRowClick, onIndicatorClick, startIdx }: GroupRowsProps) {
  const meta = group.metadata
  return (
    <>
      {/* Group header row */}
      <tr
        className="bg-muted/30 border-b border-border cursor-pointer hover:bg-muted/50 transition-colors"
        onClick={onToggle}
      >
        <td className="px-2 py-2" />
        <td className="px-4 py-2 font-medium" colSpan={9}>
          <div className="flex items-center gap-2">
            {collapsed
              ? <ChevronRight className="size-3.5 text-muted-foreground" />
              : <ChevronDown className="size-3.5 text-muted-foreground" />
            }
            <span className="text-foreground">{group.prefix}</span>
            {meta && (
              <span className="text-xs text-muted-foreground font-mono">
                {meta.actual_samples}/{meta.expected_samples} samples ({meta.missing_pct.toFixed(1)}% missing)
              </span>
            )}
            {lowConfidence && (
              <span className="text-xs text-warning px-1.5 py-0.5 rounded bg-warning/10 border border-warning/20">
                low confidence
              </span>
            )}
          </div>
        </td>
      </tr>
      {/* Child rows */}
      {!collapsed && group.indicators.map((ind, i) => {
        const methodSuffix = ind.metric.substring(group.prefix.length + 1)
        return (
          <IndicatorRow
            key={ind.metric}
            ind={ind}
            idx={startIdx + 1 + i}
            isSelected={ind.metric === selectedMetric}
            onClick={onRowClick}
            onIndicatorClick={onIndicatorClick}
            displayName={methodSuffix}
            indented
          />
        )
      })}
    </>
  )
}

interface IndicatorRowProps {
  ind: IndicatorResult
  idx: number
  isSelected: boolean
  onClick: (metric: string, tabGroup: string) => void
  onIndicatorClick?: (metric: string, tabGroup: string) => void
  displayName?: string
  indented?: boolean
}

function IndicatorRow({ ind, idx, isSelected, onClick, onIndicatorClick, displayName, indented }: IndicatorRowProps) {
  const zebraBase = idx % 2 === 0 ? 'bg-table-row-bg' : 'bg-table-row-alt'
  const rowBg = isSelected ? 'bg-table-row-selected' : zebraBase
  const rowHover = isSelected ? 'hover:bg-table-row-selected' : 'hover:bg-table-row-hover'
  const rowRing = isSelected ? 'ring-1 ring-inset ring-muted-foreground/60' : ''
  const label = displayName ?? ind.display_name || ind.metric

  return (
    <tr
      onClick={() => onClick(ind.metric, ind.tab_group ?? 'summary')}
      className={`transition-colors group border-b border-border/60 last:border-0 cursor-pointer ${rowBg} ${rowHover} ${rowRing}`}
    >
      <td className="px-2 py-3 text-center">
        {ind.key_sli && (
          <span className="text-indicator-key-sli text-xs leading-none" title="Key SLI">◆</span>
        )}
      </td>
      <td className={`px-4 py-3 font-medium whitespace-nowrap ${indented ? 'pl-10' : ''}`}>
        {onIndicatorClick ? (
          <button
            className="text-left group/name"
            title={`${ind.metric} — click to go to trend chart`}
          >
            <span className="flex items-center gap-1">
              <span className="text-foreground group-hover/name:text-link-hover transition-colors underline decoration-dotted underline-offset-2 decoration-muted-foreground/60 group-hover/name:decoration-link-hover">
                {label}
              </span>
              <span className="text-muted-foreground/60 group-hover/name:text-link-hover text-xs">↓</span>
            </span>
          </button>
        ) : (
          <span className="text-foreground" title={ind.metric}>
            {label}
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-right font-mono">{fmt(ind.value)}</td>
      <td className="px-4 py-3 text-right font-mono text-muted-foreground">{fmt(ind.compared_value)}</td>
      <td className="px-4 py-3 text-right font-mono">
        {ind.change_relative_pct != null ? (
          <span className={STATUS_TEXT[ind.status] ?? 'text-foreground'}>
            {fmtPct(ind.change_relative_pct)}
          </span>
        ) : '—'}
      </td>
      <td className="px-4 py-3 text-right text-muted-foreground">{ind.weight}</td>
      <td className="px-4 py-3 text-right font-mono">{fmt(ind.score)}</td>
      <td className={`px-4 py-3 font-semibold uppercase text-xs ${STATUS_TEXT[ind.status] ?? ''}`}>
        {ind.status}
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground">
        {ind.pass_targets?.map((t, i) => (
          <div key={i} className={`font-mono ${t.violated ? 'text-destructive-form-text' : ''}`}>
            {t.criteria}{t.violated && ' ✗'}
          </div>
        ))}
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground">
        {ind.warning_targets?.map((t, i) => (
          <div key={i} className="font-mono">{t.criteria}</div>
        ))}
      </td>
    </tr>
  )
}
```

- [ ] **Step 4: Update EvaluationIndicatorSection to pass sliMetadata**

In `EvaluationIndicatorSection.tsx`, pass the metadata through to `SLIBreakdownTable`:

The evaluation detail object has `sli_metadata` in a nested structure. Extract it and pass it:

```tsx
// After the useTabState call, extract metadata:
  const sliMetadata = (ev as Record<string, unknown>).sli_metadata as
    Record<string, import('../types').SliMetadata> | undefined
```

Then add `sliMetadata={sliMetadata}` to the `<SLIBreakdownTable>` render.

- [ ] **Step 5: Run all breakdown table tests**

Run: `./scripts/ui-test.sh --tail 25 src/features/evaluations/components/SLIBreakdownTable.test.tsx`
Expected: all tests PASS (existing + new grouped tests)

- [ ] **Step 6: Commit**

```
feat(ui): group aggregated SLI rows in breakdown table with sample metadata
```

---

## Task 9a: Backend — Pass sli_metadata Through to API Response

**Files:**
- Modify: `api/app/modules/quality_gate/presenter.py`
- Modify: `api/app/modules/quality_gate/schemas.py`
- Modify: `api/tests/services/test_presenter.py`

Phase 1a stores `sli_metadata` inside `Evaluation.job_stats`, but the presenter's `build_detail()` function does not extract it into the API response. The UI needs it for sample-count badges and low-confidence warnings.

- [ ] **Step 1: Add sli_metadata field to EvaluationDetail schema**

In `api/app/modules/quality_gate/schemas.py`, find the `EvaluationDetail` model and add:

```python
    sli_metadata: dict[str, Any] | None = None
```

- [ ] **Step 2: Pass sli_metadata through in presenter.py**

In `api/app/modules/quality_gate/presenter.py`, in the `build_detail()` function, add `sli_metadata` to the dict passed to `EvaluationDetail.model_validate()`:

```python
            'sli_metadata': job_stats_detail.get('sli_metadata'),
```

Add this line after the `'total_score_warning_threshold'` line (around line 107).

- [ ] **Step 3: Add test for sli_metadata round-trip**

In `api/tests/services/test_presenter.py`, add a test that verifies `sli_metadata` from `job_stats` appears in the detail response. Use the existing test patterns in that file — create an evaluation with `job_stats={'sli_metadata': {'cpu': {'mode': 'aggregated', 'expected_samples': 100, 'actual_samples': 95, 'missing_pct': 5.0, 'chunks_failed': 0}}}` and assert `detail.sli_metadata['cpu']['expected_samples'] == 100`.

- [ ] **Step 4: Run API tests**

Run: `./scripts/api-test.sh --tail 10`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```
fix(api): pass sli_metadata from job_stats through to evaluation detail response
```

---

## Task 9b: Fix Evaluation Column Selection — Show All SLOs Together

**Files:**
- Modify: `ui/src/features/navigator/components/AssetPanel.tsx`
- Modify: `ui/src/features/navigator/components/AssetHeatmap.tsx`
- Modify: `ui/src/features/navigator/components/AssetPanelHeatmapView.tsx`
- Modify: `ui/src/features/evaluations/components/EvaluationIndicatorSection.tsx`

**Bug:** When an asset has multiple SLO bindings (e.g., a raw SLO + an aggregated SLO), the heatmap shows one row per SLO. Each cell maps to a single evaluation ID. Clicking a cell loads only THAT SLO's evaluation — the user sees only the aggregated indicators (cpu.mean, cpu.p99, cpu.max) OR only the raw indicators (error_rate), never both together. The user expects clicking anywhere in a time column to show ALL evaluations for that asset at that time slot, with all indicators and all trend charts combined.

**Root cause:** `AssetPanel` holds `selectedEvalId: string | undefined` — a single evaluation. `useEvaluationDetail(effectiveEvalId)` fetches one evaluation. The entire detail view (header, breakdown table, trend charts) is driven by this single `ev` object.

**Fix approach:** Change the heatmap cell click to select a **time slot** (period_start), not a single eval ID. The AssetPanel then fetches ALL evaluations for that asset at that time slot and merges their `indicator_results` into a combined view. The evaluation header shows a summary (e.g., worst result across SLOs), and the breakdown table + trends show all indicators from all SLOs.

This is a significant architectural change. The implementation details depend on how much of the detail view assumes a single evaluation. The steps below outline the approach:

- [ ] **Step 1: Change heatmap click to emit time slot instead of eval ID**

In `AssetHeatmap.tsx`, change `onCellClick` to emit `{ periodStart: string, evalIds: string[] }` instead of a single `evalId`. The heatmap data already contains period_start per column — collect all eval IDs for that column.

Update `AssetPanelHeatmapView.tsx` and `AssetPanel.tsx` to accept the new callback shape.

- [ ] **Step 2: Add multi-eval fetching to AssetPanel**

In `AssetPanel.tsx`, replace `useEvaluationDetail(effectiveEvalId)` with parallel queries for all eval IDs in the selected time slot:

```tsx
const [selectedSlot, setSelectedSlot] = useState<{ periodStart: string; evalIds: string[] } | undefined>()

// Fetch all evals for the selected slot
const evalQueries = useQueries({
  queries: (selectedSlot?.evalIds ?? []).map(id => ({
    queryKey: evaluationKeys.detail(id),
    queryFn: () => fetchEvaluationDetail(id),
    enabled: !!id,
  })),
})

const allEvals = evalQueries
  .filter(q => q.data != null)
  .map(q => q.data!)
```

- [ ] **Step 3: Merge indicator results for combined display**

Create a helper that merges `indicator_results` from multiple evaluations and collects `sli_metadata` across all:

```tsx
function mergeEvalIndicators(evals: EvaluationDetail[]): {
  indicators: IndicatorResult[]
  sliMetadata: Record<string, SliMetadata>
  worstResult: string
  combinedScore: number
} {
  const indicators = evals.flatMap(ev => ev.indicator_results)
  const sliMetadata: Record<string, SliMetadata> = {}
  for (const ev of evals) {
    if (ev.sli_metadata) Object.assign(sliMetadata, ev.sli_metadata)
  }
  // Worst result across all evals
  const results = evals.map(ev => ev.result)
  const worstResult = results.includes('fail') ? 'fail'
    : results.includes('warning') ? 'warning' : 'pass'
  // Average score weighted by indicator count
  const totalWeight = evals.reduce((sum, ev) => sum + ev.indicator_results.length, 0)
  const combinedScore = totalWeight > 0
    ? evals.reduce((sum, ev) => sum + ev.score * ev.indicator_results.length, 0) / totalWeight
    : 0
  return { indicators, sliMetadata, worstResult, combinedScore }
}
```

- [ ] **Step 4: Update EvaluationIndicatorSection to accept merged data**

Pass the merged `indicators` and `sliMetadata` to `EvaluationIndicatorSection` instead of a single `ev.indicator_results`.

- [ ] **Step 5: Update evaluation header to show multi-SLO summary**

When multiple evaluations are selected, the header should show:
- Time range (shared across all evals)
- Combined result (worst of all SLOs)
- List of SLO names involved
- Individual SLO scores as sub-items

- [ ] **Step 6: Verify manually**

Click any cell in a heatmap column → detail view shows indicators from ALL SLOs for that time slot. Trend charts show all metrics. Table shows all indicators (grouped by SLI prefix for aggregated, ungrouped for raw).

- [ ] **Step 7: Commit**

```
feat(ui): show all SLO evaluations together when selecting a heatmap time column
```

---

## Task 10: Bootstrap Data — Aggregated SLI + SLO Template

**Files:**
- Modify: `bootstrap_mock/manifests/sli-definitions.yaml`
- Modify: `bootstrap_mock/manifests/slo-definitions.yaml`
- Modify: `clients/python/tropek_client/manifest.py`

- [ ] **Step 1: Add aggregated SLI to bootstrap manifests**

Append to `bootstrap_mock/manifests/sli-definitions.yaml`:

```yaml
---
api_version: tropek/v1
kind: SLI
metadata:
  name: process-cpu-agg
  display_name: Process CPU (Aggregated)
  author: bootstrap
  notes: Aggregated-mode SLI for per-process CPU — computes mean, p99, and max from time-series data.
  tags:
    domain: endpoint-monitoring
    mode: aggregated
spec:
  adapter_type: prometheus
  mode: aggregated
  query_template: 'rate(windows_process_cpu_time_total{instance="$host",process="$process_name"}[$interval]) * 100'
  interval: 1m
  methods:
    - mean
    - p99
    - max
```

- [ ] **Step 2: Add SLO template with method_criteria**

Append to `bootstrap_mock/manifests/slo-definitions.yaml`:

```yaml
---
api_version: tropek/v1
kind: SLO
metadata:
  name: process-cpu-agg-slo
  display_name: Process CPU (Aggregated)
  author: bootstrap
  notes: SLO template using aggregated-mode SLI with per-method criteria overrides.
spec:
  sli_name: process-cpu-agg
  kind: template
  objectives:
    - sli: process_cpu
      pass_threshold:
        - "<25"
      weight: 1
      key_sli: false
  method_criteria:
    mean:
      pass_threshold:
        - "<10"
    p99:
      pass_threshold:
        - "<25"
      weight: 2
      key_sli: true
    max:
      pass_threshold:
        - "<40"
  total_score:
    pass: 90
    warning: 75
```

- [ ] **Step 3: Update manifest loader to pass through new fields**

In `clients/python/tropek_client/manifest.py`, update the SLI `_create()` function to include aggregated fields. Find where the SLI creation call is made and add:

```python
# For SLI creation — after adapter_type, add these optional fields:
mode=doc.spec.get("mode"),
query_template=doc.spec.get("query_template"),
interval=doc.spec.get("interval"),
methods=doc.spec.get("methods"),
```

For SLO creation, add `method_criteria`:

```python
# For SLO creation — add this optional field:
method_criteria=doc.spec.get("method_criteria"),
```

These pass through as kwargs to the API — the client's `create()` uses `**kwargs` so no model changes are needed.

- [ ] **Step 4: Commit**

```
feat: add aggregated-mode SLI and SLO template to bootstrap manifests
```

---

## Task 11: Run Full Test Suite

- [ ] **Step 1: Run all UI tests**

Run: `./scripts/ui-test.sh --tail 20`
Expected: all tests PASS

- [ ] **Step 2: Run API unit tests**

Run: `./scripts/api-test.sh --tail 5`
Expected: all tests PASS

- [ ] **Step 3: Fix any failing tests**

If any tests fail, diagnose and fix. Likely causes:
- Existing SLI form tests may need `mode: 'raw'` added to `mockSli` fixture
- Type changes may require updating test fixtures

- [ ] **Step 4: Commit any fixes**

```
fix(ui): update test fixtures for aggregated-mode type changes
```

---

## Summary

| Task | Component | Tests | Files |
|------|-----------|-------|-------|
| 1 | Aggregation constants | — | 1 new |
| 2 | TypeScript types | — | 3 modified |
| 3 | AggregatedModeFields | 8 tests | 2 new |
| 4 | SLI Form mode toggle | 5 tests | 2 modified |
| 5 | SLI Detail aggregated view | — | 1 modified |
| 6 | MethodCriteriaTable | 7 tests | 2 new |
| 7 | SLO Wizard integration | — | 2 modified |
| 8 | SLO Detail method criteria | — | 1 modified |
| 9 | SLI Breakdown grouping | 5 tests | 2 modified |
| 9a | Backend sli_metadata passthrough | 1 test | 3 modified |
| 9b | Multi-SLO eval column fix | — | 4 modified |
| 10 | Bootstrap data | — | 3 modified |
| 11 | Full test suite | all | — |
