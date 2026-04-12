# Column-Level Note Indicators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drive note-indicator icons in the Navigator AssetPanel heatmap from a backend-supplied per-column `has_notes` boolean instead of from the (paginated and lossy) eval-list.

**Architecture:** Notes are conceptually attached to a parent `EvaluationRun` (one column = one run). Annotations live on `evaluation_annotations.slo_evaluation_id`. The grouped heatmap response gets a new `EvaluationColumn.has_notes` field, populated by a single `DISTINCT` query that joins `slo_evaluations → evaluation_annotations` and filters out hidden ones. The frontend stops deriving `notedSlots` from the eval list and instead reads `has_notes` directly from the heatmap columns. Tooltip content stays lazy-loaded via the existing `column-annotations` endpoint.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Pydantic v2, React 19, React Query, TypeScript.

**Out of scope (explicitly):**
- The `EvaluationHeatmap` group view (`ui/src/features/evaluations/components/EvaluationHeatmap.tsx`) — this uses a separate render path that builds cell-level `hasNote` from the eval-list `annotation_count` and is not affected by the bug. Leave it alone.
- The `HeatmapChart`'s `annotations` prop and the in-cell orange-square render branch (`HeatmapChart.tsx:304-316`) — only used by the group view above. Do not delete.

---

## File Map

**Backend:**
- Modify `api/app/modules/quality_gate/schemas/heatmap.py` — add `has_notes` to `EvaluationColumn`.
- Modify `api/app/modules/quality_gate/trend_repository.py` — add `get_run_ids_with_notes()`.
- Modify `api/app/modules/quality_gate/router.py` — wire `noted_run_ids` through `_build_grouped_heatmap_response` and `get_grouped_metric_heatmap`.
- Modify `api/tests/services/test_heatmap_builder.py` — add a single new test for `has_notes` propagation; existing 8 callsites stay green via default arg.
- Add `api/tests/db/test_grouped_heatmap_has_notes.py` — integration test that the endpoint marks the right columns.

**Frontend:**
- Modify `ui/src/features/navigator/types.ts` — add `has_notes?: boolean` to `EvaluationColumn`.
- Modify `ui/src/features/navigator/components/AssetPanel.tsx` — replace `notedSlots` derivation (lines 222-242).
- Modify `ui/src/components/charts/NoteIndicatorRow.tsx` — switch tooltip data source from `useEvaluationDetail` to `useColumnAnnotations`.
- Modify `ui/src/features/navigator/components/AssetPanel.test.tsx` — fixture updates if existing tests asserted on the old behaviour.
- Add `ui/src/features/navigator/components/AssetPanel.test.tsx` cases for the new column-driven flow.

---

## Task 1: Backend — add `has_notes` field to `EvaluationColumn` schema

**Files:**
- Modify: `api/app/modules/quality_gate/schemas/heatmap.py:85-92`

- [ ] **Step 1: Add the field**

Edit `api/app/modules/quality_gate/schemas/heatmap.py`, change the `EvaluationColumn` class to:

```python
class EvaluationColumn(BaseModel):
    """One heatmap column — corresponds to one parent EvaluationRun."""

    evaluation_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    eval_name: str
    has_notes: bool = False
```

The `= False` default is critical: keeps every existing constructor call (router, tests, fixtures) compiling unchanged.

- [ ] **Step 2: Run schema-touching tests to confirm nothing breaks**

Run: `./scripts/api-test.sh --tail 10 tests/services/test_heatmap_builder.py -v`
Expected: PASS — all 8 existing tests still green because the new field defaults to `False`.

- [ ] **Step 3: Commit**

```bash
git add api/app/modules/quality_gate/schemas/heatmap.py
git commit -m "feat(api): add has_notes field to EvaluationColumn schema"
```

---

## Task 2: Backend — repository helper `get_run_ids_with_notes()`

**Files:**
- Modify: `api/app/modules/quality_gate/trend_repository.py`
- Test: covered indirectly by Task 5 integration test

The query joins `slo_evaluations` (which carries `evaluation_id` FK to `EvaluationRun`) with `evaluation_annotations`, filters out hidden rows, restricts to the run IDs in scope, and returns distinct run IDs.

- [ ] **Step 1: Add the import for `EvaluationAnnotation`**

Edit `api/app/modules/quality_gate/trend_repository.py`, change the import line from:

```python
from app.db.models import EvaluationRun, IndicatorResultRow, SLIValue, SLOEvaluation, SLOObjective
```

to:

```python
from app.db.models import (
    EvaluationAnnotation,
    EvaluationRun,
    IndicatorResultRow,
    SLIValue,
    SLOEvaluation,
    SLOObjective,
)
```

- [ ] **Step 2: Add the helper method**

Insert this method into class `TrendRepository`, immediately after `get_grouped_metric_heatmap` (around line 93 in `trend_repository.py`):

```python
    async def get_run_ids_with_notes(
        self, run_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]:
        """Return the subset of `run_ids` that has at least one non-hidden annotation
        on any of its child SLO evaluations.

        Single roundtrip; uses `idx_annotations_slo_evaluation` for the inner join
        and `slo_evaluations.evaluation_id` (FK) for the run-id filter.
        """
        if not run_ids:
            return set()
        q = (
            select(SLOEvaluation.evaluation_id)
            .join(
                EvaluationAnnotation,
                EvaluationAnnotation.slo_evaluation_id == SLOEvaluation.id,
            )
            .where(
                SLOEvaluation.evaluation_id.in_(run_ids),
                EvaluationAnnotation.hidden_at.is_(None),
            )
            .distinct()
        )
        result = await self._session.execute(q)
        return {row[0] for row in result.all()}
```

- [ ] **Step 3: Run the type checker**

Run: `uv run mypy api/app`
Expected: PASS, no new errors.

- [ ] **Step 4: Run the existing trend repository tests to confirm no regression**

Run: `./scripts/api-test.sh --tail 10 tests/db -v -k trend`
Expected: PASS (or "no tests collected" if there are none — both are acceptable; we are only checking for regression).

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/quality_gate/trend_repository.py
git commit -m "feat(api): add TrendRepository.get_run_ids_with_notes helper"
```

---

## Task 3: Backend — thread `noted_run_ids` through the builder

**Files:**
- Modify: `api/app/modules/quality_gate/router.py:152-290`

- [ ] **Step 1: Update `_build_grouped_heatmap_response` signature with default**

Edit `api/app/modules/quality_gate/router.py` line 152. Change:

```python
def _build_grouped_heatmap_response(
    asset_name: str,
    runs: list[EvaluationRun],
) -> GroupedMetricHeatmapResponse:
```

to:

```python
def _build_grouped_heatmap_response(
    asset_name: str,
    runs: list[EvaluationRun],
    noted_run_ids: set[uuid.UUID] | None = None,
) -> GroupedMetricHeatmapResponse:
```

The `None`-default keeps all 8 existing test callsites unchanged.

- [ ] **Step 2: Use the parameter when constructing `EvaluationColumn`**

In the same file, replace the `columns = [...]` block (lines 164-172):

```python
    columns = [
        EvaluationColumn(
            evaluation_id=run.id,
            period_start=run.period_start,
            period_end=run.period_end,
            eval_name=run.eval_name,
        )
        for run in runs_asc
    ]
```

with:

```python
    noted = noted_run_ids or set()
    columns = [
        EvaluationColumn(
            evaluation_id=run.id,
            period_start=run.period_start,
            period_end=run.period_end,
            eval_name=run.eval_name,
            has_notes=run.id in noted,
        )
        for run in runs_asc
    ]
```

- [ ] **Step 3: Run the existing builder tests — they must still pass**

Run: `./scripts/api-test.sh --tail 10 tests/services/test_heatmap_builder.py -v`
Expected: PASS — `noted_run_ids` defaults to empty, so all columns get `has_notes=False`. None of the existing tests assert on `has_notes`.

- [ ] **Step 4: Commit**

```bash
git add api/app/modules/quality_gate/router.py
git commit -m "refactor(api): thread noted_run_ids through grouped heatmap builder"
```

---

## Task 4: Backend — add unit test for `_build_grouped_heatmap_response` `has_notes`

**Files:**
- Modify: `api/tests/services/test_heatmap_builder.py`

- [ ] **Step 1: Write the failing test**

Append at the end of `api/tests/services/test_heatmap_builder.py`:

```python
def test_has_notes_marks_columns_present_in_noted_set() -> None:
    run_with_notes = _make_run()  # whatever helper exists in this file
    run_without_notes = _make_run()

    resp = _build_grouped_heatmap_response(
        'test-asset',
        [run_with_notes, run_without_notes],
        noted_run_ids={run_with_notes.id},
    )

    by_id = {c.evaluation_id: c for c in resp.columns}
    assert by_id[run_with_notes.id].has_notes is True
    assert by_id[run_without_notes.id].has_notes is False


def test_has_notes_defaults_to_false_when_noted_run_ids_omitted() -> None:
    run = _make_run()
    resp = _build_grouped_heatmap_response('test-asset', [run])
    assert resp.columns[0].has_notes is False
```

If `_make_run` does not exist in this file, look near the top of the file for the existing `_make_slo_eval` helper and the run-construction pattern used by the existing tests (around line 120) and reuse it. Do not invent a new helper — match what is already there.

- [ ] **Step 2: Run the new tests**

Run: `./scripts/api-test.sh --tail 10 tests/services/test_heatmap_builder.py -v -k has_notes`
Expected: PASS for both new tests.

- [ ] **Step 3: Run the full builder test file**

Run: `./scripts/api-test.sh --tail 10 tests/services/test_heatmap_builder.py -v`
Expected: PASS for all tests (8 existing + 2 new).

- [ ] **Step 4: Commit**

```bash
git add api/tests/services/test_heatmap_builder.py
git commit -m "test(api): cover has_notes propagation in grouped heatmap builder"
```

---

## Task 5: Backend — wire `noted_run_ids` into the endpoint

**Files:**
- Modify: `api/app/modules/quality_gate/router.py:367-385`

- [ ] **Step 1: Update the endpoint to query and pass noted IDs**

Edit `api/app/modules/quality_gate/router.py`, replace the body of `get_grouped_metric_heatmap` (lines 367-385):

```python
@router.get('/evaluate/metric-heatmap', response_model=GroupedMetricHeatmapResponse)
async def get_grouped_metric_heatmap(
    asset_name: str,
    evaluation_name: list[str] | None = Query(default=None),
    from_ts: datetime | None = Query(default=None, alias='from'),
    to_ts: datetime | None = Query(default=None, alias='to'),
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> GroupedMetricHeatmapResponse:
    """Return a grouped metric heatmap — one column per parent EvaluationRun."""
    asset = await repos.asset_repo.get_by_name(asset_name)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"asset '{asset_name}' not found")
    runs = await repos.trend_repo.get_grouped_metric_heatmap(
        asset_id=asset.id,
        eval_name=evaluation_name,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    noted_run_ids = await repos.trend_repo.get_run_ids_with_notes(
        [run.id for run in runs]
    )
    return _build_grouped_heatmap_response(asset_name, runs, noted_run_ids)
```

- [ ] **Step 2: Type check**

Run: `uv run mypy api/app`
Expected: PASS.

- [ ] **Step 3: Lint**

Run: `uv run ruff check api/app/modules/quality_gate/router.py api/app/modules/quality_gate/trend_repository.py`
Expected: PASS, no new warnings.

- [ ] **Step 4: Commit**

```bash
git add api/app/modules/quality_gate/router.py
git commit -m "feat(api): populate has_notes from annotations in grouped heatmap endpoint"
```

---

## Task 6: Backend — integration test for the endpoint

**Files:**
- Create: `api/tests/db/test_grouped_heatmap_has_notes.py`

This test seeds an asset, runs two completed evaluations, and adds an annotation to one. It then hits the endpoint and asserts only the annotated column is marked.

- [ ] **Step 1: Pre-flight — make sure test infra is up**

Run: `just test-env`
Expected: container running.

- [ ] **Step 2: Locate an existing integration test as a template**

Run: `ls api/tests/db/ | head`

Expected output: a list including files like `test_baseline_query.py`, `test_evaluation_repo.py`, etc. Open one to copy its fixture-loading and async client setup style. Critical: do not invent a new pattern — match what is already there.

- [ ] **Step 3: Write the failing test**

Create `api/tests/db/test_grouped_heatmap_has_notes.py`:

```python
"""Integration test: grouped heatmap endpoint marks columns with annotations."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_has_notes_only_set_for_columns_with_non_hidden_annotations(
    api_client,           # whatever the existing httpx fixture is named
    seed_two_completed_runs,  # custom fixture defined below or inline
):
    """Two completed runs exist; one has an annotation, one does not.
    The endpoint must mark only the annotated column with has_notes=True.
    """
    asset_name, annotated_run_id, plain_run_id = seed_two_completed_runs

    resp = await api_client.get(
        '/evaluate/metric-heatmap',
        params={'asset_name': asset_name},
    )
    assert resp.status_code == 200
    body = resp.json()

    by_id = {c['evaluation_id']: c for c in body['columns']}
    assert by_id[str(annotated_run_id)]['has_notes'] is True
    assert by_id[str(plain_run_id)]['has_notes'] is False


async def test_hidden_annotations_do_not_set_has_notes(
    api_client,
    seed_run_with_hidden_annotation,
):
    """If every annotation on a run is soft-deleted (hidden_at != NULL),
    the column must report has_notes=False.
    """
    asset_name, run_id = seed_run_with_hidden_annotation
    resp = await api_client.get(
        '/evaluate/metric-heatmap',
        params={'asset_name': asset_name},
    )
    body = resp.json()
    by_id = {c['evaluation_id']: c for c in body['columns']}
    assert by_id[str(run_id)]['has_notes'] is False
```

If a suitable seeding fixture does not exist in `api/tests/db/conftest.py`, add one. Look at how `test_baseline_query.py` or another existing integration test seeds an asset + completed evaluation, and follow the same shape. The fixture must:

1. Create an asset.
2. Create two `EvaluationRun` rows in `completed` status with at least one `SLOEvaluation` child each.
3. For `seed_two_completed_runs`: add one `EvaluationAnnotation` (hidden_at=None) to a child SLO of the first run.
4. For `seed_run_with_hidden_annotation`: add one annotation with `hidden_at=datetime.now(UTC)`.

Do not handcraft new ORM models from scratch — reuse the helpers under `api/tests/db/conftest.py`.

- [ ] **Step 4: Run the integration test, expect FAIL until fixtures are wired**

Run: `./scripts/api-test.sh --tail 20 tests/db/test_grouped_heatmap_has_notes.py -v -m integration`
Expected on first run: either FAIL with assertion mismatch (means endpoint is wired but data set up wrong) or fixture/import errors. Iterate on the fixture until both tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/tests/db/test_grouped_heatmap_has_notes.py api/tests/db/conftest.py
git commit -m "test(api): integration test for has_notes on grouped heatmap endpoint"
```

---

## Task 7: Frontend — add `has_notes` to the `EvaluationColumn` type

**Files:**
- Modify: `ui/src/features/navigator/types.ts:46-52`

- [ ] **Step 1: Update the type**

Edit `ui/src/features/navigator/types.ts`. Change:

```ts
// One column in the grouped heatmap — corresponds to one EvaluationRun
export interface EvaluationColumn {
  evaluation_id: string
  period_start: string
  period_end: string
  eval_name: string
}
```

to:

```ts
// One column in the grouped heatmap — corresponds to one EvaluationRun
export interface EvaluationColumn {
  evaluation_id: string
  period_start: string
  period_end: string
  eval_name: string
  has_notes?: boolean
}
```

`?` (optional) keeps every existing mock and test fixture compiling.

- [ ] **Step 2: Type-check the UI**

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add ui/src/features/navigator/types.ts
git commit -m "feat(ui): add has_notes to EvaluationColumn type"
```

---

## Task 8: Frontend — replace `notedSlots` derivation in AssetPanel

**Files:**
- Modify: `ui/src/features/navigator/components/AssetPanel.tsx:222-242`

This is the actual bug fix. The current code restricts the icon row to columns whose annotated SLO happens to appear in the (potentially truncated) eval list. The new code reads the per-column flag from the heatmap response directly.

- [ ] **Step 1: Replace the `notedSlots` block**

Edit `ui/src/features/navigator/components/AssetPanel.tsx`. Replace lines 222-242 (the entire `const notedSlots = useMemo(...)` block) with:

```ts
  const notedSlots = useMemo(() => {
    const slots = new Map<string, { evalId: string; count: number }>()
    if (!heatmapData) return slots
    for (const col of heatmapData.columns) {
      if (col.has_notes) {
        // Use period_start as the slot key (matches HeatmapChart column key) and
        // store the parent evaluation_id for hover-time annotation fetches.
        // count=0 because the actual number is loaded lazily on hover.
        slots.set(col.period_start, { evalId: col.evaluation_id, count: 0 })
      }
    }
    return slots
  }, [heatmapData])
```

Note that the dependency array shrinks from `[evals, heatmapData]` to `[heatmapData]` — the icon row is now independent of the eval list entirely.

- [ ] **Step 2: Type-check**

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: PASS.

- [ ] **Step 3: Run all AssetPanel tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/navigator/components/AssetPanel.test.tsx`
Expected: most tests PASS; tests that asserted on the eval-list-driven `notedSlots` will FAIL. Note which ones fail; they will be updated in Task 10. If no tests fail, that is also acceptable (means no test ever exercised the old derivation).

- [ ] **Step 4: Commit**

```bash
git add ui/src/features/navigator/components/AssetPanel.tsx
git commit -m "fix(ui): drive notedSlots from heatmap columns instead of eval list"
```

---

## Task 9: Frontend — switch tooltip data source to column-annotations

**Files:**
- Modify: `ui/src/components/charts/NoteIndicatorRow.tsx`

The `NoteIcon` currently calls `useEvaluationDetail(info.evalId)`. Previously `info.evalId` was a `slo_evaluation_id`; after Task 8 it is the parent `evaluation_id` (column key). We must switch to `useColumnAnnotations`, which already takes the parent ID and aggregates across all SLOs in the column.

- [ ] **Step 1: Update the import**

Edit `ui/src/components/charts/NoteIndicatorRow.tsx`. Change line 5:

```ts
import { useEvaluationDetail } from '@/features/evaluations'
```

to:

```ts
import { useColumnAnnotations } from '@/features/evaluations/hooks'
```

Verify `useColumnAnnotations` is exported from `@/features/evaluations` barrel — if so, prefer the barrel import for consistency:

```ts
import { useColumnAnnotations } from '@/features/evaluations'
```

Quick check: `grep -n "useColumnAnnotations" ui/src/features/evaluations/index.ts` (or whatever the barrel is). Use whichever path the existing AssetPanel.tsx uses (line 6). At time of writing, `AssetPanel.tsx` imports from `@/features/evaluations/hooks` directly — use the same.

- [ ] **Step 2: Replace the data fetch and tooltip body**

Inside the `NoteIcon` component, replace the block from line 37 to the closing `</div>` of the tooltip (lines 37-94 — the entire fetch + render). The new body:

```tsx
  const { data: annotations, isFetching } = useColumnAnnotations(
    open ? info.evalId : undefined,
  )
  const latest = annotations?.[annotations.length - 1]
  const count = annotations?.length ?? 0
```

Then in the tooltip JSX (the `{open && (...)}` block), replace the header line:

```tsx
            <span className="text-[10px] text-muted-foreground">
              {info.count} note{info.count !== 1 ? 's' : ''}
            </span>
```

with:

```tsx
            <span className="text-[10px] text-muted-foreground">
              {annotations ? `${count} note${count !== 1 ? 's' : ''}` : 'Notes'}
            </span>
```

The rest of the tooltip body (`{latest ? ... : <Loader2 .../>}`) keeps working unchanged because `latest` now comes from the annotations array.

- [ ] **Step 3: Drop `count` from `SlotNote`? No — keep it.**

Do NOT remove the `count` field from the `SlotNote` interface. The group view (`EvaluationHeatmap.tsx`) is out of scope and may still produce non-zero counts via a different code path. Keeping `count` optional/zero costs nothing and avoids touching unrelated code.

- [ ] **Step 4: Type-check**

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: PASS.

- [ ] **Step 5: Lint**

Run: `./scripts/ui-lint.sh --tail 10 src/components/charts/NoteIndicatorRow.tsx`
Expected: PASS, no warnings.

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/charts/NoteIndicatorRow.tsx
git commit -m "fix(ui): use column-annotations endpoint for note tooltip content"
```

---

## Task 10: Frontend — update AssetPanel tests for new flow

**Files:**
- Modify: `ui/src/features/navigator/components/AssetPanel.test.tsx`

- [ ] **Step 1: Inspect existing test mocks**

Run: `grep -n "annotation_count\|notedSlots\|has_notes" ui/src/features/navigator/components/AssetPanel.test.tsx`

Expected: zero or a small number of matches. If zero matches, no test asserted on the old behaviour and Task 8 already passed cleanly — skip to Step 4.

- [ ] **Step 2: Add a positive test**

Append a new test case to `AssetPanel.test.tsx`:

```tsx
it('renders note indicator above each column whose has_notes flag is true', async () => {
  // Render AssetPanel with mocked heatmap data containing two columns,
  // only the first with has_notes=true.
  mockUseMetricHeatmap.mockReturnValue({
    data: {
      asset_name: 'asset-1',
      columns: [
        { evaluation_id: 'col-A', period_start: '2026-04-01T00:00:00Z', period_end: '2026-04-01T01:00:00Z', eval_name: 'nightly', has_notes: true },
        { evaluation_id: 'col-B', period_start: '2026-04-02T00:00:00Z', period_end: '2026-04-02T01:00:00Z', eval_name: 'nightly', has_notes: false },
      ],
      groups: [],
      composite: [],
    },
    isLoading: false,
  })

  render(<AssetPanel assetName="asset-1" />, { wrapper })

  // Exactly one indicator icon must be rendered (the first column).
  const icons = await screen.findAllByRole('button', { name: /note/i })
  expect(icons).toHaveLength(1)
})
```

Match the existing mock-setup style in the file — if the file uses `vi.mock` factories, follow that pattern. If existing tests pass `{ wrapper }` from a helper, reuse it. Do not introduce new test infra.

- [ ] **Step 3: Run the new test**

Run: `./scripts/ui-test.sh --tail 20 src/features/navigator/components/AssetPanel.test.tsx`
Expected: PASS for the new test plus all existing tests.

- [ ] **Step 4: Commit**

```bash
git add ui/src/features/navigator/components/AssetPanel.test.tsx
git commit -m "test(ui): cover column-driven note indicator rendering in AssetPanel"
```

---

## Task 11: Manual smoke test against scale dataset

The unit and integration tests verify mechanical correctness, but the original bug report was visual ("only 4 icons appear"). A manual sanity check on the lab-monitor-01 asset (24 SLOs × 90 days, seeded specifically for scale testing) confirms the fix end-to-end.

- [ ] **Step 1: Start the dev environment**

Run: `just dev`
Wait until the API and UI are both reachable.

- [ ] **Step 2: Open the navigator and select `lab-monitor-01`**

Navigate to `http://localhost:5173`, click the Navigator tab, and select the `lab-monitor-01` asset. Wait for the heatmap to render fully.

- [ ] **Step 3: Visually verify**

Expected:
- Every column whose underlying parent run has at least one note shows the amber chat-alert icon, **regardless of which SLO inside the column owns the annotation**.
- Hovering an icon opens a tooltip that shows the latest annotation content with the correct count.
- Icons remain pixel-aligned with the cell columns underneath them when the window is resized.

If any column with known annotations is still missing its icon, the integration test in Task 6 should have caught it — re-check the test fixture covers the same SLO/run shape as the production seed data.

- [ ] **Step 4: Inspect the network response in DevTools**

Open DevTools → Network → filter for `metric-heatmap`. Click the response tab, search for `has_notes`. Confirm the values returned by the backend match what the UI is rendering. This is the most robust way to isolate "is it the API or the UI?" if any visual mismatch persists.

- [ ] **Step 5: Stop the dev environment with Ctrl+C and commit nothing — this task is a verification gate, not a code change.**

---

## Risk / Breakage Assessment

| Area | Risk | Mitigation |
|---|---|---|
| `_build_grouped_heatmap_response` signature change | LOW — 8 existing test callsites | New parameter is optional with `None` default; tests stay green. Verified in Task 1, Task 3 steps. |
| `EvaluationColumn` Pydantic schema change | LOW | New field has `= False` default; all existing constructors work unchanged. Pydantic v2 ignores the new field when serializing old data. |
| Old UI clients consuming the response | NONE | The new field is additive. Old UI builds simply ignore `has_notes`. |
| Group view (`EvaluationHeatmap.tsx`) | NONE | Out of scope — uses a separate endpoint and a separate render path. No code touched there. |
| In-cell orange square in `HeatmapChart` | NONE | Out of scope — gated by an `annotations` prop only the group view passes. Unchanged. |
| Database performance | NEGLIGIBLE | One extra `SELECT DISTINCT` per heatmap fetch. Hits `idx_annotations_slo_evaluation`; row counts are bounded by `runs.length × avg_slos × avg_annotations` and the IN clause is at most 100 IDs (safety cap in `get_grouped_metric_heatmap`). |
| Tooltip data source change in `NoteIndicatorRow` | MEDIUM-LOW | `useEvaluationDetail` was returning a single SLO eval; `useColumnAnnotations` returns the full annotation list across all SLOs in the column. Behaviour changes from "latest of one SLO" to "latest of column". This is exactly what the user asked for ("notes are for eval not for SLO"). Covered by manual smoke test in Task 11. |

## Rollback

Each task is one commit. If anything goes wrong:
- Backend-only revert: `git revert <task-1>..<task-6>` reverts API changes; UI keeps reading the old `EvaluationColumn` shape (the field becomes undefined → falsy → no icons, matching pre-fix behaviour).
- Full revert: `git revert <task-1>..<task-10>`.

## Self-review notes

- **Spec coverage** ✓ — every requirement in the conversation is mapped to a task: backend `has_notes` field (Task 1, 5), data source replacement (Task 8), tooltip rewire (Task 9), per-column icon presence (Task 8), no count required upfront (Task 9 keeps `count=0` and computes on hover).
- **No placeholders** ✓ — every code block is concrete and copy-pasteable.
- **Type/name consistency** ✓ — `noted_run_ids: set[uuid.UUID]` matches across Tasks 2/3/4/5; `has_notes: bool` matches between schema (Task 1) and TypeScript (Task 7).
- **Out-of-scope items** are listed at the top so the executor doesn't accidentally touch the group view.
