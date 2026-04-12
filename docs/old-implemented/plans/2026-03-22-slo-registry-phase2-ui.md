# SLO Registry Phase 2 — UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the SLO Registry page with a 3-mode sidebar (Asset | SLO | Datasource), drill-down entity trees, datasource/SLI CRUD UI, SLO creation wizard with structured criteria input, and universal tag filtering — designed for 400+ SLO scale.

**Architecture:** The existing `SloRegistryPage` is replaced with a sidebar-driven layout using a segmented control to switch between three tree modes. Each mode renders the same entity graph from a different root (assets drill to SLOs, SLOs drill to SLIs, datasources drill to SLIs). The main panel shows detail/edit views for the selected entity. TDD is required — every component gets tests before implementation.

**Tech Stack:** React 19, TypeScript 5.9, Vite 8, Tailwind CSS v4, React Query, react-hook-form + zod, shadcn/ui (dialog, tabs, popover, command), Vitest + React Testing Library.

**Testing strategy:** TDD at all levels except E2E. Unit tests for pure logic (criteria parsing, variable merge). Component tests for every UI component (render, interaction, edge cases). Integration tests for hooks with mocked fetch. No Playwright/E2E tests.

---

## Important: Module Consolidation

The existing codebase has `DataSource` and `SliDefinition` types duplicated in `features/slos/types.ts` (simplified versions used by `SloLinkDialog`). This plan consolidates:

- **`DataSource`** → canonical definition in `features/datasources/types.ts`. Remove from `slos/types.ts`.
- **`SliDefinition`** → canonical definition in `features/slis/types.ts`. Remove from `slos/types.ts`.
- **`fetchDatasources()`** → canonical in `features/datasources/api.ts`. Remove from `slos/api.ts`.
- **`fetchSliDefinitions()`** → canonical in `features/slis/api.ts`. Remove from `slos/api.ts`.
- **`useDatasources()`** → canonical in `features/datasources/hooks.ts`. Remove from `slos/hooks.ts`.
- **`useSliDefinitions()`** → canonical in `features/slis/hooks.ts`. Remove from `slos/hooks.ts`.

All consumers (e.g., `SloLinkDialog.tsx`) update their imports to the canonical modules.

---

## File Structure

### New files

```
ui/src/
├── features/datasources/              # NEW — Datasource management
│   ├── types.ts                        # DataSource, DataSourceCreate, DataSourceUpdate, TagKeyCount, TagValueCount
│   ├── api.ts                          # CRUD + tag endpoints + adapter_type filter
│   └── hooks.ts                        # React Query hooks
│
├── features/registry/                  # NEW — Registry page orchestration
│   ├── types.ts                        # RegistryMode, SelectedNode, TreeNode, TagFilter types
│   ├── RegistrySidebar.tsx             # Sidebar: segmented control + search + tag filter + tree
│   ├── RegistrySidebar.test.tsx        # Sidebar component tests
│   ├── RegistryTree.tsx                # Tree renderer with expand/collapse
│   ├── RegistryTree.test.tsx           # Tree component tests
│   ├── useRegistryTree.ts             # Hook: builds tree data from API responses per mode
│   ├── useRegistryTree.test.ts        # Hook unit tests (all 3 builders + filter)
│   ├── RegistryDetailPanel.tsx         # Routes selected node to correct detail view
│   └── RegistryDetailPanel.test.tsx    # Detail panel component tests
│
├── features/registry/details/          # NEW — Entity detail views
│   ├── SloDetailView.tsx               # SLO detail: chain, variables, objectives, history
│   ├── SloDetailView.test.tsx
│   ├── SliDetailView.tsx               # SLI detail: indicators table, used-by, history
│   ├── SliDetailView.test.tsx
│   ├── DatasourceDetailView.tsx        # DS detail: connection info, token, used-by
│   ├── DatasourceDetailView.test.tsx
│   ├── AssetBindingView.tsx            # Asset binding cards with variable resolution
│   └── AssetBindingView.test.tsx
│
├── features/registry/forms/            # NEW — Create/edit forms
│   ├── DatasourceForm.tsx              # DS create/edit dialog
│   ├── DatasourceForm.test.tsx
│   ├── SliForm.tsx                     # SLI create/new version dialog
│   ├── SliForm.test.tsx
│   ├── SloWizard.tsx                   # 4-step progressive disclosure wizard
│   ├── SloWizard.test.tsx
│   ├── WizardStepIdentity.tsx          # Step 1: name, display_name, author, notes
│   ├── WizardStepPickSli.tsx           # Step 2: datasource filter + SLI combobox
│   ├── WizardStepIndicators.tsx        # Step 3: indicator checkboxes + criteria
│   ├── WizardStepIndicators.test.tsx
│   ├── WizardStepComparison.tsx        # Step 4: comparison config + score thresholds
│   ├── SloLinkDialogRevised.tsx        # Revised 4-step cascade with searchable comboboxes
│   ├── SloLinkDialogRevised.test.tsx
│   └── criteriaUtils.ts               # Parse/serialize criteria strings
│
├── components/shared/                  # NEW — Reusable across features
│   ├── SearchableComboBox.tsx          # Combobox with search + tag filtering
│   ├── SearchableComboBox.test.tsx
│   ├── TagFilterBar.tsx                # Search + tag pills + add combobox
│   ├── TagFilterBar.test.tsx
│   ├── StructuredCriteriaInput.tsx     # Operator/sign/value/% dropdowns
│   ├── StructuredCriteriaInput.test.tsx
│   ├── BindingChainBreadcrumb.tsx      # SLO → SLI → DS colored badges
│   ├── BindingChainBreadcrumb.test.tsx
│   ├── VariableResolutionPanel.tsx     # Shows merged variable sources
│   └── VariableResolutionPanel.test.tsx
```

### Modified files

```
ui/src/
├── features/slos/types.ts             # MODIFY — meta→tags, add variables, REMOVE DataSource/SliDefinition (moved to canonical modules)
├── features/slos/api.ts               # MODIFY — meta→tags+variables in payload, REMOVE fetchDatasources/fetchSliDefinitions (moved), add tag endpoints
├── features/slos/hooks.ts             # MODIFY — REMOVE useDatasources/useSliDefinitions (moved), add tag hooks
├── features/slos/components/SloLinkDialog.tsx  # MODIFY — update imports to features/datasources and features/slis
├── features/slis/types.ts             # MODIFY — meta→tags, add adapter_type, update SliDefinitionCreate
├── features/slis/api.ts               # MODIFY — add adapter_type+tag_key+tag_val params, add tag endpoints, return SliDefinition[] (unwrap paged)
├── features/slis/hooks.ts             # MODIFY — add adapter_type param, add tag hooks
├── lib/queryKeys.ts                   # MODIFY — add tag keys to datasource/sli/slo key factories
├── pages/SloRegistryPage.tsx          # REPLACE — new registry layout
├── pages/SloRegistryPage.test.tsx     # REPLACE — new tests for registry layout
```

---

## Implementation Tasks

### Task 1: Criteria Utilities (Pure Logic)

**Files:**
- Create: `ui/src/features/registry/forms/criteriaUtils.ts`
- Test: `ui/src/features/registry/forms/criteriaUtils.test.ts`

Pure functions for parsing and serializing SLO criteria strings. Zero dependencies on React or DOM.

- [ ] **Step 1: Write failing tests for `parseCriteria`**

```typescript
// ui/src/features/registry/forms/criteriaUtils.test.ts
import { describe, it, expect } from 'vitest'
import { parseCriteria, serializeCriteria, type CriteriaParts } from './criteriaUtils'

describe('parseCriteria', () => {
  it('parses fixed threshold: <600', () => {
    expect(parseCriteria('<600')).toEqual({
      operator: '<', sign: null, value: 600, percent: false,
    })
  })

  it('parses relative percent: <=+10%', () => {
    expect(parseCriteria('<=+10%')).toEqual({
      operator: '<=', sign: '+', value: 10, percent: true,
    })
  })

  it('parses relative negative percent: >=-5%', () => {
    expect(parseCriteria('>=-5%')).toEqual({
      operator: '>=', sign: '-', value: 5, percent: true,
    })
  })

  it('parses relative absolute: <=+50', () => {
    expect(parseCriteria('<=+50')).toEqual({
      operator: '<=', sign: '+', value: 50, percent: false,
    })
  })

  it('parses equality: =100', () => {
    expect(parseCriteria('=100')).toEqual({
      operator: '=', sign: null, value: 100, percent: false,
    })
  })

  it('parses decimal values: <99.5', () => {
    expect(parseCriteria('<99.5')).toEqual({
      operator: '<', sign: null, value: 99.5, percent: false,
    })
  })

  it('returns null for invalid input', () => {
    expect(parseCriteria('')).toBeNull()
    expect(parseCriteria('abc')).toBeNull()
    expect(parseCriteria('<=+%')).toBeNull()
  })
})

describe('serializeCriteria', () => {
  it('serializes fixed threshold', () => {
    expect(serializeCriteria({ operator: '<', sign: null, value: 600, percent: false }))
      .toBe('<600')
  })

  it('serializes relative percent', () => {
    expect(serializeCriteria({ operator: '<=', sign: '+', value: 10, percent: true }))
      .toBe('<=+10%')
  })

  it('serializes relative negative percent', () => {
    expect(serializeCriteria({ operator: '>=', sign: '-', value: 5, percent: true }))
      .toBe('>=-5%')
  })

  it('serializes relative absolute', () => {
    expect(serializeCriteria({ operator: '<=', sign: '+', value: 50, percent: false }))
      .toBe('<=+50')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/forms/criteriaUtils.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Implement criteriaUtils**

```typescript
// ui/src/features/registry/forms/criteriaUtils.ts
export type Operator = '<' | '<=' | '>' | '>=' | '='
export type Sign = '+' | '-'

export interface CriteriaParts {
  operator: Operator
  sign: Sign | null
  value: number
  percent: boolean
}

const OPERATORS: Operator[] = ['<=', '>=', '<', '>', '=']

export function parseCriteria(raw: string): CriteriaParts | null {
  const s = raw.trim()
  if (!s) return null

  let operator: Operator | null = null
  let rest = s
  for (const op of OPERATORS) {
    if (s.startsWith(op)) {
      operator = op
      rest = s.slice(op.length)
      break
    }
  }
  if (!operator) return null

  let sign: Sign | null = null
  if (rest.startsWith('+')) {
    sign = '+'
    rest = rest.slice(1)
  } else if (rest.startsWith('-')) {
    sign = '-'
    rest = rest.slice(1)
  }

  const percent = rest.endsWith('%')
  if (percent) rest = rest.slice(0, -1)

  const value = parseFloat(rest)
  if (isNaN(value)) return null

  return { operator, sign, value, percent }
}

export function serializeCriteria(parts: CriteriaParts): string {
  const sign = parts.sign ?? ''
  const pct = parts.percent ? '%' : ''
  return `${parts.operator}${sign}${parts.value}${pct}`
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/forms/criteriaUtils.test.ts`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```
feat(ui): add criteria parse/serialize utilities for structured SLO input
```

---

### Task 2: Type Definitions & Module Consolidation

**Files:**
- Modify: `ui/src/features/slos/types.ts` — rename meta→tags, add variables, REMOVE `DataSource` and `SliDefinition` interfaces
- Modify: `ui/src/features/slis/types.ts` — rename meta→tags, add adapter_type, update `SliDefinitionCreate`
- Create: `ui/src/features/datasources/types.ts`
- Create: `ui/src/features/registry/types.ts`
- Modify: `ui/src/features/slos/components/SloLinkDialog.tsx` — update imports

This task consolidates duplicate types and renames fields to match Phase 1 backend changes.

- [ ] **Step 1: Update `features/slos/types.ts`**

Remove `DataSource` and `SliDefinition` interfaces (they move to their canonical modules). Update `SloDefinition`:

```typescript
// In SloDefinition: rename meta → tags, add variables
export interface SloDefinition {
  id: string
  name: string
  version: number
  comparable_from_version: number
  display_name: string | null
  author: string | null
  notes: string | null
  tags: Record<string, string>      // was: meta
  variables: Record<string, string> // NEW
  created_at: string
  active: boolean
  objectives: SloObjective[]
  total_score_pass_pct: number
  total_score_warning_pct: number
  comparison: Record<string, unknown>
}
```

Remove these interfaces entirely from this file (they lived here for SloLinkDialog convenience):
- `DataSource` — now in `features/datasources/types.ts`
- `SliDefinition` — now in `features/slis/types.ts`

- [ ] **Step 2: Update `features/slis/types.ts`**

```typescript
// ui/src/features/slis/types.ts
export interface SliDefinition {
  id: string
  name: string
  display_name: string | null
  adapter_type: string              // ADDED — needed for DS mode filtering
  version: number
  comparable_from_version: number
  indicators: Record<string, string>
  notes: string | null
  author: string | null
  tags: Record<string, string>      // was: meta
  active: boolean
  created_at: string
}

export interface SliDefinitionCreate {
  name: string
  display_name?: string
  adapter_type: string              // ADDED
  indicators: Record<string, string>
  comparable_from_version?: number
  notes?: string
  author?: string
  tags?: Record<string, string>     // was: meta
}
```

- [ ] **Step 3: Create `features/datasources/types.ts`**

```typescript
// ui/src/features/datasources/types.ts
export interface DataSource {
  id: string
  name: string
  display_name: string | null
  adapter_type: string
  adapter_url: string
  tags: Record<string, string>
  has_token: boolean
  created_at: string
  updated_at: string
}

export interface DataSourceCreate {
  name: string
  display_name?: string
  adapter_type: string
  adapter_url: string
  token?: string
  tags?: Record<string, string>
}

export interface DataSourceUpdate {
  display_name?: string
  adapter_url?: string
  token?: string
  tags?: Record<string, string>
}

export interface TagKeyCount {
  key: string
  count: number
}

export interface TagValueCount {
  value: string
  count: number
}
```

- [ ] **Step 4: Create `features/registry/types.ts`**

```typescript
// ui/src/features/registry/types.ts
export type RegistryMode = 'asset' | 'slo' | 'datasource'

export type NodeType = 'group' | 'asset' | 'slo' | 'sli' | 'datasource' | 'binding'

export interface TreeNode {
  id: string
  name: string
  displayName?: string
  type: NodeType
  badge?: string
  children?: TreeNode[]
  bindingChain?: { sloName: string; sliName: string; dsName: string }
}

export interface SelectedNode {
  type: NodeType
  name: string
  groupName?: string
}

export interface TagFilter {
  key: string
  value: string
}
```

- [ ] **Step 5: Update `SloLinkDialog.tsx` imports**

Change imports in `ui/src/features/slos/components/SloLinkDialog.tsx`:

```typescript
// OLD:
import { useDatasources, useSliDefinitions, ... } from '../hooks'
// NEW:
import { useDatasources } from '@/features/datasources/hooks'
import { useSliDefinitions } from '@/features/slis/hooks'
import { ... } from '../hooks'  // keep SLO-specific hooks
```

Also update any references to `DataSource` type:

```typescript
// OLD:
import type { DataSource, SliDefinition, ... } from '../types'
// NEW:
import type { DataSource } from '@/features/datasources/types'
import type { SliDefinition } from '@/features/slis/types'
import type { ... } from '../types'
```

- [ ] **Step 6: Commit**

```
feat(ui): consolidate types, rename meta→tags, add variables fields
```

---

### Task 3: Fix Existing Tests After Type Renames

**Files:**
- Modify: various test files that reference `meta`, `labels`, old `DataSource`/`SliDefinition` imports

The type renames from Task 2 will immediately break existing tests. Fix them now before continuing.

- [ ] **Step 1: Run full test suite to find breakage**

Run: `./scripts/ui-test.sh --tail 40`

- [ ] **Step 2: Fix all type errors in test fixtures**

Find and replace in test files:
- `meta:` → `tags:` in SLO/SLI mock objects
- Add `variables: {}` to SLO mock objects
- `labels:` → `tags:` in DataSource mock objects
- Add `has_token: false` to DataSource mock objects
- Add `adapter_type: 'prometheus'` to SLI mock objects where missing
- Update any import paths changed by the consolidation

- [ ] **Step 3: Run full test suite again**

Run: `./scripts/ui-test.sh --tail 40`
Expected: All existing tests PASS

- [ ] **Step 4: Commit**

```
fix(ui): update test fixtures for tags/variables type renames
```

---

### Task 4: Query Keys & API Layer Consolidation

**Files:**
- Modify: `ui/src/lib/queryKeys.ts` — add tag key factories
- Create: `ui/src/features/datasources/api.ts`
- Create: `ui/src/features/datasources/hooks.ts`
- Modify: `ui/src/features/slos/api.ts` — remove `fetchDatasources`/`fetchSliDefinitions`, add tag endpoints, update `createSloDefinition` payload
- Modify: `ui/src/features/slos/hooks.ts` — remove `useDatasources`/`useSliDefinitions`, add tag hooks
- Modify: `ui/src/features/slis/api.ts` — add `adapter_type`/tag params, unwrap paged response, add tag endpoints
- Modify: `ui/src/features/slis/hooks.ts` — add `adapter_type` param, add tag hooks

- [ ] **Step 1: Extend query keys**

Add to `ui/src/lib/queryKeys.ts`:

```typescript
// Replace existing datasourceKeys with:
export const datasourceKeys = {
  all: ['datasources'] as const,
  detail: (name: string) => [...datasourceKeys.all, name] as const,
  tagKeys: () => [...datasourceKeys.all, 'tag-keys'] as const,
  tagValues: (key: string) => [...datasourceKeys.all, 'tag-values', key] as const,
}

// Add tagKeys/tagValues to existing sloKeys:
export const sloKeys = {
  all: ['slos'] as const,
  detail: (name: string) => [...sloKeys.all, name] as const,
  tagKeys: () => [...sloKeys.all, 'tag-keys'] as const,
  tagValues: (key: string) => [...sloKeys.all, 'tag-values', key] as const,
}

// Add tagKeys/tagValues to existing sliKeys:
export const sliKeys = {
  all: ['sli-definitions'] as const,
  detail: (name: string) => [...sliKeys.all, name] as const,
  versions: (name: string) => [...sliKeys.detail(name), 'versions'] as const,
  tagKeys: () => [...sliKeys.all, 'tag-keys'] as const,
  tagValues: (key: string) => [...sliKeys.all, 'tag-values', key] as const,
}
```

- [ ] **Step 2: Create `features/datasources/api.ts`**

```typescript
// ui/src/features/datasources/api.ts
import type { DataSource, DataSourceCreate, DataSourceUpdate, TagKeyCount, TagValueCount } from './types'

const BASE = '/api'

export async function fetchDatasources(tagKey?: string, tagVal?: string): Promise<DataSource[]> {
  const params = new URLSearchParams()
  if (tagKey) params.set('tag_key', tagKey)
  if (tagVal) params.set('tag_val', tagVal)
  const qs = params.toString()
  const res = await fetch(`${BASE}/datasources${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`fetchDatasources: ${res.status}`)
  const data: { items: DataSource[]; total: number } = await res.json()
  return data.items
}

export async function fetchDatasource(name: string): Promise<DataSource> {
  const res = await fetch(`${BASE}/datasources/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchDatasource: ${res.status}`)
  return res.json()
}

export async function createDatasource(payload: DataSourceCreate): Promise<DataSource> {
  const res = await fetch(`${BASE}/datasources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`createDatasource: ${res.status}`)
  return res.json()
}

export async function updateDatasource(name: string, payload: DataSourceUpdate): Promise<DataSource> {
  const res = await fetch(`${BASE}/datasources/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`updateDatasource: ${res.status}`)
  return res.json()
}

export async function deleteDatasource(name: string): Promise<Response> {
  return fetch(`${BASE}/datasources/${encodeURIComponent(name)}`, { method: 'DELETE' })
}

export async function fetchDatasourceTagKeys(): Promise<TagKeyCount[]> {
  const res = await fetch(`${BASE}/datasources/tag-keys`)
  if (!res.ok) throw new Error(`fetchDatasourceTagKeys: ${res.status}`)
  return res.json()
}

export async function fetchDatasourceTagValues(key: string): Promise<TagValueCount[]> {
  const res = await fetch(`${BASE}/datasources/tag-values?key=${encodeURIComponent(key)}`)
  if (!res.ok) throw new Error(`fetchDatasourceTagValues: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 3: Create `features/datasources/hooks.ts`**

```typescript
// ui/src/features/datasources/hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { datasourceKeys } from '@/lib/queryKeys'
import {
  fetchDatasources, fetchDatasource, createDatasource,
  updateDatasource, deleteDatasource,
  fetchDatasourceTagKeys, fetchDatasourceTagValues,
} from './api'
import type { DataSourceCreate, DataSourceUpdate } from './types'

export function useDatasources(tagKey?: string, tagVal?: string) {
  return useQuery({
    queryKey: [...datasourceKeys.all, { tagKey, tagVal }],
    queryFn: () => fetchDatasources(tagKey, tagVal),
  })
}

export function useDatasource(name: string) {
  return useQuery({
    queryKey: datasourceKeys.detail(name),
    queryFn: () => fetchDatasource(name),
    enabled: !!name,
  })
}

export function useCreateDatasource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: DataSourceCreate) => createDatasource(payload),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: datasourceKeys.all }) },
  })
}

export function useUpdateDatasource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, ...body }: DataSourceUpdate & { name: string }) =>
      updateDatasource(name, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: datasourceKeys.all }) },
  })
}

export function useDeleteDatasource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => deleteDatasource(name),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: datasourceKeys.all }) },
  })
}

export function useDatasourceTagKeys() {
  return useQuery({ queryKey: datasourceKeys.tagKeys(), queryFn: fetchDatasourceTagKeys })
}

export function useDatasourceTagValues(key: string) {
  return useQuery({
    queryKey: datasourceKeys.tagValues(key),
    queryFn: () => fetchDatasourceTagValues(key),
    enabled: !!key,
  })
}
```

- [ ] **Step 4: Update `features/slos/api.ts`**

Remove `fetchDatasources()` and `fetchSliDefinitions()` functions (now in their canonical modules).

Update `createSloDefinition` payload type:

```typescript
// Change meta → tags, add variables:
export async function createSloDefinition(payload: {
  name: string
  objectives: SloObjective[]
  total_score_pass_pct: number
  total_score_warning_pct: number
  comparison: Record<string, unknown>
  display_name?: string
  notes?: string
  author?: string
  tags?: Record<string, string>       // was: meta
  variables?: Record<string, string>  // NEW
  comparable_from_version?: number
}): Promise<SloDefinition> { ... }
```

Update `fetchSlos` to accept tag params:

```typescript
export async function fetchSlos(tagKey?: string, tagVal?: string): Promise<SloDefinition[]> {
  const params = new URLSearchParams()
  if (tagKey) params.set('tag_key', tagKey)
  if (tagVal) params.set('tag_val', tagVal)
  const qs = params.toString()
  const res = await fetch(`${BASE}/slo-definitions${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`fetchSlos: ${res.status}`)
  const data: { items: SloDefinition[]; total: number } = await res.json()
  return data.items
}
```

Add tag discovery endpoints:

```typescript
export async function fetchSloTagKeys(): Promise<{ key: string; count: number }[]> {
  const res = await fetch(`${BASE}/slo-definitions/tag-keys`)
  if (!res.ok) throw new Error(`fetchSloTagKeys: ${res.status}`)
  return res.json()
}

export async function fetchSloTagValues(key: string): Promise<{ value: string; count: number }[]> {
  const res = await fetch(`${BASE}/slo-definitions/tag-values?key=${encodeURIComponent(key)}`)
  if (!res.ok) throw new Error(`fetchSloTagValues: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 5: Update `features/slos/hooks.ts`**

Remove `useDatasources()` and `useSliDefinitions()` hooks (now in canonical modules).

Add tag hooks:

```typescript
import { fetchSloTagKeys, fetchSloTagValues } from './api'

export function useSloTagKeys() {
  return useQuery({ queryKey: sloKeys.tagKeys(), queryFn: fetchSloTagKeys })
}

export function useSloTagValues(key: string) {
  return useQuery({
    queryKey: sloKeys.tagValues(key),
    queryFn: () => fetchSloTagValues(key),
    enabled: !!key,
  })
}
```

- [ ] **Step 6: Update `features/slis/api.ts`**

Change `fetchSliDefinitions` to accept `adapter_type`, `tag_key`, `tag_val` and return `SliDefinition[]` (unwrap paged response):

```typescript
import type { SliDefinition, SliDefinitionCreate } from './types'

export async function fetchSliDefinitions(
  adapterType?: string, tagKey?: string, tagVal?: string,
): Promise<SliDefinition[]> {
  const params = new URLSearchParams()
  if (adapterType) params.set('adapter_type', adapterType)
  if (tagKey) params.set('tag_key', tagKey)
  if (tagVal) params.set('tag_val', tagVal)
  const qs = params.toString()
  const res = await fetch(`${BASE}/sli-definitions${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`fetchSliDefinitions: ${res.status}`)
  const data: { items: SliDefinition[]; total: number } = await res.json()
  return data.items
}
```

Add tag discovery endpoints:

```typescript
export async function fetchSliTagKeys(): Promise<{ key: string; count: number }[]> {
  const res = await fetch(`${BASE}/sli-definitions/tag-keys`)
  if (!res.ok) throw new Error(`fetchSliTagKeys: ${res.status}`)
  return res.json()
}

export async function fetchSliTagValues(key: string): Promise<{ value: string; count: number }[]> {
  const res = await fetch(`${BASE}/sli-definitions/tag-values?key=${encodeURIComponent(key)}`)
  if (!res.ok) throw new Error(`fetchSliTagValues: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 7: Update `features/slis/hooks.ts`**

Add `adapterType` param to `useSliDefinitions`, add tag hooks:

```typescript
import { fetchSliTagKeys, fetchSliTagValues } from './api'

export function useSliDefinitions(adapterType?: string) {
  return useQuery({
    queryKey: [...sliKeys.all, { adapterType }],
    queryFn: () => fetchSliDefinitions(adapterType),
  })
}

export function useSliTagKeys() {
  return useQuery({ queryKey: sliKeys.tagKeys(), queryFn: fetchSliTagKeys })
}

export function useSliTagValues(key: string) {
  return useQuery({
    queryKey: sliKeys.tagValues(key),
    queryFn: () => fetchSliTagValues(key),
    enabled: !!key,
  })
}
```

- [ ] **Step 8: Add `useAllGroupLinks` aggregation hook**

The SLO and Datasource tree modes need SLO links to derive child relationships (SLO↔SLI↔DS). Links are stored per asset group. Add a hook that fetches links for all groups:

```typescript
// Add to features/slos/hooks.ts (or features/registry/hooks.ts)
import { useQueries } from '@tanstack/react-query'
import { groupKeys } from '@/lib/queryKeys'

export function useAllGroupLinks(groupNames: string[]) {
  const results = useQueries({
    queries: groupNames.map(name => ({
      queryKey: groupKeys.links(name),
      queryFn: () => fetchGroupSloLinks(name),
      staleTime: 30_000,
    })),
  })

  const allLinks = results.flatMap(r => r.data ?? [])
  const isLoading = results.some(r => r.isLoading)
  return { data: allLinks, isLoading }
}
```

- [ ] **Step 9: Run full test suite to verify no regressions**

Run: `./scripts/ui-test.sh --tail 40`
Expected: All tests PASS (import path changes may need fixing in existing consumers)

- [ ] **Step 10: Commit**

```
feat(ui): consolidate API layers, add tag filtering hooks for all entities
```

---

### Task 5: TagFilterBar Component

**Files:**
- Create: `ui/src/components/shared/TagFilterBar.tsx`
- Test: `ui/src/components/shared/TagFilterBar.test.tsx`

Reusable search + tag filter bar. Used in sidebar and form dropdowns.

- [ ] **Step 1: Write failing test**

```typescript
// ui/src/components/shared/TagFilterBar.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TagFilterBar } from './TagFilterBar'
import type { TagFilter } from '@/features/registry/types'

describe('TagFilterBar', () => {
  const defaultProps = {
    search: '',
    onSearchChange: vi.fn(),
    tags: [] as TagFilter[],
    onTagsChange: vi.fn(),
    tagKeySuggestions: [{ key: 'env', count: 5 }, { key: 'team', count: 3 }],
    tagValueSuggestions: [{ value: 'prod', count: 4 }],
    onTagKeySelected: vi.fn(),
    isLoadingKeys: false,
    isLoadingValues: false,
  }

  it('renders search input with placeholder', () => {
    render(<TagFilterBar {...defaultProps} />)
    expect(screen.getByPlaceholderText('Filter...')).toBeInTheDocument()
  })

  it('calls onSearchChange when typing', () => {
    render(<TagFilterBar {...defaultProps} />)
    fireEvent.change(screen.getByPlaceholderText('Filter...'), { target: { value: 'http' } })
    expect(defaultProps.onSearchChange).toHaveBeenCalledWith('http')
  })

  it('renders active tag pills with remove button', () => {
    const tags = [{ key: 'env', value: 'prod' }]
    render(<TagFilterBar {...defaultProps} tags={tags} />)
    expect(screen.getByText('env')).toBeInTheDocument()
    expect(screen.getByText('prod')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /remove/i })).toBeInTheDocument()
  })

  it('removes tag when × clicked', () => {
    const tags = [{ key: 'env', value: 'prod' }, { key: 'team', value: 'core' }]
    const onChange = vi.fn()
    render(<TagFilterBar {...defaultProps} tags={tags} onTagsChange={onChange} />)
    const removeButtons = screen.getAllByRole('button', { name: /remove/i })
    fireEvent.click(removeButtons[0])
    expect(onChange).toHaveBeenCalledWith([{ key: 'team', value: 'core' }])
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/ui-test.sh --tail 20 src/components/shared/TagFilterBar.test.tsx`

- [ ] **Step 3: Implement TagFilterBar**

Two-step tag add flow: click "Add tag filter" → pick key from dropdown → pick value from dropdown → pill added. Search input with magnifying glass icon. Tag pills with `×` remove button. Sans-serif font for the component. Uses `Search`, `X`, `Plus` from lucide-react.

Key implementation details:
- `search` input with `onChange` → parent manages state
- Active tags rendered as `<span>` pills with key:value and remove button with `aria-label="remove tag"`
- "Add tag filter" button toggles inline key→value selection flow
- Key dropdown shows `tagKeySuggestions` filtered by typed text
- After key selected, value dropdown shows `tagValueSuggestions` filtered by typed text
- Escape key cancels the add flow

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 20 src/components/shared/TagFilterBar.test.tsx`

- [ ] **Step 5: Commit**

```
feat(ui): add TagFilterBar component with search and tag pill filtering
```

---

### Task 6: StructuredCriteriaInput Component

**Files:**
- Create: `ui/src/components/shared/StructuredCriteriaInput.tsx`
- Test: `ui/src/components/shared/StructuredCriteriaInput.test.tsx`

A single criteria row: `[Operator ▼] [Sign ▼] [Value] [%]` with a **Preview** cell showing the serialized string. This component is used inside WizardStepIndicators (Task 15) which renders the full table with pass AND warn columns, multi-criteria AND rows, and +/− buttons.

- [ ] **Step 1: Write failing test**

```typescript
// ui/src/components/shared/StructuredCriteriaInput.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { StructuredCriteriaInput } from './StructuredCriteriaInput'
import type { CriteriaParts } from '@/features/registry/forms/criteriaUtils'

describe('StructuredCriteriaInput', () => {
  const defaultParts: CriteriaParts = { operator: '<', sign: null, value: 600, percent: false }

  it('renders operator select, value input, and % toggle', () => {
    render(<StructuredCriteriaInput value={defaultParts} onChange={vi.fn()} />)
    expect(screen.getByDisplayValue('<')).toBeInTheDocument()
    expect(screen.getByDisplayValue('600')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /%/i })).toBeInTheDocument()
  })

  it('shows preview string in preview cell', () => {
    render(<StructuredCriteriaInput value={defaultParts} onChange={vi.fn()} showPreview />)
    expect(screen.getByText('<600')).toBeInTheDocument()
  })

  it('calls onChange when value changes', () => {
    const onChange = vi.fn()
    render(<StructuredCriteriaInput value={defaultParts} onChange={onChange} />)
    fireEvent.change(screen.getByDisplayValue('600'), { target: { value: '800' } })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ value: 800 }))
  })

  it('toggles percent mode', () => {
    const onChange = vi.fn()
    render(<StructuredCriteriaInput value={defaultParts} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /%/i }))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ percent: true }))
  })

  it('renders relative percent preview', () => {
    const parts: CriteriaParts = { operator: '<=', sign: '+', value: 10, percent: true }
    render(<StructuredCriteriaInput value={parts} onChange={vi.fn()} showPreview />)
    expect(screen.getByText('<=+10%')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Implement StructuredCriteriaInput**

Four inline controls:
1. Operator `<select>`: `<`, `<=`, `>`, `>=`, `=`
2. Sign `<select>`: `—` (null), `+`, `-`
3. Value `<input type="number">`
4. `%` toggle `<button>` — green (`--primary`) when active

When `showPreview` prop is true, renders a preview cell using `serializeCriteria()` from Task 1. The preview is shown inline in the same row (not below).

This is a **single criterion** input. Multiple criteria per indicator (AND logic) are handled by WizardStepIndicators rendering multiple `StructuredCriteriaInput` rows grouped with an AND bracket — see Task 15.

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

```
feat(ui): add StructuredCriteriaInput with operator/sign/value/% controls
```

---

### Task 7: BindingChainBreadcrumb & VariableResolutionPanel

**Files:**
- Create: `ui/src/components/shared/BindingChainBreadcrumb.tsx`
- Test: `ui/src/components/shared/BindingChainBreadcrumb.test.tsx`
- Create: `ui/src/components/shared/VariableResolutionPanel.tsx`
- Test: `ui/src/components/shared/VariableResolutionPanel.test.tsx`

- [ ] **Step 1: Write BindingChainBreadcrumb test**

```typescript
// ui/src/components/shared/BindingChainBreadcrumb.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { BindingChainBreadcrumb } from './BindingChainBreadcrumb'

describe('BindingChainBreadcrumb', () => {
  it('renders SLO → SLI → DS chain', () => {
    render(
      <BindingChainBreadcrumb
        sloName="http-availability-slo" sloVersion="3.1"
        sliName="http-service-sli" dsName="prometheus-local"
        onClickSlo={vi.fn()} onClickSli={vi.fn()} onClickDs={vi.fn()}
      />
    )
    expect(screen.getByText(/http-availability-slo/)).toBeInTheDocument()
    expect(screen.getByText(/http-service-sli/)).toBeInTheDocument()
    expect(screen.getByText(/prometheus-local/)).toBeInTheDocument()
  })

  it('calls onClickSli when SLI badge clicked', () => {
    const onClickSli = vi.fn()
    render(
      <BindingChainBreadcrumb
        sloName="slo" sliName="sli" dsName="ds"
        onClickSlo={vi.fn()} onClickSli={onClickSli} onClickDs={vi.fn()}
      />
    )
    fireEvent.click(screen.getByText('sli'))
    expect(onClickSli).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Implement BindingChainBreadcrumb**

Three clickable badges with entity-colored borders (SLO=#7dc540, SLI=#A371F7, DS=#58A6FF), separated by `→` arrows (lucide ArrowRight). Version badge appended to SLO name in muted color. Sans-serif font.

- [ ] **Step 3: Write VariableResolutionPanel test**

```typescript
// ui/src/components/shared/VariableResolutionPanel.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { VariableResolutionPanel } from './VariableResolutionPanel'

describe('VariableResolutionPanel', () => {
  it('renders variable sources in priority order', () => {
    render(
      <VariableResolutionPanel
        assetVariables={{ job: 'checkout', namespace: 'prod' }}
        sloVariables={{ aggregation_window: '5m' }}
        reserved={{ asset_name: 'checkout-api' }}
      />
    )
    expect(screen.getByText('asset.variables:')).toBeInTheDocument()
    expect(screen.getByText(/\$job/)).toBeInTheDocument()
    expect(screen.getByText('slo.variables:')).toBeInTheDocument()
    expect(screen.getByText('reserved:')).toBeInTheDocument()
  })

  it('hides empty sections', () => {
    render(
      <VariableResolutionPanel
        assetVariables={{}} sloVariables={{ window: '5m' }} reserved={{}}
      />
    )
    expect(screen.queryByText('asset.variables:')).not.toBeInTheDocument()
    expect(screen.getByText('slo.variables:')).toBeInTheDocument()
  })
})
```

- [ ] **Step 4: Implement VariableResolutionPanel**

Dark panel with monospace text. Each variable source on its own line: label (muted) followed by `$key=value` pairs with `$key` in orange (#FFA657). Hides sections with no entries.

- [ ] **Step 5: Run all shared component tests**

Run: `./scripts/ui-test.sh --tail 20 src/components/shared/`

- [ ] **Step 6: Commit**

```
feat(ui): add BindingChainBreadcrumb and VariableResolutionPanel components
```

---

### Task 8: SearchableComboBox Component

**Files:**
- Create: `ui/src/components/shared/SearchableComboBox.tsx`
- Test: `ui/src/components/shared/SearchableComboBox.test.tsx`

Replaces native `<select>` for SLI/SLO/DS pickers.

- [ ] **Step 1: Write failing test**

```typescript
// ui/src/components/shared/SearchableComboBox.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SearchableComboBox } from './SearchableComboBox'

describe('SearchableComboBox', () => {
  const items = [
    { value: 'http-service-sli', label: 'HTTP Service SLI', badge: 'prometheus' },
    { value: 'db-sli', label: 'DB SLI', badge: 'prometheus' },
    { value: 'k8s-pod-sli', label: 'K8s Pod SLI', badge: 'mock' },
  ]

  it('shows placeholder when no value selected', () => {
    render(<SearchableComboBox value="" items={items} onSelect={vi.fn()} placeholder="Select SLI..." />)
    expect(screen.getByText('Select SLI...')).toBeInTheDocument()
  })

  it('shows selected value label', () => {
    render(<SearchableComboBox value="db-sli" items={items} onSelect={vi.fn()} />)
    expect(screen.getByText('DB SLI')).toBeInTheDocument()
  })

  it('opens dropdown on click and shows all items', () => {
    render(<SearchableComboBox value="" items={items} onSelect={vi.fn()} placeholder="Pick..." />)
    fireEvent.click(screen.getByText('Pick...'))
    expect(screen.getByText('HTTP Service SLI')).toBeInTheDocument()
    expect(screen.getByText('DB SLI')).toBeInTheDocument()
  })

  it('calls onSelect when item clicked', () => {
    const onSelect = vi.fn()
    render(<SearchableComboBox value="" items={items} onSelect={onSelect} placeholder="Pick..." />)
    fireEvent.click(screen.getByText('Pick...'))
    fireEvent.click(screen.getByText('DB SLI'))
    expect(onSelect).toHaveBeenCalledWith('db-sli')
  })
})
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Implement SearchableComboBox**

Button trigger showing selected label or placeholder + ChevronDown icon. Dropdown with search input (magnifying glass) + scrollable item list. Items filtered by text matching label/value. Badges right-aligned. Click-outside closes dropdown. Sans-serif font.

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

```
feat(ui): add SearchableComboBox component replacing native select
```

---

### Task 9: useRegistryTree Hook (Tree Builders)

**Files:**
- Create: `ui/src/features/registry/useRegistryTree.ts`
- Test: `ui/src/features/registry/useRegistryTree.test.ts`

Builds tree data from API responses for each sidebar mode. Pure data transformation.

- [ ] **Step 1: Write failing tests for all three builders + filter**

```typescript
// ui/src/features/registry/useRegistryTree.test.ts
import { describe, it, expect } from 'vitest'
import { buildSloTree, buildDatasourceTree, buildAssetTree, filterTree } from './useRegistryTree'
import type { TreeNode } from './types'

describe('buildSloTree', () => {
  it('builds SLO → SLI → DS hierarchy from links', () => {
    const slos = [{ name: 'http-slo', display_name: 'HTTP SLO', version: 3, active: true }]
    const slis = [{ name: 'http-sli', display_name: null, adapter_type: 'prometheus', active: true, indicators: { rt: 'q1', err: 'q2' } }]
    const datasources = [{ name: 'prom', display_name: null, adapter_type: 'prometheus' }]
    const links = [{ slo_name: 'http-slo', sli_name: 'http-sli', data_source_name: 'prom' }]

    const tree = buildSloTree(slos, slis, datasources, links)
    expect(tree).toHaveLength(1)
    expect(tree[0]).toMatchObject({ name: 'http-slo', type: 'slo', badge: 'v3' })
    expect(tree[0].children).toHaveLength(1)
    expect(tree[0].children![0]).toMatchObject({ name: 'http-sli', type: 'sli' })
    expect(tree[0].children![0].children).toHaveLength(1)
    expect(tree[0].children![0].children![0]).toMatchObject({ name: 'prom', type: 'datasource' })
  })

  it('shows SLO with no links as leaf node', () => {
    const slos = [{ name: 'orphan-slo', version: 1, active: true }]
    const tree = buildSloTree(slos, [], [], [])
    expect(tree).toHaveLength(1)
    expect(tree[0].children).toHaveLength(0)
  })
})

describe('buildDatasourceTree', () => {
  it('builds DS → SLI → SLO hierarchy', () => {
    const datasources = [{ name: 'prom', display_name: null, adapter_type: 'prometheus' }]
    const slis = [{ name: 'http-sli', display_name: null, adapter_type: 'prometheus', active: true, indicators: { rt: 'q' } }]
    const slos = [{ name: 'http-slo', display_name: null, version: 2, active: true }]
    const links = [{ slo_name: 'http-slo', sli_name: 'http-sli', data_source_name: 'prom' }]

    const tree = buildDatasourceTree(datasources, slis, slos, links)
    expect(tree).toHaveLength(1)
    expect(tree[0]).toMatchObject({ type: 'datasource', badge: '[prometheus]' })
    expect(tree[0].children![0]).toMatchObject({ type: 'sli' })
    expect(tree[0].children![0].children![0]).toMatchObject({ type: 'slo' })
  })
})

describe('buildAssetTree', () => {
  it('builds Group → Asset → Binding chain hierarchy', () => {
    const groups = [{ name: 'core', display_name: null, members: [{ asset_name: 'checkout-api' }] }]
    const groupLinksMap = { core: [{ slo_name: 'http-slo', sli_name: 'http-sli', data_source_name: 'prom' }] }

    const tree = buildAssetTree(groups, groupLinksMap)
    expect(tree).toHaveLength(1)
    expect(tree[0]).toMatchObject({ type: 'group', name: 'core' })
    expect(tree[0].children).toHaveLength(1)
    expect(tree[0].children![0]).toMatchObject({ type: 'asset', name: 'checkout-api' })
    expect(tree[0].children![0].children).toHaveLength(1)
    expect(tree[0].children![0].children![0]).toMatchObject({
      type: 'binding',
      bindingChain: { sloName: 'http-slo', sliName: 'http-sli', dsName: 'prom' },
    })
  })

  it('shows asset with no links as leaf', () => {
    const groups = [{ name: 'core', members: [{ asset_name: 'lonely-svc' }] }]
    const tree = buildAssetTree(groups, {})
    expect(tree[0].children![0].children).toBeUndefined()
  })
})

describe('filterTree', () => {
  it('filters by name substring', () => {
    const tree: TreeNode[] = [
      { id: '1', name: 'http-slo', type: 'slo' },
      { id: '2', name: 'db-slo', type: 'slo' },
    ]
    expect(filterTree(tree, 'http')).toHaveLength(1)
    expect(filterTree(tree, 'http')[0].name).toBe('http-slo')
  })

  it('keeps parent if any child matches', () => {
    const tree: TreeNode[] = [
      { id: '1', name: 'parent', type: 'slo', children: [
        { id: '2', name: 'matching-child', type: 'sli' },
        { id: '3', name: 'other', type: 'sli' },
      ]},
    ]
    const result = filterTree(tree, 'matching')
    expect(result).toHaveLength(1)
    expect(result[0].children).toHaveLength(1)
  })

  it('returns all nodes when search is empty', () => {
    const tree: TreeNode[] = [
      { id: '1', name: 'a', type: 'slo' },
      { id: '2', name: 'b', type: 'slo' },
    ]
    expect(filterTree(tree, '')).toHaveLength(2)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/useRegistryTree.test.ts`

- [ ] **Step 3: Implement tree builders**

Key implementation note for `buildAssetTree`: accepts `groupLinksMap: Record<string, MinLink[]>` where each key is the group name and value is that group's SLO links. This avoids the bug of showing all links for every group.

```typescript
// ui/src/features/registry/useRegistryTree.ts
import type { TreeNode } from './types'

interface MinSlo { name: string; display_name?: string | null; version: number; active: boolean }
interface MinSli { name: string; display_name?: string | null; adapter_type: string; active: boolean; indicators?: Record<string, string> }
interface MinDs { name: string; display_name?: string | null; adapter_type: string }
interface MinLink { slo_name: string; sli_name: string; data_source_name: string }
interface MinGroup { name: string; display_name?: string | null; members?: { asset_name: string }[] }

export function buildSloTree(
  slos: MinSlo[], slis: MinSli[], datasources: MinDs[], links: MinLink[],
): TreeNode[] {
  const sliByName = new Map(slis.map(s => [s.name, s]))
  const dsByName = new Map(datasources.map(d => [d.name, d]))

  return slos.filter(s => s.active).map(slo => {
    const sloLinks = links.filter(l => l.slo_name === slo.name)
    const sliNames = [...new Set(sloLinks.map(l => l.sli_name))]

    const sliChildren: TreeNode[] = sliNames.map(sliName => {
      const sli = sliByName.get(sliName)
      const dsNames = [...new Set(sloLinks.filter(l => l.sli_name === sliName).map(l => l.data_source_name))]
      const dsChildren: TreeNode[] = dsNames.map(dsName => ({
        id: `ds:${dsName}`, name: dsName, displayName: dsByName.get(dsName)?.display_name ?? undefined,
        type: 'datasource' as const,
      }))
      const indicatorCount = sli?.indicators ? Object.keys(sli.indicators).length : 0
      return {
        id: `sli:${sliName}`, name: sliName, displayName: sli?.display_name ?? undefined,
        type: 'sli' as const, badge: `${indicatorCount} indicators`,
        children: dsChildren,
      }
    })

    return {
      id: `slo:${slo.name}`, name: slo.name, displayName: slo.display_name ?? undefined,
      type: 'slo' as const, badge: `v${slo.version}`,
      children: sliChildren,
    }
  })
}

export function buildDatasourceTree(
  datasources: MinDs[], slis: MinSli[], slos: MinSlo[], links: MinLink[],
): TreeNode[] {
  const sloByName = new Map(slos.map(s => [s.name, s]))
  return datasources.map(ds => {
    const dsSlis = slis.filter(s => s.adapter_type === ds.adapter_type && s.active)
    const sliChildren: TreeNode[] = dsSlis.map(sli => {
      const sloNames = [...new Set(links.filter(l => l.sli_name === sli.name && l.data_source_name === ds.name).map(l => l.slo_name))]
      const sloChildren: TreeNode[] = sloNames.map(sloName => ({
        id: `slo:${sloName}`, name: sloName, displayName: sloByName.get(sloName)?.display_name ?? undefined,
        type: 'slo' as const, badge: sloByName.get(sloName) ? `v${sloByName.get(sloName)!.version}` : undefined,
      }))
      const indicatorCount = sli.indicators ? Object.keys(sli.indicators).length : 0
      return {
        id: `sli:${sli.name}`, name: sli.name, displayName: sli.display_name ?? undefined,
        type: 'sli' as const, badge: `${indicatorCount} indicators`,
        children: sloChildren,
      }
    })
    return {
      id: `ds:${ds.name}`, name: ds.name, displayName: ds.display_name ?? undefined,
      type: 'datasource' as const, badge: `[${ds.adapter_type}]`,
      children: sliChildren,
    }
  })
}

export function buildAssetTree(
  groups: MinGroup[],
  groupLinksMap: Record<string, MinLink[]>,
): TreeNode[] {
  return groups.map(group => {
    const groupLinks = groupLinksMap[group.name] ?? []
    const memberChildren: TreeNode[] = (group.members ?? []).map(member => {
      const bindingChildren: TreeNode[] = groupLinks.map(link => ({
        id: `binding:${member.asset_name}:${link.slo_name}`,
        name: link.slo_name,
        type: 'binding' as const,
        bindingChain: { sloName: link.slo_name, sliName: link.sli_name, dsName: link.data_source_name },
        badge: `→ ${link.sli_name} → ${link.data_source_name}`,
      }))
      return {
        id: `asset:${member.asset_name}`, name: member.asset_name,
        type: 'asset' as const,
        children: bindingChildren.length > 0 ? bindingChildren : undefined,
      }
    })
    return {
      id: `group:${group.name}`, name: group.name, displayName: group.display_name ?? undefined,
      type: 'group' as const, badge: `${group.members?.length ?? 0} assets`,
      children: memberChildren,
    }
  })
}

export function filterTree(nodes: TreeNode[], search: string): TreeNode[] {
  if (!search) return nodes
  const lower = search.toLowerCase()
  return nodes.reduce<TreeNode[]>((acc, node) => {
    const nameMatch = node.name.toLowerCase().includes(lower) ||
      (node.displayName?.toLowerCase().includes(lower) ?? false)
    const filteredChildren = node.children ? filterTree(node.children, search) : []
    if (nameMatch || filteredChildren.length > 0) {
      acc.push({
        ...node,
        children: nameMatch ? node.children : (filteredChildren.length > 0 ? filteredChildren : undefined),
      })
    }
    return acc
  }, [])
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/useRegistryTree.test.ts`

- [ ] **Step 5: Commit**

```
feat(ui): add tree builder functions for SLO/Datasource/Asset sidebar modes
```

---

### Task 10: RegistryTree Component

**Files:**
- Create: `ui/src/features/registry/RegistryTree.tsx`
- Test: `ui/src/features/registry/RegistryTree.test.tsx`

Renders the hierarchical tree with expand/collapse, entity-colored icons, and click selection.

- [ ] **Step 1: Write failing test**

```typescript
// ui/src/features/registry/RegistryTree.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { RegistryTree } from './RegistryTree'
import type { TreeNode, SelectedNode } from './types'

describe('RegistryTree', () => {
  const nodes: TreeNode[] = [
    {
      id: 'slo:http-slo', name: 'http-slo', type: 'slo', badge: 'v3.1',
      children: [
        { id: 'sli:http-sli', name: 'http-sli', type: 'sli', badge: '3 indicators' },
      ],
    },
    { id: 'slo:db-slo', name: 'db-slo', type: 'slo', badge: 'v1.0' },
  ]

  it('renders root nodes', () => {
    render(<RegistryTree nodes={nodes} selected={null} onSelect={vi.fn()} />)
    expect(screen.getByText('http-slo')).toBeInTheDocument()
    expect(screen.getByText('db-slo')).toBeInTheDocument()
  })

  it('expands node on toggle click to show children', () => {
    render(<RegistryTree nodes={nodes} selected={null} onSelect={vi.fn()} />)
    // Click toggle to expand
    fireEvent.click(screen.getByTestId('toggle-slo:http-slo'))
    expect(screen.getByText('http-sli')).toBeInTheDocument()
  })

  it('calls onSelect with node info on name click', () => {
    const onSelect = vi.fn()
    render(<RegistryTree nodes={nodes} selected={null} onSelect={onSelect} />)
    fireEvent.click(screen.getByText('http-slo'))
    expect(onSelect).toHaveBeenCalledWith({ type: 'slo', name: 'http-slo' })
  })

  it('highlights selected node', () => {
    const selected: SelectedNode = { type: 'slo', name: 'db-slo' }
    render(<RegistryTree nodes={nodes} selected={selected} onSelect={vi.fn()} />)
    const node = screen.getByTestId('node-slo:db-slo')
    expect(node).toHaveAttribute('data-selected', 'true')
  })

  it('shows badges', () => {
    render(<RegistryTree nodes={nodes} selected={null} onSelect={vi.fn()} />)
    expect(screen.getByText('v3.1')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/RegistryTree.test.tsx`

- [ ] **Step 3: Implement RegistryTree**

```typescript
// ui/src/features/registry/RegistryTree.tsx
import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import type { TreeNode, SelectedNode } from './types'

const TYPE_COLORS: Record<string, string> = {
  slo: '#7dc540',
  sli: '#A371F7',
  datasource: '#58A6FF',
  group: '#8b949e',
  asset: '#c9d1d9',
  binding: '#7dc540',
}

interface Props {
  nodes: TreeNode[]
  selected: SelectedNode | null
  onSelect: (node: SelectedNode) => void
}

export function RegistryTree({ nodes, selected, onSelect }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const toggle = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="flex-1 overflow-y-auto py-1" style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}>
      {nodes.map(node => (
        <TreeNodeRow
          key={node.id} node={node} depth={0}
          expanded={expanded} onToggle={toggle}
          selected={selected} onSelect={onSelect}
        />
      ))}
      {nodes.length === 0 && (
        <div className="px-4 py-3 text-xs text-muted-foreground italic">No items</div>
      )}
    </div>
  )
}

function TreeNodeRow({ node, depth, expanded, onToggle, selected, onSelect }: {
  node: TreeNode
  depth: number
  expanded: Set<string>
  onToggle: (id: string) => void
  selected: SelectedNode | null
  onSelect: (node: SelectedNode) => void
}) {
  const hasChildren = node.children && node.children.length > 0
  const isExpanded = expanded.has(node.id)
  const isSelected = selected?.type === node.type && selected?.name === node.name
  const color = TYPE_COLORS[node.type] ?? '#c9d1d9'

  return (
    <>
      <div
        data-testid={`node-${node.id}`}
        data-selected={isSelected ? 'true' : 'false'}
        className="flex items-center gap-1 px-2 py-1 cursor-pointer transition-colors hover:bg-accent/50"
        style={{
          paddingLeft: `${8 + depth * 16}px`,
          ...(isSelected ? { backgroundColor: `${color}12`, borderLeft: `2px solid ${color}` } : {}),
        }}
      >
        {/* Expand/collapse toggle */}
        {hasChildren ? (
          <button
            data-testid={`toggle-${node.id}`}
            onClick={e => { e.stopPropagation(); onToggle(node.id) }}
            className="shrink-0 p-0.5 text-muted-foreground hover:text-foreground"
          >
            {isExpanded
              ? <ChevronDown className="size-3" />
              : <ChevronRight className="size-3" />
            }
          </button>
        ) : (
          <span className="shrink-0 w-4" />
        )}

        {/* Node name — click selects */}
        <button
          onClick={() => onSelect({ type: node.type, name: node.name })}
          className="flex-1 text-left text-xs truncate"
          style={{ color }}
        >
          {node.displayName ?? node.name}
        </button>

        {/* Badge */}
        {node.badge && (
          <span className="shrink-0 text-[10px] text-muted-foreground">{node.badge}</span>
        )}
      </div>

      {/* Children */}
      {hasChildren && isExpanded && node.children!.map(child => (
        <TreeNodeRow
          key={child.id} node={child} depth={depth + 1}
          expanded={expanded} onToggle={onToggle}
          selected={selected} onSelect={onSelect}
        />
      ))}
    </>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/RegistryTree.test.tsx`

- [ ] **Step 5: Commit**

```
feat(ui): add RegistryTree component with expand/collapse and entity colors
```

---

### Task 11: RegistrySidebar Component

**Files:**
- Create: `ui/src/features/registry/RegistrySidebar.tsx`
- Test: `ui/src/features/registry/RegistrySidebar.test.tsx`

Composes: segmented control + TagFilterBar + RegistryTree + Create button.

- [ ] **Step 1: Write failing test**

```typescript
// ui/src/features/registry/RegistrySidebar.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RegistrySidebar } from './RegistrySidebar'
import type { RegistryMode, SelectedNode } from './types'

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('RegistrySidebar', () => {
  const defaultProps = {
    mode: 'asset' as RegistryMode,
    onModeChange: vi.fn(),
    selected: null as SelectedNode | null,
    onSelect: vi.fn(),
    onCreateAction: vi.fn() as (type: 'datasource' | 'sli' | 'slo' | 'group', context?: { adapterType?: string }) => void,
  }

  it('renders segmented control with Asset as default/first', () => {
    render(<RegistrySidebar {...defaultProps} />, { wrapper: Wrapper })
    const buttons = screen.getAllByRole('button')
    const assetBtn = screen.getByText('Asset')
    const sloBtn = screen.getByText('SLO')
    const dsBtn = screen.getByText('Datasource')
    expect(assetBtn).toBeInTheDocument()
    expect(sloBtn).toBeInTheDocument()
    expect(dsBtn).toBeInTheDocument()
  })

  it('switches mode on click', () => {
    render(<RegistrySidebar {...defaultProps} />, { wrapper: Wrapper })
    fireEvent.click(screen.getByText('SLO'))
    expect(defaultProps.onModeChange).toHaveBeenCalledWith('slo')
  })

  it('renders search input', () => {
    render(<RegistrySidebar {...defaultProps} />, { wrapper: Wrapper })
    expect(screen.getByPlaceholderText('Filter...')).toBeInTheDocument()
  })

  it('renders create button', () => {
    render(<RegistrySidebar {...defaultProps} />, { wrapper: Wrapper })
    expect(screen.getByText(/create/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Implement RegistrySidebar**

```typescript
// ui/src/features/registry/RegistrySidebar.tsx
import { useState, useMemo } from 'react'
import { Plus } from 'lucide-react'
import { TagFilterBar } from '@/components/shared/TagFilterBar'
import { RegistryTree } from './RegistryTree'
import { buildSloTree, buildDatasourceTree, buildAssetTree, filterTree } from './useRegistryTree'
import { useSlos, useGroupTree, useSloTagKeys, useSloTagValues } from '@/features/slos/hooks'
import { useSliDefinitions, useSliTagKeys, useSliTagValues } from '@/features/slis/hooks'
import { useDatasources, useDatasourceTagKeys, useDatasourceTagValues } from '@/features/datasources/hooks'
import { useAllGroupLinks } from '@/features/slos/hooks'
import { useTagKeys, useTagValues } from '@/features/assets/hooks'
import type { MinLink } from './useRegistryTree'
import type { RegistryMode, SelectedNode, TagFilter } from './types'

const MODES: { key: RegistryMode; label: string }[] = [
  { key: 'asset', label: 'Asset' },
  { key: 'slo', label: 'SLO' },
  { key: 'datasource', label: 'Datasource' },
]

interface Props {
  mode: RegistryMode
  onModeChange: (mode: RegistryMode) => void
  selected: SelectedNode | null
  onSelect: (node: SelectedNode) => void
  onCreateAction: (type: 'datasource' | 'sli' | 'slo' | 'group', context?: { adapterType?: string }) => void
}

export function RegistrySidebar({ mode, onModeChange, selected, onSelect, onCreateAction }: Props) {
  const [search, setSearch] = useState('')
  const [tags, setTags] = useState<TagFilter[]>([])
  const [pendingTagKey, setPendingTagKey] = useState('')

  // Data fetching — each mode's primary entity
  const { data: slos } = useSlos()
  const { data: slis } = useSliDefinitions()
  const { data: datasources } = useDatasources()
  const { data: tree } = useGroupTree()

  // Fetch all group SLO links for tree building (SLO & DS modes need link data)
  const groupNames = useMemo(() => (tree?.all_groups ?? []).map(g => g.name), [tree])
  const { data: allLinks } = useAllGroupLinks(groupNames)

  // Tag suggestions — mode-dependent
  const { data: sloTagKeys, isLoading: sloKeysLoading } = useSloTagKeys()
  const { data: sloTagValues, isLoading: sloValsLoading } = useSloTagValues(pendingTagKey)
  const { data: sliTagKeys, isLoading: sliKeysLoading } = useSliTagKeys()
  const { data: sliTagValues, isLoading: sliValsLoading } = useSliTagValues(pendingTagKey)
  const { data: dsTagKeys, isLoading: dsKeysLoading } = useDatasourceTagKeys()
  const { data: dsTagValues, isLoading: dsValsLoading } = useDatasourceTagValues(pendingTagKey)
  const { data: assetTagKeys, isLoading: assetKeysLoading } = useTagKeys() // from @/features/assets/hooks
  const { data: assetTagValues, isLoading: assetValsLoading } = useTagValues(pendingTagKey)

  // Pick tag suggestions based on mode
  const tagKeySuggestions = mode === 'slo' ? (sloTagKeys ?? [])
    : mode === 'datasource' ? (dsTagKeys ?? [])
    : (assetTagKeys ?? []) // asset mode uses asset tags
  const tagValueSuggestions = mode === 'slo' ? (sloTagValues ?? [])
    : mode === 'datasource' ? (dsTagValues ?? [])
    : (assetTagValues ?? [])
  const isLoadingKeys = mode === 'slo' ? sloKeysLoading : mode === 'datasource' ? dsKeysLoading : assetKeysLoading
  const isLoadingValues = mode === 'slo' ? sloValsLoading : mode === 'datasource' ? dsValsLoading : assetValsLoading

  // Build groupLinksMap for asset mode (keyed by group name)
  const groupLinksMap = useMemo(() => {
    const map: Record<string, typeof allLinks> = {}
    for (const link of allLinks ?? []) {
      // Group links have group_id; match to group name from tree
      const group = (tree?.all_groups ?? []).find(g => g.id === link.group_id)
      if (group) (map[group.name] ??= []).push(link)
    }
    return map
  }, [allLinks, tree])

  // Build tree nodes
  const treeNodes = useMemo(() => {
    const links = (allLinks ?? []).map(l => ({
      slo_name: l.slo_name, sli_name: l.sli_name, data_source_name: l.data_source_name,
    }))
    if (mode === 'slo') {
      return buildSloTree(slos ?? [], slis ?? [], datasources ?? [], links)
    }
    if (mode === 'datasource') {
      return buildDatasourceTree(datasources ?? [], slis ?? [], slos ?? [], links)
    }
    // asset mode
    return buildAssetTree(tree?.all_groups ?? [], groupLinksMap as Record<string, MinLink[]>)
  }, [mode, slos, slis, datasources, tree, allLinks, groupLinksMap])

  const filteredNodes = useMemo(() => filterTree(treeNodes, search), [treeNodes, search])

  return (
    <div className="flex flex-col h-full border-r border-border bg-black/30" style={{ width: 260 }}>
      {/* Segmented control */}
      <div className="flex gap-0.5 p-2 bg-muted/30 mx-2 mt-2 rounded-md">
        {MODES.map(m => (
          <button
            key={m.key}
            onClick={() => onModeChange(m.key)}
            className={`flex-1 text-center py-1 text-xs font-medium rounded transition-colors ${
              mode === m.key
                ? 'bg-primary/15 text-primary'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Search + tag filter */}
      <div className="mt-2">
        <TagFilterBar
          search={search} onSearchChange={setSearch}
          tags={tags} onTagsChange={setTags}
          tagKeySuggestions={tagKeySuggestions}
          tagValueSuggestions={tagValueSuggestions}
          onTagKeySelected={setPendingTagKey}
          isLoadingKeys={isLoadingKeys}
          isLoadingValues={isLoadingValues}
        />
      </div>

      {/* Tree */}
      <RegistryTree nodes={filteredNodes} selected={selected} onSelect={onSelect} />

      {/* Create button */}
      <div className="p-2 border-t border-border">
        <CreateDropdown mode={mode} onCreateAction={onCreateAction} />
      </div>
    </div>
  )
}

function CreateDropdown({ mode, onCreateAction }: {
  mode: RegistryMode
  onCreateAction: Props['onCreateAction']
}) {
  const [open, setOpen] = useState(false)

  const items = [
    { type: 'slo' as const, label: 'New SLO', color: '#7dc540' },
    { type: 'sli' as const, label: 'New SLI Definition', color: '#A371F7' },
    { type: 'datasource' as const, label: 'New Datasource', color: '#58A6FF' },
    { type: 'group' as const, label: 'New Asset Group', color: '#8B949E' },
  ]

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-center gap-1.5 py-2 text-xs font-medium rounded border border-primary/40 text-primary hover:bg-primary/10 transition-colors"
      >
        <Plus className="size-3.5" /> Create
      </button>
      {open && (
        <div className="absolute bottom-full mb-1 left-0 w-full bg-popover border border-border rounded-lg shadow-lg py-1 z-50"
             style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}>
          {items.map(item => (
            <button
              key={item.type}
              className="w-full px-3 py-1.5 text-xs text-left hover:bg-accent transition-colors flex items-center gap-2"
              onClick={() => { onCreateAction(item.type); setOpen(false) }}
            >
              <span className="w-1 h-4 rounded-full" style={{ backgroundColor: item.color }} />
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/RegistrySidebar.test.tsx`

- [ ] **Step 5: Commit**

```
feat(ui): add RegistrySidebar with segmented control, tag filter, and tree
```

---

### Task 12: Datasource Detail & Form

**Files:**
- Create: `ui/src/features/registry/details/DatasourceDetailView.tsx`
- Test: `ui/src/features/registry/details/DatasourceDetailView.test.tsx`
- Create: `ui/src/features/registry/forms/DatasourceForm.tsx`
- Test: `ui/src/features/registry/forms/DatasourceForm.test.tsx`

- [ ] **Step 1: Write DatasourceDetailView test**

Test rendering of: name, adapter_type badge, adapter_url, token mask (`••••••••` when has_token=true, "None" when false), tags as pills, "Used by" SLI list, Edit/Delete buttons. Test that delete shows confirmation. Test cross-navigation callback when SLI name clicked.

- [ ] **Step 2: Implement DatasourceDetailView**

Header: display_name + name (mono) + adapter_type badge. Fields: adapter_url (mono), token display (has_token ? `••••••••` : "None"), tags as pills. "Used by" section: SLIs with same adapter_type (clickable → `onNavigate({ type: 'sli', name })`) . Actions: Edit (opens DatasourceForm), Delete (confirmation dialog that checks response for 409 and displays affected SLO links from error body).

- [ ] **Step 3: Write DatasourceForm test**

Test: form renders name/display_name/adapter_type/adapter_url/token fields. Test: token field is password type. Test: tags key-value row editor add/remove. Test: submit calls create mutation. Test: edit mode pre-fills values and disables name field.

- [ ] **Step 4: Implement DatasourceForm**

Dialog with react-hook-form + zod. Fields: name (create only), display_name, adapter_type, adapter_url, token (password input — only sends if non-empty), tags (key-value rows). Token: create = plain input, edit = `••••••••` placeholder, only included in payload if user types a new value.

- [ ] **Step 5: Run tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/details/DatasourceDetailView.test.tsx src/features/registry/forms/DatasourceForm.test.tsx`

- [ ] **Step 6: Commit**

```
feat(ui): add DatasourceDetailView and DatasourceForm with token handling
```

---

### Task 13: SLI Detail & Form

**Files:**
- Create: `ui/src/features/registry/details/SliDetailView.tsx`
- Test: `ui/src/features/registry/details/SliDetailView.test.tsx`
- Create: `ui/src/features/registry/forms/SliForm.tsx`
- Test: `ui/src/features/registry/forms/SliForm.test.tsx`

- [ ] **Step 1: Write SliDetailView test**

Test: renders name, version badge, adapter_type badge, active/inactive. Test: indicators table with Name | Query columns, `$variable` highlighted orange. Test: "Used by" SLOs section clickable. Test: New Version and Deactivate buttons present.

- [ ] **Step 2: Implement SliDetailView**

Header: display_name + name (mono) + version badge + active badge. Indicators table: monospace query with `$variable` highlighted via regex replace into `<span style="color:#FFA657">`. Tags, notes, author. "Used by" section lists SLOs that reference this SLI's indicators (clickable → onNavigate). Version history. Actions: New Version (opens SliForm pre-filled), Deactivate (calls useDeleteSli).

- [ ] **Step 3: Write SliForm test**

Test: renders fields. Test: indicators dynamic rows add/remove. Test: "New version" pre-fills. Test: adapter_type pre-filled when `defaultAdapterType` prop provided. Test: submit calls useCreateSli.

- [ ] **Step 4: Implement SliForm**

Dialog. Props: `open`, `onOpenChange`, `editFrom?: SliDefinition` (for new version), `defaultAdapterType?: string` (from sidebar context). Fields: name (create only), display_name, adapter_type (pre-filled), author, notes. Indicators: useFieldArray — each row has name (text) + query (mono input). `+ Add indicator`. Tags: key-value rows. Submit: calls `useCreateSli()`.

- [ ] **Step 5: Run tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/details/SliDetailView.test.tsx src/features/registry/forms/SliForm.test.tsx`

- [ ] **Step 6: Commit**

```
feat(ui): add SliDetailView with variable highlighting and SliForm
```

---

### Task 14: SLO Detail & Asset Binding Views

**Files:**
- Create: `ui/src/features/registry/details/SloDetailView.tsx`
- Test: `ui/src/features/registry/details/SloDetailView.test.tsx`
- Create: `ui/src/features/registry/details/AssetBindingView.tsx`
- Test: `ui/src/features/registry/details/AssetBindingView.test.tsx`

- [ ] **Step 1: Write SloDetailView test**

Test: renders name, version badge, active status. Test: objectives table displayed with pass AND warn criteria. Test: score thresholds + comparison summary shown. Test: tags and variables shown. Test: linked assets list. Test: version history entries. Test: "New Version" button calls onEdit. Test: "Deactivate" button calls onDeactivate.

- [ ] **Step 2: Implement SloDetailView**

Reuses existing `SloObjectiveTable` for objectives. Adds BindingChainBreadcrumb when link context available. Tags, variables, notes, author. Score thresholds summary: "Pass ≥ 90% · Warning ≥ 75%". Comparison summary: "several_results (3) · include: pass_or_warn · aggregate: avg". Version history entries with date + notes. Linked Assets section shows assets using this SLO via group links.

**Actions (top-right):**
- "New Version" — opens SloWizard pre-filled with current SLO data (edit flow = create new version)
- "Deactivate" — soft-deletes all versions

There is NO separate "Edit" button — editing IS creating a new version via the same wizard form. The wizard title changes to show e.g. "web-perf-v3 · New Version" with subtitle "Editing creates version 3.2 · All fields pre-filled from v3.1".

- [ ] **Step 3: Write AssetBindingView test**

Test: renders asset name. Test: renders binding cards with chain breadcrumb + variable resolution. Test: empty state shows "Link an SLO" button. Test: clicking chain entities fires onNavigate.

- [ ] **Step 4: Implement AssetBindingView**

Shows SLO bindings for selected asset (from parent group's links). Each binding card: BindingChainBreadcrumb, VariableResolutionPanel (asset.variables + slo.variables + reserved), objectives summary table with pass/warn criteria, weight, and key SLI star.

**Per-binding actions:** Test SLO, Edit (opens SloWizard pre-filled = creates new version), Unlink.

Empty state: "Link an SLO" button opens revised SLO Link dialog.

- [ ] **Step 5: Run tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/details/`

- [ ] **Step 6: Commit**

```
feat(ui): add SloDetailView and AssetBindingView with binding chain
```

---

### Task 15: SLO Creation Wizard

**Files:**
- Create: `ui/src/features/registry/forms/SloWizard.tsx`
- Test: `ui/src/features/registry/forms/SloWizard.test.tsx`
- Create: `ui/src/features/registry/forms/WizardStepIdentity.tsx`
- Create: `ui/src/features/registry/forms/WizardStepPickSli.tsx`
- Create: `ui/src/features/registry/forms/WizardStepIndicators.tsx`
- Test: `ui/src/features/registry/forms/WizardStepIndicators.test.tsx`
- Create: `ui/src/features/registry/forms/WizardStepComparison.tsx`

4-step progressive disclosure wizard. Supports both **create** and **edit** flows — edit pre-fills all fields from an existing SLO and always creates a new version (no in-place mutation). See Penpot board "Redesign — SLO Creation Wizard" for the visual reference.

**Create vs Edit flow:**
- Create: title = "New SLO Definition", footer button = "Create SLO"
- Edit: title = "{name} · New Version", subtitle = "Editing creates version {N+1} · All fields pre-filled from v{N}", footer button = "Create Version"
- The wizard accepts an optional `editSlo?: SloDefinition` prop. When present, all steps are pre-filled.

- [ ] **Step 1: Write WizardStepIndicators test (most complex step)**

```typescript
// ui/src/features/registry/forms/WizardStepIndicators.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { WizardStepIndicators } from './WizardStepIndicators'

describe('WizardStepIndicators', () => {
  const indicators = { response_time: 'query1', error_rate: 'query2', availability: 'query3' }

  it('renders all indicators as checkable rows', () => {
    render(<WizardStepIndicators indicators={indicators} objectives={[]} onChange={vi.fn()} />)
    expect(screen.getByText('response_time')).toBeInTheDocument()
    expect(screen.getByText('error_rate')).toBeInTheDocument()
    expect(screen.getByText('availability')).toBeInTheDocument()
    expect(screen.getAllByRole('checkbox')).toHaveLength(3)
  })

  it('unchecked indicators are dimmed and show no criteria inputs', () => {
    render(<WizardStepIndicators indicators={indicators} objectives={[]} onChange={vi.fn()} />)
    screen.getAllByRole('checkbox').forEach(cb => expect(cb).not.toBeChecked())
    // Dimmed text visible
    expect(screen.getByText('(unchecked — will not be included)')).toBeInTheDocument()
  })

  it('shows pass AND warn criteria columns when indicator checked', () => {
    render(<WizardStepIndicators indicators={indicators} objectives={[]} onChange={vi.fn()} />)
    fireEvent.click(screen.getAllByRole('checkbox')[0]) // check response_time
    expect(screen.getByDisplayValue('<')).toBeInTheDocument()
    // Both column headers visible
    expect(screen.getByText('PASS CRITERIA')).toBeInTheDocument()
    expect(screen.getByText('WARNING CRITERIA')).toBeInTheDocument()
  })

  it('supports multiple criteria rows per indicator (AND logic)', () => {
    render(<WizardStepIndicators indicators={indicators} objectives={[]} onChange={vi.fn()} />)
    fireEvent.click(screen.getAllByRole('checkbox')[0]) // check response_time
    // Click + button to add another pass criterion
    fireEvent.click(screen.getByRole('button', { name: /add criterion/i }))
    // Should now have 2 operator selects for pass criteria
    const operatorSelects = screen.getAllByDisplayValue('<')
    expect(operatorSelects.length).toBeGreaterThanOrEqual(2)
  })

  it('shows AND label between multi-criteria rows', () => {
    const objectives = [{
      sli: 'error_rate', weight: 3, key_sli: true,
      pass_criteria: ['<=+10%', '<5'], warning_criteria: ['<=+20%', '<10'],
    }]
    render(<WizardStepIndicators indicators={indicators} objectives={objectives} onChange={vi.fn()} />)
    expect(screen.getAllByText('AND').length).toBeGreaterThanOrEqual(1)
  })

  it('shows preview for both pass and warn criteria', () => {
    const objectives = [{
      sli: 'response_time', weight: 2, key_sli: false,
      pass_criteria: ['<600'], warning_criteria: ['<800'],
    }]
    render(<WizardStepIndicators indicators={indicators} objectives={objectives} onChange={vi.fn()} />)
    expect(screen.getByText('<600')).toBeInTheDocument()
    expect(screen.getByText('<800')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Implement WizardStepIdentity**

Fields: name (slug input), display_name, author, notes. Calls `onComplete(data)` when name is non-empty.
In edit mode, `name` field is read-only (you can't rename an SLO, only create a new version of the same name).

- [ ] **Step 3: Implement WizardStepPickSli**

Two SearchableComboBox fields:
1. Datasource — from useDatasources() (UI filter only, not saved to SLO)
2. SLI — from useSliDefinitions(selectedDs.adapter_type), filtered by adapter_type

Calls `onComplete({ sliName, indicators })` when SLI selected. In edit mode, pre-selects the SLI matching the existing SLO's indicator names.

- [ ] **Step 4: Implement WizardStepIndicators**

**Table layout** (matches Penpot mockup "Redesign — SLO Creation Wizard"):

Column headers: `☑ | Indicator | Wt | Key | PASS CRITERIA (Op, Sign, Value, %, Preview) | WARNING CRITERIA (Op, Sign, Value, %, Preview) | +`

Each row = one indicator from the selected SLI. Indicators start checked if they were objectives in the `editSlo` or if newly added. Unchecked rows show dimmed text "(unchecked — will not be included)" with `opacity-40`.

**Multi-criteria AND logic:**
- `pass_criteria` and `warning_criteria` are **lists** — ALL criteria must pass (AND logic)
- Each indicator can have 1+ pass criteria rows and 1+ warn criteria rows
- When an indicator has >1 criterion, sub-rows are grouped visually with an "AND" bracket/label between them
- `+` button at row end adds another criterion row (both pass + warn together)
- `−` button removes a criterion row (minimum 1 remains)
- Each criterion row has its own `StructuredCriteriaInput` for pass AND a separate one for warn
- **Both** pass and warn columns have a Preview cell showing the serialized string (e.g., `<600`, `<=+10%`)

The subtitle above the table reads: "Multiple criteria = AND logic. Use + to add."

- [ ] **Step 5: Implement WizardStepComparison**

**Left column — Comparison Settings:**
- Baseline Mode dropdown: "Previous evaluations" (default), "Manual"
- Compare against last: number input (default: 3) + "evaluations" label
- Aggregate Function dropdown: avg, p50, p90, p95, p99
- Include Result With Score dropdown: pass_or_warn (default), pass, all

**Right column — Score Thresholds:**
- Pass ≥ input (default: 90) with % suffix
- Warn ≥ input (default: 75) with % suffix
- **Visual threshold bar** showing three colored zones:
  - Fail (red, 0→warn%) | Warning (yellow, warn%→pass%) | Pass (green, pass%→100%)
  - Zone labels + threshold markers update reactively as inputs change

**Tags section:**
- Reuses the existing `TagBuilder` component from asset views (see `features/assets/`) with SLO-colored accents (green `#7dc540`)
- NOT a custom key-value editor — same component, different color context

**Variables section:**
- Simple key-value rows with + to add more (these are SLO-level variable defaults, lower priority than asset variables)

- [ ] **Step 6: Implement SloWizard container**

Full-page form (not a dialog). Progressive disclosure: Step 1 always visible, Step 2 when name filled, Step 3 when SLI selected, Step 4 when any indicator has pass criteria.

**Title area:**
- Create mode: "New SLO Definition"
- Edit mode: "{name} · New Version" with subtitle "Editing creates version {N+1} · All fields pre-filled from v{N}"

**Footer:** Cancel (text) | Primary button:
- Create mode: "Create SLO" (green)
- Edit mode: "Create Version" (green)

On submit: serializes all criteria via `serializeCriteria()`, calls `useCreateSlo()` mutation. Both create and edit call the same POST endpoint (backend auto-increments version).

**Pre-fill logic (edit mode):**
When `editSlo` prop is set, populate all fields from the existing SLO definition:
- Step 1: name (readonly), display_name, author, notes
- Step 2: auto-select SLI matching existing objectives' indicator names
- Step 3: check matching indicators, fill criteria from `pass_criteria[]` and `warning_criteria[]`, set weights and key_sli flags
- Step 4: fill comparison config, score thresholds, tags, variables

- [ ] **Step 7: Write SloWizard integration test**

Test: initial shows only Step 1. Test: filling name reveals Step 2. Test: selecting SLI reveals Step 3. Test: checking indicator + adding criteria reveals Step 4. Test: Create button disabled until valid. Test: edit mode shows "New Version" title and pre-fills all fields. Test: edit mode footer says "Create Version".

- [ ] **Step 8: Run all wizard tests**

Run: `./scripts/ui-test.sh --tail 30 src/features/registry/forms/`

- [ ] **Step 9: Commit**

```
feat(ui): add SLO creation wizard with multi-criteria AND rows and edit flow
```

---

### Task 16: Revised SLO Link Dialog

**Files:**
- Create: `ui/src/features/registry/forms/SloLinkDialogRevised.tsx`
- Test: `ui/src/features/registry/forms/SloLinkDialogRevised.test.tsx`

Replaces the existing `SloLinkDialog` with SearchableComboBox pickers instead of native selects. Used by AssetBindingView "Link an SLO" action.

- [ ] **Step 1: Write test**

Test: renders 4-step cascade (DS → SLI → SLO → Group). Test: SLI picker disabled until DS selected. Test: SLO picker uses SearchableComboBox. Test: duplicate link detection. Test: calls createGroupSloLink on submit.

- [ ] **Step 2: Implement SloLinkDialogRevised**

Same cascade logic as existing `SloLinkDialog` but uses `SearchableComboBox` instead of native `<select>` for all pickers. Accepts `lockedGroupName` and `lockedSloName` props for contextual usage. Uses hooks from canonical modules (`features/datasources/hooks`, `features/slis/hooks`).

- [ ] **Step 3: Run tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/forms/SloLinkDialogRevised.test.tsx`

- [ ] **Step 4: Commit**

```
feat(ui): add revised SLO Link dialog with searchable comboboxes
```

---

### Task 17: RegistryDetailPanel Router

**Files:**
- Create: `ui/src/features/registry/RegistryDetailPanel.tsx`
- Test: `ui/src/features/registry/RegistryDetailPanel.test.tsx`

Routes `SelectedNode` to the correct detail view component.

- [ ] **Step 1: Write failing test**

```typescript
// ui/src/features/registry/RegistryDetailPanel.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RegistryDetailPanel } from './RegistryDetailPanel'

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('RegistryDetailPanel', () => {
  it('shows empty state when nothing selected', () => {
    render(<RegistryDetailPanel selected={null} onNavigate={vi.fn()} />, { wrapper: Wrapper })
    expect(screen.getByText(/select an item/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Implement RegistryDetailPanel**

Switch on `selected.type`:
- `slo` → `<SloDetailView name={selected.name} onNavigate={onNavigate} />`
- `sli` → `<SliDetailView name={selected.name} onNavigate={onNavigate} />`
- `datasource` → `<DatasourceDetailView name={selected.name} onNavigate={onNavigate} />`
- `asset` / `group` → `<AssetBindingView assetName={...} groupName={...} onNavigate={onNavigate} />`
- `null` → empty state: "Select an item from the sidebar"

- [ ] **Step 3: Run tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/RegistryDetailPanel.test.tsx`

- [ ] **Step 4: Commit**

```
feat(ui): add RegistryDetailPanel routing selected node to detail views
```

---

### Task 18: Page Integration — Replace SloRegistryPage

**Files:**
- Replace: `ui/src/pages/SloRegistryPage.tsx`
- Replace: `ui/src/pages/SloRegistryPage.test.tsx`

Wire everything together.

- [ ] **Step 1: Write new page test**

```typescript
// ui/src/pages/SloRegistryPage.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { SloRegistryPage } from './SloRegistryPage'

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter>
      <QueryClientProvider client={new QueryClient()}>
        {children}
      </QueryClientProvider>
    </MemoryRouter>
  )
}

describe('SloRegistryPage', () => {
  it('renders segmented control with Asset as first/default', () => {
    render(<SloRegistryPage />, { wrapper: Wrapper })
    expect(screen.getByText('Asset')).toBeInTheDocument()
    expect(screen.getByText('SLO')).toBeInTheDocument()
    expect(screen.getByText('Datasource')).toBeInTheDocument()
  })

  it('renders search input', () => {
    render(<SloRegistryPage />, { wrapper: Wrapper })
    expect(screen.getByPlaceholderText('Filter...')).toBeInTheDocument()
  })

  it('renders empty state in main panel', () => {
    render(<SloRegistryPage />, { wrapper: Wrapper })
    expect(screen.getByText(/select an item/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Rewrite SloRegistryPage**

New layout: `RegistrySidebar` + `RegistryDetailPanel` + form dialogs/wizard. URL state: `?mode=asset&type=slo&selected=http-slo&group=core`. Cross-entity navigation: `onNavigate` callback switches mode based on target type. `onCreateAction` receives entity type + optional context (e.g., `{ adapterType: 'prometheus' }` when creating SLI from datasource context).

**Form routing:**
- DatasourceForm, SliForm — dialogs for DS/SLI create/edit
- SloWizard — full-page form (replaces detail panel), opened via:
  - "+ Create" → "New SLO" (create mode, no `editSlo` prop)
  - SloDetailView "New Version" button (edit mode, passes current SloDefinition as `editSlo`)
  - AssetBindingView "Edit" button (same edit mode)
- SloLinkDialogRevised — dialog for linking existing SLO to asset group

When SloWizard is active, it replaces the detail panel content. Cancel returns to previous detail view.

- [ ] **Step 3: Run page tests**

Run: `./scripts/ui-test.sh --tail 20 src/pages/SloRegistryPage.test.tsx`

- [ ] **Step 4: Run full test suite**

Run: `./scripts/ui-test.sh --tail 40`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```
feat(ui): replace SloRegistryPage with 3-mode registry layout
```

---

### Task 19: TypeScript Type Check & Final Verification

- [ ] **Step 1: Run type checker**

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`

- [ ] **Step 2: Fix any type errors**

- [ ] **Step 3: Run all UI tests**

Run: `./scripts/ui-test.sh --tail 40`
Expected: All tests PASS

- [ ] **Step 4: Visual smoke test (manual)**

Start dev server (`just dev`), navigate to `/slos`, verify:
- Segmented control: Asset (default) | SLO | Datasource
- Search filters tree nodes
- Clicking tree nodes shows detail in main panel
- Create dropdown opens appropriate form (4 items: SLO, SLI, DS, Group)
- SLO wizard steps unfold progressively
- Multi-criteria AND rows: clicking + adds a new criterion row with AND label
- Both pass AND warn columns show preview strings
- % toggle turns green when active
- Unchecked indicators are dimmed
- Score threshold visual bar updates as pass/warn % change
- Tags section uses same builder as asset view
- Edit flow: clicking "New Version" on SLO detail opens wizard pre-filled, title shows "· New Version"
- Binding chain breadcrumbs are clickable for cross-navigation
- Tag pills add/remove correctly

- [ ] **Step 5: Commit if any fixes needed**

```
chore(ui): final cleanup for SLO Registry Phase 2
```
