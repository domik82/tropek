# Deactivation Audit Trail for Registry Entities

**Date:** 2026-04-03
**Status:** Approved

## Problem

Registry entities (DataSource, SLI, SLO, SLO Group) can be deleted/deactivated without
recording who did it or why. The `DeletionConfirmForm` component was designed with
`reason`/`author` callback params, and the detail views had `_reason`/`_author` placeholders
in their handlers — but the feature was never wired up end-to-end.

Additionally, evaluation invalidation collects `author` in the UI but never sends it to the
backend — there is no DB column for it.

## Scope

- Add required `reason` + `author` fields to all deactivation/deletion flows for the 4
  registry entity types.
- Convert DataSource from hard-delete to soft-delete (align with SLI/SLO/SLO Group pattern).
- Fix the existing evaluation invalidation gap: persist `author` alongside `invalidation_note`.
- Audit trail is stored but not surfaced in the UI (no "show inactive" toggle — future work).

## DB Changes

### New columns on 4 tables

Added to `sli_definitions`, `slo_definitions`, `slo_groups`, and `data_sources`:

| Column | Type | Nullable | Default |
|---|---|---|---|
| `deactivated_at` | `timestamptz` | yes | `NULL` |
| `deactivated_by` | `text` | yes | `NULL` |
| `deactivation_reason` | `text` | yes | `NULL` |

### DataSource soft-delete conversion

New column on `data_sources`:

| Column | Type | Nullable | Default |
|---|---|---|---|
| `active` | `boolean` | no | `true` |

### Evaluation invalidation author

New column on `slo_evaluations`:

| Column | Type | Nullable | Default |
|---|---|---|---|
| `invalidation_author` | `text` | yes | `NULL` |

### Migration

Single Alembic migration covering all column additions. No data backfill needed — existing
deactivated rows will have `NULL` for the new audit columns.

## API Changes

### Registry entity deactivation

All 4 DELETE endpoints change from no-body to accepting a JSON body with two required fields.

**Shared Pydantic schema** (`DeactivateRequest` in `app.modules.common.schemas`):

```python
class DeactivateRequest(StrictInput):
    reason: str
    author: str
```

**Endpoints:**

```
DELETE /datasources/{name}           Body: DeactivateRequest
DELETE /sli-definitions/{name}       Body: DeactivateRequest
DELETE /slo-definitions/{name:path}  Body: DeactivateRequest
DELETE /slo-groups/{name}            Body: DeactivateRequest
```

Each endpoint passes `reason` and `author` through the service/repository layer to populate
the three audit columns before setting `active=false`.

### Evaluation invalidation

Extend the existing `InvalidateRequest` schema:

```python
class InvalidateRequest(StrictInput):
    invalidation_note: str
    author: str           # NEW — required
```

Endpoint unchanged: `PATCH /evaluations/{eval_id}/invalidate`

## Repository Changes

### Deactivation methods

Each repository's `deactivate()` method gains `reason: str, author: str` parameters:

```python
async def deactivate(self, name: str, *, reason: str, author: str) -> None:
    # SET active=false, deactivated_at=now(), deactivated_by=author,
    #     deactivation_reason=reason
```

### DataSource: hard-delete → soft-delete

- `DataSourceRepository.delete_by_name()` → renamed to `deactivate()`, uses soft-delete
  with the same audit columns.
- All list/get queries in `DataSourceRepository` gain `.where(DataSource.active == true())`
  filter (same pattern as SLI/SLO repositories).

### Evaluation invalidation

`EvaluationRepository.invalidate()` gains an `author: str` parameter, writes it to the new
`invalidation_author` column.

## Frontend Changes

### Deletion/deactivation forms

The `DeletionConfirmForm` component already supports `requireReason` and `requireAuthor`
boolean props — they are currently set to `false` everywhere. Changes:

1. Flip to `requireReason={true}` and add `requireAuthor={true}` on all 4 detail views.
2. Restore `reason`/`author` parameters in each handler:
   - `DatasourceDetailView.handleDelete(reason, author)`
   - `SliDetailView.handleDeactivate(reason, author)`
   - `SloDetailView.handleDeactivate(reason, author)`
   - `SloGroupDetailView.handleDelete(reason, author)`

### Hooks and API functions

Each delete/deactivate hook changes from `mutationFn: (name: string)` to
`mutationFn: (payload: { name: string; reason: string; author: string })`.

Each API function changes to send a JSON body with the DELETE request:

```typescript
export async function deleteDatasource(
  name: string, reason: string, author: string,
): Promise<void> {
  await fetch(`${BASE}/datasources/${encodeURIComponent(name)}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason, author }),
  })
}
```

### Evaluation invalidation fix

`invalidateEvaluation()` API function: add `author` to the request body alongside
`invalidation_note`.

`useInvalidateEvaluation` hook: already receives `{ note, author }` from the form — just
needs to pass `author` through to the API function.

## Out of Scope

- Surfacing deactivated entities in the UI (e.g., "show inactive" toggle)
- Displaying audit info (who/when/why) in GET responses or detail views
- Audit log table or event sourcing
- Undo/reactivation flows

These can build on the audit columns added here.
