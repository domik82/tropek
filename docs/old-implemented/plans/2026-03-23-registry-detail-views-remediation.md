# Registry Detail Views Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring ALL Registry views — AssetBindingView, SloDetailView, Create dropdown, and SLO Wizard — up to the Penpot design spec. Fixes missing data, colors, table styling, and visual polish across the board.

**Architecture:** The AssetBindingView is rewritten to fetch full asset detail (tags, variables, type) and SLO definitions for each binding, then renders rich binding cards matching the Penpot "Redesign — Registry (Asset Mode)" board. The SloDetailView's criteria get status colors and the "Linked Assets" placeholder is replaced with real data. The Create dropdown gets two-line descriptions. The SLO Wizard gets visual polish. No backend changes needed — all data is already available via existing API endpoints.

**Tech Stack:** React 19, TypeScript 5.9, Vite 8, Tailwind CSS v4, React Query, Vitest + React Testing Library.

**Reference screenshots:**
- Design: `C:\Users\djezi\OneDrive\Dokumenty\ShareX\Screenshots\2026-03\chrome_2026-03-23_19-34-52.png`
- Current: `C:\Users\djezi\OneDrive\Dokumenty\ShareX\Screenshots\2026-03\chrome_2026-03-23_19-36-55.png`

---

## Audit Summary (what's wrong)

| Component | Gap | Severity |
|---|---|---|
| **AssetBindingView** | Skeleton — only breadcrumb + Unlink. Missing: asset header, per-binding objectives table, VariableResolutionPanel, actions, binding count. Uses wrong table classes | Critical |
| **SloDetailView** | "Linked Assets" placeholder. Custom objectives table instead of reusing `SloObjectiveTable`. Pass/warn criteria use `text-muted-foreground` instead of `#7dc540`/`#e6be00` | Critical |
| **ALL registry tables** | Use `border-border text-muted-foreground` — Navigator uses `border-slate-700 bg-slate-800/60 text-slate-400` + zebra rows + hover states | Critical |
| **ALL registry panels** | Use `p-4 space-y-4` — Navigator uses `p-6 space-y-6` + `text-xl` headers | High |
| **Asset type (UI)** | Missing `variables` field — backend returns it but UI type doesn't declare it | High |
| **Create dropdown** | Single-line labels, small dot accent. Navigator menu uses `w-[3px] h-[36px]` accent bar + `text-[13px]` label + `text-[11px]` description, `rounded-xl shadow-xl` | High |
| **SLO Wizard** | Shows scrollbar instead of using viewport. Notes is `<Input>` not `<textarea>`. No step badges. Sections lack card boundaries | High |
| **Group creation dialog** | Inline overlay — should use proper dialog positioning like Navigator | Medium |
| **BindingChainBreadcrumb** | `sloVersion` prop exists but never passed by caller | Low |

---

## Visual Alignment Reference

**These are the established Navigator patterns. ALL registry views MUST use these exact classes.**

### Entity color identity — PRESERVE THIS

Each entity type has a dedicated color used for accent strips, tree nodes, and breadcrumb badges:

| Entity | Color | Hex | Used in |
|--------|-------|-----|---------|
| SLO | Green | `#7dc540` (`ENTITY_COLORS.slo`) | Accent strip on SloDetailView, SLO wizard |
| SLI | Violet | `#A371F7` (`ENTITY_COLORS.sli`) | SLI detail views, tree nodes |
| Datasource | Blue | `#58A6FF` (`ENTITY_COLORS.ds`) | DS detail views, tree nodes |
| Group/Asset | Gray | `#8B949E` (`ENTITY_COLORS.group`) | AssetBindingView accent strip |

**Every detail view MUST have a 3px accent strip** at the top, colored by entity type:
```tsx
<div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.slo }} />
```

**Known tradeoff:** `SloObjectiveTable` colors indicator (SLI) names green `#7dc540` instead of violet `#A371F7`. This is intentional for readability in the SLO objectives context — the table is an SLO view, not an SLI view. The sidebar tree and SLI detail views correctly use violet.

### Table pattern (see `GroupDetailPanel.tsx:156-215`, `SloObjectiveTable.tsx`)

```tsx
{/* Table container — rounded border, dark bg */}
<div className="border border-slate-700 rounded-lg overflow-hidden">
  <table className="w-full text-sm">
    <thead>
      <tr className="border-b border-slate-700 bg-[#111827]">
        <th className="text-left px-3 py-2 text-xs uppercase text-muted-foreground font-medium">Col</th>
      </tr>
    </thead>
    <tbody>
      {items.map((item, idx) => (
        <tr key={item.id} className={`border-b border-slate-800/60 last:border-0 hover:bg-gray-700/50 transition-colors ${
          idx % 2 === 0 ? 'bg-gray-900' : 'bg-gray-800/50'
        }`}>
          <td className="px-3 py-2">...</td>
        </tr>
      ))}
    </tbody>
  </table>
</div>
```

### Objectives table — REUSE `SloObjectiveTable` component

`SloObjectiveTable` at `ui/src/features/slos/components/SloObjectiveTable.tsx` already has the correct styling:
- `rounded-lg border border-slate-700`
- Header: `text-xs uppercase text-slate-400 bg-slate-800/60 border-b border-slate-700`
- Rows: `divide-y divide-slate-800` + `hover:bg-slate-800/40 transition-colors`
- Key SLI: cyan diamond `◆`
- Pass criteria: `text-[#7dc540]` (green)
- Warning criteria: `text-[#e6be00]` (yellow)
- Score summary footer with colored totals

**Do NOT write custom objectives tables. Import and use `SloObjectiveTable`.**

### Panel layout pattern (see `GroupDetailPanel.tsx:62-66`)

```tsx
<div className="p-6 space-y-6" style={{ fontFamily: SANS_SERIF }}>
  {/* Header */}
  <div>
    <h2 className="text-xl font-semibold text-foreground">Title</h2>
    <p className="text-sm text-muted-foreground mt-0.5">subtitle line</p>
  </div>
  {/* Sections with text-sm font-semibold headers */}
</div>
```

### Action button patterns (see `GroupDetailPanel.tsx:76-98`)

```tsx
{/* Outline edit */}
<button className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5">
  <Pencil className="w-3.5 h-3.5" /> Edit
</button>

{/* Blue accent (Link SLO) */}
<button className="px-3 py-1.5 text-xs rounded bg-[#0D2847] border border-[#58A6FF] text-[#58A6FF] hover:bg-[#0D2847]/80 transition-colors flex items-center gap-1.5">
  <Link className="w-3.5 h-3.5" /> Link SLO
</button>

{/* Red accent (Delete/Unlink) */}
<button className="px-3 py-1.5 text-xs rounded bg-[#3D1418] border border-[#F85149] text-[#F85149] hover:bg-[#3D1418]/80 transition-colors flex items-center gap-1.5">
  <Trash2 className="w-3.5 h-3.5" /> Delete
</button>
```

### Dropdown menu pattern (see `EvaluationActions.tsx:126-171`)

```tsx
<div className="absolute right-0 top-full mt-1 z-20 min-w-[280px] bg-popover border border-border rounded-xl shadow-xl overflow-hidden py-2">
  {items.map(item => (
    <button className="flex items-start gap-3 w-full text-left px-3 py-2.5 transition-colors hover:bg-accent group">
      <div className="w-[3px] rounded-full shrink-0 mt-0.5" style={{ backgroundColor: item.color, height: 36 }} />
      <div className="min-w-0">
        <div className="text-[13px] font-medium text-popover-foreground">{item.label}</div>
        <div className="text-[11px] text-muted-foreground mt-0.5">{item.desc}</div>
      </div>
    </button>
  ))}
</div>
```

### Section header pattern

```tsx
<h3 className="text-sm font-semibold text-foreground">Section Name ({count})</h3>
```

---

## File Structure

### Modified files

```
ui/src/
├── features/assets/types.ts                          # MODIFY — add variables field to Asset
├── features/registry/details/AssetBindingView.tsx     # REWRITE — full binding cards per design
├── features/registry/details/AssetBindingView.test.tsx # REWRITE — tests for new binding view
├── features/registry/details/SloDetailView.tsx        # MODIFY — wire Linked Groups + criteria colors
├── features/registry/details/SloDetailView.test.tsx   # MODIFY — add linked groups test
├── features/registry/RegistryDetailPanel.tsx          # MODIFY — pass groupLinksMap prop
├── features/registry/RegistrySidebar.tsx              # MODIFY — accept link data as props + Create dropdown descriptions
├── features/registry/forms/SloWizard.tsx              # MODIFY — card-wrapped sections
├── features/registry/forms/WizardStepIdentity.tsx     # MODIFY — textarea notes + step badge
├── features/registry/forms/WizardStepPickSli.tsx      # MODIFY — step badge
├── features/registry/forms/WizardStepIndicators.tsx   # MODIFY — step badge
├── features/registry/forms/WizardStepComparison.tsx   # MODIFY — step badge
├── pages/SloRegistryPage.tsx                          # MODIFY — thread link data to detail panel
```

### New files

```
ui/src/
├── features/registry/useAllGroupLinks.ts              # NEW — extracted hook for group link fetching
```

---

## Implementation Tasks

### Task 1: Add `variables` to Asset Type

**Files:**
- Modify: `ui/src/features/assets/types.ts`

The backend `AssetRead` schema includes `variables: dict[str, str]` but the UI `Asset` interface doesn't declare it. Every other feature depending on asset variables (VariableResolutionPanel, the binding view) needs this field.

- [ ] **Step 1: Add `variables` to the Asset interface**

```typescript
// ui/src/features/assets/types.ts — add to existing Asset interface
export interface Asset {
  id: string
  name: string
  display_name?: string
  type_name: string
  tags: Record<string, string>
  variables: Record<string, string>  // ADD THIS LINE
  created_at: string
  updated_at: string
}
```

- [ ] **Step 2: Run type check to verify no regressions**

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json 2>&1 | grep -c 'error TS'`

Adding a field to an interface is backward-compatible — existing code that doesn't use `variables` is unaffected. The type check should show the same error count as before (pre-existing errors in DatasourceForm.tsx).

- [ ] **Step 3: Commit**

```
fix(ui): add variables field to Asset type matching backend schema
```

---

### Task 2: Rewrite AssetBindingView — Test First

**Files:**
- Rewrite: `ui/src/features/registry/details/AssetBindingView.test.tsx`

The current test file tests a skeleton. Rewrite tests to match the full design spec.

- [ ] **Step 1: Write failing tests for the full AssetBindingView**

```typescript
// ui/src/features/registry/details/AssetBindingView.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AssetBindingView } from './AssetBindingView'

vi.mock('@/features/slos/hooks', () => ({
  useGroupSloLinks: vi.fn(),
  useDeleteGroupSloLink: vi.fn(() => ({ mutate: vi.fn() })),
  useSloDetail: vi.fn(),
}))

vi.mock('@/features/assets/hooks', () => ({
  useAsset: vi.fn(),
}))

import { useGroupSloLinks, useSloDetail } from '@/features/slos/hooks'
import { useAsset } from '@/features/assets/hooks'

const MOCK_ASSET = {
  id: '1',
  name: 'checkout-api',
  display_name: 'Checkout API',
  type_name: 'service',
  tags: { env: 'production', team: 'payments', tier: 'critical' },
  variables: { job: 'checkout-api', namespace: 'ecommerce' },
  created_at: '2026-03-15T00:00:00Z',
  updated_at: '2026-03-15T00:00:00Z',
}

const MOCK_SLO = {
  id: 's1',
  name: 'http-availability-slo',
  version: 1,
  comparable_from_version: 1,
  display_name: 'HTTP Availability SLO',
  author: 'bootstrap',
  notes: null,
  tags: {},
  variables: { aggregation_window: '5m' },
  created_at: '2026-03-15T00:00:00Z',
  active: true,
  objectives: [
    { sli: 'response_time_p99', display_name: 'P99 Latency', pass_criteria: ['<600'], warning_criteria: ['<800'], weight: 2, key_sli: false, sort_order: 0 },
    { sli: 'error_rate', display_name: 'Error Rate', pass_criteria: ['<1%'], warning_criteria: ['<2%'], weight: 3, key_sli: true, sort_order: 1 },
  ],
  total_score_pass_pct: 90,
  total_score_warning_pct: 75,
  comparison: {},
}

const MOCK_LINKS = [
  {
    id: '1',
    link_name: 'checkout-api-http',
    group_id: 'g1',
    slo_name: 'http-availability-slo',
    sli_name: 'http-service-sli',
    data_source_name: 'prometheus-local',
    created_at: '2026-03-15T00:00:00Z',
  },
]

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('AssetBindingView', () => {
  beforeEach(() => {
    vi.mocked(useAsset).mockReturnValue({ data: MOCK_ASSET, isLoading: false } as any)
    vi.mocked(useGroupSloLinks).mockReturnValue({ data: MOCK_LINKS, isLoading: false } as any)
    vi.mocked(useSloDetail).mockReturnValue({ data: MOCK_SLO, isLoading: false } as any)
  })

  it('renders asset name and type', () => {
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText('Checkout API')).toBeInTheDocument()
    expect(screen.getByText(/service/)).toBeInTheDocument()
  })

  it('renders asset tags as chips', () => {
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText(/env: production/)).toBeInTheDocument()
    expect(screen.getByText(/team: payments/)).toBeInTheDocument()
  })

  it('renders asset variables', () => {
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText(/\$job/)).toBeInTheDocument()
    expect(screen.getByText(/checkout-api/)).toBeInTheDocument()
  })

  it('renders binding count in section header', () => {
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText(/SLO Bindings \(1\)/)).toBeInTheDocument()
  })

  it('renders binding chain breadcrumb', () => {
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText('http-availability-slo')).toBeInTheDocument()
    expect(screen.getByText('http-service-sli')).toBeInTheDocument()
    expect(screen.getByText('prometheus-local')).toBeInTheDocument()
  })

  it('renders objectives table with pass/warn criteria', () => {
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText('response_time_p99')).toBeInTheDocument()
    expect(screen.getByText('<600')).toBeInTheDocument()
    expect(screen.getByText('<800')).toBeInTheDocument()
    expect(screen.getByText('error_rate')).toBeInTheDocument()
  })

  it('renders empty state with Link SLO button', () => {
    vi.mocked(useGroupSloLinks).mockReturnValue({ data: [], isLoading: false } as any)
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText(/No SLO bindings/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/details/AssetBindingView.test.tsx`
Expected: FAIL — current AssetBindingView doesn't render asset metadata, tags, variables, or binding count.

- [ ] **Step 3: Commit test**

```
test(ui): rewrite AssetBindingView tests to match design spec
```

---

### Task 3: Rewrite AssetBindingView — Implementation

**Files:**
- Rewrite: `ui/src/features/registry/details/AssetBindingView.tsx`

**CRITICAL: Match Navigator visual patterns exactly. See "Visual Alignment Reference" section above.**

**Existing components to reuse (do NOT recreate):**
- `BindingChainBreadcrumb` — SLO→SLI→DS chain badges. Has `sloVersion` prop.
- `VariableResolutionPanel` — asset/SLO/reserved variables in monospace panel.
- `SloObjectiveTable` at `ui/src/features/slos/components/SloObjectiveTable.tsx` — **USE THIS for objectives**. It already has correct zebra, hover, colors, border-radius. Accepts `{ slo: SloDefinition }`.
- `ENTITY_COLORS`, `SANS_SERIF` — color and font constants.

**Existing hooks to use:**
- `useAsset(name)`, `useGroupSloLinks(groupName)`, `useDeleteGroupSloLink()`, `useSloDetail(name)`

**Design spec — must match `GroupDetailPanel` layout conventions:**

**Asset header** (matches `GroupDetailPanel.tsx:62-98`):
- Panel wrapper: `p-6 space-y-6` with `fontFamily: SANS_SERIF`
- Title: `text-xl font-semibold text-foreground` (NOT text-base)
- Subtitle: `text-sm text-muted-foreground mt-0.5` — stats line like `service · 3 variables · 3 tags`
- "Link SLO" button: blue accent style `bg-[#0D2847] border-[#58A6FF] text-[#58A6FF]`
- Variables row: `text-sm text-slate-400` monospace with `$key = value`
- Tags: use `LabelChips` if available, or plain chips

**Per binding card** (matches `border border-slate-700 rounded-lg` container):
- Card: `border border-slate-700 rounded-lg overflow-hidden`
- Header row: `p-3 bg-[#111827] border-b border-slate-700` with breadcrumb + action buttons
- Edit button: outline style `border-border text-muted-foreground hover:text-foreground`
- Unlink button: red accent `bg-[#3D1418] border-[#F85149] text-[#F85149]`
- Objectives: **use `<SloObjectiveTable slo={slo} />`** — do NOT write custom table
- Variable resolution panel between header and objectives

- [ ] **Step 1: Implement AssetBindingView**

```typescript
// ui/src/features/registry/details/AssetBindingView.tsx
import { Link, Unlink, Pencil } from 'lucide-react'
import { BindingChainBreadcrumb } from '@/components/shared/BindingChainBreadcrumb'
import { VariableResolutionPanel } from '@/components/shared/VariableResolutionPanel'
import { SloObjectiveTable } from '@/features/slos/components/SloObjectiveTable'
import { useAsset } from '@/features/assets/hooks'
import { useGroupSloLinks, useDeleteGroupSloLink, useSloDetail } from '@/features/slos/hooks'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import type { AssetGroupSLOLink } from '@/features/slos/types'
import type { Asset } from '@/features/assets/types'
import type { SelectedNode } from '@/features/registry/types'

interface AssetBindingViewProps {
  assetName: string
  groupName: string
  onNavigate: (node: SelectedNode) => void
  onLinkSlo: () => void
}

export function AssetBindingView({
  assetName,
  groupName,
  onNavigate,
  onLinkSlo,
}: AssetBindingViewProps) {
  const { data: asset, isLoading: assetLoading } = useAsset(assetName)
  const { data: links, isLoading: linksLoading } = useGroupSloLinks(groupName)

  if (assetLoading || linksLoading) {
    return (
      <div className="p-6 text-sm text-muted-foreground" style={{ fontFamily: SANS_SERIF }}>
        Loading…
      </div>
    )
  }

  const bindings = links ?? []
  const varCount = Object.keys(asset?.variables ?? {}).length
  const tagCount = Object.keys(asset?.tags ?? {}).length
  const statsLine = [
    asset?.type_name ?? 'asset',
    varCount > 0 ? `${varCount} variables` : null,
    tagCount > 0 ? `${tagCount} tags` : null,
  ].filter(Boolean).join(' · ')

  return (
    <div className="overflow-auto h-full" style={{ fontFamily: SANS_SERIF }}>
      {/* Entity accent strip — group color */}
      <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.group }} />

      <div className="p-6 space-y-6">
      {/* Header — matches GroupDetailPanel layout */}
      <div>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold text-foreground">
              {asset?.display_name ?? assetName}
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">{statsLine}</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onLinkSlo}
              className="px-3 py-1.5 text-xs rounded bg-[#0D2847] border border-[#58A6FF] text-[#58A6FF] hover:bg-[#0D2847]/80 transition-colors flex items-center gap-1.5"
            >
              <Link className="w-3.5 h-3.5" />
              Link SLO
            </button>
          </div>
        </div>

        {/* Variables row — monospace like GroupDetailPanel metadata */}
        {varCount > 0 && (
          <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-400">
            {Object.entries(asset!.variables).map(([k, v]) => (
              <span key={k} className="font-mono">
                <span className="text-[#FFA657]">${k}</span> = {v}
              </span>
            ))}
          </div>
        )}

        {/* Tag chips */}
        {tagCount > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {Object.entries(asset!.tags).map(([k, v]) => (
              <span
                key={k}
                className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary border border-primary/20"
              >
                {k}: {v}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* SLO Bindings section */}
      <div>
        <h3 className="text-sm font-semibold text-foreground mb-3">
          SLO Bindings ({bindings.length})
        </h3>

        {bindings.length === 0 ? (
          <p className="text-sm text-muted-foreground italic">No SLO bindings</p>
        ) : (
          <div className="space-y-4">
            {bindings.map(link => (
              <BindingCard
                key={link.id}
                link={link}
                asset={asset ?? null}
                groupName={groupName}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        )}
      </div>
    </div>{/* close p-6 wrapper */}
    </div>
  )
}

function BindingCard({
  link,
  asset,
  groupName,
  onNavigate,
}: {
  link: AssetGroupSLOLink
  asset: Asset | null
  groupName: string
  onNavigate: (node: SelectedNode) => void
}) {
  const { data: slo } = useSloDetail(link.slo_name)
  const deleteMutation = useDeleteGroupSloLink()

  const assetVars = asset?.variables ?? {}
  const sloVars = slo?.variables ?? {}
  const reserved: Record<string, string> = {}
  if (asset?.name) reserved['asset_name'] = asset.name

  return (
    <div className="border border-slate-700 rounded-lg overflow-hidden">
      {/* Binding header — dark bg like table headers */}
      <div className="flex items-center justify-between gap-2 px-3 py-2.5 bg-[#111827] border-b border-slate-700">
        <BindingChainBreadcrumb
          sloName={link.slo_name}
          sloVersion={slo ? String(slo.version) : undefined}
          sliName={link.sli_name}
          dsName={link.data_source_name}
          onClickSlo={() => onNavigate({ type: 'slo', name: link.slo_name })}
          onClickSli={() => onNavigate({ type: 'sli', name: link.sli_name })}
          onClickDs={() => onNavigate({ type: 'datasource', name: link.data_source_name })}
        />
        <div className="flex shrink-0 gap-2">
          <button
            onClick={() => onNavigate({ type: 'slo', name: link.slo_name })}
            className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5"
          >
            <Pencil className="w-3.5 h-3.5" />
            Edit
          </button>
          <button
            onClick={() => deleteMutation.mutate({ groupName, linkName: link.link_name })}
            className="px-3 py-1.5 text-xs rounded bg-[#3D1418] border border-[#F85149] text-[#F85149] hover:bg-[#3D1418]/80 transition-colors flex items-center gap-1.5"
          >
            <Unlink className="w-3.5 h-3.5" />
            Unlink
          </button>
        </div>
      </div>

      {/* Variable resolution */}
      {(Object.keys(assetVars).length > 0 || Object.keys(sloVars).length > 0 || Object.keys(reserved).length > 0) && (
        <div className="px-3 pt-3">
          <VariableResolutionPanel
            assetVariables={assetVars}
            sloVariables={sloVars}
            reserved={reserved}
          />
        </div>
      )}

      {/* Objectives — REUSE SloObjectiveTable */}
      {slo && slo.objectives.length > 0 && (
        <div className="p-3">
          <SloObjectiveTable slo={slo} />
        </div>
      )}

      {/* Loading state */}
      {!slo && (
        <div className="p-3 text-sm text-muted-foreground">Loading SLO details…</div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 20 src/features/registry/details/AssetBindingView.test.tsx`

- [ ] **Step 3: Run type check**

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json 2>&1 | tail -5`

- [ ] **Step 4: Commit**

```
feat(ui): rewrite AssetBindingView with full binding cards per design spec
```

---

### Task 4: Fix SloDetailView "Linked Groups" Section

**Files:**
- Modify: `ui/src/features/registry/details/SloDetailView.tsx`
- Modify: `ui/src/features/registry/details/SloDetailView.test.tsx`

The "Linked Assets" section at line 236-239 is a placeholder saying "No linked assets". It needs to show which groups and assets reference this SLO. The data source: fetch all group links (same as sidebar) and filter by `slo_name`.

**Approach:** Add a new prop `allLinks` (array of `{slo_name, sli_name, data_source_name, groupName}`) to SloDetailView. The parent (RegistryDetailPanel → SloRegistryPage) already has this data from the sidebar's `useQueries`. Thread it down.

Alternatively, simpler: SloDetailView fetches group links itself using the same `useQueries` approach. But that duplicates the sidebar's fetching.

Simplest: Add a prop `linkedGroups` to SloDetailView — an array of group names that link to this SLO. The caller computes it from the allLinks data.

- [ ] **Step 1: Write test for linked groups**

```typescript
// Add to SloDetailView.test.tsx
it('renders linked groups', () => {
  // Mock useSloDetail to return a valid SLO
  // Pass linkedGroups={['core-services', 'data-tier']}
  render(<SloDetailView name="http-availability-slo" onNavigate={vi.fn()}
    onNewVersion={vi.fn()} linkedGroups={['core-services', 'data-tier']} />, { wrapper })
  expect(screen.getByText(/Linked Groups/)).toBeInTheDocument()
  expect(screen.getByText('core-services')).toBeInTheDocument()
  expect(screen.getByText('data-tier')).toBeInTheDocument()
})
```

- [ ] **Step 2: Add `linkedGroups` prop to SloDetailView**

```typescript
// In SloDetailView.tsx, add to props interface:
interface SloDetailViewProps {
  name: string
  onNavigate: (node: SelectedNode) => void
  onNewVersion: (slo: SloDefinition) => void
  linkedGroups?: string[]  // ADD
}
```

Replace the placeholder section (lines 236-239):

```typescript
{/* Linked Groups */}
<div>
  <p className="text-xs text-muted-foreground mb-2">
    Linked Groups ({(linkedGroups ?? []).length})
  </p>
  {(linkedGroups ?? []).length === 0 ? (
    <p className="text-xs text-muted-foreground">No groups linked to this SLO</p>
  ) : (
    <ul className="space-y-1">
      {(linkedGroups ?? []).map(gn => (
        <li key={gn}>
          <button
            type="button"
            className="text-sm text-primary hover:underline cursor-pointer"
            onClick={() => onNavigate({ type: 'group', name: gn })}
          >
            {gn}
          </button>
        </li>
      ))}
    </ul>
  )}
</div>
```

- [ ] **Step 3: Extract `useAllGroupLinks` hook**

Create a small hook that encapsulates the `useQueries` logic currently in `RegistrySidebar.tsx` lines 64-93.

New file: `ui/src/features/registry/useAllGroupLinks.ts`

```typescript
// ui/src/features/registry/useAllGroupLinks.ts
import { useMemo } from 'react'
import { useQueries } from '@tanstack/react-query'
import { groupKeys } from '@/lib/queryKeys'
import { fetchGroupSloLinks } from '@/features/slos/api'
import type { MinLink } from './useRegistryTree'

export function useAllGroupLinks(groupNames: string[]) {
  const filtered = useMemo(
    () => groupNames.filter(n => n !== '__ungrouped__'),
    [groupNames],
  )

  const linkQueries = useQueries({
    queries: filtered.map(name => ({
      queryKey: groupKeys.links(name),
      queryFn: () => fetchGroupSloLinks(name),
    })),
  })

  return useMemo(() => {
    const flat: MinLink[] = []
    const byGroup: Record<string, MinLink[]> = {}
    for (let i = 0; i < filtered.length; i++) {
      const data = linkQueries[i]?.data ?? []
      const links: MinLink[] = data.map(l => ({
        slo_name: l.slo_name,
        sli_name: l.sli_name,
        data_source_name: l.data_source_name,
      }))
      byGroup[filtered[i]] = links
      flat.push(...links)
    }
    const seen = new Set<string>()
    const unique = flat.filter(l => {
      const key = `${l.slo_name}|${l.sli_name}|${l.data_source_name}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    return { allLinks: unique, groupLinksMap: byGroup }
  }, [filtered, linkQueries])
}
```

- [ ] **Step 4: Update RegistrySidebar to accept link data as props**

In `RegistrySidebar.tsx`, change the component to accept pre-computed link data instead of fetching internally:

```typescript
// RegistrySidebar.tsx — updated Props interface
interface Props {
  mode: RegistryMode
  onModeChange: (mode: RegistryMode) => void
  selected: SelectedNode | null
  onSelect: (node: SelectedNode) => void
  onCreateAction: (type: 'datasource' | 'sli' | 'slo' | 'group', context?: { adapterType?: string }) => void
  allLinks: MinLink[]       // ADD
  groupLinksMap: Record<string, MinLink[]>  // ADD
}
```

Remove from the component body:
- The `useQueries` import (line 2)
- The `groupKeys` import (line 5)
- The `fetchGroupSloLinks` import (line 8)
- The `import type { MinLink }` (line 9) — keep if still needed for prop type
- The entire `groupNames` useMemo block (lines 64-67)
- The entire `linkQueries` useQueries block (lines 68-72)
- The entire `{ allLinks, groupLinksMap }` useMemo block (lines 74-93)

Replace the `treeNodes` useMemo to use the props directly:

```typescript
const treeNodes = useMemo(() => {
  if (mode === 'slo') return buildSloTree(slos ?? [], slis ?? [], datasources ?? [], allLinks)
  if (mode === 'datasource') return buildDatasourceTree(datasources ?? [], slis ?? [], slos ?? [], allLinks)
  return buildAssetTree(tree?.all_groups ?? [], groupLinksMap)
}, [mode, slos, slis, datasources, tree, allLinks, groupLinksMap])
```

- [ ] **Step 5: Update RegistryDetailPanel to accept and use groupLinksMap**

```typescript
// RegistryDetailPanel.tsx — updated props interface
import type { MinLink } from './useRegistryTree'

interface RegistryDetailPanelProps {
  selected: SelectedNode | null
  onNavigate: (node: SelectedNode) => void
  onEditDatasource?: (name: string) => void
  onNewSloVersion?: (slo: SloDefinition) => void
  onNewSliVersion?: (sli: SliDefinition) => void
  onLinkSlo?: (groupName: string) => void
  groupLinksMap?: Record<string, MinLink[]>  // ADD
}
```

In the SLO detail branch (line 38-46), compute and pass `linkedGroups`:

```typescript
if (selected.type === 'slo') {
  const linkedGroups = Object.entries(groupLinksMap ?? {})
    .filter(([, links]) => links.some(l => l.slo_name === selected.name))
    .map(([gn]) => gn)
  return (
    <SloDetailView
      name={selected.name}
      onNavigate={onNavigate}
      onNewVersion={onNewSloVersion ?? (() => {})}
      linkedGroups={linkedGroups}
    />
  )
}
```

- [ ] **Step 6: Update SloRegistryPage to call useAllGroupLinks and thread data**

```typescript
// SloRegistryPage.tsx — add imports
import { useAllGroupLinks } from '@/features/registry/useAllGroupLinks'
import { useGroupTree } from '@/features/slos/hooks'

// Inside SloRegistryPage component, after existing data fetching:
const { data: tree } = useGroupTree()
const groupNames = useMemo(
  () => (tree?.all_groups ?? []).map(g => g.name),
  [tree],
)
const { allLinks, groupLinksMap } = useAllGroupLinks(groupNames)
```

Note: `useGroupTree` is already called inside `RegistrySidebar`. Calling it at the page level too is fine — React Query deduplicates the request (same queryKey). This avoids prop-drilling the tree data.

Thread to sidebar:
```typescript
<RegistrySidebar
  mode={mode}
  onModeChange={handleModeChange}
  selected={selected}
  onSelect={handleSelect}
  onCreateAction={handleCreateAction}
  allLinks={allLinks}
  groupLinksMap={groupLinksMap}
/>
```

Thread to detail panel:
```typescript
<RegistryDetailPanel
  selected={selected}
  onNavigate={handleNavigate}
  onEditDatasource={handleEditDatasource}
  onNewSloVersion={handleNewSloVersion}
  onLinkSlo={handleLinkSlo}
  groupLinksMap={groupLinksMap}
/>
```

Add the `useMemo` import if not already present:
```typescript
import { useState, useCallback, useMemo } from 'react'
```

- [ ] **Step 7: Run all tests**

Run: `./scripts/ui-test.sh --tail 15`

- [ ] **Step 8: Commit**

```
feat(ui): wire linked groups into SloDetailView, extract useAllGroupLinks hook
```

---

### Task 5: TypeScript Verification & Final Polish

**Files:**
- All modified files from Tasks 1-5

- [ ] **Step 1: Run type check**

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json 2>&1 | tail -20`

Fix any new errors. Pre-existing errors in `DatasourceForm.tsx` are out of scope.

- [ ] **Step 2: Run full test suite**

Run: `./scripts/ui-test.sh --tail 15`

All 422+ tests must pass.

- [ ] **Step 3: Visual review checklist**

If `./scripts/dev-start.sh` is running, verify in browser:

- [ ] Asset mode → click "checkout-api" → see header with "Checkout API", "service · Asset", tags, variables
- [ ] Binding card shows breadcrumb with version, variable resolution panel, objectives table
- [ ] Objectives table has colored pass (green) and warn (yellow) criteria
- [ ] Edit button navigates to SLO detail view
- [ ] Unlink button works
- [ ] SLO mode → click any SLO → "Linked Assets" section shows group names (not "No linked assets")
- [ ] Clicking a linked group navigates to asset mode

- [ ] **Step 4: Commit any polish fixes**

```
fix(ui): address type errors and polish detail view rendering
```

---

### Task 6: Replace SloDetailView Custom Table with SloObjectiveTable + Navigator Layout

**Files:**
- Modify: `ui/src/features/registry/details/SloDetailView.tsx`

The SloDetailView has two problems:
1. Custom objectives table (lines 106-152) with wrong colors/styling — should reuse `SloObjectiveTable`
2. Panel uses `p-4 text-base` header — should use `p-6 text-xl` like Navigator

- [ ] **Step 1: Import SloObjectiveTable and replace custom table**

```typescript
// Add import:
import { SloObjectiveTable } from '@/features/slos/components/SloObjectiveTable'
```

Replace the entire custom objectives table (lines 106-152) with:

```typescript
{/* Objectives table — reuse Navigator's shared component */}
<div>
  <SloObjectiveTable slo={slo} />
</div>
```

This gives us proper `rounded-lg border border-slate-700`, `bg-slate-800/60` header, `divide-y divide-slate-800` rows, `hover:bg-slate-800/40`, cyan `◆` for key SLI, green `#7dc540` pass criteria, yellow `#e6be00` warn criteria, and score summary footer — all matching Navigator exactly.

- [ ] **Step 2: Fix panel layout to match Navigator conventions**

Change header from `text-base` to `text-xl`:

```typescript
// BEFORE (line 49):
<h2 className="text-base font-semibold text-foreground truncate">

// AFTER:
<h2 className="text-xl font-semibold text-foreground truncate">
```

Change to flat layout with accent strip PRESERVED:

```typescript
// BEFORE (line 40):
<div className="flex flex-col h-full overflow-auto" style={{ fontFamily: SANS_SERIF }}>
  <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.slo }} />
  <div className="p-4 border-b border-border">...</div>
  <div className="p-4 space-y-4">

// AFTER:
<div className="overflow-auto h-full" style={{ fontFamily: SANS_SERIF }}>
  <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.slo }} />
  <div className="p-6 space-y-6">
```

Keep the accent strip (entity identity), remove the separate border-b header, use `p-6 space-y-6` like GroupDetailPanel.

- [ ] **Step 3: Remove now-unused ENTITY_COLORS import if only used for ★**

After replacing the table, check if `ENTITY_COLORS` is still needed. The ★ is now handled by `SloObjectiveTable`'s cyan diamond `◆`.

- [ ] **Step 4: Run tests**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/details/SloDetailView.test.tsx`

- [ ] **Step 5: Commit**

```
fix(ui): replace custom objectives table with SloObjectiveTable, match Navigator layout
```

---

### Task 7: Create Dropdown — Match EvaluationActions Menu Pattern

**Files:**
- Modify: `ui/src/features/registry/RegistrySidebar.tsx` (lines 156-213)

The Create dropdown must match `EvaluationActions.tsx:126-171` exactly:
- `min-w-[280px] bg-popover border border-border rounded-xl shadow-xl py-2`
- Items: `flex items-start gap-3 px-3 py-2.5 hover:bg-accent`
- Accent bar: `w-[3px] rounded-full` with `height: 36px`
- Title: `text-[13px] font-medium text-popover-foreground`
- Description: `text-[11px] text-muted-foreground mt-0.5`

**Current (broken):** `rounded-lg shadow-lg py-1`, `w-1 h-4` dots, single-line `text-xs` labels.

- [ ] **Step 1: Add descriptions to items array**

```typescript
const items = [
  { type: 'slo' as const, label: 'New SLO', desc: 'Versioned quality gate definition', color: ENTITY_COLORS.slo },
  { type: 'sli' as const, label: 'New SLI Definition', desc: 'Service level indicator template', color: ENTITY_COLORS.sli },
  { type: 'datasource' as const, label: 'New Datasource', desc: 'Metric source connection', color: ENTITY_COLORS.ds },
  { type: 'group' as const, label: 'New Asset Group', desc: 'Group assets and bind SLOs', color: ENTITY_COLORS.group },
]
```

- [ ] **Step 2: Rewrite dropdown container and items to match EvaluationActions**

```typescript
{open && (
  <div
    className="absolute bottom-full mb-1 left-0 w-full min-w-[280px] bg-popover border border-border rounded-xl shadow-xl overflow-hidden py-2 z-50"
    style={{ fontFamily: SANS_SERIF }}
  >
    {items.map(item => (
      <button
        key={item.type}
        className="flex items-start gap-3 w-full text-left px-3 py-2.5 transition-colors hover:bg-accent group"
        onClick={() => {
          onCreateAction(item.type)
          setOpen(false)
        }}
      >
        <div
          className="w-[3px] rounded-full shrink-0 mt-0.5"
          style={{ backgroundColor: item.color, height: 36 }}
        />
        <div className="min-w-0">
          <div className="text-[13px] font-medium text-popover-foreground">{item.label}</div>
          <div className="text-[11px] text-muted-foreground mt-0.5">{item.desc}</div>
        </div>
      </button>
    ))}
  </div>
)}
```

- [ ] **Step 3: Commit**

```
fix(ui): match Create dropdown to EvaluationActions menu pattern
```

---

### Task 8: SLO Wizard — Fix Viewport Scroll + Visual Polish

**Files:**
- Modify: `ui/src/features/registry/forms/SloWizard.tsx`
- Modify: `ui/src/features/registry/forms/WizardStepIdentity.tsx`
- Modify: `ui/src/features/registry/forms/WizardStepPickSli.tsx`
- Modify: `ui/src/features/registry/forms/WizardStepIndicators.tsx`
- Modify: `ui/src/features/registry/forms/WizardStepComparison.tsx`

**Issues:**
1. **Scrollbar instead of viewport** — The wizard has `max-w-5xl` and `flex-1 overflow-y-auto` but the parent container doesn't give it enough height. The wizard renders inside `<div className="flex-1 overflow-y-auto">` in SloRegistryPage — this is correct, but the wizard's own `flex flex-col h-full` with inner `flex-1 overflow-y-auto` creates double scrollbars. Fix: remove the inner scroll container and let the wizard use the parent's scroll.
2. **Notes is `<Input>` not `<textarea>`** — should be multi-line
3. **No step badges** — add numbered circle badges
4. **Sections have no visual boundary** — wrap in cards matching `border border-slate-700 rounded-lg`

- [ ] **Step 1: Fix wizard viewport — remove double scroll**

In `SloWizard.tsx`, the current structure is:

```typescript
// BEFORE:
<div className="flex flex-col h-full bg-background" style={{ fontFamily: SANS_SERIF }}>
  <div className="h-[3px] shrink-0" ... />
  <div className="px-6 py-4 border-b border-border shrink-0">...</div>
  <div className="flex-1 overflow-y-auto px-6 py-6 space-y-8 max-w-5xl">
    {/* steps */}
  </div>
  <div className="shrink-0 flex justify-end ...">...</div>
</div>
```

Change to a flat scrollable layout — no flex-col/flex-1 nesting:

```typescript
// AFTER:
<div className="p-6 space-y-6" style={{ fontFamily: SANS_SERIF }}>
  {/* Header */}
  <div>
    <h1 className="text-xl font-semibold text-foreground">{title}</h1>
    {subtitle && <p className="text-sm text-muted-foreground mt-0.5">{subtitle}</p>}
  </div>

  {/* Steps in card wrappers */}
  <section className="border border-slate-700 rounded-lg p-5">
    <WizardStepIdentity ... />
  </section>

  {showStep2 && (
    <section className="border border-slate-700 rounded-lg p-5">
      <WizardStepPickSli ... />
    </section>
  )}

  {showStep3 && (
    <section className="border border-slate-700 rounded-lg p-5">
      <WizardStepIndicators ... />
    </section>
  )}

  {showStep4 && (
    <section className="border border-slate-700 rounded-lg p-5">
      <WizardStepComparison ... />
    </section>
  )}

  {/* Submit buttons — inline at bottom of scroll, not fixed */}
  <div className="flex justify-end gap-2 pt-2 border-t border-slate-700">
    {onClose && (
      <button onClick={onClose} className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:text-foreground transition-colors">
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
```

The parent `<div className="flex-1 overflow-y-auto">` in `SloRegistryPage` handles scrolling. The wizard just renders content that grows naturally.

- [ ] **Step 2: Fix notes field to textarea**

In `WizardStepIdentity.tsx`, replace the notes `<Input>`:

```typescript
// BEFORE:
<Input id="slo-notes" value={data.notes} onChange={(e) => update('notes', e.target.value)} placeholder="Optional notes" />

// AFTER:
<textarea
  id="slo-notes"
  className="flex w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
  rows={3}
  value={data.notes}
  onChange={(e) => update('notes', e.target.value)}
  placeholder="Optional notes about this SLO definition"
/>
```

- [ ] **Step 3: Add step number badges to headers**

In each `WizardStep*.tsx`, change the `<h3>` to include a badge:

```typescript
// Pattern for all four steps (change number and label):
<div className="flex items-center gap-2 mb-3">
  <span className="inline-flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-[10px] font-bold">1</span>
  <h3 className="text-sm font-semibold text-foreground">Identity</h3>
</div>
```

Note: use `text-sm font-semibold text-foreground` (Navigator section header pattern) instead of `text-xs uppercase text-muted-foreground tracking-wider`.

Step labels: `1 Identity`, `2 Pick SLI`, `3 Indicators & Criteria`, `4 Comparison & Scoring`

- [ ] **Step 4: Run tests**

Run: `./scripts/ui-test.sh --tail 15`

- [ ] **Step 5: Commit**

```
fix(ui): fix wizard viewport scroll, add step cards/badges, textarea notes
```

---

### Task 9: Group Creation Dialog — Use Proper Dialog Positioning

**Files:**
- Modify: `ui/src/pages/SloRegistryPage.tsx` (lines 201-247)

The group creation dialog uses a raw `div` overlay with manual positioning. Navigator uses shadcn `Dialog` component (`ui/src/components/ui/dialog.tsx`) which provides proper centering, backdrop blur, focus trapping, and escape-to-close. The current inline dialog appears in inconsistent positions.

- [ ] **Step 1: Replace raw overlay with shadcn Dialog**

```typescript
// Add imports:
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'

// Replace the groupDialogOpen block (lines 201-247):
<Dialog open={groupDialogOpen} onOpenChange={setGroupDialogOpen}>
  <DialogContent className="sm:max-w-sm">
    <div className="h-[3px] -mx-4 -mt-4 mb-0" style={{ backgroundColor: ENTITY_COLORS.group }} />
    <DialogHeader>
      <DialogTitle>New Asset Group</DialogTitle>
    </DialogHeader>
    <div>
      <label htmlFor="group-name" className="block text-xs text-muted-foreground mb-1">Name</label>
      <Input
        id="group-name"
        value={groupName}
        onChange={(e) => setGroupName(e.target.value)}
        placeholder="my-asset-group"
        onKeyDown={(e) => { if (e.key === 'Enter') handleGroupCreate() }}
      />
    </div>
    <DialogFooter>
      <Button size="xs" variant="outline" onClick={() => setGroupDialogOpen(false)}>Cancel</Button>
      <Button size="xs" disabled={!groupName.trim() || createGroup.isPending} onClick={handleGroupCreate}>
        {createGroup.isPending ? 'Creating…' : 'Create'}
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

- [ ] **Step 2: Commit**

```
fix(ui): use shadcn Dialog for group creation — proper centering and focus trap
```

---

## Execution Order

Tasks are sequential — each builds on the previous:

1. **Task 1** — Add `variables` to Asset type (prerequisite for Task 3)
2. **Task 2** — Tests for AssetBindingView (TDD)
3. **Task 3** — Implement AssetBindingView (make tests pass, using Navigator patterns)
4. **Task 4** — Linked Groups in SloDetailView + extract useAllGroupLinks hook + wire sidebar/detail panel
5. **Task 5** — TypeScript verification and visual review
6. **Task 6** — Replace SloDetailView custom table with SloObjectiveTable + Navigator layout
7. **Task 7** — Create dropdown matching EvaluationActions menu pattern
8. **Task 8** — SLO Wizard viewport scroll fix + visual polish
9. **Task 9** — Group creation dialog proper positioning

Tasks 6-9 are independent of each other and can run in parallel after Task 5.
