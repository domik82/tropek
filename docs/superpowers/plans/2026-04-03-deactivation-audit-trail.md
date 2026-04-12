# Deactivation Audit Trail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `reason` + `author` audit fields to all registry entity deactivation flows, convert DataSource from hard-delete to soft-delete, and fix the evaluation invalidation author gap.

**Architecture:** Add 3 audit columns (`deactivated_at`, `deactivated_by`, `deactivation_reason`) to 4 tables plus `active` to `data_sources`, and `invalidation_author` to `slo_evaluations`. Thread `reason`/`author` from UI → API → repository → DB. The `DeletionConfirmForm` component already supports `requireReason`/`requireAuthor` props — flip them on and wire through the full stack.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Alembic, React 19, TypeScript, React Query

---

## File Map

### Backend — modified
- `api/app/db/models.py` — Add audit columns to DataSource, SLIDefinition, SLODefinition, SLOGroup; add `invalidation_author` to SLOEvaluation
- `api/app/modules/common/schemas.py` — Add `DeactivateRequest` schema
- `api/app/modules/datasource/repository.py` — Replace `delete_by_name()` with `deactivate()`, add `active` filter to all queries
- `api/app/modules/datasource/router.py` — Accept `DeactivateRequest` body, call `deactivate()`
- `api/app/modules/datasource/schemas.py` — Add `active` to `DataSourceRead`
- `api/app/modules/sli_registry/repository.py` — Add `reason`/`author` params to `deactivate()`
- `api/app/modules/sli_registry/router.py` — Accept `DeactivateRequest` body
- `api/app/modules/slo_registry/repository.py` — Add `reason`/`author` params to `deactivate()`
- `api/app/modules/slo_registry/router.py` — Accept `DeactivateRequest` body
- `api/app/modules/slo_groups/repository.py` — Add `reason`/`author` params to `deactivate()`
- `api/app/modules/slo_groups/router.py` — Accept `DeactivateRequest` body, pass through to both SLO + group repos
- `api/app/modules/quality_gate/schemas/baseline.py` — Add `author` field to `InvalidateRequest`
- `api/app/modules/quality_gate/repository.py` — Add `author` param to `invalidate()`
- `api/app/modules/quality_gate/router.py` — Pass `author` to `invalidate()`

### Backend — test files (modified or created)
- `api/tests/db/test_deactivation_audit.py` — Integration tests for audit columns on all 4 entity types
- `api/tests/db/test_invalidation_author.py` — Integration test for evaluation invalidation author

### Frontend — modified
- `ui/src/features/datasources/api.ts` — Add `reason`/`author` body to DELETE
- `ui/src/features/datasources/hooks.ts` — Change mutationFn payload
- `ui/src/features/slis/api.ts` — Add `reason`/`author` body to DELETE
- `ui/src/features/slis/hooks.ts` — Change mutationFn payload
- `ui/src/features/slos/api.ts` — Add `reason`/`author` body to DELETE
- `ui/src/features/slos/hooks.ts` — Change mutationFn payload
- `ui/src/features/slo-groups/api.ts` — Add `reason`/`author` body to DELETE
- `ui/src/features/slo-groups/hooks.ts` — Change mutationFn payload
- `ui/src/features/evaluations/api.ts` — Add `author` to invalidation body
- `ui/src/features/evaluations/hooks.ts` — Pass `author` through to API function
- `ui/src/features/registry/details/DatasourceDetailView.tsx` — Wire reason/author to handler
- `ui/src/features/registry/details/SliDetailView.tsx` — Wire reason/author to handler
- `ui/src/features/registry/details/SloDetailView.tsx` — Wire reason/author to handler
- `ui/src/features/registry/details/SloGroupDetailView.tsx` — Wire reason/author to handler

---

## Task 1: Add Audit Columns to DB Models

**Files:**
- Modify: `api/app/db/models.py:128-151` (DataSource), `:154-188` (SLIDefinition), `:241-280` (SLODefinition), `:336-359` (SLOGroup), `:470-561` (SLOEvaluation)

- [ ] **Step 1: Add audit columns to DataSource model**

In `api/app/db/models.py`, add `active` and the 3 deactivation audit columns to the `DataSource` class. Add them after the `updated_at` column (line 149), before the `# fmt: on` comment:

```python
    active:                Mapped[bool]             = mapped_column(Boolean, nullable=False, server_default=true(), default=True)
    deactivated_at:        Mapped[datetime | None]  = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_by:        Mapped[str | None]       = mapped_column(Text, nullable=True)
    deactivation_reason:   Mapped[str | None]       = mapped_column(Text, nullable=True)
```

Also add the `Boolean` import if not already present (it is — check line 7 area).

- [ ] **Step 2: Add audit columns to SLIDefinition model**

After the `active` column (line 185) and before `created_at`, add:

```python
    deactivated_at:        Mapped[datetime | None]  = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_by:        Mapped[str | None]       = mapped_column(Text, nullable=True)
    deactivation_reason:   Mapped[str | None]       = mapped_column(Text, nullable=True)
```

- [ ] **Step 3: Add audit columns to SLODefinition model**

After the `active` column (line 271) and before `created_at`, add:

```python
    deactivated_at:        Mapped[datetime | None]  = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_by:        Mapped[str | None]       = mapped_column(Text, nullable=True)
    deactivation_reason:   Mapped[str | None]       = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Add audit columns to SLOGroup model**

After the `active` column (line 355) and before `created_at`, add:

```python
    deactivated_at:        Mapped[datetime | None]  = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_by:        Mapped[str | None]       = mapped_column(Text, nullable=True)
    deactivation_reason:   Mapped[str | None]       = mapped_column(Text, nullable=True)
```

- [ ] **Step 5: Add invalidation_author to SLOEvaluation model**

After the `invalidation_note` column (line 545), add:

```python
    invalidation_author:   Mapped[str | None]       = mapped_column(Text, nullable=True)
```

- [ ] **Step 6: Regenerate migration**

Run: `./scripts/db-regen-migrations.sh`

This regenerates the Alembic migration from the current model state. Verify the generated migration includes the new columns.

- [ ] **Step 7: Commit**

```bash
git add api/app/db/models.py api/alembic/versions/
git commit -m "feat: add deactivation audit columns and invalidation_author to DB models"
```

---

## Task 2: Add DeactivateRequest Schema

**Files:**
- Modify: `api/app/modules/common/schemas.py`

- [ ] **Step 1: Add DeactivateRequest to common schemas**

In `api/app/modules/common/schemas.py`, add after the `StrictInput` class:

```python
class DeactivateRequest(StrictInput):
    """Request body for deactivating a registry entity."""

    reason: str
    author: str
```

- [ ] **Step 2: Add author field to InvalidateRequest**

In `api/app/modules/quality_gate/schemas/baseline.py`, add the `author` field:

```python
class InvalidateRequest(StrictInput):
    """Request body for invalidating an evaluation."""

    invalidation_note: str
    author: str
```

- [ ] **Step 3: Commit**

```bash
git add api/app/modules/common/schemas.py api/app/modules/quality_gate/schemas/baseline.py
git commit -m "feat: add DeactivateRequest schema and author to InvalidateRequest"
```

---

## Task 3: Update DataSource Repository — Hard-Delete to Soft-Delete

**Files:**
- Modify: `api/app/modules/datasource/repository.py`
- Modify: `api/app/modules/datasource/schemas.py`

- [ ] **Step 1: Add active filter to all list/get queries**

In `api/app/modules/datasource/repository.py`:

Update imports — add `true` from `sqlalchemy`:

```python
from sqlalchemy import select, update
from sqlalchemy.sql.expression import true
```

(Remove `delete` from imports since we're switching to soft-delete.)

In `get_by_name()` (line 67), add active filter:

```python
    async def get_by_name(self, name: str) -> DataSource | None:
        """Return active datasource by unique name, or None."""
        result = await self._session.execute(
            select(DataSource).where(DataSource.name == name, DataSource.active == true())
        )
        return result.scalar_one_or_none()
```

In `get_by_id()` (line 70), add active filter:

```python
    async def get_by_id(self, ds_id: uuid.UUID) -> DataSource | None:
        """Return active datasource by primary key, or None."""
        result = await self._session.execute(
            select(DataSource).where(DataSource.id == ds_id, DataSource.active == true())
        )
        return result.scalar_one_or_none()
```

In `list_all()` (line 92), add active filter:

```python
        q = select(DataSource).where(DataSource.active == true()).order_by(DataSource.name)
```

- [ ] **Step 2: Replace delete methods with deactivate()**

Remove `delete()` and `delete_by_name()` methods. Add `deactivate()`:

```python
    async def deactivate(self, name: str, *, reason: str, author: str) -> bool:
        """Soft-delete a datasource by name with audit trail.

        Returns False if not found.
        """
        ds = await self.get_by_name(name)
        if ds is None:
            return False
        await self._session.execute(
            update(DataSource)
            .where(DataSource.id == ds.id)
            .values(
                active=False,
                deactivated_at=func.now(),
                deactivated_by=author,
                deactivation_reason=reason,
            )
        )
        return True
```

Add `func` to the sqlalchemy imports:

```python
from sqlalchemy import func, select, update
from sqlalchemy.sql.expression import true
```

- [ ] **Step 3: Add active field to DataSourceRead schema**

In `api/app/modules/datasource/schemas.py`, add `active: bool` to `DataSourceRead`:

```python
class DataSourceRead(BaseModel):
    """DataSource API response."""

    name: str
    display_name: str | None
    adapter_type: str
    adapter_url: str
    tags: dict[str, Any]
    has_token: bool
    active: bool
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Commit**

```bash
git add api/app/modules/datasource/repository.py api/app/modules/datasource/schemas.py
git commit -m "feat: convert datasource from hard-delete to soft-delete with audit"
```

---

## Task 4: Update SLI, SLO, SLO Group Repositories

**Files:**
- Modify: `api/app/modules/sli_registry/repository.py:170-176`
- Modify: `api/app/modules/slo_registry/repository.py:204-219`
- Modify: `api/app/modules/slo_groups/repository.py:100-107`

- [ ] **Step 1: Update SLI repository deactivate()**

In `api/app/modules/sli_registry/repository.py`, update the `deactivate()` method (line 170):

```python
    async def deactivate(self, name: str, *, reason: str, author: str) -> None:
        """Soft-delete all versions of a named SLI with audit trail."""
        await self._session.execute(
            update(SLIDefinition)
            .where(SLIDefinition.name == name)
            .values(
                active=False,
                deactivated_at=func.now(),
                deactivated_by=author,
                deactivation_reason=reason,
            )
        )
```

Add `func` to the sqlalchemy imports at the top of the file.

- [ ] **Step 2: Update SLO repository deactivate()**

In `api/app/modules/slo_registry/repository.py`, update the `deactivate()` method (line 204):

```python
    async def deactivate(self, name: str, *, reason: str, author: str) -> int:
        """Mark all versions of a named SLO as inactive with audit trail.

        Evaluations that used this SLO retain their `slo_name`/`slo_version` snapshots.
        """
        cursor = cast(
            'CursorResult[Any]',
            await self._session.execute(
                update(SLODefinition)
                .where(SLODefinition.name == name)
                .values(
                    active=False,
                    deactivated_at=func.now(),
                    deactivated_by=author,
                    deactivation_reason=reason,
                )
            ),
        )
        return cursor.rowcount
```

Add `func` to the sqlalchemy imports at the top of the file.

- [ ] **Step 3: Update SLO Group repository deactivate()**

In `api/app/modules/slo_groups/repository.py`, update the `deactivate()` method (line 100):

```python
    async def deactivate(self, name: str, *, reason: str, author: str) -> None:
        """Mark the group as inactive (soft delete) with audit trail. No-op if not found."""
        group = await self.get_by_name(name)
        if group is None:
            return
        group.active = False
        group.deactivated_at = datetime.now(UTC)
        group.deactivated_by = author
        group.deactivation_reason = reason
        group.updated_at = datetime.now(UTC)
        await self._session.flush()
```

- [ ] **Step 4: Update evaluation invalidate() to accept author**

In `api/app/modules/quality_gate/repository.py`, update the `invalidate()` method (line 395):

```python
    async def invalidate(self, eval_id: uuid.UUID, *, note: str, author: str) -> SLOEvaluation | None:
        """Mark an evaluation and all its siblings in the same run as invalidated."""
        ev = await self.get_by_id(eval_id)
        if ev is None:
            return None
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.evaluation_id == ev.evaluation_id)
            .values(invalidated=True, invalidation_note=note, invalidation_author=author)
        )
        return await self.get_by_id(eval_id)
```

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/sli_registry/repository.py api/app/modules/slo_registry/repository.py api/app/modules/slo_groups/repository.py api/app/modules/quality_gate/repository.py
git commit -m "feat: add reason/author params to all deactivate and invalidate repository methods"
```

---

## Task 5: Update All Backend Routers

**Files:**
- Modify: `api/app/modules/datasource/router.py:105-115`
- Modify: `api/app/modules/sli_registry/router.py:103-113`
- Modify: `api/app/modules/slo_registry/router.py:203-213`
- Modify: `api/app/modules/slo_groups/router.py:319-335`
- Modify: `api/app/modules/quality_gate/router.py:420-430`

- [ ] **Step 1: Update datasource DELETE endpoint**

In `api/app/modules/datasource/router.py`, add `DeactivateRequest` to imports:

```python
from app.modules.common.schemas import DeactivateRequest, PagedResponse
```

Update the delete endpoint (line 105):

```python
@router.delete('/datasources/{name}', status_code=204)
async def delete_datasource(
    name: str,
    body: DeactivateRequest,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Deactivate a datasource by name."""
    repo = DataSourceRepository(session)
    deactivated = await repo.deactivate(name, reason=body.reason, author=body.author)
    if not deactivated:
        raise NotFoundError('datasource', name)
    return Response(status_code=204)
```

- [ ] **Step 2: Update SLI DELETE endpoint**

In `api/app/modules/sli_registry/router.py`, add `DeactivateRequest` to imports:

```python
from app.modules.common.schemas import DeactivateRequest
```

Update the delete endpoint (line 103):

```python
@router.delete('/sli-definitions/{name}', status_code=204)
async def delete_sli_definition(
    name: str,
    body: DeactivateRequest,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Deactivate all versions of an SLI definition."""
    repo = SLIRepository(session)
    existing = await repo.get_latest(name)
    if existing is None:
        raise NotFoundError('sli definition', name)
    await repo.deactivate(name, reason=body.reason, author=body.author)
```

- [ ] **Step 3: Update SLO DELETE endpoint**

In `api/app/modules/slo_registry/router.py`, add `DeactivateRequest` to imports:

```python
from app.modules.common.schemas import DeactivateRequest
```

Update the delete endpoint (line 203):

```python
@router.delete('/slo-definitions/{name:path}', status_code=204)
async def delete_slo_definition(
    name: str,
    body: DeactivateRequest,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Deactivate all versions of an SLO definition."""
    repo = SLORepository(session)
    existing = await repo.get_latest(name)
    if existing is None:
        raise NotFoundError('slo definition', name)
    await repo.deactivate(name, reason=body.reason, author=body.author)
```

- [ ] **Step 4: Update SLO Group DELETE endpoint**

In `api/app/modules/slo_groups/router.py`, add `DeactivateRequest` to imports:

```python
from app.modules.common.schemas import DeactivateRequest
```

Update the delete endpoint (line 319):

```python
@router.delete('/slo-groups/{name}', status_code=204)
async def delete_slo_group(
    name: str,
    body: DeactivateRequest,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Deactivate an SLO group and its generated SLOs."""
    group_repo = SLOGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise_not_found('slo group', name)

    slo_repo = SLORepository(session)
    generated_slos = await slo_repo.list_by_group_id(group.id)
    for slo in generated_slos:
        await slo_repo.deactivate(slo.name, reason=body.reason, author=body.author)

    await group_repo.deactivate(name, reason=body.reason, author=body.author)
```

- [ ] **Step 5: Update evaluation invalidation endpoint**

In `api/app/modules/quality_gate/router.py`, update the invalidation endpoint (line 420):

```python
@router.patch('/evaluations/{eval_id}/invalidate', response_model=EvaluationSummary)
async def invalidate_evaluation(
    eval_id: uuid.UUID,
    body: InvalidateRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationSummary:
    """Mark an evaluation as invalidated."""
    ev = await repos.eval_repo.invalidate(eval_id, note=body.invalidation_note, author=body.author)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    return build_summary(ev, annotation_count=0, latest_ann=None)
```

- [ ] **Step 6: Run linter and type checker**

Run: `./scripts/api-test.sh --tail 5`

Then: `uv run ruff check api/`

Then: `uv run mypy api/app`

Fix any issues.

- [ ] **Step 7: Commit**

```bash
git add api/app/modules/datasource/router.py api/app/modules/sli_registry/router.py api/app/modules/slo_registry/router.py api/app/modules/slo_groups/router.py api/app/modules/quality_gate/router.py
git commit -m "feat: wire DeactivateRequest body through all DELETE endpoints"
```

---

## Task 6: Backend Integration Tests

**Files:**
- Create: `api/tests/db/test_deactivation_audit.py`
- Create: `api/tests/db/test_invalidation_author.py`

- [ ] **Step 1: Write deactivation audit integration tests**

Create `api/tests/db/test_deactivation_audit.py`:

```python
"""Integration tests: deactivation audit trail on registry entities."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DataSource, SLIDefinition, SLODefinition, SLOGroup
from app.modules.datasource.repository import DataSourceRepository
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_registry.repository import SLORepository
from app.modules.slo_groups.repository import SLOGroupRepository

pytestmark = pytest.mark.integration


async def test_datasource_deactivate_sets_audit_columns(session: AsyncSession) -> None:
    repo = DataSourceRepository(session)
    await repo.create(name='ds-audit', adapter_type='prometheus', adapter_url='http://localhost')

    result = await repo.deactivate('ds-audit', reason='end of life', author='alice')

    assert result is True
    # Fetch bypassing active filter to verify audit columns
    row = (await session.execute(select(DataSource).where(DataSource.name == 'ds-audit'))).scalar_one()
    assert row.active is False
    assert row.deactivated_by == 'alice'
    assert row.deactivation_reason == 'end of life'
    assert row.deactivated_at is not None


async def test_datasource_deactivate_hides_from_list(session: AsyncSession) -> None:
    repo = DataSourceRepository(session)
    await repo.create(name='ds-visible', adapter_type='prometheus', adapter_url='http://localhost')
    await repo.create(name='ds-hidden', adapter_type='prometheus', adapter_url='http://localhost')
    await repo.deactivate('ds-hidden', reason='deprecated', author='bob')

    visible = await repo.list_all()
    names = [ds.name for ds in visible]
    assert 'ds-visible' in names
    assert 'ds-hidden' not in names


async def test_datasource_deactivate_not_found(session: AsyncSession) -> None:
    repo = DataSourceRepository(session)
    result = await repo.deactivate('nonexistent', reason='n/a', author='x')
    assert result is False


async def test_sli_deactivate_sets_audit_columns(session: AsyncSession) -> None:
    repo = SLIRepository(session)
    await repo.create(
        name='sli-audit',
        adapter_type='prometheus',
        indicators={'metric': 'query'},
    )

    await repo.deactivate('sli-audit', reason='replaced', author='charlie')

    row = (await session.execute(
        select(SLIDefinition).where(SLIDefinition.name == 'sli-audit')
    )).scalar_one()
    assert row.active is False
    assert row.deactivated_by == 'charlie'
    assert row.deactivation_reason == 'replaced'
    assert row.deactivated_at is not None


async def test_slo_deactivate_sets_audit_columns(session: AsyncSession) -> None:
    repo = SLORepository(session)
    sli_repo = SLIRepository(session)
    sli = await sli_repo.create(
        name='sli-for-slo-audit',
        adapter_type='prometheus',
        indicators={'metric': 'query'},
    )
    await repo.create(
        name='slo-audit',
        total_score_pass_threshold=90,
        total_score_warning_threshold=75,
        sli_definition_id=sli.id,
        objectives=[],
    )

    count = await repo.deactivate('slo-audit', reason='obsolete', author='dave')

    assert count == 1
    row = (await session.execute(
        select(SLODefinition).where(SLODefinition.name == 'slo-audit')
    )).scalar_one()
    assert row.active is False
    assert row.deactivated_by == 'dave'
    assert row.deactivation_reason == 'obsolete'
    assert row.deactivated_at is not None


async def test_slo_group_deactivate_sets_audit_columns(session: AsyncSession) -> None:
    sli_repo = SLIRepository(session)
    slo_repo = SLORepository(session)
    sli = await sli_repo.create(
        name='sli-for-group-audit',
        adapter_type='prometheus',
        indicators={'metric': 'query'},
    )
    template = await slo_repo.create(
        name='template-for-group-audit',
        total_score_pass_threshold=90,
        total_score_warning_threshold=75,
        sli_definition_id=sli.id,
        objectives=[],
        kind='template',
    )

    group_repo = SLOGroupRepository(session)
    group = await group_repo.create(
        name='group-audit',
        template_slo_definition_id=template.id,
        gen_variables={'env': ['prod']},
    )

    await group_repo.deactivate('group-audit', reason='retired', author='eve')

    row = (await session.execute(
        select(SLOGroup).where(SLOGroup.name == 'group-audit')
    )).scalar_one()
    assert row.active is False
    assert row.deactivated_by == 'eve'
    assert row.deactivation_reason == 'retired'
    assert row.deactivated_at is not None
```

- [ ] **Step 2: Write invalidation author integration test**

Create `api/tests/db/test_invalidation_author.py`:

```python
"""Integration test: evaluation invalidation persists author."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quality_gate.repository import EvaluationRepository

pytestmark = pytest.mark.integration


async def test_invalidation_stores_author(
    session: AsyncSession,
    seeded_evaluation_id: str,
) -> None:
    repo = EvaluationRepository(session)
    ev = await repo.invalidate(
        seeded_evaluation_id,
        note='bad data',
        author='frank',
    )
    assert ev is not None
    assert ev.invalidated is True
    assert ev.invalidation_note == 'bad data'
    assert ev.invalidation_author == 'frank'
```

Note: `seeded_evaluation_id` is a fixture that should exist in `api/tests/db/conftest.py`. If it doesn't, you'll need to create an evaluation record in the test setup. Check existing integration test fixtures for the pattern.

- [ ] **Step 3: Start test environment and run integration tests**

Run: `just test-env`

Then: `./scripts/api-test.sh --tail 20 tests/db/test_deactivation_audit.py tests/db/test_invalidation_author.py -v`

Fix any failures.

- [ ] **Step 4: Commit**

```bash
git add api/tests/db/test_deactivation_audit.py api/tests/db/test_invalidation_author.py
git commit -m "test: add integration tests for deactivation audit trail and invalidation author"
```

---

## Task 7: Frontend — Update API Functions

**Files:**
- Modify: `ui/src/features/datasources/api.ts:42-45`
- Modify: `ui/src/features/slis/api.ts:38-43`
- Modify: `ui/src/features/slos/api.ts:67-70`
- Modify: `ui/src/features/slo-groups/api.ts:38-43`
- Modify: `ui/src/features/evaluations/api.ts:127-138`

- [ ] **Step 1: Update deleteDatasource**

In `ui/src/features/datasources/api.ts`, replace the `deleteDatasource` function:

```typescript
export async function deleteDatasource(
  name: string, reason: string, author: string,
): Promise<void> {
  const res = await fetch(`${BASE}/datasources/${encodeURIComponent(name)}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason, author }),
  })
  if (!res.ok) throw new Error(`deleteDatasource: ${res.status}`)
}
```

- [ ] **Step 2: Update deleteSliDefinition**

In `ui/src/features/slis/api.ts`, replace the `deleteSliDefinition` function:

```typescript
export async function deleteSliDefinition(
  name: string, reason: string, author: string,
): Promise<void> {
  const res = await fetch(`${BASE}/sli-definitions/${encodeURIComponent(name)}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason, author }),
  })
  if (!res.ok) throw new Error(`deleteSliDefinition: ${res.status}`)
}
```

- [ ] **Step 3: Update deleteSlo**

In `ui/src/features/slos/api.ts`, replace the `deleteSlo` function:

```typescript
export async function deleteSlo(
  name: string, reason: string, author: string,
): Promise<void> {
  const res = await fetch(`${BASE}/slo-definitions/${encodeURIComponent(name)}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason, author }),
  })
  if (!res.ok) throw new Error(`deleteSlo: ${res.status}`)
}
```

- [ ] **Step 4: Update deleteSloGroup**

In `ui/src/features/slo-groups/api.ts`, replace the `deleteSloGroup` function:

```typescript
export async function deleteSloGroup(
  name: string, reason: string, author: string,
): Promise<void> {
  const res = await fetch(`${BASE}/slo-groups/${encodeURIComponent(name)}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason, author }),
  })
  if (!res.ok) throw new Error(`deleteSloGroup: ${res.status}`)
}
```

- [ ] **Step 5: Update invalidateEvaluation**

In `ui/src/features/evaluations/api.ts`, replace the `invalidateEvaluation` function:

```typescript
export async function invalidateEvaluation(
  evalId: string,
  note: string,
  author: string,
): Promise<EvaluationSummary> {
  const res = await fetch(`${BASE}/evaluations/${evalId}/invalidate`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ invalidation_note: note, author }),
  })
  if (!res.ok) throw new Error(`invalidateEvaluation: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/datasources/api.ts ui/src/features/slis/api.ts ui/src/features/slos/api.ts ui/src/features/slo-groups/api.ts ui/src/features/evaluations/api.ts
git commit -m "feat(ui): send reason/author in all delete and invalidation API calls"
```

---

## Task 8: Frontend — Update Hooks

**Files:**
- Modify: `ui/src/features/datasources/hooks.ts:42-48`
- Modify: `ui/src/features/slis/hooks.ts:48-56`
- Modify: `ui/src/features/slos/hooks.ts:44-52`
- Modify: `ui/src/features/slo-groups/hooks.ts:43-52`
- Modify: `ui/src/features/evaluations/hooks.ts:93-104`

- [ ] **Step 1: Update useDeleteDatasource**

In `ui/src/features/datasources/hooks.ts`, update the hook:

```typescript
export function useDeleteDatasource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { name: string; reason: string; author: string }) =>
      deleteDatasource(payload.name, payload.reason, payload.author),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: datasourceKeys.all }) },
  })
}
```

- [ ] **Step 2: Update useDeleteSli**

In `ui/src/features/slis/hooks.ts`, update the hook:

```typescript
export function useDeleteSli() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { name: string; reason: string; author: string }) =>
      deleteSliDefinition(payload.name, payload.reason, payload.author),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sliKeys.all })
    },
  })
}
```

- [ ] **Step 3: Update useDeleteSlo**

In `ui/src/features/slos/hooks.ts`, update the hook:

```typescript
export function useDeleteSlo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { name: string; reason: string; author: string }) =>
      deleteSlo(payload.name, payload.reason, payload.author),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}
```

- [ ] **Step 4: Update useDeleteSloGroup**

In `ui/src/features/slo-groups/hooks.ts`, update the hook:

```typescript
export function useDeleteSloGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { name: string; reason: string; author: string }) =>
      deleteSloGroup(payload.name, payload.reason, payload.author),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: sloGroupKeys.all })
      void qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}
```

- [ ] **Step 5: Fix useInvalidateEvaluation to pass author through**

In `ui/src/features/evaluations/hooks.ts`, update the hook to pass `author`:

```typescript
export function useInvalidateEvaluation(evalId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { note: string; author: string }) =>
      invalidateEvaluation(evalId, payload.note, payload.author),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evaluationKeys.detail(evalId) })
      qc.invalidateQueries({ queryKey: evaluationKeys.all })
      qc.invalidateQueries({ queryKey: evaluationKeys.allNames })
      qc.invalidateQueries({ queryKey: evaluationKeys.allHeatmaps })
    },
  })
}
```

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/datasources/hooks.ts ui/src/features/slis/hooks.ts ui/src/features/slos/hooks.ts ui/src/features/slo-groups/hooks.ts ui/src/features/evaluations/hooks.ts
git commit -m "feat(ui): update delete/invalidation hooks to pass reason and author"
```

---

## Task 9: Frontend — Wire Detail Views to DeletionConfirmForm

**Files:**
- Modify: `ui/src/features/registry/details/DatasourceDetailView.tsx`
- Modify: `ui/src/features/registry/details/SliDetailView.tsx`
- Modify: `ui/src/features/registry/details/SloDetailView.tsx`
- Modify: `ui/src/features/registry/details/SloGroupDetailView.tsx`

- [ ] **Step 1: Update DatasourceDetailView**

In `ui/src/features/registry/details/DatasourceDetailView.tsx`:

Update `handleDelete` (line 34):

```typescript
  function handleDelete(reason: string, author: string) {
    deleteMutation.mutate({ name: ds!.name, reason, author })
    setShowDeleteConfirm(false)
  }
```

Update the `DeletionConfirmForm` usage (line 80) — set `requireReason={true}` and add `requireAuthor={true}`:

```tsx
              <DeletionConfirmForm
                title={`Delete datasource "${ds.name}"?`}
                onConfirm={handleDelete}
                onCancel={() => setShowDeleteConfirm(false)}
                confirmLabel="Delete"
                pendingLabel="Deleting…"
                isPending={deleteMutation.isPending}
                requireReason={true}
                requireAuthor={true}
              />
```

- [ ] **Step 2: Update SliDetailView**

In `ui/src/features/registry/details/SliDetailView.tsx`:

Update `handleDeactivate` (line 55):

```typescript
  function handleDeactivate(reason: string, author: string) {
    deleteMutation.mutate({ name: sli!.name, reason, author })
    setShowDeleteConfirm(false)
  }
```

Update the `DeletionConfirmForm` usage (line 124) — set `requireReason={true}` and add `requireAuthor={true}`:

```tsx
              <DeletionConfirmForm
                title={`Deactivate SLI "${sli.name}"?`}
                onConfirm={handleDeactivate}
                onCancel={() => setShowDeleteConfirm(false)}
                confirmLabel="Deactivate"
                pendingLabel="Deactivating…"
                isPending={deleteMutation.isPending}
                requireReason={true}
                requireAuthor={true}
              />
```

- [ ] **Step 3: Update SloDetailView**

In `ui/src/features/registry/details/SloDetailView.tsx`:

Update `handleDeactivate` (line 55):

```typescript
  function handleDeactivate(reason: string, author: string) {
    deleteMutation.mutate({ name: slo!.name, reason, author })
    setShowDeleteConfirm(false)
  }
```

Update the `DeletionConfirmForm` usage — set `requireReason={true}` and add `requireAuthor={true}`:

```tsx
              <DeletionConfirmForm
                title={`Deactivate SLO "${slo.name}"?`}
                onConfirm={handleDeactivate}
                onCancel={() => setShowDeleteConfirm(false)}
                confirmLabel="Deactivate"
                pendingLabel="Deactivating…"
                isPending={deleteMutation.isPending}
                requireReason={true}
                requireAuthor={true}
              />
```

- [ ] **Step 4: Update SloGroupDetailView**

In `ui/src/features/registry/details/SloGroupDetailView.tsx`:

Update `handleDelete` (line 34):

```typescript
  function handleDelete(reason: string, author: string) {
    deleteMutation.mutate({ name: group!.name, reason, author })
    setShowDelete(false)
  }
```

Update the `DeletionConfirmForm` usage (line 249) — set `requireReason={true}` and add `requireAuthor={true}`:

```tsx
              <DeletionConfirmForm
                title={`Delete group "${group.name}"?`}
                onConfirm={handleDelete}
                onCancel={() => setShowDelete(false)}
                confirmLabel="Delete"
                pendingLabel="Deleting…"
                isPending={deleteMutation.isPending}
                requireReason={true}
                requireAuthor={true}
              />
```

- [ ] **Step 5: Run UI lint and type check**

Run: `./scripts/ui-lint.sh --tail 10`

Then: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`

Fix any errors.

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/registry/details/DatasourceDetailView.tsx ui/src/features/registry/details/SliDetailView.tsx ui/src/features/registry/details/SloDetailView.tsx ui/src/features/registry/details/SloGroupDetailView.tsx
git commit -m "feat(ui): require reason and author in all deletion confirmation forms"
```

---

## Task 10: Run Full Test Suite and Final Verification

- [ ] **Step 1: Run all API unit tests**

Run: `./scripts/api-test.sh --tail 5`

All should pass. Fix any regressions.

- [ ] **Step 2: Run integration tests**

Run: `just test-env` (if not already running)

Then: `./scripts/api-test.sh --tail 20 -m integration -v`

All should pass.

- [ ] **Step 3: Run UI component tests**

Run: `./scripts/ui-test.sh --tail 10`

All should pass. Fix any regressions from changed hook signatures.

- [ ] **Step 4: Run full lint and typecheck**

Run: `uv run ruff check api/`

Run: `uv run mypy api/app`

Run: `./scripts/ui-lint.sh --tail 10`

- [ ] **Step 5: Commit any fixes**

If any fixes were needed:

```bash
git add -u
git commit -m "fix: address test and lint issues from audit trail feature"
```
