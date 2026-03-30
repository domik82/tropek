# Re-evaluation Baseline Pin Conflict Resolution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect when re-evaluation `from_date` is before the active baseline pin and let the user choose to skip to the pin or ignore it, instead of silently wiping baselines.

**Architecture:** Add `pin_strategy` field to `ReEvaluateRequest`. The re-evaluator detects conflicts, raises `BaselinePinConflictError` (→ 409) when no strategy is specified, and passes `skip_pin_filter` flag through to `get_reeval_baselines` when ignoring. The UI catches 409 and shows an inline choice dialog.

**Tech Stack:** Python/FastAPI (API), React/TypeScript (UI), Python client SDK

**Spec:** `docs/superpowers/specs/2026-03-30-reeval-pin-conflict-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `api/app/modules/quality_gate/baseline_repository.py` | Modify | Add `get_active_pin()`, add `skip_pin_filter` to `get_reeval_baselines` |
| `api/app/modules/quality_gate/re_evaluation_schemas.py` | Modify | Add `pin_strategy` field, add `BaselinePinConflictError` |
| `api/app/modules/quality_gate/re_evaluator.py` | Modify | Conflict detection, strategy dispatch, propagate skip flag |
| `api/app/modules/quality_gate/router.py` | Modify | Catch `BaselinePinConflictError` → 409 |
| `api/tests/engine/test_reeval_pin_conflict.py` | Create | Unit tests for conflict detection logic |
| `ui/src/features/evaluations/types.ts` | Modify | Add `pin_strategy` to payload, add `PinConflictError` type |
| `ui/src/features/evaluations/api.ts` | Modify | Structured 409 error handling |
| `ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx` | Modify | Conflict dialog UI |
| `clients/python/tropek_client/client.py` | Modify | Add `pin_strategy` param |
| `scripts/e2e_tests.py` | Modify | Pass `pin_strategy='ignore_pin'` in `test_reeval_from_date` |

---

### Task 1: Add `get_active_pin()` and `skip_pin_filter` to baseline repository

**Files:**
- Modify: `api/app/modules/quality_gate/baseline_repository.py:21-163`

- [ ] **Step 1: Add `get_active_pin` method**

Add after the `__init__` method (after line 26):

```python
async def get_active_pin(
    self,
    *,
    asset_id: uuid.UUID,
    slo_name: str,
) -> tuple[datetime, uuid.UUID] | None:
    """Return (period_start, evaluation_id) of the active baseline pin, or None."""
    q = select(Evaluation.period_start, Evaluation.id).where(
        Evaluation.asset_id == asset_id,
        Evaluation.slo_name == slo_name,
        Evaluation.baseline_pinned_at.is_not(None),
        Evaluation.baseline_unpinned_at.is_(None),
    )
    row = await self._session.execute(q)
    result = row.one_or_none()
    if result is None:
        return None
    return result.period_start, result.id
```

- [ ] **Step 2: Add `skip_pin_filter` parameter to `get_reeval_baselines`**

Change the signature at line 66 to add the new parameter:

```python
async def get_reeval_baselines(
    self,
    *,
    asset_id: uuid.UUID,
    slo_name: str,
    period_start_before: datetime,
    include_result_with_score: str,
    limit: int,
    sli_version_range: tuple[int, int] | None = None,
    restrict_to_ids: list[uuid.UUID] | None = None,
    tag_filters: dict[str, str] | None = None,
    skip_pin_filter: bool = False,
) -> list[Evaluation]:
```

Change the pin filter call at line 118 to be conditional:

```python
        if not skip_pin_filter:
            q = await self._apply_pin_filter(q, asset_id=asset_id, slo_name=slo_name)
```

- [ ] **Step 3: Run lint/typecheck**

Run: `./scripts/api-test.sh --tail 5`
Expected: existing tests still pass (no behavior change yet — `skip_pin_filter` defaults to False)

- [ ] **Step 4: Commit**

```
git add api/app/modules/quality_gate/baseline_repository.py
git commit -m "feat: add get_active_pin and skip_pin_filter to baseline repository"
```

---

### Task 2: Add `pin_strategy` to schema and `BaselinePinConflictError`

**Files:**
- Modify: `api/app/modules/quality_gate/re_evaluation_schemas.py`

- [ ] **Step 1: Add `pin_strategy` field and error class**

Add `Literal` to the imports at line 1-8, add `pin_strategy` to the request model, and add the error class:

```python
"""Pydantic schemas for the re-evaluation endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator


class ReEvaluateRequest(BaseModel):
    """Request body for POST /evaluations/re-evaluate."""

    asset_name: str
    slo_name: str

    # Scope — exactly one required
    from_date: datetime | None = None
    from_baseline: bool = False
    from_evaluation_id: uuid.UUID | None = None

    # Optional
    slo_version: int | None = None
    dry_run: bool = False
    pin_strategy: Literal['skip_to_pin', 'ignore_pin'] | None = None

    @model_validator(mode='after')
    def exactly_one_scope(self) -> ReEvaluateRequest:
        """Ensure exactly one scope parameter is provided."""
        scopes = sum(
            [
                self.from_date is not None,
                self.from_baseline,
                self.from_evaluation_id is not None,
            ]
        )
        if scopes != 1:
            msg = 'exactly one of from_date, from_baseline, or from_evaluation_id is required'
            raise ValueError(msg)
        return self


class BaselinePinConflictError(Exception):
    """Raised when re-evaluation from_date is before the active baseline pin."""

    def __init__(self, pin_date: datetime, pin_evaluation_id: uuid.UUID) -> None:
        self.pin_date = pin_date
        self.pin_evaluation_id = pin_evaluation_id
        super().__init__('re-evaluation start date is before the active baseline pin')


class ReEvalResultItem(BaseModel):
    """One re-evaluated evaluation in the response."""

    id: uuid.UUID
    evaluation_name: str
    period_start: datetime
    period_end: datetime
    old_result: str
    new_result: str
    old_score: float
    new_score: float


class ReEvaluateResponse(BaseModel):
    """Response body for POST /evaluations/re-evaluate."""

    affected_evaluations: int
    slo_version_used: int
    results: list[ReEvalResultItem]
```

- [ ] **Step 2: Commit**

```
git add api/app/modules/quality_gate/re_evaluation_schemas.py
git commit -m "feat: add pin_strategy field and BaselinePinConflictError"
```

---

### Task 3: Wire conflict detection into `re_evaluator.py`

**Files:**
- Modify: `api/app/modules/quality_gate/re_evaluator.py:194-281`

- [ ] **Step 1: Add import for `BaselinePinConflictError`**

Update the import at line 18-22:

```python
from app.modules.quality_gate.re_evaluation_schemas import (
    BaselinePinConflictError,
    ReEvalResultItem,
    ReEvaluateRequest,
    ReEvaluateResponse,
)
```

- [ ] **Step 2: Add `skip_pin_filter` parameter to `_rescore_single`**

Add `skip_pin_filter: bool` to the function signature at line 132:

```python
async def _rescore_single(  # noqa: PLR0913
    ev: Evaluation,
    *,
    slo_model: SLO,
    slo_def: SLODefinition,
    slo_version: int,
    eligible_ids: list[uuid.UUID],
    asset_id: uuid.UUID,
    slo_name: str,
    default_sli_version_range: tuple[int, int] | None,
    baseline_repo: BaselineRepository,
    sli_repo: SLIRepository,
    dry_run: bool,
    skip_pin_filter: bool = False,
) -> ReEvalResultItem:
```

Pass it through to `get_reeval_baselines` at line 152:

```python
    baseline_evals = await baseline_repo.get_reeval_baselines(
        asset_id=asset_id,
        slo_name=slo_name,
        period_start_before=ev.period_start,
        include_result_with_score=slo_model.comparison.include_result_with_score.value,
        limit=slo_model.comparison.number_of_comparison_results,
        sli_version_range=sli_range,
        restrict_to_ids=eligible_ids if eligible_ids else None,
        skip_pin_filter=skip_pin_filter,
    )
```

- [ ] **Step 3: Add conflict detection and strategy handling to `re_evaluate`**

In the `re_evaluate` function, after resolving `from_date` (after line 232), add conflict detection:

```python
    # Determine window start
    from_date = await _resolve_from_date(request, asset.id, eval_repo, baseline_repo)

    # Detect baseline pin conflict
    skip_pin = False
    if not request.from_baseline:
        pin_info = await baseline_repo.get_active_pin(asset_id=asset.id, slo_name=request.slo_name)
        if pin_info is not None:
            pin_date, pin_eval_id = pin_info
            if from_date < pin_date:
                if request.pin_strategy is None:
                    raise BaselinePinConflictError(pin_date, pin_eval_id)
                if request.pin_strategy == 'skip_to_pin':
                    from_date = pin_date
                elif request.pin_strategy == 'ignore_pin':
                    skip_pin = True
```

- [ ] **Step 4: Pass `skip_pin` to pre-window baseline query**

Update the `pre_baselines` call at line 248:

```python
    pre_baselines = await baseline_repo.get_reeval_baselines(
        asset_id=asset.id,
        slo_name=request.slo_name,
        period_start_before=from_date,
        include_result_with_score=slo_model.comparison.include_result_with_score.value,
        limit=slo_model.comparison.number_of_comparison_results,
        sli_version_range=default_sli_range,
        skip_pin_filter=skip_pin,
    )
```

- [ ] **Step 5: Pass `skip_pin_filter` to `_rescore_single` in cascade loop**

Update the call at line 261:

```python
        item = await _rescore_single(
            ev,
            slo_model=slo_model,
            slo_def=slo_def,
            slo_version=slo_def.version,
            eligible_ids=eligible_ids,
            asset_id=asset.id,
            slo_name=request.slo_name,
            default_sli_version_range=default_sli_range,
            baseline_repo=baseline_repo,
            sli_repo=sli_repo,
            dry_run=request.dry_run,
            skip_pin_filter=skip_pin,
        )
```

- [ ] **Step 6: Run tests**

Run: `./scripts/api-test.sh --tail 5`
Expected: all existing tests pass

- [ ] **Step 7: Commit**

```
git add api/app/modules/quality_gate/re_evaluator.py
git commit -m "feat: add pin conflict detection and strategy handling to re-evaluator"
```

---

### Task 4: Catch `BaselinePinConflictError` in router

**Files:**
- Modify: `api/app/modules/quality_gate/router.py:17,216-225`

- [ ] **Step 1: Add import**

Update the import at line 17-18:

```python
from app.modules.quality_gate.re_evaluation_schemas import (
    BaselinePinConflictError,
    ReEvaluateRequest,
    ReEvaluateResponse,
)
```

- [ ] **Step 2: Add 409 handler**

Replace the `re_evaluate_evaluations` endpoint (lines 216-225):

```python
@router.post('/evaluations/re-evaluate', response_model=ReEvaluateResponse)
async def re_evaluate_evaluations(
    body: ReEvaluateRequest,
    session: AsyncSession = Depends(get_session),
) -> ReEvaluateResponse:
    """Re-evaluate completed evaluations from stored SLI values."""
    try:
        return await re_evaluate(body, session)
    except BaselinePinConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={
                'detail': str(e),
                'pin_date': e.pin_date.isoformat(),
                'pin_evaluation_id': str(e.pin_evaluation_id),
            },
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
```

- [ ] **Step 3: Commit**

```
git add api/app/modules/quality_gate/router.py
git commit -m "feat: return 409 on re-evaluation baseline pin conflict"
```

---

### Task 5: Unit tests for conflict detection

**Files:**
- Create: `api/tests/engine/test_reeval_pin_conflict.py`

These are pure unit tests — no DB needed. They test `BaselinePinConflictError` construction and `ReEvaluateRequest` validation with pin_strategy.

- [ ] **Step 1: Write tests**

```python
"""Unit tests for re-evaluation pin conflict schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.modules.quality_gate.re_evaluation_schemas import (
    BaselinePinConflictError,
    ReEvaluateRequest,
)


class TestBaselinePinConflictError:
    def test_error_stores_pin_details(self) -> None:
        pin_date = datetime(2026, 3, 16, 10, 0, tzinfo=UTC)
        pin_id = uuid.uuid4()
        err = BaselinePinConflictError(pin_date, pin_id)

        assert err.pin_date == pin_date
        assert err.pin_evaluation_id == pin_id
        assert 'before the active baseline pin' in str(err)

    def test_error_is_exception(self) -> None:
        err = BaselinePinConflictError(datetime.now(tz=UTC), uuid.uuid4())
        assert isinstance(err, Exception)


class TestReEvaluateRequestPinStrategy:
    def test_pin_strategy_none_by_default(self) -> None:
        req = ReEvaluateRequest(
            asset_name='checkout-api',
            slo_name='http-slo',
            from_date=datetime(2026, 3, 15, tzinfo=UTC),
        )
        assert req.pin_strategy is None

    def test_pin_strategy_skip_to_pin(self) -> None:
        req = ReEvaluateRequest(
            asset_name='checkout-api',
            slo_name='http-slo',
            from_date=datetime(2026, 3, 15, tzinfo=UTC),
            pin_strategy='skip_to_pin',
        )
        assert req.pin_strategy == 'skip_to_pin'

    def test_pin_strategy_ignore_pin(self) -> None:
        req = ReEvaluateRequest(
            asset_name='checkout-api',
            slo_name='http-slo',
            from_date=datetime(2026, 3, 15, tzinfo=UTC),
            pin_strategy='ignore_pin',
        )
        assert req.pin_strategy == 'ignore_pin'

    def test_pin_strategy_invalid_value_rejected(self) -> None:
        with pytest.raises(Exception):
            ReEvaluateRequest(
                asset_name='checkout-api',
                slo_name='http-slo',
                from_date=datetime(2026, 3, 15, tzinfo=UTC),
                pin_strategy='invalid',  # type: ignore[arg-type]
            )
```

- [ ] **Step 2: Run tests**

Run: `./scripts/api-test.sh --tail 10 tests/engine/test_reeval_pin_conflict.py -v`
Expected: all 5 tests PASS

- [ ] **Step 3: Commit**

```
git add api/tests/engine/test_reeval_pin_conflict.py
git commit -m "test: add unit tests for re-eval pin conflict schemas"
```

---

### Task 6: Update Python client SDK

**Files:**
- Modify: `clients/python/tropek_client/client.py:651-676`

- [ ] **Step 1: Add `pin_strategy` parameter**

Update the `re_evaluate` method:

```python
    def re_evaluate(
        self,
        asset_name: str,
        slo_name: str,
        *,
        from_date: str | None = None,
        from_baseline: bool = False,
        from_evaluation_id: str | None = None,
        slo_version: int | None = None,
        dry_run: bool = False,
        pin_strategy: str | None = None,
    ) -> dict[str, Any]:
        """Re-evaluate completed evaluations from stored SLI values."""
        body: dict[str, Any] = {'asset_name': asset_name, 'slo_name': slo_name}
        if from_date is not None:
            body['from_date'] = from_date
        if from_baseline:
            body['from_baseline'] = True
        if from_evaluation_id is not None:
            body['from_evaluation_id'] = from_evaluation_id
        if slo_version is not None:
            body['slo_version'] = slo_version
        if dry_run:
            body['dry_run'] = True
        if pin_strategy is not None:
            body['pin_strategy'] = pin_strategy
        resp = self._http.post('/evaluations/re-evaluate', json=body)
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]
```

- [ ] **Step 2: Commit**

```
git add clients/python/tropek_client/client.py
git commit -m "feat: add pin_strategy param to Python client re_evaluate"
```

---

### Task 7: Fix e2e test to pass `pin_strategy`

**Files:**
- Modify: `scripts/e2e_tests.py:226-238`

- [ ] **Step 1: Update `test_reeval_from_date`**

Replace the function:

```python
def test_reeval_from_date(client: TropekClient) -> None:
    """Re-evaluate evaluations from a specific date."""
    step('Step 15: Re-evaluate from date')
    result = client.evaluations.re_evaluate(
        'checkout-api',
        'http-availability-slo',
        from_date='2026-03-15T16:00:00Z',
        pin_strategy='ignore_pin',
    )
    print(f're-evaluated {result["affected_evaluations"]} evals (SLO v{result["slo_version_used"]})')
    assert result['affected_evaluations'] >= 1, 'expected at least 1 re-evaluated eval'
    for r in result['results']:
        print(f'  {r["period_start"][:16]}: {r["old_result"]} -> {r["new_result"]}')
    print('PASS: re-evaluate from date')
```

- [ ] **Step 2: Commit**

```
git add scripts/e2e_tests.py
git commit -m "fix: pass pin_strategy='ignore_pin' in e2e re-eval from date test"
```

---

### Task 8: UI — structured 409 error handling in `api.ts`

**Files:**
- Modify: `ui/src/features/evaluations/types.ts`
- Modify: `ui/src/features/evaluations/api.ts:202-214`

- [ ] **Step 1: Add types**

In `types.ts`, add `pin_strategy` to `ReEvaluatePayload` and add `PinConflictInfo`:

```typescript
export interface ReEvaluatePayload {
  asset_name: string
  slo_name: string
  from_date?: string
  from_baseline?: boolean
  from_evaluation_id?: string
  slo_version?: number
  dry_run?: boolean
  pin_strategy?: 'skip_to_pin' | 'ignore_pin'
}
```

Add after `ReEvaluateResponse`:

```typescript
export interface PinConflictInfo {
  pin_date: string
  pin_evaluation_id: string
}
```

- [ ] **Step 2: Add structured error class and update `reEvaluate`**

In `api.ts`, add a class before the `reEvaluate` function and update error handling:

```typescript
export class PinConflictError extends Error {
  pin_date: string
  pin_evaluation_id: string

  constructor(info: PinConflictInfo) {
    super('re-evaluation start date is before the active baseline pin')
    this.pin_date = info.pin_date
    this.pin_evaluation_id = info.pin_evaluation_id
  }
}

export async function reEvaluate(
  payload: ReEvaluatePayload
): Promise<ReEvaluateResponse> {
  const res = await fetch(`${BASE}/evaluations/re-evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    if (res.status === 409 && body.detail?.pin_date) {
      throw new PinConflictError(body.detail)
    }
    const message = typeof body.detail === 'string' ? body.detail : `reEvaluate: ${res.status}`
    throw new Error(message)
  }
  return res.json()
}
```

- [ ] **Step 3: Commit**

```
git add ui/src/features/evaluations/types.ts ui/src/features/evaluations/api.ts
git commit -m "feat: add structured PinConflictError for 409 re-eval responses"
```

---

### Task 9: UI — conflict dialog in `ReEvaluateForm`

**Files:**
- Modify: `ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx`

- [ ] **Step 1: Rewrite the form with conflict state**

```tsx
// ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx
import { useState, useCallback } from 'react'
import { useReEvaluate } from '../../hooks'
import { PinConflictError } from '../../api'
import { Input } from '@/components/ui/input'
import { ActionFormShell } from './ActionFormShell'
import type { ReEvaluateResponse, PinConflictInfo } from '../../types'

const ACTION_DEF = {
  label: 'Run Evaluations',
  description: 'Re-score all evaluations from stored data with current SLO thresholds.',
  accentColor: 'var(--entity-sli)',
  accentBorder: 'border-entity-sli/25',
  accentText: 'text-entity-sli',
  confirmClasses: 'bg-entity-sli hover:bg-entity-sli/80',
}

interface Props {
  evaluationId: string
  assetName: string
  sloName: string
  defaultFromDate?: string
  onComplete: () => void
}

export function ReEvaluateForm({ assetName, sloName, defaultFromDate, onComplete }: Props) {
  const [fromDate, setFromDate] = useState(defaultFromDate ?? '')
  const [fromBaseline, setFromBaseline] = useState(false)
  const [reEvalResult, setReEvalResult] = useState<ReEvaluateResponse | null>(null)
  const [pinConflict, setPinConflict] = useState<PinConflictInfo | null>(null)
  const reEvaluate = useReEvaluate()

  const canConfirm = fromBaseline || !!fromDate

  const submitReEval = useCallback(
    (pinStrategy?: 'skip_to_pin' | 'ignore_pin') => {
      setPinConflict(null)
      reEvaluate.mutate(
        {
          asset_name: assetName,
          slo_name: sloName,
          ...(fromBaseline ? { from_baseline: true } : { from_date: new Date(fromDate).toISOString() }),
          ...(pinStrategy ? { pin_strategy: pinStrategy } : {}),
        },
        {
          onSuccess: (data) => setReEvalResult(data),
          onError: (err) => {
            if (err instanceof PinConflictError) {
              setPinConflict({ pin_date: err.pin_date, pin_evaluation_id: err.pin_evaluation_id })
            }
          },
        },
      )
    },
    [fromBaseline, fromDate, assetName, sloName, reEvaluate],
  )

  const handleConfirm = useCallback(() => {
    if (!canConfirm) return
    submitReEval()
  }, [canConfirm, submitReEval])

  // Results view
  if (reEvalResult) {
    return (
      <ActionFormShell
        actionDef={ACTION_DEF}
        onClose={onComplete}
        onConfirm={onComplete}
        canConfirm={false}
        isPending={false}
        hideButtons
      >
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
                  <span className="text-muted-foreground/60 mx-1">{'\u2192'}</span>
                  <span className={
                    r.new_result === 'pass' ? 'text-pass'
                      : r.new_result === 'warning' ? 'text-warning'
                        : 'text-fail'
                  }>
                    {r.new_result}
                  </span>
                </span>
                <span className="text-muted-foreground">
                  {r.old_score.toFixed(1)} {'\u2192'} {r.new_score.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
          <div className="flex justify-end">
            <button
              onClick={onComplete}
              className="px-3 py-1.5 text-xs rounded-md border border-border text-muted-foreground hover:text-foreground transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </ActionFormShell>
    )
  }

  return (
    <ActionFormShell
      actionDef={ACTION_DEF}
      onClose={onComplete}
      onConfirm={handleConfirm}
      canConfirm={canConfirm && !pinConflict}
      isPending={reEvaluate.isPending}
      confirmLabel={'\u25B6 Run'}
    >
      {/* Pin conflict dialog */}
      {pinConflict && (
        <div className="text-xs border border-warning/30 bg-warning/5 rounded px-3 py-2 space-y-2">
          <p className="text-warning">
            Start date is before the baseline pin at{' '}
            <span className="text-foreground">{new Date(pinConflict.pin_date).toLocaleString()}</span>
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => submitReEval('skip_to_pin')}
              className="px-2 py-1 rounded border border-border text-muted-foreground hover:text-foreground transition-colors"
            >
              Start from pin
            </button>
            <button
              onClick={() => submitReEval('ignore_pin')}
              className="px-2 py-1 rounded border border-border text-muted-foreground hover:text-foreground transition-colors"
            >
              Ignore pin
            </button>
          </div>
        </div>
      )}
      {/* Generic error (non-conflict) */}
      {reEvaluate.isError && !pinConflict && (
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
          onChange={(e) => { setFromBaseline(e.target.checked); setPinConflict(null) }}
          className="rounded border-border accent-[var(--entity-sli)]"
        />
        Run from last baseline
      </label>
      {!fromBaseline && (
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Start date</label>
          <Input
            type="datetime-local"
            value={fromDate}
            onChange={(e) => { setFromDate(e.target.value); setPinConflict(null) }}
          />
        </div>
      )}
    </ActionFormShell>
  )
}
```

- [ ] **Step 2: Run UI tests**

Run: `./scripts/ui-test.sh --tail 10`
Expected: existing tests pass. The `ReEvaluateForm` doesn't have its own test file currently — the `EvaluationActions.test.tsx` mocks `useReEvaluate`, so it won't exercise the new conflict path but shouldn't break.

- [ ] **Step 3: Commit**

```
git add ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx
git commit -m "feat: add pin conflict dialog to ReEvaluateForm"
```

---

### Task 10: Run full test suite and verify

- [ ] **Step 1: Run API unit tests**

Run: `./scripts/api-test.sh --tail 5`
Expected: all pass

- [ ] **Step 2: Run UI tests**

Run: `./scripts/ui-test.sh --tail 10`
Expected: all pass

- [ ] **Step 3: Run lint + typecheck**

Run: `uv run ruff check api/ adapters/`
Run: `uv run mypy api/app`
Expected: clean

- [ ] **Step 4: Commit any fixes if needed**
