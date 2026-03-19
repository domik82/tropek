# Duplicate Evaluation Prevention

## Problem

No uniqueness enforcement exists on evaluations. Multiple evaluations can be created
for the same (asset, SLO, time period), causing heatmap cell collisions, ambiguous
override/baseline behavior, and confusing UI state where selecting one evaluation
appears to affect another.

Additionally, evaluations of different granularity (hourly, daily, weekly) or purpose
(main vs branch) share the same heatmap view with no way to filter them, making the
heatmap noisy and hard to read.

## Evaluation Identity

The unique identity of an evaluation is the tuple:

```
(asset_id, slo_name, evaluation_name, period_start, period_end)
```

`evaluation_name` is part of identity — it distinguishes evaluation series of
different granularity or purpose (e.g., "nightly-hourly", "nightly-daily",
"release-check"). Different names at the same (asset, SLO, period) are separate
evaluations. Same name at the same period is a duplicate.

At most **one non-failed evaluation** may exist per identity tuple.

## Database Changes

### Make `asset_id` and `slo_name` non-nullable

These fields are currently nullable but an evaluation without an asset or SLO has no
meaning in practice. Change both columns to `NOT NULL`.

### Partial unique index

```sql
CREATE UNIQUE INDEX uq_evaluations_identity
    ON evaluations (asset_id, slo_name, evaluation_name, period_start, period_end)
    WHERE status != 'failed';
```

This allows retrying a failed evaluation (creates a new row) while preventing
duplicates for all other statuses.

### Foreign key on `asset_id`

Set `ondelete='RESTRICT'` on the `asset_id` FK. Assets are never hard-deleted — see
the Soft Delete section below. RESTRICT prevents accidental data loss if someone
bypasses the application layer and runs DELETE directly in SQL.

### Regenerate migration

Use `db-regen-migrations.sh` to regenerate from the updated model.

## API Behavior

### `POST /evaluations` (single trigger)

Before creating the evaluation, query for an existing non-failed evaluation with the
same identity tuple.

- **Found (pending/running)** — return **409 Conflict**:
  ```json
  {"detail": "evaluation is already in progress for this period"}
  ```
- **Found (completed/invalidated)** — return **409 Conflict**:
  ```json
  {"detail": "evaluation already exists for this asset/SLO/period — use re-evaluate to re-score"}
  ```
- **Not found** — proceed as today (create pending, enqueue job, return 202).

The DB constraint is the safety net; the app-level check exists for clean, actionable
error messages.

### `POST /evaluations/batch` (batch trigger)

All-or-nothing. Before creating any evaluations, check all items against existing
records. If **any** item would be a duplicate, the entire batch fails with
**409 Conflict** listing every conflicting item:

```json
{
  "detail": "batch contains duplicate evaluations",
  "conflicts": [
    {
      "asset_name": "checkout-api",
      "slo_name": "latency-slo",
      "evaluation_name": "nightly-hourly",
      "period_start": "2026-03-10T06:00:00Z",
      "period_end": "2026-03-10T07:00:00Z",
      "existing_status": "completed"
    }
  ]
}
```

Single transaction — no partial creation.

### `POST /evaluations/re-evaluate`

No change. Re-evaluate updates the existing evaluation row in place (same UUID),
stores original result/score in `job_stats`, and adds an annotation. It does not
create a new row and therefore does not conflict with the unique constraint.

## Retry and Re-score Decision Tree

This logic must be documented inline in the codebase (code comments on the
repository check and router error handling) so future developers understand the
design intent.

```
Can I trigger a new evaluation for this (asset, SLO, name, period)?
│
├─ No existing non-failed evaluation → YES, create new evaluation
│
├─ Existing evaluation with status = 'failed' → YES, create new evaluation
│   (failed evals are excluded from the unique constraint)
│
├─ Existing evaluation with status = 'pending' or 'running'
│   → NO — "evaluation is already in progress for this period"
│
├─ Existing evaluation with status = 'completed'
│   → NO — "evaluation already exists, use re-evaluate to re-score"
│
└─ Existing evaluation that is invalidated (completed + invalidated=true)
    → NO — "evaluation exists (invalidated), use re-evaluate to re-score"
```

## Heatmap Evaluation Name Filter

The heatmap currently shows all evaluations for an asset regardless of
`evaluation_name`. With multiple series (hourly, daily, weekly, branch runs), this
becomes noisy. Add a filter control near the heatmap.

### Filter behavior

- **Control type**: checkbox combo / multi-select dropdown next to the heatmap.
  Lists all distinct `evaluation_name` values that exist for the current asset.
- **Default**: all names selected (show everything).
- **Per-asset default**: an asset can optionally store a default evaluation name
  filter in its DB configuration. When set, the heatmap opens with only those names
  selected instead of all. This is a user-configurable preference, not a hard
  restriction.
- **Persistence**: the per-asset default is stored in the asset DB record (e.g., a
  JSON field like `heatmap_config.default_eval_names: string[]`). Runtime filter
  selections are client-side state only (not persisted beyond the session).

### Out of scope

- Filtering by evaluation tags (e.g., "show only evals tagged `release`") is a
  separate feature with its own design challenges. Not addressed here.

## Soft Delete (Future Work — Noted for Context)

Asset deletion should be soft, not hard. When a user "deletes" an asset:

1. The asset is marked as **disabled** (e.g., `disabled_at` timestamp).
2. All evaluations for the asset are also marked disabled (or filtered by the
   asset's disabled state).
3. SLO/SLI links not used by other assets are also disabled.
4. Disabled assets and their evaluations are hidden from the UI.
5. Restoring a disabled asset requires manual DB intervention (intentionally — this
   is a safety net, not a routine operation).

This is a separate spec and implementation. The `RESTRICT` FK on `asset_id` prevents
accidental hard deletes in the meantime.

## What Does Not Change

- **Re-evaluate** — updates in place, same UUID, stores original score
- **Override** — modifies existing evaluation result
- **Invalidate** — marks existing evaluation as invalid
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
