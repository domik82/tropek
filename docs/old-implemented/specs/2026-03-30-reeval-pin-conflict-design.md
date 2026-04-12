# Re-evaluation Baseline Pin Conflict Resolution

**Date:** 2026-03-30
**Status:** Draft

## Problem

When a user triggers re-evaluation with `from_date` earlier than the active baseline pin, the pin filter (`period_start >= pin_date`) makes it impossible for any re-evaluated evaluation to find baselines. The baseline query simultaneously requires `period_start >= pin_date` AND `period_start < current_eval_time` — contradictory when `current_eval_time < pin_date`.

The re-evaluator's cascading `eligible_ids` mechanism cannot help: even though prior eval IDs are passed via `restrict_to_ids`, the pin filter removes them because their `period_start` is before the pin.

Result: `update_reeval_result` deletes the original indicator rows (which had baselines from the initial evaluation) and writes new rows with `compared_value = NULL`. All baselines are silently wiped for every eval between `from_date` and `pin_date`.

### Reproduction

The bug is triggered by `scripts/e2e_tests.py`:

1. `test_reeval_from_pinned_baseline` pins `completed[1]` (~`2026-03-16T10:00`) for checkout-api / http-availability-slo
2. `test_reeval_from_date` re-evaluates from `2026-03-15T16:00` while pin is active
3. All load-test evals from 16:00 through 10:00 on 03-16 lose their baselines

## Design

### API: new optional field on `ReEvaluateRequest`

```python
# re_evaluation_schemas.py
class ReEvaluateRequest(BaseModel):
    # ... existing fields ...
    pin_strategy: Literal['skip_to_pin', 'ignore_pin'] | None = None
```

### Behavior matrix

| Condition | Result |
|-----------|--------|
| No active pin | Proceed normally (backward compatible) |
| `from_date >= pin_date` | No conflict, proceed normally |
| `from_date < pin_date` and `pin_strategy` is None | **409 Conflict** with pin details |
| `from_date < pin_date` and `pin_strategy = "skip_to_pin"` | Clamp `from_date` to `pin_date`, proceed |
| `from_date < pin_date` and `pin_strategy = "ignore_pin"` | Skip pin filter for this run, pin stays active |
| `from_baseline = True` | No conflict possible (starts from pin by definition) |
| `from_evaluation_id` with eval before pin | Same conflict detection as `from_date` |

### 409 response body

```json
{
  "detail": "re-evaluation start date is before the active baseline pin",
  "pin_date": "2026-03-16T10:00:00Z",
  "pin_evaluation_id": "abc-123"
}
```

The UI uses `pin_date` and `pin_evaluation_id` to present the conflict dialog. The `detail` string is for human/script consumers.

### Implementation layers

#### 1. `baseline_repository.py` — skip pin filter flag

`get_reeval_baselines` gets a new parameter:

```python
async def get_reeval_baselines(
    self,
    *,
    # ... existing params ...
    skip_pin_filter: bool = False,
) -> list[Evaluation]:
```

When `skip_pin_filter=True`, the method skips the `_apply_pin_filter` call. All other filtering (status, invalidated, result score, SLI version range, restrict_to_ids) still applies.

Also add a public method to look up the active pin:

```python
async def get_active_pin(
    self, *, asset_id: uuid.UUID, slo_name: str
) -> tuple[datetime, uuid.UUID] | None:
    """Return (pin_period_start, pin_evaluation_id) or None."""
```

This extracts the existing pin query from `_apply_pin_filter` into a reusable method.

#### 2. `re_evaluator.py` — conflict detection and strategy handling

New custom exception:

```python
class BaselinePinConflictError(Exception):
    def __init__(self, pin_date: datetime, pin_evaluation_id: uuid.UUID) -> None:
        self.pin_date = pin_date
        self.pin_evaluation_id = pin_evaluation_id
        super().__init__('re-evaluation start date is before the active baseline pin')
```

In `re_evaluate()`, after resolving `from_date` and asset:

1. Query active pin via `baseline_repo.get_active_pin(asset_id, slo_name)`
2. If pin exists and `from_date < pin_date`:
   - If `pin_strategy is None` → raise `BaselinePinConflictError(pin_date, pin_eval_id)`
   - If `pin_strategy == 'skip_to_pin'` → set `from_date = pin_date`
   - If `pin_strategy == 'ignore_pin'` → set `skip_pin = True`
3. Pass `skip_pin` flag through to both the pre-window seed query and per-eval cascade queries in `_rescore_single`

The `skip_pin` flag propagates as a parameter to `_rescore_single` and through to `get_reeval_baselines(skip_pin_filter=skip_pin)`.

#### 3. `router.py` — catch conflict error

```python
@router.post('/evaluations/re-evaluate', response_model=ReEvaluateResponse)
async def re_evaluate_evaluations(body: ReEvaluateRequest, session=Depends(get_session)):
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

#### 4. UI `ReEvaluateForm.tsx` — conflict dialog

When the mutation returns a 409:

1. Parse the error response to extract `pin_date` and `pin_evaluation_id`
2. Show an inline conflict prompt (replaces the error banner):
   - "Start date is before the baseline pin at {formatted pin_date}."
   - Two buttons: **[Start from pin]** and **[Ignore pin]**
3. On button click, re-send the request with `pin_strategy: 'skip_to_pin' | 'ignore_pin'`

The conflict state is local to the form — no new routes or modals needed.

Changes to types/api:

```typescript
// types.ts — extend payload
export interface ReEvaluatePayload {
  // ... existing fields ...
  pin_strategy?: 'skip_to_pin' | 'ignore_pin'
}

// api.ts — parse 409 as structured error (not generic message)
```

The `reEvaluate` function in `api.ts` currently throws `new Error(body.detail ?? ...)`. For 409 responses, it needs to throw a structured error so the form can detect the conflict and extract pin details. A simple approach: throw an object with `status` and `body` fields, and the form checks `error.status === 409`.

#### 5. Python client SDK

```python
def re_evaluate(
    self,
    asset_name: str,
    slo_name: str,
    *,
    # ... existing params ...
    pin_strategy: str | None = None,
) -> dict[str, Any]:
```

Add `pin_strategy` to the request body when provided.

#### 6. E2e test fix

`test_reeval_from_date` in `scripts/e2e_tests.py` passes `pin_strategy='ignore_pin'` to avoid the silent baseline wipe that motivated this design:

```python
result = client.evaluations.re_evaluate(
    'checkout-api',
    'http-availability-slo',
    from_date='2026-03-15T16:00:00Z',
    pin_strategy='ignore_pin',
)
```

## What doesn't change

- **Normal evaluation flow** (worker.py) — still respects pins
- **`from_baseline=True` re-evaluation** — starts from pin by definition, no conflict
- **Pin/unpin endpoints** — untouched
- **Pin persistence** — `ignore_pin` is a one-off override, pin stays active

## Files touched

| File | Change |
|------|--------|
| `api/app/modules/quality_gate/re_evaluation_schemas.py` | Add `pin_strategy` field |
| `api/app/modules/quality_gate/baseline_repository.py` | Add `skip_pin_filter` param, extract `get_active_pin` |
| `api/app/modules/quality_gate/re_evaluator.py` | Conflict detection, strategy handling, propagate flag |
| `api/app/modules/quality_gate/router.py` | Catch `BaselinePinConflictError` → 409 |
| `ui/src/features/evaluations/types.ts` | Add `pin_strategy` to `ReEvaluatePayload` |
| `ui/src/features/evaluations/api.ts` | Structured 409 error handling |
| `ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx` | Conflict dialog UI |
| `clients/python/tropek_client/client.py` | Add `pin_strategy` param |
| `scripts/e2e_tests.py` | Pass `pin_strategy='ignore_pin'` in `test_reeval_from_date` |
