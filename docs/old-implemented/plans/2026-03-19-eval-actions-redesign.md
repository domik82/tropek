# Evaluation Actions Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the EvaluationActions dropdown button and inline action forms to match the Penpot "Actions Redesign Proposal" — compact right-aligned cards with accent strips, two-line dropdown menu items, theme-aware button, and inline re-evaluation (no modal).

**Architecture:** The existing `EvaluationActions.tsx` (button + form) and `ReEvaluateModal.tsx` are replaced by three focused components: a dropdown button, a dropdown menu, and an action form. The form handles all four action types inline (no modal). The re-evaluate form has different fields (checkbox + date) vs the other three (reason + author). Color identity moves from tinted backgrounds to neutral cards with colored accent strips, titles, and confirm buttons. The Actions button uses `--primary` (theme-aware) instead of hardcoded gray.

**Tech Stack:** React 18, TypeScript, Tailwind CSS v4, lucide-react icons, existing React Query mutation hooks.

**Penpot reference:** Board "Actions Redesign Proposal" on page "TROPEK — Eval Detail".

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/features/evaluations/components/EvaluationActions.tsx` | **Rewrite** | All three sub-components: `EvaluationActionsButton`, `EvaluationActionsMenu`, `EvaluationActionForm` |
| `src/features/evaluations/components/ReEvaluateModal.tsx` | **Delete** | Replaced by inline re-evaluate form inside `EvaluationActionForm` |
| `src/pages/EvaluationDetailPage.tsx` | **Modify (lines 10-12, 142-158)** | Remove `ReEvaluateModal` import, unify action form rendering (no special case for `re-evaluate`) |
| `src/features/navigator/components/AssetPanel.tsx` | **Modify (lines 13, 159-174)** | Same changes as EvaluationDetailPage — remove `ReEvaluateModal`, unify rendering |

No new files. No hook/API/type changes needed — all existing mutations and types are reused as-is.

---

## Task 1: Rewrite EvaluationActions — Action Definitions

**Files:**
- Modify: `src/features/evaluations/components/EvaluationActions.tsx:1-92`

The current `ActionDef` interface has 10 color fields (`borderColor`, `bgColor`, `confirmBg`, `confirmHoverBg`, `dotColor`, `textColor`, `focusBorder`). The redesign simplifies to 3: `accentColor` (hex for the accent strip, title, and confirm button), `accentTailwind` (Tailwind class prefix like `red` for confirm button hover), and keeps `kind`, `label`, `description`.

- [ ] **Step 1: Rewrite ActionDef and action constants**

Replace the entire top section (lines 1–92) with:

```tsx
import { useState, useEffect, useRef, useCallback } from 'react'
import { MoreVertical } from 'lucide-react'
import { useInvalidateEvaluation, useOverrideStatus, usePinBaseline, useReEvaluate } from '../hooks'
import type { ReEvaluateResponse } from '../types'

export type ActionKind = 'invalidate' | 'override' | 'baseline' | 're-evaluate'

interface ActionDef {
  kind: ActionKind
  label: string
  description: string
  accentColor: string        // hex — used for accent strip, title text, confirm bg
  accentBorder: string       // Tailwind border class for card outline
  accentText: string         // Tailwind text class for title
  confirmClasses: string     // Tailwind classes for confirm button bg + hover
}

const INVALIDATE: ActionDef = {
  kind: 'invalidate',
  label: 'Invalidate',
  description: 'Discard this evaluation — it will not be used for scoring or baselines.',
  accentColor: '#8B949E',
  accentBorder: 'border-slate-500/25',
  accentText: 'text-slate-400',
  confirmClasses: 'bg-slate-500 hover:bg-slate-400',
}

const OVERRIDE_TO_PASS: ActionDef = {
  kind: 'override',
  label: 'Mark as Successful',
  description: 'Override the failed result — SLOs false-flagged this evaluation.',
  accentColor: '#22C55E',
  accentBorder: 'border-green-500/25',
  accentText: 'text-green-400',
  confirmClasses: 'bg-green-600 hover:bg-green-500',
}

const OVERRIDE_TO_FAIL: ActionDef = {
  kind: 'override',
  label: 'Mark as Failure',
  description: 'Override the passed result — SLOs missed an issue in this evaluation.',
  accentColor: '#F85149',
  accentBorder: 'border-red-500/25',
  accentText: 'text-red-400',
  confirmClasses: 'bg-red-600 hover:bg-red-500',
}

const BASELINE: ActionDef = {
  kind: 'baseline',
  label: 'Pin Baseline',
  description: 'Set this evaluation as the new baseline — future comparisons start from here.',
  accentColor: '#58A6FF',
  accentBorder: 'border-blue-500/25',
  accentText: 'text-blue-400',
  confirmClasses: 'bg-blue-600 hover:bg-blue-500',
}

const RE_EVALUATE: ActionDef = {
  kind: 're-evaluate',
  label: 'Run Evaluations',
  description: 'Re-score all evaluations from stored data with current SLO thresholds.',
  accentColor: '#A371F7',
  accentBorder: 'border-purple-500/25',
  accentText: 'text-purple-400',
  confirmClasses: 'bg-purple-600 hover:bg-purple-500',
}

function getActions(currentResult: string): ActionDef[] {
  return [
    INVALIDATE,
    currentResult === 'pass' ? OVERRIDE_TO_FAIL : OVERRIDE_TO_PASS,
    BASELINE,
    RE_EVALUATE,
  ]
}
```

- [ ] **Step 2: Verify file saves without syntax errors**

Run: `npx tsc --noEmit --pretty 2>&1 | head -20` from `ui/` directory.
Expected: Errors about missing `EvaluationActionsButton` and `EvaluationActionForm` exports (because we haven't written them yet). No syntax errors on the new code.

- [ ] **Step 3: Commit**

```
feat(ui): rewrite EvaluationActions action definitions — simplified color scheme
```

---

## Task 2: Rewrite EvaluationActionsButton — Theme-Aware Primary Button

**Files:**
- Modify: `src/features/evaluations/components/EvaluationActions.tsx` (append after action defs)

The button uses `--primary` color (CSS var from the theme system) instead of hardcoded gray. It shows a `MoreVertical` (kebab) icon from lucide-react plus "Actions" text. The dropdown menu is a separate visual block with left accent bars and two-line items.

- [ ] **Step 1: Write EvaluationActionsButton**

Append after `getActions()`:

```tsx
interface ButtonProps {
  currentResult: string
  invalidated: boolean
  activeAction: ActionKind | null
  onSelectAction: (kind: ActionKind) => void
}

export function EvaluationActionsButton({ currentResult, invalidated, activeAction, onSelectAction }: ButtonProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [menuOpen])

  if (invalidated) {
    return <span className="text-xs text-muted-foreground italic">invalidated</span>
  }

  const actions = getActions(currentResult)

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setMenuOpen(v => !v)}
        className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors ${
          activeAction
            ? 'bg-primary/15 border-primary/40 text-primary'
            : 'bg-primary/10 border-primary/30 text-primary hover:bg-primary/20'
        }`}
      >
        <MoreVertical className="w-3.5 h-3.5" />
        Actions
      </button>

      {menuOpen && (
        <div className="absolute right-0 top-full mt-1 z-20 min-w-[280px] bg-popover border border-border rounded-xl shadow-xl overflow-hidden py-2">
          {actions.map(action => (
            <button
              key={action.kind}
              onClick={() => { onSelectAction(action.kind); setMenuOpen(false) }}
              className="flex items-start gap-3 w-full text-left px-3 py-2.5 transition-colors hover:bg-accent group"
            >
              <div
                className="w-[3px] rounded-full shrink-0 mt-0.5"
                style={{ backgroundColor: action.accentColor, height: 36 }}
              />
              <div className="min-w-0">
                <div className={`text-[13px] font-medium text-popover-foreground`}>
                  {action.label}
                </div>
                <div className="text-[11px] text-muted-foreground mt-0.5">
                  {action.description}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `npx tsc --noEmit --pretty 2>&1 | head -20` from `ui/`.
Expected: Only errors about missing `EvaluationActionForm` export. Button should compile clean.

- [ ] **Step 3: Commit**

```
feat(ui): rewrite EvaluationActionsButton — theme-aware primary color, accent bar menu
```

---

## Task 3: Rewrite EvaluationActionForm — Unified Inline Form

**Files:**
- Modify: `src/features/evaluations/components/EvaluationActions.tsx` (append after button)

This is the biggest change. The form now handles ALL four action types inline (including re-evaluate, which was a modal). Two form layouts:
- **reason+author** layout: for `override`, `baseline` (invalidate shows reason only — the API takes only `note`, not `author`)
- **checkbox+date** layout: for `re-evaluate`

Both layouts share the same card chrome: neutral bg, colored top accent strip, colored title, colored confirm button.

The re-evaluate form needs `assetName` and `sloName` props (previously passed to the modal). The form also shows results after a successful re-evaluation.

- [ ] **Step 1: Write the unified EvaluationActionForm**

Append after `EvaluationActionsButton`:

```tsx
interface FormProps {
  evalId: string
  currentResult: string
  activeAction: ActionKind
  onClose: () => void
  /** Required for re-evaluate action */
  assetName?: string
  sloName?: string
  defaultFromDate?: string
}

export function EvaluationActionForm({
  evalId, currentResult, activeAction, onClose,
  assetName, sloName, defaultFromDate,
}: FormProps) {
  const [reason, setReason] = useState('')
  const [author, setAuthor] = useState('')
  const [fromDate, setFromDate] = useState(defaultFromDate ?? '')
  const [fromBaseline, setFromBaseline] = useState(false)
  const [reEvalResult, setReEvalResult] = useState<ReEvaluateResponse | null>(null)

  const invalidate = useInvalidateEvaluation(evalId)
  const override = useOverrideStatus(evalId)
  const baseline = usePinBaseline(evalId)
  const reEvaluate = useReEvaluate()

  const isPending = invalidate.isPending || override.isPending || baseline.isPending || reEvaluate.isPending
  const isReEval = activeAction === 're-evaluate'
  const actions = getActions(currentResult)
  const actionDef = actions.find(a => a.kind === activeAction)!

  const handleConfirm = useCallback(() => {
    const onSuccess = () => onClose()

    if (activeAction === 'invalidate') {
      if (!reason.trim()) return
      invalidate.mutate(reason, { onSuccess })
    } else if (activeAction === 'override') {
      if (!reason.trim() || !author.trim()) return
      const newResult = currentResult === 'pass' ? 'fail' : 'pass'
      override.mutate({ new_result: newResult, reason, author }, { onSuccess })
    } else if (activeAction === 'baseline') {
      if (!reason.trim() || !author.trim()) return
      baseline.mutate({ reason, author }, { onSuccess })
    } else if (activeAction === 're-evaluate') {
      if (!fromBaseline && !fromDate) return
      reEvaluate.mutate(
        {
          asset_name: assetName ?? '',
          slo_name: sloName ?? '',
          ...(fromBaseline ? { from_baseline: true } : { from_date: new Date(fromDate).toISOString() }),
        },
        { onSuccess: (data) => setReEvalResult(data) }
      )
    }
  }, [activeAction, reason, author, currentResult, fromBaseline, fromDate, assetName, sloName,
      invalidate, override, baseline, reEvaluate, onClose])

  const needsAuthor = activeAction === 'override' || activeAction === 'baseline'
  const canConfirm = isReEval
    ? (fromBaseline || !!fromDate)
    : (!!reason.trim() && (!needsAuthor || !!author.trim()))

  return (
    <div className="flex justify-end">
      <div className={`w-full max-w-md border ${actionDef.accentBorder} rounded-xl bg-popover overflow-hidden`}>
        {/* Accent strip */}
        <div className="h-[3px]" style={{ backgroundColor: actionDef.accentColor, opacity: 0.7 }} />

        <div className="p-4 space-y-3">
          {/* Title + description */}
          <div>
            <p className={`text-sm font-medium ${actionDef.accentText}`}>
              {actionDef.label}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">{actionDef.description}</p>
          </div>

          {/* Re-evaluate results view */}
          {isReEval && reEvalResult && (
            <div className="space-y-2">
              <p className="text-sm text-foreground">
                {reEvalResult.affected_evaluations} evaluation{reEvalResult.affected_evaluations !== 1 ? 's' : ''}{' '}
                re-evaluated (SLO v{reEvalResult.slo_version_used})
              </p>
              <div className="max-h-48 overflow-y-auto space-y-1">
                {reEvalResult.results.map((r) => (
                  <div key={r.id} className="flex items-center justify-between text-xs px-3 py-1.5 bg-muted/50 rounded">
                    <span className="text-muted-foreground">
                      {new Date(r.period_start).toLocaleDateString()}
                    </span>
                    <span>
                      <span className="text-muted-foreground">{r.old_result}</span>
                      <span className="text-muted-foreground/60 mx-1">→</span>
                      <span className={
                        r.new_result === 'pass' ? 'text-pass'
                          : r.new_result === 'warning' ? 'text-warning'
                            : 'text-fail'
                      }>
                        {r.new_result}
                      </span>
                    </span>
                    <span className="text-muted-foreground">
                      {r.old_score.toFixed(1)} → {r.new_score.toFixed(1)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex justify-end">
                <button
                  onClick={onClose}
                  className="px-3 py-1.5 text-xs rounded-md border border-border text-muted-foreground hover:text-foreground transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          )}

          {/* Re-evaluate input form (checkbox + date) */}
          {isReEval && !reEvalResult && (
            <div className="space-y-3">
              {reEvaluate.isError && (
                <p className="text-xs text-fail bg-fail/10 border border-fail/20 rounded px-3 py-2">
                  {reEvaluate.error instanceof Error ? reEvaluate.error.message : 'Request failed'}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                Re-score <span className="text-foreground">{assetName}</span>{' '}
                with SLO <span className="text-foreground">{sloName}</span>
              </p>
              <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={fromBaseline}
                  onChange={(e) => setFromBaseline(e.target.checked)}
                  className="rounded border-border accent-purple-500"
                />
                Run from last baseline
              </label>
              {!fromBaseline && (
                <div>
                  <label className="block text-xs text-muted-foreground mb-1">Start date</label>
                  <input
                    type="datetime-local"
                    value={fromDate}
                    onChange={(e) => setFromDate(e.target.value)}
                    className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground focus:outline-none focus:border-purple-500"
                  />
                </div>
              )}
            </div>
          )}

          {/* Reason + author form (invalidate shows reason only; override/baseline show both) */}
          {!isReEval && (
            <>
              <input
                value={reason}
                onChange={e => setReason(e.target.value)}
                placeholder="Reason…"
                className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none"
              />
              {needsAuthor && (
                <input
                  value={author}
                  onChange={e => setAuthor(e.target.value)}
                  placeholder="Author"
                  className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none"
                />
              )}
            </>
          )}

          {/* Buttons (hidden when showing re-eval results) */}
          {!(isReEval && reEvalResult) && (
            <div className="flex gap-2 justify-end">
              <button
                onClick={onClose}
                className="px-3 py-1.5 text-xs rounded-md border border-border text-muted-foreground hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                disabled={!canConfirm || isPending}
                className={`px-3 py-1.5 text-xs font-medium rounded-md text-white ${actionDef.confirmClasses} disabled:opacity-40 disabled:cursor-not-allowed transition-colors`}
              >
                {isPending
                  ? 'Saving…'
                  : isReEval
                    ? '▶ Run'
                    : 'Confirm'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles clean**

Run: `npx tsc --noEmit --pretty 2>&1 | head -20` from `ui/`.
Expected: No errors in `EvaluationActions.tsx`. May still have errors in `EvaluationDetailPage.tsx` referencing old `ReEvaluateModal`.

- [ ] **Step 3: Commit**

```
feat(ui): rewrite EvaluationActionForm — unified inline form for all action types
```

---

## Task 4: Update EvaluationDetailPage — Remove Modal, Unify Rendering

**Files:**
- Modify: `src/pages/EvaluationDetailPage.tsx:1-12, 142-158`

Remove the `ReEvaluateModal` import. Remove the special-case rendering for `re-evaluate` vs other actions. Replace with a single `EvaluationActionForm` that handles all action types. Pass `assetName`, `sloName`, and `defaultFromDate` props (needed by re-evaluate).

- [ ] **Step 1: Update imports (lines 10-12)**

Replace:
```tsx
import { EvaluationActionsButton, EvaluationActionForm } from '@/features/evaluations/components/EvaluationActions'
import { ReEvaluateModal } from '@/features/evaluations/components/ReEvaluateModal'
import type { ActionKind } from '@/features/evaluations/components/EvaluationActions'
```

With:
```tsx
import { EvaluationActionsButton, EvaluationActionForm, type ActionKind } from '@/features/evaluations/components/EvaluationActions'
```

- [ ] **Step 2: Unify action form rendering (lines 142-158)**

Replace:
```tsx
{/* Action form */}
{activeAction === 're-evaluate' && (
  <ReEvaluateModal
    assetName={ev.asset_snapshot.name}
    sloName={ev.slo_name ?? ''}
    defaultFromDate={ev.period_start.slice(0, 16)}
    onClose={() => setActiveAction(null)}
  />
)}
{activeAction && activeAction !== 're-evaluate' && !ev.invalidated && (
  <EvaluationActionForm
    evalId={id!}
    currentResult={ev.result}
    activeAction={activeAction}
    onClose={() => setActiveAction(null)}
  />
)}
```

With:
```tsx
{/* Action form — button guard already prevents selection when invalidated,
    but we also guard here for safety */}
{activeAction && !ev.invalidated && (
  <EvaluationActionForm
    evalId={id!}
    currentResult={ev.result}
    activeAction={activeAction}
    onClose={() => setActiveAction(null)}
    assetName={ev.asset_snapshot.name}
    sloName={ev.slo_name ?? ''}
    defaultFromDate={ev.period_start.slice(0, 16)}
  />
)}
```

- [ ] **Step 3: Verify TypeScript compiles clean**

Run: `npx tsc --noEmit --pretty 2>&1 | head -20` from `ui/`.
Expected: No errors.

- [ ] **Step 4: Commit**

```
feat(ui): unify action form rendering — remove ReEvaluateModal, single inline form
```

---

## Task 5: Update AssetPanel — Same Changes as EvaluationDetailPage

**Files:**
- Modify: `src/features/navigator/components/AssetPanel.tsx:13-14, 159-174`

`AssetPanel.tsx` also imports `ReEvaluateModal` and has the same dual-rendering pattern. Apply the same changes.

- [ ] **Step 1: Update imports (line 13-14)**

Replace:
```tsx
import { ReEvaluateModal } from '@/features/evaluations/components/ReEvaluateModal'
import type { ActionKind } from '@/features/evaluations/components/EvaluationActions'
```

With:
```tsx
import { EvaluationActionsButton, EvaluationActionForm, type ActionKind } from '@/features/evaluations/components/EvaluationActions'
```

Note: `EvaluationActionsButton` and `EvaluationActionForm` are already imported on line 12; merge the `type ActionKind` into that import and delete line 13-14. The result should be a single import:
```tsx
import { EvaluationActionsButton, EvaluationActionForm, type ActionKind } from '@/features/evaluations/components/EvaluationActions'
```

- [ ] **Step 2: Unify action form rendering (lines 158-174)**

Replace:
```tsx
{/* Action form */}
{activeAction === 're-evaluate' && ev && (
  <ReEvaluateModal
    assetName={assetName}
    sloName={ev.slo_name ?? ''}
    defaultFromDate={earliestPeriodStart?.slice(0, 16)}
    onClose={() => setActiveAction(null)}
  />
)}
{activeAction && activeAction !== 're-evaluate' && effectiveEvalId && ev && !ev.invalidated && (
  <EvaluationActionForm
    evalId={effectiveEvalId}
    currentResult={ev.result}
    activeAction={activeAction}
    onClose={() => setActiveAction(null)}
  />
)}
```

With:
```tsx
{/* Action form */}
{activeAction && effectiveEvalId && ev && !ev.invalidated && (
  <EvaluationActionForm
    evalId={effectiveEvalId}
    currentResult={ev.result}
    activeAction={activeAction}
    onClose={() => setActiveAction(null)}
    assetName={assetName}
    sloName={ev.slo_name ?? ''}
    defaultFromDate={earliestPeriodStart?.slice(0, 16)}
  />
)}
```

- [ ] **Step 3: Verify TypeScript compiles clean**

Run: `npx tsc --noEmit --pretty 2>&1 | head -20` from `ui/`.
Expected: No errors.

- [ ] **Step 4: Commit**

```
feat(ui): update AssetPanel — remove ReEvaluateModal, use unified inline form
```

---

## Task 6: Delete ReEvaluateModal

**Files:**
- Delete: `src/features/evaluations/components/ReEvaluateModal.tsx`

- [ ] **Step 1: Check for other imports of ReEvaluateModal**

Run: `grep -r "ReEvaluateModal" src/` from `ui/`.
Expected: Only the file itself. Both `EvaluationDetailPage.tsx` (Task 4) and `AssetPanel.tsx` (Task 5) imports were already removed.

- [ ] **Step 2: Delete the file**

```bash
rm src/features/evaluations/components/ReEvaluateModal.tsx
```

- [ ] **Step 3: Verify TypeScript compiles clean**

Run: `npx tsc --noEmit --pretty 2>&1 | head -20` from `ui/`.
Expected: No errors.

- [ ] **Step 4: Commit**

```
refactor(ui): delete ReEvaluateModal — replaced by inline EvaluationActionForm
```

---

## Task 7: Visual Verification

**Files:** None (manual testing)

- [ ] **Step 1: Start the dev server**

Run: `npx vite --host` from `ui/`.

- [ ] **Step 2: Navigate to an evaluation detail page**

Open `http://localhost:5173/navigator`, click an asset, click an evaluation.

- [ ] **Step 3: Verify the Actions button**

Check:
- Button text shows "Actions" with kebab icon (⋮)
- Button uses primary color (green on forest theme, light on current theme)
- Clicking opens dropdown menu

- [ ] **Step 4: Verify the dropdown menu**

Check:
- Four items with left accent bars (gray, red, blue, purple)
- Each item has two lines: label + description
- Clicking an item closes the menu and opens the form

- [ ] **Step 5: Verify override forms (Invalidate, Mark as Failure, Pin Baseline)**

Check:
- Form appears right-aligned below the header
- Neutral card background (no tinted bg)
- Colored accent strip at top (3px)
- Title text in action color
- Single-line inputs for Reason and Author (not a textarea)
- Confirm button in action color
- Cancel closes the form
- Confirm fires the mutation and closes on success

- [ ] **Step 6: Verify Run Evaluations form**

Check:
- Inline card (NOT a modal overlay)
- Checkbox: "Run from last baseline"
- When checkbox checked, date input hidden
- When checkbox unchecked, date input visible
- "▶ Run" button in purple
- After success, shows results table with old→new result/score
- Close button dismisses results

- [ ] **Step 7: Verify invalidated evaluations**

Check:
- Button shows "invalidated" text (italic, muted)
- No dropdown
- No action form visible

- [ ] **Step 8: Commit if any fixes were needed**

```
fix(ui): polish evaluation actions redesign
```
