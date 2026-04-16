# Evaluation Trend Chart — Note Annotations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface chart-worthy annotation notes directly on `MetricTrendBlock` trend charts via a new `AnnotationCategory` entity, a per-chart on/off toggle, a dedicated override ring on overridden points, and CRUD UI for managing categories.

**Architecture:** New global `annotation_category` table with FK from `evaluation_annotations.category_id`; regenerated migrations (no prod users); ECharts `markPoint` driven by a shared `buildNoteMarkPoint` helper; override visual driven by `Evaluation.originalOutcome`, independent of categories.

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy async / Alembic, React 19 / Vite / React Query / ECharts, pytest (unit + integration marker), Vitest + RTL.

**Spec:** `docs/superpowers/specs/2026-04-16-eval-trend-note-annotations-design.md`

---

## File map

### Backend — create

- `api/tropek/modules/quality_gate/repositories/annotation_category.py` — CRUD for categories.
- `api/tropek/modules/quality_gate/schemas/annotation_categories.py` — Pydantic schemas + palette enum.
- `api/tests/db/test_annotation_category_repository.py` — integration tests.
- `api/tests/db/test_note_category_router.py` — router integration tests.

### Backend — modify

- `api/tropek/db/models.py` — add `AnnotationCategory`, add `category_id` FK to `EvaluationAnnotation`, drop `category` text column, add relationship.
- `api/tropek/modules/quality_gate/schemas/__init__.py` — export new schemas.
- `api/tropek/modules/quality_gate/schemas/annotations.py` — replace `category: str | None` with `category_id: UUID`; embed `category: AnnotationCategoryRead` on read.
- `api/tropek/modules/quality_gate/repositories/annotation.py` — replace `category: str | None` param with `category_id: UUID`.
- `api/tropek/modules/quality_gate/shared/dependencies.py` — register new repo in `QualityGateRepos`.
- `api/tropek/modules/quality_gate/router.py` — add `/note-categories` router; update annotation endpoints to take `category_id`.
- `api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py` — look up `re-evaluation` category by name before calling `add_annotation`.
- `api/alembic/versions/002_timescaledb_hypertable_and_seed_data.py` — seed four category rows.
- `scripts/seed_evaluations.py` — seed a handful of annotations spanning each visible category.

### Frontend — create

- `ui/src/features/note-categories/domain.ts`
- `ui/src/features/note-categories/mappers.ts`
- `ui/src/features/note-categories/api.ts`
- `ui/src/features/note-categories/hooks.ts`
- `ui/src/features/note-categories/ui-types.ts` — palette token → CSS var resolver.
- `ui/src/features/note-categories/index.ts`
- `ui/src/features/note-categories/mappers.test.ts`
- `ui/src/features/note-categories/components/CategoryManagementPage.tsx`
- `ui/src/features/note-categories/components/CategoryRow.tsx`
- `ui/src/features/note-categories/components/CategoryForm.tsx`
- `ui/src/features/note-categories/components/CategoryForm.test.tsx`
- `ui/src/lib/chartAnnotations.ts`
- `ui/src/lib/chartAnnotations.test.ts`

### Frontend — modify

- `ui/src/generated/api.ts` — regenerated via `just codegen`.
- `ui/src/features/evaluations/domain.ts` — `Annotation.category: NoteCategory` + `categoryId: string` in place of `category: string | null`; `TrendPoint.overridden: boolean`.
- `ui/src/features/evaluations/mappers.ts` — update `dtoToAnnotation`, update `dtoToTrendPoint` to populate `overridden`.
- `ui/src/features/evaluations/api.ts` — add `useTrendAnnotations` fetch; update `addAnnotation`/`addRunAnnotation` to send `category_id`.
- `ui/src/features/evaluations/hooks.ts` — add `useTrendAnnotations` wrapper.
- `ui/src/features/evaluations/components/AddNoteForm.tsx` — dropdown from `useCategories()`, default `info`.
- `ui/src/features/evaluations/components/NoteEntry.tsx` — use `a.category.label` + palette color.
- `ui/src/features/evaluations/components/EvaluationNotesSection.tsx` — gear icon linking to `/settings/note-categories`.
- `ui/src/features/evaluations/hooks/useMetricTrendState.ts` — accept `annotations` + `categories` + `notesVisible`; include markPoint when visible.
- `ui/src/features/evaluations/components/MetricTrendBlock.tsx` — fetch annotations, toggle button, pass through.
- `ui/src/App.tsx` (or wherever routes live) — add `/settings/note-categories` route.

### Tests — new

Backend and frontend tests listed under each task below.

---

## Phase 1 — Backend data model

### Task 1: Add `AnnotationCategory` ORM model

**Files:**
- Modify: `api/tropek/db/models.py`

- [ ] **Step 1: Add the ORM class**

In `api/tropek/db/models.py`, add (near `EvaluationAnnotation`):

```python
class AnnotationCategory(Base):
    """Category taxonomy for evaluation annotations.

    System rows (is_system=True) cannot be deleted; their name is immutable,
    but show_on_graph remains toggleable.
    """

    __tablename__ = 'annotation_categories'

    id:             Mapped[uuid.UUID]  = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:           Mapped[str]        = mapped_column(Text, unique=True, nullable=False)
    label:          Mapped[str]        = mapped_column(Text, nullable=False)
    color:          Mapped[str]        = mapped_column(Text, nullable=False)
    show_on_graph:  Mapped[bool]       = mapped_column(Boolean, nullable=False, server_default=text('true'))
    is_system:      Mapped[bool]       = mapped_column(Boolean, nullable=False, server_default=text('false'))
    created_at:     Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
```

- [ ] **Step 2: Replace `category` text column with `category_id` FK**

In the `EvaluationAnnotation` class, remove:

```python
category:          Mapped[str | None]       = mapped_column(Text, nullable=True)
```

Add:

```python
category_id:       Mapped[uuid.UUID]        = mapped_column(UUID, ForeignKey('annotation_categories.id'), nullable=False)
category:          Mapped['AnnotationCategory'] = relationship('AnnotationCategory')
```

- [ ] **Step 3: Commit**

```bash
git add api/tropek/db/models.py
git commit -m "feat(annotations): add AnnotationCategory model and category_id FK"
```

---

### Task 2: Regenerate migrations

**Files:**
- Regenerate: `api/alembic/versions/001_initial_schema.py`

- [ ] **Step 1: Run regen script**

Run: `./scripts/db-regen-migrations.sh`

Expected: script finishes with "Migration regeneration complete." and the integration DB comes up cleanly.

- [ ] **Step 2: Sanity-check the generated 001**

Run: `grep -n 'annotation_categories' api/alembic/versions/001_initial_schema.py`
Expected: one or more matches (the new table + its FK).

- [ ] **Step 3: Commit**

```bash
git add api/alembic/versions/001_initial_schema.py
git commit -m "chore(db): regenerate initial schema for annotation categories"
```

---

### Task 3: Seed categories in migration 002

**Files:**
- Modify: `api/alembic/versions/002_timescaledb_hypertable_and_seed_data.py`

- [ ] **Step 1: Extend upgrade() with category seeds**

Append to `upgrade()` after the asset-types block:

```python
    op.execute("""
        INSERT INTO annotation_categories (id, name, label, color, show_on_graph, is_system) VALUES
            (gen_random_uuid(), 'failure',       'Failure',       'red',   true,  false),
            (gen_random_uuid(), 'info',          'Info',          'sky',   true,  false),
            (gen_random_uuid(), 'investigation', 'Investigation', 'amber', true,  false),
            (gen_random_uuid(), 're-evaluation', 'Re-eval',       'gray',  false, true)
        ON CONFLICT (name) DO NOTHING
    """)
```

- [ ] **Step 2: Extend downgrade() with category removal**

Append to `downgrade()`:

```python
    op.execute("""
        DELETE FROM annotation_categories
        WHERE name IN ('failure', 'info', 'investigation', 're-evaluation')
    """)
```

- [ ] **Step 3: Verify by restarting test infra**

Run: `just test-env-down && just test-env`
Expected: test DB comes up with all migrations applied cleanly.

- [ ] **Step 4: Verify rows present via psql**

Run: `docker exec -i tropek-timescale-test psql -U tropek -d tropek_test -c "SELECT name, show_on_graph, is_system FROM annotation_categories ORDER BY name"`
Expected: 4 rows with the values above.

- [ ] **Step 5: Commit**

```bash
git add api/alembic/versions/002_timescaledb_hypertable_and_seed_data.py
git commit -m "feat(db): seed annotation categories"
```

---

## Phase 2 — Backend repositories and schemas

### Task 4: `AnnotationCategory` Pydantic schemas

**Files:**
- Create: `api/tropek/modules/quality_gate/schemas/annotation_categories.py`
- Modify: `api/tropek/modules/quality_gate/schemas/__init__.py`

- [ ] **Step 1: Write schemas**

```python
"""Pydantic schemas for annotation categories."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from tropek.modules.common.schemas import StrictInput


class CategoryColor(str, Enum):
    SKY = 'sky'
    GREEN = 'green'
    AMBER = 'amber'
    RED = 'red'
    PURPLE = 'purple'
    PINK = 'pink'
    SLATE = 'slate'
    GRAY = 'gray'


LabelStr = Annotated[str, Field(min_length=1, max_length=12)]
NameStr = Annotated[str, Field(min_length=1, max_length=40, pattern=r'^[a-z][a-z0-9\-]*$')]


class AnnotationCategoryRead(BaseModel):
    id: uuid.UUID
    name: str
    label: str
    color: CategoryColor
    show_on_graph: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AnnotationCategoryCreate(StrictInput):
    name: NameStr
    label: LabelStr
    color: CategoryColor
    show_on_graph: bool = True


class AnnotationCategoryUpdate(StrictInput):
    name: NameStr | None = None
    label: LabelStr | None = None
    color: CategoryColor | None = None
    show_on_graph: bool | None = None
```

- [ ] **Step 2: Export from schemas `__init__.py`**

Add to `api/tropek/modules/quality_gate/schemas/__init__.py`:

```python
from tropek.modules.quality_gate.schemas.annotation_categories import (
    AnnotationCategoryCreate,
    AnnotationCategoryRead,
    AnnotationCategoryUpdate,
    CategoryColor,
)
```

Include the new names in `__all__`.

- [ ] **Step 3: Commit**

```bash
git add api/tropek/modules/quality_gate/schemas/
git commit -m "feat(schemas): add AnnotationCategory schemas"
```

---

### Task 5: `AnnotationCategoryRepository` (TDD)

**Files:**
- Create: `api/tropek/modules/quality_gate/repositories/annotation_category.py`
- Create: `api/tests/db/test_annotation_category_repository.py`

- [ ] **Step 1: Write failing integration tests**

Create `api/tests/db/test_annotation_category_repository.py`:

```python
"""Integration tests for AnnotationCategoryRepository."""

from __future__ import annotations

import uuid

import pytest

from tropek.modules.quality_gate.repositories.annotation_category import (
    AnnotationCategoryRepository,
    CategoryInUseError,
    SystemCategoryError,
)

pytestmark = pytest.mark.integration


async def test_list_all_returns_seeded_rows(db_session):
    repo = AnnotationCategoryRepository(db_session)
    rows = await repo.list_all()
    names = {r.name for r in rows}
    assert {'info', 'failure', 'investigation', 're-evaluation'} <= names


async def test_get_by_name_returns_category(db_session):
    repo = AnnotationCategoryRepository(db_session)
    cat = await repo.get_by_name('info')
    assert cat is not None
    assert cat.is_system is False


async def test_create_adds_row(db_session):
    repo = AnnotationCategoryRepository(db_session)
    created = await repo.create(name='release', label='Release', color='green', show_on_graph=True)
    assert created.id is not None
    assert created.is_system is False


async def test_update_modifies_fields(db_session):
    repo = AnnotationCategoryRepository(db_session)
    created = await repo.create(name='incident', label='Incident', color='red', show_on_graph=True)
    updated = await repo.update(created.id, label='Inc', show_on_graph=False)
    assert updated.label == 'Inc'
    assert updated.show_on_graph is False


async def test_update_rejects_name_change_on_system(db_session):
    repo = AnnotationCategoryRepository(db_session)
    re_eval = await repo.get_by_name('re-evaluation')
    assert re_eval is not None
    with pytest.raises(SystemCategoryError):
        await repo.update(re_eval.id, name='renamed')


async def test_delete_rejects_system_rows(db_session):
    repo = AnnotationCategoryRepository(db_session)
    re_eval = await repo.get_by_name('re-evaluation')
    assert re_eval is not None
    with pytest.raises(SystemCategoryError):
        await repo.delete(re_eval.id)


async def test_delete_reassigns_referencing_annotations(db_session, seeded_evaluation_run):
    """Deleting a category with references must move them to 'info' and return the count."""
    repo = AnnotationCategoryRepository(db_session)
    dummy = await repo.create(name='temp', label='Temp', color='purple', show_on_graph=True)

    # Create an annotation referencing this category
    from tropek.modules.quality_gate.repositories.annotation import AnnotationRepository
    ann_repo = AnnotationRepository(db_session)
    await ann_repo.add_run_annotation(
        seeded_evaluation_run.id,
        content='x',
        category_id=dummy.id,
    )
    await db_session.commit()

    reassigned = await repo.delete(dummy.id)
    assert reassigned == 1

    info = await repo.get_by_name('info')
    assert info is not None
    refreshed = await ann_repo.list_for_run(seeded_evaluation_run.id)
    assert refreshed[0].category_id == info.id


async def test_delete_returns_zero_when_unused(db_session):
    repo = AnnotationCategoryRepository(db_session)
    dummy = await repo.create(name='unused', label='Unused', color='pink', show_on_graph=True)
    reassigned = await repo.delete(dummy.id)
    assert reassigned == 0
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `./scripts/api-test.sh --tail 30 -m integration tests/db/test_annotation_category_repository.py -v`
Expected: all tests fail with ImportError (module doesn't exist yet).

- [ ] **Step 3: Implement the repository**

Create `api/tropek/modules/quality_gate/repositories/annotation_category.py`:

```python
"""Annotation category repository — CRUD for annotation_categories."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import AnnotationCategory, EvaluationAnnotation


class SystemCategoryError(Exception):
    """Raised when attempting to mutate a system category in a disallowed way."""


class CategoryInUseError(Exception):
    """Raised when a category is referenced and cannot be deleted."""


class AnnotationCategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[AnnotationCategory]:
        result = await self._session.execute(
            select(AnnotationCategory).order_by(AnnotationCategory.name)
        )
        return list(result.scalars().all())

    async def get_by_id(self, category_id: uuid.UUID) -> AnnotationCategory | None:
        result = await self._session.execute(
            select(AnnotationCategory).where(AnnotationCategory.id == category_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> AnnotationCategory | None:
        result = await self._session.execute(
            select(AnnotationCategory).where(AnnotationCategory.name == name)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        name: str,
        label: str,
        color: str,
        show_on_graph: bool = True,
    ) -> AnnotationCategory:
        row = AnnotationCategory(
            id=uuid.uuid4(),
            name=name,
            label=label,
            color=color,
            show_on_graph=show_on_graph,
            is_system=False,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def update(
        self,
        category_id: uuid.UUID,
        *,
        name: str | None = None,
        label: str | None = None,
        color: str | None = None,
        show_on_graph: bool | None = None,
    ) -> AnnotationCategory:
        row = await self.get_by_id(category_id)
        if row is None:
            raise LookupError(f'category {category_id} not found')
        if row.is_system and name is not None and name != row.name:
            raise SystemCategoryError('cannot rename a system category')

        values: dict[str, object] = {}
        if name is not None:
            values['name'] = name
        if label is not None:
            values['label'] = label
        if color is not None:
            values['color'] = color
        if show_on_graph is not None:
            values['show_on_graph'] = show_on_graph
        if values:
            await self._session.execute(
                update(AnnotationCategory).where(AnnotationCategory.id == category_id).values(**values)
            )
            await self._session.flush()
        refreshed = await self.get_by_id(category_id)
        assert refreshed is not None
        return refreshed

    async def delete(self, category_id: uuid.UUID) -> int:
        row = await self.get_by_id(category_id)
        if row is None:
            raise LookupError(f'category {category_id} not found')
        if row.is_system:
            raise SystemCategoryError('cannot delete a system category')

        info = await self.get_by_name('info')
        if info is None:
            raise LookupError("default 'info' category missing")

        reassigned = await self._session.execute(
            update(EvaluationAnnotation)
            .where(EvaluationAnnotation.category_id == category_id)
            .values(category_id=info.id)
        )
        await self._session.execute(
            delete(AnnotationCategory).where(AnnotationCategory.id == category_id)
        )
        await self._session.flush()
        return reassigned.rowcount or 0
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `./scripts/api-test.sh --tail 30 -m integration tests/db/test_annotation_category_repository.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/tropek/modules/quality_gate/repositories/annotation_category.py api/tests/db/test_annotation_category_repository.py
git commit -m "feat(repo): add AnnotationCategoryRepository"
```

---

### Task 6: Update `AnnotationRepository` to use `category_id`

**Files:**
- Modify: `api/tropek/modules/quality_gate/repositories/annotation.py`

- [ ] **Step 1: Update method signatures**

In `add_annotation`, `add_run_annotation`, and `update_annotation`, replace every `category: str | None = None` parameter with `category_id: uuid.UUID | None = None` (required on the two add methods — drop the default). In the resulting `EvaluationAnnotation(...)` and `values[...]` assignments, replace `category=category` with `category_id=category_id`.

After edits `add_annotation` signature must read:

```python
async def add_annotation(
    self,
    slo_evaluation_id: uuid.UUID,
    *,
    content: str,
    category_id: uuid.UUID,
    author: str | None = None,
    tags: dict[str, Any] | None = None,
    note_group_id: uuid.UUID | None = None,
    note_group_name: str | None = None,
) -> EvaluationAnnotation:
```

Same shape for `add_run_annotation`.

`update_annotation` keeps `category_id: uuid.UUID | None = None`.

- [ ] **Step 2: Commit**

```bash
git add api/tropek/modules/quality_gate/repositories/annotation.py
git commit -m "refactor(repo): annotation takes category_id not text"
```

---

### Task 7: Register `AnnotationCategoryRepository` in DI

**Files:**
- Modify: `api/tropek/modules/quality_gate/shared/dependencies.py`

- [ ] **Step 1: Read current dependencies module**

Open `api/tropek/modules/quality_gate/shared/dependencies.py` and inspect the `QualityGateRepos` dataclass and its factory.

- [ ] **Step 2: Add the category repo to `QualityGateRepos`**

Add import:

```python
from tropek.modules.quality_gate.repositories.annotation_category import AnnotationCategoryRepository
```

Add field to the `QualityGateRepos` dataclass:

```python
category_repo: AnnotationCategoryRepository
```

Populate it in the factory (same `AsyncSession` as `annotation_repo`):

```python
category_repo=AnnotationCategoryRepository(session),
```

- [ ] **Step 3: Commit**

```bash
git add api/tropek/modules/quality_gate/shared/dependencies.py
git commit -m "feat(di): register AnnotationCategoryRepository"
```

---

### Task 8: Update `AnnotationRead`/`AnnotationCreate` schemas

**Files:**
- Modify: `api/tropek/modules/quality_gate/schemas/annotations.py`

- [ ] **Step 1: Replace text `category` with id + embedded**

Edit the file. Remove `category: str | None` from `AnnotationRead`, `AnnotationCreate`, `AnnotationUpdate`. Add:

In `AnnotationRead`:

```python
category_id: uuid.UUID
category: AnnotationCategoryRead
```

In `AnnotationCreate`:

```python
category_id: uuid.UUID
```

In `AnnotationUpdate`:

```python
category_id: uuid.UUID | None = None
```

Import `AnnotationCategoryRead`:

```python
from tropek.modules.quality_gate.schemas.annotation_categories import AnnotationCategoryRead
```

- [ ] **Step 2: Commit**

```bash
git add api/tropek/modules/quality_gate/schemas/annotations.py
git commit -m "refactor(schemas): Annotation now carries category_id + embedded category"
```

---

### Task 9: Update `re_evaluation_service` to resolve category id

**Files:**
- Modify: `api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py`

- [ ] **Step 1: Look up re-evaluation category before calling add_annotation**

Find the call site currently passing `category='re-evaluation'`. Replace with a lookup via the repos object:

```python
re_eval_cat = await repos.category_repo.get_by_name('re-evaluation')
if re_eval_cat is None:
    raise RuntimeError("seeded 're-evaluation' category missing")

await repos.annotation_repo.add_annotation(
    slo_eval.id,
    content=note_text,
    category_id=re_eval_cat.id,
    author=author,
    note_group_id=group_id,
    note_group_name=group_name,
)
```

(Adapt variable names to match the existing surroundings.)

- [ ] **Step 2: Run re-eval unit tests**

Run: `./scripts/api-test.sh --tail 30 tests/ -k re_evaluation -v`
Expected: all re-eval tests pass (or fail with a clear missing-category signal that you then resolve by ensuring the integration fixture seeds categories).

- [ ] **Step 3: Commit**

```bash
git add api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py
git commit -m "refactor(re-eval): resolve re-evaluation category_id before annotation insert"
```

---

## Phase 3 — Backend router

### Task 10: Category CRUD router

**Files:**
- Create: `api/tests/db/test_note_category_router.py`
- Modify: `api/tropek/modules/quality_gate/router.py`

- [ ] **Step 1: Write failing router tests**

Create `api/tests/db/test_note_category_router.py`:

```python
"""Integration tests for /note-categories router."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_list_returns_seeded(client):
    res = await client.get('/note-categories')
    assert res.status_code == 200
    names = {row['name'] for row in res.json()}
    assert {'info', 'failure', 'investigation', 're-evaluation'} <= names


async def test_create_category(client):
    res = await client.post('/note-categories', json={
        'name': 'release', 'label': 'Release', 'color': 'green', 'show_on_graph': True,
    })
    assert res.status_code == 201
    body = res.json()
    assert body['name'] == 'release'
    assert body['is_system'] is False


async def test_create_rejects_bad_color(client):
    res = await client.post('/note-categories', json={
        'name': 'neon', 'label': 'Neon', 'color': 'fuschia', 'show_on_graph': True,
    })
    assert res.status_code == 422


async def test_create_rejects_long_label(client):
    res = await client.post('/note-categories', json={
        'name': 'long', 'label': 'ThisLabelIsWayTooLong', 'color': 'sky', 'show_on_graph': True,
    })
    assert res.status_code == 422


async def test_update_system_label_ok(client):
    """Renaming a system row is forbidden, but updating label is allowed."""
    list_res = await client.get('/note-categories')
    re_eval = next(r for r in list_res.json() if r['name'] == 're-evaluation')

    res = await client.patch(f'/note-categories/{re_eval["id"]}', json={'label': 'Re-Eval'})
    assert res.status_code == 200


async def test_update_system_name_rejected(client):
    list_res = await client.get('/note-categories')
    re_eval = next(r for r in list_res.json() if r['name'] == 're-evaluation')

    res = await client.patch(f'/note-categories/{re_eval["id"]}', json={'name': 'renamed'})
    assert res.status_code == 409


async def test_delete_system_rejected(client):
    list_res = await client.get('/note-categories')
    re_eval = next(r for r in list_res.json() if r['name'] == 're-evaluation')

    res = await client.delete(f'/note-categories/{re_eval["id"]}')
    assert res.status_code == 409


async def test_delete_non_system_returns_reassigned_count(client):
    create = await client.post('/note-categories', json={
        'name': 'ephemeral', 'label': 'Eph', 'color': 'purple', 'show_on_graph': True,
    })
    cat_id = create.json()['id']

    res = await client.delete(f'/note-categories/{cat_id}')
    assert res.status_code == 204
    assert res.headers.get('X-Reassigned-Annotations') == '0'
```

- [ ] **Step 2: Run the tests — they should fail (routes don't exist)**

Run: `./scripts/api-test.sh --tail 30 -m integration tests/db/test_note_category_router.py -v`
Expected: 404 on every request.

- [ ] **Step 3: Add routes**

In `api/tropek/modules/quality_gate/router.py`, add the following (place after the existing `# ---- Annotations ----` block or before — consistent with file's organisation):

```python
# ---- Note categories ----


@router.get('/note-categories', response_model=list[AnnotationCategoryRead])
async def list_note_categories(
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> list[AnnotationCategoryRead]:
    rows = await repos.category_repo.list_all()
    return [AnnotationCategoryRead.model_validate(r) for r in rows]


@router.post('/note-categories', response_model=AnnotationCategoryRead, status_code=201)
async def create_note_category(
    body: AnnotationCategoryCreate,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> AnnotationCategoryRead:
    created = await repos.category_repo.create(
        name=body.name,
        label=body.label,
        color=body.color.value,
        show_on_graph=body.show_on_graph,
    )
    return AnnotationCategoryRead.model_validate(created)


@router.patch('/note-categories/{category_id}', response_model=AnnotationCategoryRead)
async def update_note_category(
    category_id: uuid.UUID,
    body: AnnotationCategoryUpdate,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> AnnotationCategoryRead:
    try:
        updated = await repos.category_repo.update(
            category_id,
            name=body.name,
            label=body.label,
            color=body.color.value if body.color else None,
            show_on_graph=body.show_on_graph,
        )
    except SystemCategoryError as exc:
        raise ConflictError(str(exc)) from exc
    except LookupError as exc:
        raise NotFoundError('annotation_category', str(category_id)) from exc
    return AnnotationCategoryRead.model_validate(updated)


@router.delete('/note-categories/{category_id}', status_code=204)
async def delete_note_category(
    category_id: uuid.UUID,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> Response:
    try:
        reassigned = await repos.category_repo.delete(category_id)
    except SystemCategoryError as exc:
        raise ConflictError(str(exc)) from exc
    except LookupError as exc:
        raise NotFoundError('annotation_category', str(category_id)) from exc
    return Response(status_code=204, headers={'X-Reassigned-Annotations': str(reassigned)})
```

Add imports near the top:

```python
from fastapi import Response

from tropek.modules.quality_gate.repositories.annotation_category import SystemCategoryError
from tropek.modules.quality_gate.schemas import (
    AnnotationCategoryCreate,
    AnnotationCategoryRead,
    AnnotationCategoryUpdate,
)
```

- [ ] **Step 4: Update annotation create endpoints to pass `category_id`**

In `create_annotation` (line ~481) and `create_run_annotation` (line ~506), replace:

```python
category=body.category,
```

with:

```python
category_id=body.category_id,
```

- [ ] **Step 5: Run router tests — should pass**

Run: `./scripts/api-test.sh --tail 30 -m integration tests/db/test_note_category_router.py -v`
Expected: all pass.

- [ ] **Step 6: Run all API tests to catch regressions**

Run: `./scripts/api-test.sh --tail 20 -m integration tests/ -v`
Expected: all pass (including existing annotation tests — fixtures may need update; if so, add `category_id` to fixture calls).

- [ ] **Step 7: Commit**

```bash
git add api/tropek/modules/quality_gate/router.py api/tests/db/test_note_category_router.py
git commit -m "feat(router): add /note-categories CRUD and wire category_id through annotation endpoints"
```

---

## Phase 4 — Dev seeding

### Task 11: Seed example annotations for each visible category

**Files:**
- Modify: `scripts/seed_evaluations.py`

- [ ] **Step 1: Add annotation seeding helper**

At the end of the seed script (after evaluations are inserted), add:

```python
async def _seed_annotations(session: AsyncSession) -> None:
    """Attach a couple of annotations across visible categories so trend charts show pins in dev."""
    from tropek.modules.quality_gate.repositories.annotation import AnnotationRepository
    from tropek.modules.quality_gate.repositories.annotation_category import AnnotationCategoryRepository

    cat_repo = AnnotationCategoryRepository(session)
    ann_repo = AnnotationRepository(session)

    info = await cat_repo.get_by_name('info')
    failure = await cat_repo.get_by_name('failure')
    investigation = await cat_repo.get_by_name('investigation')
    assert info and failure and investigation

    # Pick the most-recent 3 runs and attach one annotation each.
    recent_runs = (await session.execute(
        select(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(3)
    )).scalars().all()
    if len(recent_runs) < 3:
        return

    await ann_repo.add_run_annotation(recent_runs[0].id, content='Routine deployment', author='seed', category_id=info.id)
    await ann_repo.add_run_annotation(recent_runs[1].id, content='Investigating timeout spike', author='seed', category_id=investigation.id)
    await ann_repo.add_run_annotation(recent_runs[2].id, content='Known flake — p99 latency', author='seed', category_id=failure.id)
    await session.commit()
```

Call `_seed_annotations(session)` from the main `main()` function after the existing eval seeding completes.

Ensure `EvaluationRun` and `select` are imported.

- [ ] **Step 2: Run the seed against dev DB**

Run: `just dev` (in a separate terminal) then invoke seeding per the project convention (`./scripts/dev-start.sh` usually handles this; if not, run the seed script directly with `uv run python scripts/seed_evaluations.py`).
Expected: no errors; when you open the UI trend charts, you see pins on three recent runs.

- [ ] **Step 3: Commit**

```bash
git add scripts/seed_evaluations.py
git commit -m "chore(seed): seed annotations spanning info/investigation/failure"
```

---

## Phase 5 — Frontend: regenerate types + note-categories feature

### Task 12: Regenerate UI DTOs

**Files:**
- Regenerate: `ui/src/generated/api.ts`

- [ ] **Step 1: Run codegen**

Run: `just codegen`
Expected: `ui/src/generated/api.ts` regenerates and includes `AnnotationCategoryRead`, `AnnotationCategoryCreate`, `AnnotationCategoryUpdate`, updated `AnnotationRead`.

- [ ] **Step 2: Verify TS compiles (will fail in mappers — expected)**

Run: `./scripts/ui-lint.sh --tail 20`
Expected: TS errors in `features/evaluations/mappers.ts` (old `category` string no longer on DTO). These get fixed in Task 16.

- [ ] **Step 3: Commit**

```bash
git add ui/src/generated/api.ts
git commit -m "chore(codegen): regenerate DTOs with AnnotationCategory"
```

---

### Task 13: `note-categories` feature — domain, mappers, palette

**Files:**
- Create: `ui/src/features/note-categories/domain.ts`
- Create: `ui/src/features/note-categories/ui-types.ts`
- Create: `ui/src/features/note-categories/mappers.ts`
- Create: `ui/src/features/note-categories/mappers.test.ts`

- [ ] **Step 1: `domain.ts`**

```ts
// ui/src/features/note-categories/domain.ts

export type CategoryColor =
  | 'sky' | 'green' | 'amber' | 'red' | 'purple' | 'pink' | 'slate' | 'gray'

export interface NoteCategory {
  id: string
  name: string
  label: string
  color: CategoryColor
  showOnGraph: boolean
  isSystem: boolean
  createdAt: Date
  updatedAt: Date | null
}

export interface NoteCategoryInput {
  name: string
  label: string
  color: CategoryColor
  showOnGraph: boolean
}

export interface NoteCategoryPatch {
  name?: string
  label?: string
  color?: CategoryColor
  showOnGraph?: boolean
}
```

- [ ] **Step 2: `ui-types.ts`** — palette token → theme-aware CSS var

```ts
// ui/src/features/note-categories/ui-types.ts
// Resolves a palette token to a CSS custom property that already adapts to the
// active theme (see ui/src/index.css). Pin + pill use these.

import type { CategoryColor } from './domain'

const PALETTE: Record<CategoryColor, { bg: string; fg: string }> = {
  sky:    { bg: 'var(--color-category-sky-bg)',    fg: 'var(--color-category-sky-fg)' },
  green:  { bg: 'var(--color-category-green-bg)',  fg: 'var(--color-category-green-fg)' },
  amber:  { bg: 'var(--color-category-amber-bg)',  fg: 'var(--color-category-amber-fg)' },
  red:    { bg: 'var(--color-category-red-bg)',    fg: 'var(--color-category-red-fg)' },
  purple: { bg: 'var(--color-category-purple-bg)', fg: 'var(--color-category-purple-fg)' },
  pink:   { bg: 'var(--color-category-pink-bg)',   fg: 'var(--color-category-pink-fg)' },
  slate:  { bg: 'var(--color-category-slate-bg)',  fg: 'var(--color-category-slate-fg)' },
  gray:   { bg: 'var(--color-category-gray-bg)',   fg: 'var(--color-category-gray-fg)' },
}

export function paletteOf(color: CategoryColor): { bg: string; fg: string } {
  return PALETTE[color]
}

export const PALETTE_OPTIONS: CategoryColor[] =
  ['sky', 'green', 'amber', 'red', 'purple', 'pink', 'slate', 'gray']
```

Also add CSS variables in `ui/src/index.css` for each `--color-category-*-bg` / `--color-category-*-fg` token (pick tones that read on both themes — see nearby conventions for `--status-*` vars and reuse same colors where sensible: e.g., `sky` ≈ the existing `#58a6ff`, `red` ≈ `--status-fail`, `amber` ≈ `--status-warning`, `green` ≈ `--status-pass`, etc.).

- [ ] **Step 3: `mappers.ts`**

```ts
// ui/src/features/note-categories/mappers.ts

import type {
  AnnotationCategoryRead as NoteCategoryDto,
  AnnotationCategoryCreate as NoteCategoryCreateDto,
  AnnotationCategoryUpdate as NoteCategoryUpdateDto,
} from '@/generated/api'
import type { NoteCategory, NoteCategoryInput, NoteCategoryPatch } from './domain'

export function dtoToNoteCategory(dto: NoteCategoryDto): NoteCategory {
  return {
    id: dto.id,
    name: dto.name,
    label: dto.label,
    color: dto.color,
    showOnGraph: dto.show_on_graph,
    isSystem: dto.is_system,
    createdAt: new Date(dto.created_at),
    updatedAt: dto.updated_at ? new Date(dto.updated_at) : null,
  }
}

export function noteCategoryInputToDto(i: NoteCategoryInput): NoteCategoryCreateDto {
  return { name: i.name, label: i.label, color: i.color, show_on_graph: i.showOnGraph }
}

export function noteCategoryPatchToDto(p: NoteCategoryPatch): NoteCategoryUpdateDto {
  return {
    name: p.name,
    label: p.label,
    color: p.color,
    show_on_graph: p.showOnGraph,
  }
}
```

- [ ] **Step 4: Mapper unit tests**

```ts
// ui/src/features/note-categories/mappers.test.ts
import { describe, it, expect } from 'vitest'
import { dtoToNoteCategory, noteCategoryInputToDto, noteCategoryPatchToDto } from './mappers'

describe('note-category mappers', () => {
  it('maps DTO to domain and parses dates', () => {
    const d = dtoToNoteCategory({
      id: 'a', name: 'info', label: 'Info', color: 'sky',
      show_on_graph: true, is_system: false,
      created_at: '2026-04-16T10:00:00Z', updated_at: null,
    } as never)
    expect(d).toMatchObject({ name: 'info', showOnGraph: true, isSystem: false })
    expect(d.createdAt).toBeInstanceOf(Date)
  })

  it('maps input to DTO using snake_case', () => {
    expect(noteCategoryInputToDto({
      name: 'x', label: 'X', color: 'sky', showOnGraph: false,
    })).toEqual({ name: 'x', label: 'X', color: 'sky', show_on_graph: false })
  })

  it('maps patch omitting undefined keys', () => {
    expect(noteCategoryPatchToDto({ label: 'Y' })).toEqual({
      name: undefined, label: 'Y', color: undefined, show_on_graph: undefined,
    })
  })
})
```

- [ ] **Step 5: Run tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/note-categories/mappers.test.ts`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/note-categories/ ui/src/index.css
git commit -m "feat(ui): note-categories domain, mappers, palette tokens"
```

---

### Task 14: `note-categories` feature — api, hooks, barrel

**Files:**
- Create: `ui/src/features/note-categories/api.ts`
- Create: `ui/src/features/note-categories/hooks.ts`
- Create: `ui/src/features/note-categories/index.ts`

- [ ] **Step 1: `api.ts`**

```ts
// ui/src/features/note-categories/api.ts
import type { NoteCategory, NoteCategoryInput, NoteCategoryPatch } from './domain'
import {
  dtoToNoteCategory,
  noteCategoryInputToDto,
  noteCategoryPatchToDto,
} from './mappers'
import type { AnnotationCategoryRead as NoteCategoryDto } from '@/generated/api'
import { BASE } from '@/lib/apiBase'

export async function listNoteCategories(): Promise<NoteCategory[]> {
  const res = await fetch(`${BASE}/note-categories`)
  if (!res.ok) throw new Error(`listNoteCategories: ${res.status}`)
  const rows: NoteCategoryDto[] = await res.json()
  return rows.map(dtoToNoteCategory)
}

export async function createNoteCategory(input: NoteCategoryInput): Promise<NoteCategory> {
  const res = await fetch(`${BASE}/note-categories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(noteCategoryInputToDto(input)),
  })
  if (!res.ok) throw new Error(`createNoteCategory: ${res.status}`)
  return dtoToNoteCategory(await res.json())
}

export async function updateNoteCategory(id: string, patch: NoteCategoryPatch): Promise<NoteCategory> {
  const res = await fetch(`${BASE}/note-categories/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(noteCategoryPatchToDto(patch)),
  })
  if (!res.ok) throw new Error(`updateNoteCategory: ${res.status}`)
  return dtoToNoteCategory(await res.json())
}

export async function deleteNoteCategory(id: string): Promise<{ reassigned: number }> {
  const res = await fetch(`${BASE}/note-categories/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`deleteNoteCategory: ${res.status}`)
  return { reassigned: Number(res.headers.get('X-Reassigned-Annotations') ?? '0') }
}
```

(If `BASE` doesn't yet live in `@/lib/apiBase`, reuse whatever constant the existing `ui/src/features/evaluations/api.ts` imports.)

- [ ] **Step 2: `hooks.ts`**

```ts
// ui/src/features/note-categories/hooks.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from './api'
import type { NoteCategoryInput, NoteCategoryPatch } from './domain'

const QK = { all: ['note-categories'] as const }

export function useNoteCategories() {
  return useQuery({
    queryKey: QK.all,
    queryFn: api.listNoteCategories,
    staleTime: 5 * 60_000,
  })
}

export function useCreateNoteCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: NoteCategoryInput) => api.createNoteCategory(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.all }),
  })
}

export function useUpdateNoteCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (args: { id: string; patch: NoteCategoryPatch }) =>
      api.updateNoteCategory(args.id, args.patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.all }),
  })
}

export function useDeleteNoteCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.deleteNoteCategory(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.all }),
  })
}
```

- [ ] **Step 3: `index.ts` barrel**

```ts
// ui/src/features/note-categories/index.ts
export type { NoteCategory, NoteCategoryInput, NoteCategoryPatch, CategoryColor } from './domain'
export { paletteOf, PALETTE_OPTIONS } from './ui-types'
export {
  useNoteCategories,
  useCreateNoteCategory,
  useUpdateNoteCategory,
  useDeleteNoteCategory,
} from './hooks'
```

- [ ] **Step 4: Commit**

```bash
git add ui/src/features/note-categories/
git commit -m "feat(ui): note-categories api + React Query hooks"
```

---

### Task 15: Category Management page + form

**Files:**
- Create: `ui/src/features/note-categories/components/CategoryRow.tsx`
- Create: `ui/src/features/note-categories/components/CategoryForm.tsx`
- Create: `ui/src/features/note-categories/components/CategoryForm.test.tsx`
- Create: `ui/src/features/note-categories/components/CategoryManagementPage.tsx`

- [ ] **Step 1: `CategoryRow.tsx`** — row in management table

```tsx
// ui/src/features/note-categories/components/CategoryRow.tsx
import { Lock, Pencil, Trash2 } from 'lucide-react'
import { paletteOf } from '../ui-types'
import type { NoteCategory } from '../domain'

interface Props {
  category: NoteCategory
  onToggleShow: (showOnGraph: boolean) => void
  onEdit: () => void
  onDelete: () => void
  busy?: boolean
}

export function CategoryRow({ category, onToggleShow, onEdit, onDelete, busy }: Props) {
  const p = paletteOf(category.color)
  return (
    <tr className="border-b border-border">
      <td className="px-2 py-1.5">
        <span className="inline-flex items-center gap-1.5">
          {category.name}
          {category.isSystem && <Lock className="size-3 text-muted-foreground" />}
        </span>
      </td>
      <td className="px-2 py-1.5">
        <span className="inline-block px-2 py-0.5 rounded text-xs"
              style={{ background: p.bg, color: p.fg }}>
          {category.label}
        </span>
      </td>
      <td className="px-2 py-1.5">{category.color}</td>
      <td className="px-2 py-1.5">
        <input type="checkbox"
               checked={category.showOnGraph}
               onChange={e => onToggleShow(e.target.checked)}
               disabled={busy}
               aria-label={`Show ${category.name} on graph`} />
      </td>
      <td className="px-2 py-1.5 text-right">
        <button onClick={onEdit} disabled={busy}
                className="text-muted-foreground hover:text-foreground mr-2">
          <Pencil className="size-4" />
        </button>
        <button onClick={onDelete}
                disabled={busy || category.isSystem}
                className="text-muted-foreground hover:text-action-destructive disabled:opacity-30">
          <Trash2 className="size-4" />
        </button>
      </td>
    </tr>
  )
}
```

- [ ] **Step 2: `CategoryForm.tsx`** — create/edit form

```tsx
// ui/src/features/note-categories/components/CategoryForm.tsx
import { useState } from 'react'
import { PALETTE_OPTIONS, paletteOf } from '../ui-types'
import type { CategoryColor, NoteCategory, NoteCategoryInput } from '../domain'

interface Props {
  initial?: NoteCategory
  disableName?: boolean
  onSubmit: (input: NoteCategoryInput) => void
  onCancel: () => void
  busy?: boolean
}

export function CategoryForm({ initial, disableName, onSubmit, onCancel, busy }: Props) {
  const [name, setName] = useState(initial?.name ?? '')
  const [label, setLabel] = useState(initial?.label ?? '')
  const [color, setColor] = useState<CategoryColor>(initial?.color ?? 'sky')
  const [showOnGraph, setShowOnGraph] = useState(initial?.showOnGraph ?? true)
  const [error, setError] = useState<string | null>(null)

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!/^[a-z][a-z0-9-]*$/.test(name)) { setError('name must be lowercase-hyphenated'); return }
    if (label.length === 0 || label.length > 12) { setError('label must be 1–12 chars'); return }
    onSubmit({ name, label, color, showOnGraph })
  }

  return (
    <form onSubmit={submit} className="bg-popover border border-border rounded-md p-3 space-y-2">
      <label className="block text-xs">
        Name
        <input value={name} onChange={e => setName(e.target.value)}
               disabled={disableName || busy}
               className="w-full bg-surface-sunken border border-border rounded px-2 py-1 text-sm" />
      </label>
      <label className="block text-xs">
        Label (≤12 chars)
        <input value={label} maxLength={12} onChange={e => setLabel(e.target.value)}
               className="w-full bg-surface-sunken border border-border rounded px-2 py-1 text-sm" />
      </label>
      <div className="text-xs">
        Color
        <div className="flex gap-1 mt-1">
          {PALETTE_OPTIONS.map(c => {
            const p = paletteOf(c)
            return (
              <button type="button" key={c}
                      onClick={() => setColor(c)}
                      className={`px-2 py-0.5 rounded ${c === color ? 'ring-2 ring-primary' : ''}`}
                      style={{ background: p.bg, color: p.fg }}>
                {c}
              </button>
            )
          })}
        </div>
      </div>
      <label className="block text-xs">
        <input type="checkbox" checked={showOnGraph}
               onChange={e => setShowOnGraph(e.target.checked)} className="mr-1" />
        Show on chart
      </label>
      {error && <p className="text-xs text-action-destructive">{error}</p>}
      <div className="flex gap-2 justify-end">
        <button type="button" onClick={onCancel} disabled={busy}
                className="text-xs text-muted-foreground">Cancel</button>
        <button type="submit" disabled={busy}
                className="text-xs px-2 py-1 bg-primary text-primary-foreground rounded">
          Save
        </button>
      </div>
    </form>
  )
}
```

- [ ] **Step 3: `CategoryForm.test.tsx`**

```tsx
// ui/src/features/note-categories/components/CategoryForm.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import { CategoryForm } from './CategoryForm'

describe('CategoryForm', () => {
  afterEach(() => cleanup())

  it('rejects invalid name', () => {
    const onSubmit = vi.fn()
    render(<CategoryForm onSubmit={onSubmit} onCancel={() => {}} />)
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'Bad Name' } })
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: 'OK' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText(/lowercase-hyphenated/i)).toBeInTheDocument()
  })

  it('rejects long label', () => {
    const onSubmit = vi.fn()
    render(<CategoryForm onSubmit={onSubmit} onCancel={() => {}} />)
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'ok' } })
    // maxLength stops at 12 but the validator also guards if somehow longer.
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits valid input', () => {
    const onSubmit = vi.fn()
    render(<CategoryForm onSubmit={onSubmit} onCancel={() => {}} />)
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'release' } })
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: 'Release' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    expect(onSubmit).toHaveBeenCalledWith({
      name: 'release', label: 'Release', color: 'sky', showOnGraph: true,
    })
  })
})
```

- [ ] **Step 4: `CategoryManagementPage.tsx`**

```tsx
// ui/src/features/note-categories/components/CategoryManagementPage.tsx
import { useState } from 'react'
import {
  useNoteCategories, useCreateNoteCategory, useUpdateNoteCategory, useDeleteNoteCategory,
} from '../hooks'
import type { NoteCategory } from '../domain'
import { CategoryRow } from './CategoryRow'
import { CategoryForm } from './CategoryForm'

export function CategoryManagementPage() {
  const { data: categories = [], isLoading } = useNoteCategories()
  const createMut = useCreateNoteCategory()
  const updateMut = useUpdateNoteCategory()
  const deleteMut = useDeleteNoteCategory()

  const [editing, setEditing] = useState<NoteCategory | null>(null)
  const [creating, setCreating] = useState(false)

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Note categories</h1>
        <button className="text-xs px-2 py-1 border border-border rounded"
                onClick={() => setCreating(true)}>
          + Add category
        </button>
      </div>

      {creating && (
        <CategoryForm
          onSubmit={input => createMut.mutate(input, { onSuccess: () => setCreating(false) })}
          onCancel={() => setCreating(false)}
          busy={createMut.isPending}
        />
      )}

      {editing && (
        <CategoryForm
          initial={editing}
          disableName={editing.isSystem}
          onSubmit={input =>
            updateMut.mutate(
              { id: editing.id, patch: input },
              { onSuccess: () => setEditing(null) },
            )}
          onCancel={() => setEditing(null)}
          busy={updateMut.isPending}
        />
      )}

      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-muted-foreground">
            <th className="px-2 py-1">Name</th>
            <th className="px-2 py-1">Label</th>
            <th className="px-2 py-1">Color</th>
            <th className="px-2 py-1">On graph</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {categories.map(c => (
            <CategoryRow
              key={c.id}
              category={c}
              onToggleShow={v =>
                updateMut.mutate({ id: c.id, patch: { showOnGraph: v } })}
              onEdit={() => setEditing(c)}
              onDelete={() => {
                if (confirm(`Delete '${c.name}'? Notes using it move to 'info'.`))
                  deleteMut.mutate(c.id)
              }}
              busy={updateMut.isPending || deleteMut.isPending}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 5: Run the component tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/note-categories/components/CategoryForm.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/note-categories/components/
git commit -m "feat(ui): category management page + form"
```

---

### Task 16: Wire route `/settings/note-categories`

**Files:**
- Modify: the top-level route definition (search: `RouterProvider` or `createBrowserRouter` / `<Routes>`).

- [ ] **Step 1: Locate router config**

Run: `grep -rn "createBrowserRouter\|<Routes>" ui/src --include='*.tsx' --include='*.ts'`

- [ ] **Step 2: Add route**

Add an entry mapping `/settings/note-categories` to `<CategoryManagementPage />` in whichever pattern the file uses.

Example for react-router data routers:

```tsx
import { CategoryManagementPage } from '@/features/note-categories/components/CategoryManagementPage'

// ...existing routes...
{ path: '/settings/note-categories', element: <CategoryManagementPage /> },
```

- [ ] **Step 3: Verify in browser**

Run: `just dev` (or use running dev server) — navigate to `http://localhost:5173/settings/note-categories`.
Expected: page lists 4 seeded categories; `Add category` flow works; deleting a user-created category succeeds; deleting a system row is disabled.

- [ ] **Step 4: Commit**

```bash
git add <route-file>
git commit -m "feat(ui): route for /settings/note-categories"
```

---

## Phase 6 — Frontend: annotation domain migration

### Task 17: Update `Annotation` domain + mapper

**Files:**
- Modify: `ui/src/features/evaluations/domain.ts`
- Modify: `ui/src/features/evaluations/mappers.ts`
- Modify: `ui/src/features/evaluations/mappers.test.ts`

- [ ] **Step 1: Update `Annotation` domain type**

In `ui/src/features/evaluations/domain.ts`, replace:

```ts
category: string | null
```

with:

```ts
categoryId: string
category: NoteCategory
```

Add import:

```ts
import type { NoteCategory } from '@/features/note-categories'
```

- [ ] **Step 2: Add `overridden` to `TrendPoint`**

In the same file, add to `TrendPoint`:

```ts
overridden: boolean
```

- [ ] **Step 3: Update `dtoToAnnotation`**

Because the DTO embeds `category: AnnotationCategoryRead`, the mapper needs to call `dtoToNoteCategory` on it. In `mappers.ts`, add import:

```ts
import { dtoToNoteCategory } from '@/features/note-categories/mappers'
```

Replace the current mapping:

```ts
export function dtoToAnnotation(dto: AnnotationDto): Annotation {
  return {
    id: dto.id,
    sloEvaluationId: dto.slo_evaluation_id,
    evaluationRunId: dto.evaluation_run_id,
    content: dto.content,
    author: dto.author,
    categoryId: dto.category_id,
    category: dtoToNoteCategory(dto.category),
    tags: dto.tags ?? {},
    noteGroupId: dto.note_group_id ?? null,
    noteGroupName: dto.note_group_name ?? null,
    hiddenAt: dto.hidden_at ? new Date(dto.hidden_at) : null,
    hiddenBy: dto.hidden_by,
    hiddenReason: dto.hidden_reason,
    createdAt: new Date(dto.created_at),
    updatedAt: dto.updated_at ? new Date(dto.updated_at) : null,
  }
}
```

Update the exhaustive key coverage check (~line 240): replace `| 'category'` with `| 'category_id'` **and** add `| 'category'` (yes, it now refers to the embedded object — keep it).

- [ ] **Step 4: Update `dtoToTrendPoint`**

The backend's `TrendPointDto` has `original_outcome` (or similar — check the regenerated DTO). Map:

```ts
overridden: Boolean(dto.original_outcome),
```

If the DTO exposes a different signal for override presence, use it instead.

- [ ] **Step 5: Update existing mapper tests**

In `mappers.test.ts`, update the `category: 'flake'` annotation fixture(s) to include the new shape — a full `AnnotationCategoryRead` object (id, name='flake', label='Flake', etc.) plus `category_id`.

- [ ] **Step 6: Run tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/mappers.test.ts`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add ui/src/features/evaluations/
git commit -m "refactor(ui): annotation domain uses NoteCategory; TrendPoint gains overridden"
```

---

### Task 18: Update `AddNoteForm` to use dropdown

**Files:**
- Modify: `ui/src/features/evaluations/components/AddNoteForm.tsx`
- Modify: `ui/src/features/evaluations/api.ts`
- Modify: `ui/src/features/evaluations/hooks.ts` (signature of `useAddRunAnnotation` payload)

- [ ] **Step 1: `api.ts` — send `category_id`**

Change `addAnnotation` and `addRunAnnotation` signatures:

```ts
export async function addAnnotation(
  evalId: string,
  payload: { content: string; categoryId: string; author?: string },
): Promise<Annotation> {
  // ...
  body: JSON.stringify({
    content: payload.content,
    category_id: payload.categoryId,
    author: payload.author,
  }),
}
```

Same change for `addRunAnnotation`.

- [ ] **Step 2: `hooks.ts` — mutation payload**

Update mutation `payload` types in `useAddAnnotation` and `useAddRunAnnotation` to `{ content: string; categoryId: string; author?: string }`.

- [ ] **Step 3: Refactor `AddNoteForm.tsx`**

Replace the free-text category `<input>` with a dropdown. Full component:

```tsx
// ui/src/features/evaluations/components/AddNoteForm.tsx
import { useState, useMemo } from 'react'
import { useAddRunAnnotation } from '../hooks'
import { useNoteCategories } from '@/features/note-categories'
import { paletteOf } from '@/features/note-categories'

interface Props { runId: string; onClose: () => void }

export function AddNoteForm({ runId, onClose }: Props) {
  const [content, setContent] = useState('')
  const [author, setAuthor] = useState('')
  const { data: categories = [] } = useNoteCategories()
  const infoCat = useMemo(() => categories.find(c => c.name === 'info'), [categories])
  const [categoryId, setCategoryId] = useState<string>('')

  // Initialize categoryId to info once categories arrive.
  if (categoryId === '' && infoCat) setCategoryId(infoCat.id)

  const add = useAddRunAnnotation(runId)

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!categoryId || !content.trim()) return
    add.mutate(
      { content, author: author || undefined, categoryId },
      { onSuccess: onClose },
    )
  }

  return (
    <form onSubmit={submit} className="bg-popover border border-border rounded-md p-3 space-y-2">
      <textarea value={content} onChange={e => setContent(e.target.value)}
                placeholder="Note"
                className="w-full h-16 bg-surface-sunken border border-border rounded px-2 py-1 text-sm" />
      <div className="flex gap-2">
        <select value={categoryId} onChange={e => setCategoryId(e.target.value)}
                className="bg-surface-sunken border border-border rounded px-1 py-0.5 text-xs">
          {categories.map(c => (
            <option key={c.id} value={c.id}>{c.label}</option>
          ))}
        </select>
        <input value={author} onChange={e => setAuthor(e.target.value)}
               placeholder="Author"
               className="flex-1 bg-surface-sunken border border-border rounded px-2 py-0.5 text-xs" />
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onClose} className="text-xs text-muted-foreground">Cancel</button>
        <button type="submit" disabled={add.isPending}
                className="text-xs px-2 py-1 bg-primary text-primary-foreground rounded">
          Add
        </button>
      </div>
    </form>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add ui/src/features/evaluations/
git commit -m "feat(ui): AddNoteForm uses category dropdown"
```

---

### Task 19: Update `NoteEntry` to use category palette

**Files:**
- Modify: `ui/src/features/evaluations/components/NoteEntry.tsx`

- [ ] **Step 1: Swap amber badge for category-palette pill**

Find both places that render the category badge:

```tsx
{a.category && (
  <span className="text-[10px] bg-amber-900/40 text-amber-300 px-1.5 py-0.5 rounded shrink-0">{a.category}</span>
)}
```

Replace with:

```tsx
<span className="text-[10px] px-1.5 py-0.5 rounded shrink-0"
      style={{ background: paletteOf(a.category.color).bg, color: paletteOf(a.category.color).fg }}>
  {a.category.label}
</span>
```

Add import:

```ts
import { paletteOf } from '@/features/note-categories'
```

Since `category` is now always present (non-null), remove the conditional wrapping `a.category &&` around the badge — it always renders.

Also update the existing test fixtures in `NoteEntry.test.tsx` to provide a full `NoteCategory` object; run the tests.

- [ ] **Step 2: Run related tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/components/NoteEntry.test.tsx src/features/evaluations/components/AnnotationForm.test.tsx`
Expected: all pass (update fixtures until green).

- [ ] **Step 3: Commit**

```bash
git add ui/src/features/evaluations/components/
git commit -m "feat(ui): NoteEntry renders category palette instead of hardcoded amber"
```

---

### Task 20: Gear link on EvaluationNotesSection

**Files:**
- Modify: `ui/src/features/evaluations/components/AnnotationForm.tsx`

- [ ] **Step 1: Add gear link in header**

In `AnnotationForm.tsx`, in the header row next to the `+ Note` button and view-mode toggle, add:

```tsx
import { Settings2 } from 'lucide-react'
import { Link } from 'react-router-dom' // or equivalent router API

// ...inside the header row:
<Link to="/settings/note-categories"
      title="Manage categories"
      className="text-muted-foreground/60 hover:text-muted-foreground text-xs">
  <Settings2 className="size-3.5" />
</Link>
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/features/evaluations/components/AnnotationForm.tsx
git commit -m "feat(ui): link to category management from notes section"
```

---

## Phase 7 — Chart annotations and override ring

### Task 21: `buildNoteMarkPoint` helper (TDD)

**Files:**
- Create: `ui/src/lib/chartAnnotations.ts`
- Create: `ui/src/lib/chartAnnotations.test.ts`

- [ ] **Step 1: Write failing tests**

```ts
// ui/src/lib/chartAnnotations.test.ts
import { describe, it, expect } from 'vitest'
import { buildNoteMarkPoint } from './chartAnnotations'
import type { Annotation, TrendPoint } from '@/features/evaluations/domain'
import type { NoteCategory } from '@/features/note-categories'

const infoCat: NoteCategory = {
  id: 'info-id', name: 'info', label: 'Info', color: 'sky',
  showOnGraph: true, isSystem: false, createdAt: new Date(), updatedAt: null,
}
const failureCat: NoteCategory = { ...infoCat, id: 'fail-id', name: 'failure', label: 'Failure', color: 'red' }
const hiddenCat: NoteCategory = { ...infoCat, id: 'hid-id', name: 'hidden', label: 'Hid', color: 'gray', showOnGraph: false }

function mkPoint(evalId: string, i: number): TrendPoint {
  return {
    timestamp: new Date(2026, 0, i + 1),
    value: 100 + i,
    score: 90,
    evalId,
    outcome: 'pass',
    baseline: null,
    evaluationName: null,
    targets: null,
    overridden: false,
  }
}

function mkAnnotation(id: string, runId: string, cat: NoteCategory): Annotation {
  return {
    id, sloEvaluationId: null, evaluationRunId: runId,
    content: 'note', author: null,
    categoryId: cat.id, category: cat,
    tags: {}, noteGroupId: null, noteGroupName: null,
    hiddenAt: null, hiddenBy: null, hiddenReason: null,
    createdAt: new Date(), updatedAt: null,
  }
}

describe('buildNoteMarkPoint', () => {
  it('emits nothing when no annotations', () => {
    const mp = buildNoteMarkPoint({
      trendPoints: [mkPoint('a', 0)],
      annotationsByEvalId: new Map(),
      categoriesById: new Map(),
      chartWidth: 500,
    })
    expect(mp.data).toEqual([])
  })

  it('filters categories with showOnGraph=false', () => {
    const mp = buildNoteMarkPoint({
      trendPoints: [mkPoint('a', 0)],
      annotationsByEvalId: new Map([['a', [mkAnnotation('n1', 'a', hiddenCat)]]]),
      categoriesById: new Map([[hiddenCat.id, hiddenCat]]),
      chartWidth: 500,
    })
    expect(mp.data).toEqual([])
  })

  it('emits one markPoint per noted eval with dominant category (alphabetical)', () => {
    const mp = buildNoteMarkPoint({
      trendPoints: [mkPoint('a', 0)],
      annotationsByEvalId: new Map([['a', [
        mkAnnotation('n1', 'a', infoCat),
        mkAnnotation('n2', 'a', failureCat),
      ]]]),
      categoriesById: new Map([[infoCat.id, infoCat], [failureCat.id, failureCat]]),
      chartWidth: 500,
    })
    expect(mp.data).toHaveLength(1)
    // 'failure' < 'info' alphabetically → dominant
    expect((mp.data[0] as { itemStyle: { color: string } }).itemStyle.color).toContain('red')
  })

  it('hides labels when density is too high', () => {
    const points = Array.from({ length: 20 }, (_, i) => mkPoint(`e${i}`, i))
    const anns = new Map(points.map(p => [p.evalId, [mkAnnotation(`n${p.evalId}`, p.evalId, infoCat)]]))
    const mp = buildNoteMarkPoint({
      trendPoints: points,
      annotationsByEvalId: anns,
      categoriesById: new Map([[infoCat.id, infoCat]]),
      chartWidth: 600, // 600/20 = 30, below 40px threshold
    })
    const first = mp.data[0] as { label?: { show: boolean } }
    expect(first.label?.show).toBe(false)
  })

  it('shows labels with (n) suffix when multiple notes on same eval', () => {
    const mp = buildNoteMarkPoint({
      trendPoints: [mkPoint('a', 0)],
      annotationsByEvalId: new Map([['a', [
        mkAnnotation('n1', 'a', infoCat),
        mkAnnotation('n2', 'a', infoCat),
      ]]]),
      categoriesById: new Map([[infoCat.id, infoCat]]),
      chartWidth: 500,
    })
    const first = mp.data[0] as { label: { formatter: string } }
    expect(first.label.formatter).toBe('Info (2)')
  })
})
```

- [ ] **Step 2: Run — expect fail**

Run: `./scripts/ui-test.sh --tail 20 src/lib/chartAnnotations.test.ts`
Expected: file not found / import errors.

- [ ] **Step 3: Implement helper**

```ts
// ui/src/lib/chartAnnotations.ts
import type { Annotation, TrendPoint } from '@/features/evaluations/domain'
import type { NoteCategory } from '@/features/note-categories'
import { paletteOf } from '@/features/note-categories'

export interface MarkPointOption {
  symbol: string
  symbolSize: [number, number]
  symbolOffset: [number, number]
  data: Array<{
    xAxis: number
    yAxis: number
    itemStyle: { color: string }
    label: { show: boolean; formatter: string; color: string; fontSize: number }
    tooltip?: { formatter: string }
    evalId: string
  }>
}

interface Input {
  trendPoints: TrendPoint[]
  annotationsByEvalId: Map<string, Annotation[]>
  categoriesById: Map<string, NoteCategory>
  chartWidth: number
}

const TEARDROP_SVG = 'path://M12,0 C5.4,0 0,5.4 0,12 C0,21 12,28 12,28 C12,28 24,21 24,12 C24,5.4 18.6,0 12,0 Z'

function dominantCategory(visible: Annotation[]): NoteCategory {
  // Alphabetical by name — deterministic tiebreaker
  const sorted = [...visible].sort((x, y) => x.category.name.localeCompare(y.category.name))
  return sorted[0].category
}

export function buildNoteMarkPoint(input: Input): MarkPointOption {
  const { trendPoints, annotationsByEvalId, chartWidth } = input

  const visibleCount = trendPoints.filter(p => {
    const anns = annotationsByEvalId.get(p.evalId) ?? []
    return anns.some(a => a.category.showOnGraph)
  }).length

  const labelsOn = visibleCount === 0 || chartWidth / visibleCount >= 40

  const data: MarkPointOption['data'] = []

  for (let i = 0; i < trendPoints.length; i++) {
    const p = trendPoints[i]
    const anns = annotationsByEvalId.get(p.evalId) ?? []
    const visible = anns.filter(a => a.category.showOnGraph)
    if (visible.length === 0) continue

    const cat = dominantCategory(visible)
    const palette = paletteOf(cat.color)
    const suffix = visible.length > 1 ? ` (${visible.length})` : ''

    const tooltipBody = visible
      .map(a => `<div><b>${a.category.label}</b>: ${escapeHtml(a.content)}</div>`)
      .join('')

    data.push({
      xAxis: i,
      yAxis: p.value,
      itemStyle: { color: palette.bg },
      label: {
        show: labelsOn,
        formatter: `${cat.label}${suffix}`,
        color: palette.fg,
        fontSize: 10,
      },
      tooltip: { formatter: tooltipBody },
      evalId: p.evalId,
    })
  }

  return {
    symbol: TEARDROP_SVG,
    symbolSize: [18, 14],
    symbolOffset: [0, -14],
    data,
  }
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]!))
}
```

- [ ] **Step 4: Run tests — should pass**

Run: `./scripts/ui-test.sh --tail 20 src/lib/chartAnnotations.test.ts`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add ui/src/lib/chartAnnotations.ts ui/src/lib/chartAnnotations.test.ts
git commit -m "feat(ui): buildNoteMarkPoint helper for chart annotations"
```

---

### Task 22: Per-asset annotations fetch

**Files:**
- Modify: `ui/src/features/evaluations/api.ts`
- Modify: `ui/src/features/evaluations/hooks.ts`

- [ ] **Step 1: Add fetch**

In `api.ts`:

```ts
export async function fetchTrendAnnotations(
  asset: string, slo: string,
): Promise<Map<string, Annotation[]>> {
  const res = await fetch(`${BASE}/evaluations/trend-annotations?asset=${encodeURIComponent(asset)}&slo=${encodeURIComponent(slo)}`)
  if (!res.ok) throw new Error(`fetchTrendAnnotations: ${res.status}`)
  const body: Record<string, AnnotationDto[]> = await res.json()
  const map = new Map<string, Annotation[]>()
  for (const [evalId, dtos] of Object.entries(body)) {
    map.set(evalId, dtos.map(dtoToAnnotation))
  }
  return map
}
```

Backend endpoint assumed at `/evaluations/trend-annotations`; returns `{evalId: AnnotationRead[]}`. If the backend does not yet have this endpoint, add it: a small router that queries annotations for all runs belonging to `(asset, slo)` in one go — see below for the backend hint.

**Backend note (implement inline if missing):** in `router.py`, add:

```python
@router.get('/evaluations/trend-annotations', response_model=dict[str, list[AnnotationRead]])
async def list_trend_annotations(
    asset: str,
    slo: str,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> dict[str, list[AnnotationRead]]:
    rows = await repos.annotation_repo.list_for_trend(asset=asset, slo=slo)
    out: dict[str, list[AnnotationRead]] = {}
    for ann in rows:
        key = str(ann.evaluation_run_id)
        out.setdefault(key, []).append(AnnotationRead.model_validate(ann))
    return out
```

and add `list_for_trend(asset: str, slo: str)` to `AnnotationRepository` — one SELECT joining `evaluation_runs` by `asset_name` and `slo_name`, filtered to non-hidden. Commit backend change separately if you do this here.

- [ ] **Step 2: Add hook**

In `hooks.ts`:

```ts
export function useTrendAnnotations(asset: string | undefined, slo: string | null | undefined) {
  return useQuery({
    queryKey: ['trend-annotations', asset, slo],
    queryFn: () => fetchTrendAnnotations(asset!, slo!),
    enabled: Boolean(asset && slo),
    staleTime: 60_000,
  })
}
```

- [ ] **Step 3: Commit**

```bash
git add ui/src/features/evaluations/ api/tropek/modules/quality_gate/
git commit -m "feat: expose trend annotations per (asset, slo)"
```

---

### Task 23: Integrate markPoint + toggle in `MetricTrendBlock`

**Files:**
- Modify: `ui/src/features/evaluations/hooks/useMetricTrendState.ts`
- Modify: `ui/src/features/evaluations/components/MetricTrendBlock.tsx`

- [ ] **Step 1: Extend `useMetricTrendState`**

Add parameters:

```ts
annotations: Map<string, Annotation[]>,
categories: NoteCategory[],
chartWidth: number,
```

Add state:

```ts
const [notesVisible, setNotesVisible] = useState(true)
```

In `buildChartOption`, when `notesVisible` is true and `annotations.size > 0`, compute:

```ts
const categoriesById = new Map(categories.map(c => [c.id, c]))
const markPoint = buildNoteMarkPoint({
  trendPoints: trendData,
  annotationsByEvalId: annotations,
  categoriesById,
  chartWidth,
})
```

Merge `markPoint` onto the main series (series[0]): `markPoint: markPoint`.

Return `notesVisible` and `toggleNotes: () => setNotesVisible(v => !v)` from the hook.

- [ ] **Step 2: Override ring in `buildChartOption`**

In the existing `chartData` loop, extend the `itemStyle` for overridden points. Current:

```ts
borderColor: isSelected(p) ? '#ffffff' : 'transparent',
borderWidth: 2,
```

Replace with:

```ts
borderColor: isSelected(p) ? '#ffffff' : (p.overridden ? ct.axisLabel : 'transparent'),
borderWidth: p.overridden || isSelected(p) ? 2 : 0,
```

(Use a CSS theme variable for the gray if one fits better than `ct.axisLabel`.)

Also amend the tooltip formatter to append override info when `p.overridden`:

```ts
if (p.overridden) lines.push(`<span style="color:${ct.axisLabel}">(override)</span>`)
```

- [ ] **Step 3: Wire into `MetricTrendBlock`**

In `MetricTrendBlock.tsx`:

```tsx
import { useTrendAnnotations } from '../api'        // or from hooks barrel
import { useNoteCategories } from '@/features/note-categories'
import { MessageSquareWarning } from 'lucide-react'

// Inside the component:
const { data: annotations = new Map() } = useTrendAnnotations(assetName, sloName)
const { data: categories = [] } = useNoteCategories()
const [containerWidth, setContainerWidth] = useState(0)
const containerRef = useRef<HTMLDivElement>(null)
useEffect(() => {
  if (!containerRef.current) return
  const ro = new ResizeObserver(entries => {
    setContainerWidth(entries[0].contentRect.width)
  })
  ro.observe(containerRef.current)
  return () => ro.disconnect()
}, [])

const { /* existing */ notesVisible, toggleNotes, chartOption } =
  useMetricTrendState(
    trend, selectedEvalId ?? '', indicator, onEvalSelect,
    selectedEvalIds, selectedPeriodStart,
    annotations, categories, containerWidth,
  )
```

Add a toggle button in the header row, next to `TargetDropdown`:

```tsx
<button onClick={toggleNotes}
        className={`p-1 rounded border transition-colors ${
          notesVisible ? 'border-primary/40 text-primary' : 'border-border text-muted-foreground/60'
        }`}
        title="Toggle notes on chart"
        aria-label="Toggle notes on chart">
  <MessageSquareWarning className="size-3.5" />
</button>
```

Wrap the chart in `<div ref={containerRef}>…</div>` so the width measurement works.

- [ ] **Step 4: Add click handler to markPoint**

In `MetricTrendBlock`, attach an ECharts event handler on the chart:

```tsx
const onEvents = useMemo(() => ({
  click: (params: { componentType?: string; data?: { evalId?: string } }) => {
    if (params.componentType === 'markPoint' && params.data?.evalId && onEvalSelect) {
      onEvalSelect(params.data.evalId)
      document.getElementById('notes-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  },
}), [onEvalSelect])

<ReactECharts /* existing */ onEvents={onEvents} />
```

Add `id="notes-section"` to the wrapper in `EvaluationNotesSection.tsx`.

- [ ] **Step 5: Run related tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/`
Expected: all existing tests still pass. If `useMetricTrendState` tests reference the old signature, update them to pass empty `new Map()`, `[]`, and `0`.

- [ ] **Step 6: Manual browser verification**

Run: `just dev` — open an evaluation page with seeded annotations. Verify:

1. Pins appear above the expected runs on each trend chart.
2. Toggle button hides/shows pins.
3. Hover shows full note content.
4. Click on pin scrolls to notes section.
5. Overridden points show a gray ring (seed at least one override if needed).
6. Selected overridden points have a white ring (selection wins).

- [ ] **Step 7: Commit**

```bash
git add ui/src/features/evaluations/
git commit -m "feat(ui): chart annotations and override ring in MetricTrendBlock"
```

---

## Phase 8 — Closing

### Task 24: Full test pass + typecheck + lint

- [ ] **Step 1: Run all API tests**

Run: `./scripts/api-test.sh --tail 10 tests/`
Run: `./scripts/api-test.sh --tail 10 -m integration tests/`
Expected: all green.

- [ ] **Step 2: Run all UI tests**

Run: `./scripts/ui-test.sh --tail 10`
Expected: all green.

- [ ] **Step 3: Lint + typecheck**

Run: `just check`
Expected: no errors.

- [ ] **Step 4: Fix any fallout**

If regressions appear, fix them in focused commits — do not mass-suppress warnings.

- [ ] **Step 5: Final commit for any fixes**

```bash
git commit -m "chore: final lint/type fixes"
```

---

## Spec coverage checklist

- §1 new `AnnotationCategory` entity — Tasks 1, 2.
- §1 palette enum — Task 4.
- §1 seeded categories — Task 3.
- §1 `category` → `category_id` migration — Tasks 1–2.
- §1 repository — Task 5.
- API `/note-categories` CRUD — Task 10.
- AnnotationRead/Create schema update — Task 8.
- re_evaluation_service update — Task 9.
- Dev seed update — Task 11.
- UI `features/note-categories` — Tasks 12–14.
- Category management page — Task 15.
- Settings route — Task 16.
- Annotation domain + mapper — Task 17.
- AddNoteForm dropdown — Task 18.
- NoteEntry palette — Task 19.
- Gear link — Task 20.
- `buildNoteMarkPoint` helper + tests — Task 21.
- Trend annotations fetch + hook — Task 22.
- `MetricTrendBlock` markPoint + toggle + override ring — Task 23.
- Final test/lint pass — Task 24.

All spec sections have at least one task.
