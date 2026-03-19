# Duplicate Evaluation Prevention

## Problem

No uniqueness enforcement exists on evaluations. Multiple evaluations can be created
for the same (asset, SLO, time period), causing heatmap cell collisions, ambiguous
override/baseline behavior, and confusing UI state where selecting one evaluation
appears to affect another.

## Evaluation Identity

The unique identity of an evaluation is the tuple:

```
(asset_id, slo_name, period_start, period_end)
```

`evaluation_name` is a descriptive label only — it does not participate in identity.

At most **one non-failed evaluation** may exist per identity tuple.

## Database Changes

### Make `asset_id` and `slo_name` non-nullable

These fields are currently nullable but an evaluation without an asset or SLO has no
meaning in practice. Change both columns to `NOT NULL`.

### Partial unique index

```sql
CREATE UNIQUE INDEX uq_evaluations_identity
    ON evaluations (asset_id, slo_name, period_start, period_end)
    WHERE status != 'failed';
```

This allows retrying a failed evaluation (creates a new row) while preventing
duplicates for all other statuses.

Regenerate migration via `db-regen-migrations.sh`.

## API Behavior

### `POST /evaluations` (single trigger)

Before creating the evaluation, query for an existing non-failed evaluation with the
same (asset_id, slo_name, period_start, period_end).

- **Found** — return **409 Conflict** with body:
  ```json
  {
    "detail": "evaluation already exists for this asset/SLO/period — use re-evaluate to re-score"
  }
  ```
- **Not found** — proceed as today (create pending, enqueue job, return 202).

The DB constraint is the safety net; the app-level check exists for clean error
messages.

### `POST /evaluations/batch` (batch trigger)

Check each item against existing evaluations. Create non-duplicates, skip duplicates.
Return **202 Accepted** with a response that reports both:

```json
{
  "evaluations": [
    {"id": "...", "status": "pending"}
  ],
  "skipped": [
    {"asset_name": "checkout-api", "reason": "duplicate period"}
  ]
}
```

### `POST /evaluations/re-evaluate`

No change. Re-evaluate updates the existing evaluation row in place (same UUID),
stores original result/score in `job_stats`, and adds an annotation. It does not
create a new row and therefore does not conflict with the unique constraint.

## Retry and Re-score Decision Tree

This logic must be documented inline in the codebase (code comments on the
repository check and router error handling) so future developers understand the
design intent.

```
Can I trigger a new evaluation for this (asset, SLO, period)?
│
├─ No existing non-failed evaluation → YES, create new evaluation
│
├─ Existing evaluation with status = 'failed' → YES, create new evaluation
│   (failed evals are excluded from the unique constraint)
│
├─ Existing evaluation with status = 'pending' or 'running'
│   → NO — "evaluation is already in progress for this period"
│
├─ Existing evaluation with status = 'completed' or 'partial'
│   → NO — "evaluation already exists, use re-evaluate to re-score"
│
└─ Existing evaluation that is invalidated (completed + invalidated=true)
    → NO — "evaluation exists (invalidated), use re-evaluate to re-score"
```

## What Does Not Change

- **Re-evaluate** — updates in place, same UUID, stores original score
- **Override** — modifies existing evaluation result
- **Invalidate** — marks existing evaluation as invalid
- **Heatmap queries** — no code change needed; duplicates can no longer occur
- **Baseline logic** — no change needed

## Edge Cases

### Null asset_id / slo_name

Eliminated by making both columns non-nullable. Existing data must be verified
before migration — any rows with NULL values need to be addressed (likely test
artifacts that can be deleted, or backfilled from `asset_snapshot`).

### Concurrent requests

Two simultaneous triggers for the same identity could both pass the app-level check.
The DB unique constraint catches the second one. The repository should handle
`IntegrityError` from asyncpg and convert it to a 409 response rather than a 500.
