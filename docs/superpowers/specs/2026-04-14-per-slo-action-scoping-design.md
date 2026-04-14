# Per-SLO Action Scoping — Design

**Date:** 2026-04-14
**Status:** Design approved, pending implementation plan
**Area:** UI (`features/evaluations`, `features/navigator`) + small backend schema bump (`schemas/re_evaluation.py`)

## Problem

The Navigator's action UI (`EvaluationActionsButton` and the five action forms under `features/evaluations/components/actions/`) was built when an asset was assumed to have a single SLO. Multi-SLO assets break that assumption silently:

- `AssetPanel.tsx` derives one `effectiveEvalId` per column (`AssetPanel.tsx:97`). When nothing is explicitly selected, `defaultEvalId` picks "most recent non-invalidated row" — which is whichever SLO happens to sort first.
- All five action forms (`Override`, `Invalidate`, `Restore`, `BaselineForm`, `ReEvaluateForm`) receive this scalar `evalId` and act on one arbitrary SLO row per column.
- A recently-fixed notes bug had the same shape: annotations were being attached to the first SLO instead of the parent evaluation.
- The current action-form layout is inline below the column header, which pushes the NOTES section to a single line and shoves the heatmap off-screen — breaking the cross-reference the user needs while deciding what to act on.

The column already contains all the SLO rows (`heatmapData.groups[].cells`). The UI just never asks which ones the user wants to target, and the forms have no way to accept "several".

## Goals

1. Every destructive action (`Override`, `Invalidate`, `Restore`, `Baseline Pin`, `Re-run`) is explicitly scoped to a user-picked subset of SLO rows in the selected column.
2. The action form preserves the surrounding decision surface (heatmap + notes) while open — the user can cross-reference cells against the SLO picker without scrolling.
3. Direct manipulation is honored: clicking a specific SLO cell and hitting Actions scopes the form to that SLO by default.
4. Arriving via the column header (no specific cell) defaults the form to ALL SLO rows in the column.
5. The 25-SLO scale (some assets have many SLOs) does not break the picker UI — search, select all, clear all, scrollable list.
6. Backend changes are additive and small: the per-row endpoints stay untouched; only `ReEvaluateRequest` gains `slo_names: list[str] | None` for one-shot scoped re-runs.

## Non-goals

- Atomic ("all or nothing") multi-SLO actions. Fan-out is acceptable; partial failures are shown per-SLO and retryable. A future follow-up could add bulk endpoints if real usage demands transactional semantics.
- Bulk multi-column actions (selecting N days of the same SLO across the heatmap and flipping them in one action). The scope here is always one column.
- Cross-asset actions.
- Reworking how notes/annotations are attached. Notes stay column-scoped (parent `evaluation_id`) and are not part of the new picker pattern.
- End-to-end Playwright tests. Component-level Vitest coverage is sufficient; no E2E harness is stood up for tropek.

## Decisions summary

| # | Question | Decision |
|---|---|---|
| 1 | What set does the SLO picker show? | **A** — only SLO rows present in the selected column. No asset-wide or future-dated rows. |
| 2 | Where does the action form render? | **C** — anchored popover next to the Actions button. Preserves heatmap + notes visibility. |
| 2b | How is the 25-SLO picker shown inside the popover? | Modal overlay on top of the popover. The popover's `SloScopeField` opens the modal when clicked. |
| 3 | How does Override handle mixed current states? | **B** — single "Override result..." menu item; form contains a radio (`pass` / `warning` / `fail`) that applies uniformly to the selected subset. |
| 4 | How does the UI execute multi-SLO actions against the backend? | **C — Hybrid.** Per-row endpoints remain unchanged; UI fans out via `Promise.allSettled`. Re-run gets a new additive `slo_names: list[str] | None` schema field so a single async job covers a scoped subset. |
| 5 | What does "default ALL" mean when a specific cell is clicked? | **B** — click on an SLO-group cell defaults scope to that one SLO; click on the composite "Overall Score" row or the column/slot header defaults to ALL. A Reset button in the picker widens back to ALL in one click. |

## Architecture

The column-header Actions button currently opens an inline form that receives a single `evalId`. The new architecture introduces a **scoped action surface**: a popover container that owns a single piece of state — `selectedSloNames: Set<string>` — and injects it into whichever action form the user picks.

**What stays the same:**

- The five action endpoints (`PATCH /override-status`, `PATCH /invalidate`, `PATCH /restore`, `PATCH /baseline-pin`, and the existing `POST /re-evaluate` body shape for single-SLO calls).
- Each action form's internal layout (reason, author, radio buttons, date pickers).
- The `EvaluationActionsButton` → `EvaluationActionForm` routing pattern.
- Notes / annotations — they're column-scoped and outside this design's scope.

**What changes:**

- `EvaluationActions.tsx` — the smart `OVERRIDE_TO_PASS` / `OVERRIDE_TO_FAIL` branching collapses into a single "Override result..." menu entry. Radio in the form picks the target.
- Forms move from inline-below-header into an anchored popover (`ActionPopover`).
- All five forms gain a new `SloScopeField` component as their first field (read-only summary row with an "edit" button that opens the modal picker and a "reset" button).
- Each form's submit handler loops over `selectedSloNames`, maps them to `eval_id` values via the heatmap's column data, and fans out parallel fetches with `Promise.allSettled`, then shows a per-SLO result list.
- `ReEvaluateRequest` schema adds `slo_names: list[str] | None` (additive; `slo_name` retained for back-compat).
- `AssetPanel.tsx` stops collapsing the column to a single `effectiveEvalId` for action purposes — it exposes both `selectedColumnEvalId` and `selectedSingleSloEvalId` (the latter optional, set when a specific cell is clicked).

## Component design

Three new pieces plus edits to existing forms.

### `SloScopePicker` — shared hook + component trio

New directory `ui/src/features/evaluations/components/actions/slo-scope/`:

```
slo-scope/
├── SloScopeField.tsx     # compact summary row shown inside each action form
├── SloScopeModal.tsx     # full-screen modal with search + checklist
├── useSloScope.ts        # state + column-row derivation hook
└── types.ts              # SloScopeResult, SloScopeOption, filter enum
```

**`useSloScope(columnEvalId, initialMode, filter?)`**

- Derives the list of SLO rows for a column from `heatmapData.groups` (each group = one SLO; cells are keyed by `evaluation_id`).
- Returns `{ availableSlos, selected, setSelected, reset }`.
- `availableSlos: SloScopeOption[]` — each item has `sloName`, `displayName`, `sloEvaluationId`, `currentResult` (`pass` / `warning` / `fail` / `invalidated`).
- `initialMode: 'all' | { singleSlo: string }` — determines the default selection when the hook mounts.
- `filter: 'all' | 'invalidated-only' | 'not-invalidated'` — supports Invalidate (hides already-invalidated) and Restore (shows only invalidated).
- `reset()` always widens `selected` to every row in `availableSlos` (i.e. ALL), regardless of `initialMode`. The semantic is "I made a mistake, give me everything back" — not "go to the mode I started with".

**`SloScopeField`**

Small horizontal row inside each action form:

```
Applies to: 3 of 5 SLOs  [edit]  [reset]
```

Click `edit` → opens `SloScopeModal`. `reset` widens the selection to every row in `availableSlos` (ALL) without opening the modal, regardless of whether the form was initially scoped to one cell-click SLO. Takes `scope` and `onChange` props.

**`SloScopeModal`**

Opens on top of `ActionPopover` with a higher z-index. Contains:

- Search input at the top (filters by SLO display name or raw name).
- "Select all" / "Clear" buttons next to search.
- Scrollable flat checklist — each row shows SLO display name + a current-result badge (`pass` / `warning` / `fail` / `invalidated`) colored with the existing status palette.
- Footer: Cancel (discard) + Confirm (commit selection and close).

### `ActionPopover`

New container `ui/src/features/evaluations/components/ActionPopover.tsx`.

- Anchors to the Actions button DOM ref via a ref prop.
- Positions using floating-ui (already in the dep tree via shadcn/ui primitives) with standard offset + collision padding.
- Renders one of the five existing form components (`OverrideForm`, `InvalidateForm`, `RestoreForm`, `BaselineForm`, `ReEvaluateForm`) based on `activeAction`.
- Click-outside dismisses unless `SloScopeModal` is open (z-index + event-stop interaction).
- `ESC` closes.
- Takes `scope` as a prop (created via `useSloScope` in `AssetPanel` and lifted down).

### Existing form edits

Each `*Form.tsx` under `components/actions/`:

- Replaces the `evaluationId: string` prop with `scope: SloScopeResult` + `columnEvalId: string`.
- First field in the form body is `<SloScopeField scope={scope} onChange={...} />`.
- Submit handler changes shape:

```ts
const targets = [...scope.selected].map(sloName => ({
  sloName,
  evalId: scope.lookupEvalId(sloName),
}))
const results = await Promise.allSettled(
  targets.map(t => mutation({ evalId: t.evalId, ...formFields })),
)
```

- Result view (post-submit) shows a per-SLO success/failure list: green row for successes, red row with error message for failures, summary header (`"3 succeeded · 2 failed · 0 skipped"`), and a single "Retry failed" button that re-opens the form with scope narrowed to the failed subset.

The `slo_name → slo_evaluation_id` lookup lives in `useSloScope` so no form re-derives it. Column rows are already in `heatmapData.groups[].cells`.

### Not extracted: `useFanOut`

Each form's mutation has different shape (override takes `new_result`+`reason`+`author`, invalidate takes `note`, re-run takes a whole different endpoint). A generic fan-out hook would grow awkward. Accept the 5× light duplication; the fan-out loop is ~6 lines per form.

## Data flow walkthrough

Concrete scenario: user clicks a red `latency-slo` cell at day-7, hits Actions → Override result → picks Fail → Confirm.

1. **Cell click → AssetPanel state.** `AssetHeatmap`'s cell click sets `selectedSlot: { columnEvalId, periodStart, sloEvaluationId }`. `AssetPanel` now exposes both `selectedColumnEvalId` and `selectedSingleSloEvalId` (the clicked cell or `undefined` if only the slot header was selected).

2. **Actions button → ActionPopover.** Button click mounts `<ActionPopover anchorRef columnEvalId singleSloEvalId onClose />`. Popover opens with `activeAction: null` and shows the action menu. Scope is derived at mount:

   ```ts
   const initialMode = singleSloEvalId
     ? { singleSlo: sloNameFor(singleSloEvalId) }
     : 'all'
   const scope = useSloScope(columnEvalId, initialMode)
   ```

   `scope.selected` is a `Set<string>` of SLO names. It persists across action switches within the same popover lifetime — if the user picks Override, cancels, and picks Invalidate, the picker keeps the same 1 SLO.

3. **Form renders.** `OverrideForm` receives `{ scope, columnEvalId, onClose }`. First field: `<SloScopeField />` showing "1 of 5 SLOs". User leaves selection alone, picks radio `fail`, fills reason, clicks Confirm.

   Special case: if the click landed on the composite "Overall Score" row rather than a specific SLO-group row, `singleSloEvalId` is `undefined` and `initialMode` falls back to `'all'` — the overall row is not a single-SLO affordance.

4. **Fan-out submit.**

   ```ts
   const targets = [...scope.selected].map(sloName => ({
     sloName,
     evalId: scope.lookupEvalId(sloName),
   }))
   const results = await Promise.allSettled(
     targets.map(t => overrideStatusMutation({
       evalId: t.evalId,
       new_result: 'fail',
       reason,
       author,
     })),
   )
   ```

   For our scenario, `targets.length === 1` — one PATCH fires. Result view shows a one-row success list.

5. **Result aggregation + cache invalidation.** After `allSettled`, the form renders the per-SLO result list. On any success, a shared helper `invalidateColumnQueries(queryClient, columnEvalId)` invalidates:

   - `['evaluation', evalId]` for each successful `evalId`
   - `['asset-evaluations', assetName]`
   - `['metric-heatmap', assetName, selectedNames]`

   The heatmap re-renders with updated cell colors; any open evaluation detail view re-fetches.

6. **Dismissal.** User closes the result view → popover unmounts → `AssetPanel` state idles. No leaked selection.

**Key invariants:**

- `useSloScope` is the only place that knows how to map `sloName → sloEvaluationId` for a given column.
- Form-level mutation hooks are unchanged — the form just wraps them in a `Promise.allSettled`.
- Popover holds no mutation state directly; it's a positioning + routing container.
- Column cache invalidation goes through one shared helper so all forms stay consistent.

## Backend contract

Almost nothing changes. One additive schema field.

### Unchanged endpoints

- `PATCH /evaluations/{eval_id}/override-status`
- `PATCH /evaluations/{eval_id}/invalidate`
- `PATCH /evaluations/{eval_id}/restore`
- `PATCH /evaluations/{eval_id}/baseline-pin`

Same request bodies, same responses, same audit-log behavior. The popover fires N of these in parallel and aggregates client-side.

### Changed: `POST /evaluations/re-evaluate`

Current `ReEvaluateRequest` (`api/tropek/modules/quality_gate/schemas/re_evaluation.py:14`):

```python
asset_name: str
slo_name: str | None = None   # None = all SLOs on asset
```

New:

```python
asset_name: str
slo_name: str | None = None         # kept for back-compat
slo_names: list[str] | None = None  # new — explicit subset scoping
```

Rules:

- `slo_name` and `slo_names` are mutually exclusive. Sending both → 422 validation error.
- Empty `slo_names: []` → 422 validation error (no silent no-op).
- The UI always sends `slo_names` going forward. `slo_name` remains only for mock fixtures, specs, and possible external callers. Removing it is a later chore.

Resolution logic in `re_evaluate_service.py` filters the asset's assigned SLOs to the list before dispatching scoring. One async job runs for the full scoped subset, not N separate jobs — that's the whole reason the schema change exists rather than fan-out for re-run.

## Per-form specifics and edge cases

### `OverrideForm`

- Radio replaces the current pass/fail title branching. Target values: `pass`, `warning`, `fail`.
- No-op filter at submit: skip SLOs whose current result already equals the target. Result list shows `"2 skipped (already pass)"` so users see the intent wasn't silently dropped.
- Reason and author fields apply uniformly across the fanned-out calls.

### `InvalidateForm`

- `useSloScope` filter: `not-invalidated`. Already-invalidated rows are hidden from `availableSlos` because re-invalidating is a no-op.
- One shared `note` fans out to all selected rows.

### `RestoreForm`

- `useSloScope` filter: `invalidated-only`. Only invalidated rows appear.
- When the column has zero invalidated rows, the Restore menu item is disabled with a tooltip (`"no invalidated SLOs in this column"`).

### Menu-item availability rules (shared)

The Actions menu hides or disables entries when the current column state makes them no-ops:

- **Invalidate** — disabled if every row in the column is already invalidated (no work to do). Tooltip: `"all SLOs in this column are already invalidated"`.
- **Restore** — disabled if no row is invalidated. Tooltip as above.
- **Override** — always enabled; mixed-state columns are the whole point.
- **Baseline Pin** — always enabled.
- **Re-run** — always enabled.

When a specific cell is clicked and that cell's state is incompatible with an action's filter (e.g. click an already-invalidated cell, pick Invalidate), the form falls back to `initialMode: 'all'` so the single-SLO default doesn't silently become an empty selection. The user explicitly re-picks if they want a subset.

### `BaselineForm`

- Baseline pins are per-asset-per-SLO; pinning N SLOs creates N independent pins. Semantically sound — each pin resets its own SLO's baseline window.
- One shared `reason`, one shared `author`.
- Pin conflicts surface as 409s with conflict info. Result list shows `pinned ✓` / `conflict: previous pin at 2026-04-01` per SLO. Retry affordance narrows scope to the conflicted subset and re-opens the form.
- When scope > 5, the Confirm button adds a count indicator: `"This will create N baseline pins"`. Not a dialog — just inline text. Keeps the warning visible without adding a second confirm step.

### `ReEvaluateForm`

- Uses the new `slo_names: list[str]` field. Single HTTP call regardless of scope size.
- Scope picker doesn't filter — any row that exists can be re-run.
- `fromBaseline` and `fromDate` UI remains unchanged.

### Notes / annotations

Stay column-scoped (parent `evaluation_id`). The "Add Note" menu entry remains at the top of the Actions menu as it is today. Not part of the new picker pattern.

### Partial-failure UX (shared across forms)

- Result list uses the same visual as the existing `ReEvaluateForm` per-period list.
- Green row: SLO name + new outcome.
- Red row: SLO name + error message.
- Summary header: `"3 succeeded · 2 failed · 0 skipped"`.
- Single "Retry failed" button at the bottom re-opens the form with scope narrowed to the failed subset.

## Testing plan

### UI component tests (Vitest + React Testing Library + happy-dom)

**`useSloScope.test.ts`**

- Derives SLO list correctly from heatmap column data.
- `initialMode: 'all'` selects every SLO in the column.
- `initialMode: { singleSlo }` selects only that SLO.
- `reset()` returns selection to initial mode.
- `filter: 'invalidated-only'` and `'not-invalidated'` filter `availableSlos`.

**`SloScopeField.test.tsx`**

- Renders "N of M SLOs" summary correctly.
- Click on summary opens the modal.
- Reset button clears and does not open the modal.

**`SloScopeModal.test.tsx`**

- Search filters the list.
- Select all / Clear all buttons work.
- Per-row current-result badge renders for all states.
- Confirm commits selection; Cancel discards.

**`ActionPopover.test.tsx`**

- Renders the selected action form with scope injected.
- `ESC` closes.
- Outside click closes — but not when `SloScopeModal` is open (z-index interaction).
- Result list appears after fan-out completes.

**`OverrideForm.test.tsx` (update existing)**

- Radio selects target state.
- Fan-out fires N mutations for N-SLO scope.
- Already-at-target SLOs are skipped and shown as such in the result list.
- Partial failure surfaces the "Retry failed" button.

**Minimal update tests** for `InvalidateForm`, `RestoreForm`, `BaselineForm`, `ReEvaluateForm` covering the same shape (scope + fan-out + result list + form-specific quirks).

**`AssetPanel.test.tsx` (update existing)**

- Cell click → Actions opens popover with single-SLO default.
- Column/slot click without cell → Actions opens popover with ALL default.

### Backend tests (pytest)

**`test_re_evaluation.py` (update)**

- `slo_names=[a, b]` filters scoring to only those two SLOs.
- `slo_name` + `slo_names` both set → 422 validation error.
- Empty `slo_names: []` → 422 validation error.

No new backend tests for `override`, `invalidate`, `restore`, `baseline-pin` — they're unchanged.

### Explicitly not tested (YAGNI)

- End-to-end Playwright flow — no E2E harness exists in tropek; Vitest coverage is sufficient.
- Bulk-endpoint atomicity — we're not building bulk endpoints.
- 25-SLO fan-out load test — 25 parallel PATCHes is well within normal browser + HTTP throughput.

## Follow-ups (out of scope here)

- Bulk backend endpoints (`POST /evaluations/bulk/*`) if transactional semantics ever bite us in real usage.
- Cross-column multi-select (acting on multiple days of the same SLO at once).
- Removing the deprecated `slo_name` field from `ReEvaluateRequest` after all callers migrate.
- Smarter Baseline Pin default (single-SLO rather than ALL) if users complain about the 25-pin footgun despite the inline count warning.
- Audit of other `ev.id` consumers outside the action forms — the notes bug and these action forms are the known offenders, but a quick grep should confirm nothing else silently picks the first SLO.
