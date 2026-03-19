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
duplicates for all other statuses (pending, running, completed, partial).

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
- **Found (completed/partial/invalidated)** — return **409 Conflict**:
  ```json
  {"detail": "evaluation already exists for this asset/SLO/period — use re-evaluate to re-score"}
  ```
- **Not found** — proceed as today (create pending, enqueue job, return 202).

The DB constraint is the safety net; the app-level check exists for clean, actionable
error messages. On concurrent races where two requests pass the app-level check, the
DB constraint catches the second insert. The repository should catch
`asyncpg.UniqueViolationError` (PG error code `23505`) specifically — not generic
`IntegrityError` — and convert it to a 409 response.

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

`asset_name` in the conflict response is resolved from `asset_id` for readability —
the actual duplicate check operates on `asset_id` (the identity tuple column).

Single transaction — no partial creation. Note: the current batch implementation
creates evaluations incrementally and skips failures silently. This requires
structural refactoring to achieve all-or-nothing semantics.

### `POST /evaluations/re-evaluate`

Re-evaluate updates the existing evaluation row in place (same UUID), stores original
result/score in `job_stats`, and adds an annotation. It does not create a new row and
therefore does not conflict with the unique constraint.

Re-evaluate works on **all non-failed statuses**, including:
- **completed** — re-scores against current SLO version using stored SLI data
- **partial** — re-scores; useful when missing evaluations in the baseline window
  have since been filled in (e.g., days 2-4 were missing, now exist, so day 5 needs
  re-evaluation against the corrected baseline)
- **invalidated** — re-scores invalidated evaluation, producing a new valid result

Re-evaluate does **not** re-fetch SLI data from the adapter — it always uses the
stored SLI values. Prometheus or other data sources may have already compacted the
original data.

### `GET /evaluations` (list endpoint)

Add optional query parameters for filtering:

- `evaluation_name` — filter by evaluation name (exact match, repeatable for
  multi-value)
- `metadata` — filter by metadata key-value pairs

These parameters are additive filters on the existing list endpoint. When omitted,
all evaluations are returned (current behavior preserved).

### `GET /evaluations/metric-heatmap`

Add optional `evaluation_name` query parameter (repeatable for multi-value). When
provided, only evaluations matching the given name(s) are included. When omitted, all
names are returned (backward compatible).

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
├─ Existing evaluation with status = 'completed' or 'partial'
│   → NO — "evaluation already exists, use re-evaluate to re-score"
│   (partial means some SLIs succeeded; re-evaluate re-scores with current
│    baseline which may now include previously missing evaluations)
│
└─ Existing evaluation that is invalidated (completed + invalidated=true)
    → NO — "evaluation exists (invalidated), use re-evaluate to re-score"
    (an invalidated evaluation still occupies the identity slot;
     invalidation does not free it up for a new trigger)
```

## Heatmap Evaluation Name Filter

The heatmap currently shows all evaluations for an asset regardless of
`evaluation_name`. With multiple series (hourly, daily, weekly, branch runs), this
becomes noisy. Add a filter control near the heatmap.

### UI control

- **Control type**: checkbox combo / multi-select dropdown next to the heatmap.
- **Options**: all distinct `evaluation_name` values for the current asset,
  discovered from the evaluation data already fetched (or via a dedicated query
  if needed for performance).
- **Default**: all names selected (show everything), unless the asset has a
  configured default (see below).

### Per-asset default filter

An asset can optionally store a default evaluation name filter. When set, the
heatmap opens with only those names pre-selected instead of all.

- **Storage**: new JSONB column `heatmap_config` on the `assets` table, containing
  `{"default_eval_names": ["nightly-hourly", "nightly-daily"]}`. NULL means "show
  all" (default behavior).
- **API**: exposed via the existing asset CRUD endpoints. The UI reads it on load
  and writes it when the user saves a default filter preference.
- **Runtime selections**: client-side state only, not persisted beyond the session.
  Only the "save as default" action writes to the DB.

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
The DB unique constraint catches the second one. The repository should catch
`asyncpg.UniqueViolationError` (PG error code `23505`) specifically and convert it
to a 409.
