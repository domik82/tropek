yes# Assignment Layer Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the polymorphic `slo_bindings`/`template_bindings` fan-out system with a clean three-layer architecture: version-pinned `slo_assignments`, always-latest `slo_group_assignments`, and query-time evaluation resolution.

**Architecture:** New `slo_assignments` and `slo_group_assignments` tables carry FK refs to specific DB rows (no more text name resolution). The evaluation engine resolves SLOs via a single SQL UNION ALL query at trigger time — no materialised fan-out rows, no sync functions. `SLODefinition.sli_definition_id` and `SLOGroup.template_slo_definition_id` replace the old text-ref columns.

**Tech Stack:** SQLAlchemy async ORM, FastAPI, PostgreSQL, pytest + asyncio, `scripts/db-regen-migrations.sh` (squash-style migrations).

---

## File Map

| Status | File | Change |
|---|---|---|
| Modify | `api/app/db/models.py` | Add new tables/columns; remove old ones in Task 7 |
| Modify | `api/app/modules/sli_registry/repository.py` | Add `get_by_id()` |
| Modify | `api/app/modules/slo_registry/params.py` | Add `sli_definition_id` |
| Modify | `api/app/modules/slo_registry/repository.py` | Store `sli_definition_id` |
| Modify | `api/app/modules/slo_registry/router.py` | Resolve sli_name → FK at create |
| Modify | `api/app/modules/slo_groups/repository.py` | Add `template_slo_definition_id`; remove `TemplateBindingRepository` in Task 7 |
| Modify | `api/app/modules/slo_groups/schemas.py` | Update schemas; remove TemplateBinding schemas in Task 7 |
| Modify | `api/app/modules/slo_groups/router.py` | Wire FK; remove fan-out + template binding routes in Task 7 |
| Create | `api/app/modules/assignments/repository.py` | `AssignmentRepository` + SQL resolution query |
| Create | `api/app/modules/assignments/schemas.py` | Create/Read schemas |
| Create | `api/app/modules/assignments/router.py` | CRUD routes |
| Modify | `api/app/modules/assets/repository.py` | Remove `SLOBindingRepository` in Task 7 |
| Modify | `api/app/modules/assets/router.py` | Remove SLO binding routes in Task 7 |
| Modify | `api/app/modules/quality_gate/protocols.py` | Replace `SLOBindingReader` with `AssignmentReader` |
| Modify | `api/app/modules/quality_gate/trigger.py` | New resolution using assignment repo |
| Modify | `api/app/modules/quality_gate/params.py` | Add `slo_definition_id`, `sli_definition_id` |
| Modify | `api/app/modules/quality_gate/repository.py` | Store `slo_definition_id`, `sli_definition_id` |
| Modify | `api/app/modules/quality_gate/dependencies.py` | Add `assignment_repo` |
| Modify | `api/app/main.py` | Register assignments router |
| Delete | `api/tests/db/test_slo_bindings.py` | Replaced by test_assignments.py |
| Create | `api/tests/db/test_assignments.py` | Integration tests for new module |

---

## Task 1: Add new columns and tables to models.py (additive pass)

**Files:**
- Modify: `api/app/db/models.py`

Add all new schema elements without removing old ones. Existing code stays functional.

- [ ] **Step 1: Add `sli_definition_id` to `SLODefinition`**

In `api/app/db/models.py`, inside the `SLODefinition` class after the `sli_version` column:

```python
sli_definition_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('sli_definitions.id'), nullable=True)
```

- [ ] **Step 2: Add `template_slo_definition_id` to `SLOGroup`**

In `SLOGroup`, after the `template_slo_version` column:

```python
template_slo_definition_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('slo_definitions.id'), nullable=True)
```

- [ ] **Step 3: Add `slo_definition_id` and `sli_definition_id` to `SLOEvaluation`**

In `SLOEvaluation`, after the `data_source_name` column:

```python
slo_definition_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('slo_definitions.id'), nullable=True)
sli_definition_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('sli_definitions.id'), nullable=True)
```

- [ ] **Step 4: Add `SLOAssignment` model**

After the `TemplateBinding` class in `api/app/db/models.py`:

```python
class SLOAssignment(Base):
    """Version-pinned assignment of a specific SLO definition to an asset or asset group."""

    __tablename__ = 'slo_assignments'
    __table_args__ = (
        Index(
            'uq_slo_assignments_asset_slo',
            'asset_id', 'slo_name',
            unique=True,
            postgresql_where=text('asset_id IS NOT NULL'),
        ),
        Index(
            'uq_slo_assignments_group_slo',
            'asset_group_id', 'slo_name',
            unique=True,
            postgresql_where=text('asset_group_id IS NOT NULL'),
        ),
        CheckConstraint(
            '(asset_id IS NULL) != (asset_group_id IS NULL)',
            name='ck_slo_assignments_target',
        ),
        Index('idx_slo_assignments_asset', 'asset_id'),
        Index('idx_slo_assignments_group', 'asset_group_id'),
    )

    # fmt: off
    id:                Mapped[uuid.UUID]                    = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    asset_id:          Mapped[uuid.UUID | None]              = mapped_column(UUID, ForeignKey('assets.id', ondelete='CASCADE'), nullable=True)
    asset_group_id:    Mapped[uuid.UUID | None]              = mapped_column(UUID, ForeignKey('asset_groups.id', ondelete='CASCADE'), nullable=True)
    slo_definition_id: Mapped[uuid.UUID]                    = mapped_column(UUID, ForeignKey('slo_definitions.id'), nullable=False)
    slo_name:          Mapped[str]                          = mapped_column(Text, nullable=False)
    data_source_id:    Mapped[uuid.UUID]                    = mapped_column(UUID, ForeignKey('data_sources.id'), nullable=False)
    comparison_rules:  Mapped[list[dict[str, Any]] | None]  = mapped_column(JSONB, nullable=True)
    created_at:        Mapped[datetime]                     = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # fmt: on
```

- [ ] **Step 5: Add `SLOGroupAssignment` model**

After `SLOAssignment`:

```python
class SLOGroupAssignment(Base):
    """Always-latest assignment of an SLO group to an asset or asset group."""

    __tablename__ = 'slo_group_assignments'
    __table_args__ = (
        Index(
            'uq_slo_group_assignments_asset',
            'asset_id', 'slo_group_id',
            unique=True,
            postgresql_where=text('asset_id IS NOT NULL'),
        ),
        Index(
            'uq_slo_group_assignments_group',
            'asset_group_id', 'slo_group_id',
            unique=True,
            postgresql_where=text('asset_group_id IS NOT NULL'),
        ),
        CheckConstraint(
            '(asset_id IS NULL) != (asset_group_id IS NULL)',
            name='ck_slo_group_assignments_target',
        ),
        Index('idx_slo_group_assignments_asset', 'asset_id'),
        Index('idx_slo_group_assignments_asset_group', 'asset_group_id'),
    )

    # fmt: off
    id:             Mapped[uuid.UUID]        = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    asset_id:       Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('assets.id', ondelete='CASCADE'), nullable=True)
    asset_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('asset_groups.id', ondelete='CASCADE'), nullable=True)
    slo_group_id:   Mapped[uuid.UUID]        = mapped_column(UUID, ForeignKey('slo_groups.id'), nullable=False)
    data_source_id: Mapped[uuid.UUID]        = mapped_column(UUID, ForeignKey('data_sources.id'), nullable=False)
    created_at:     Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # fmt: on
```

- [ ] **Step 6: Add `SLODisplayGroup` and `SLODisplayGroupMember` models**

After `SLOGroupAssignment`:

```python
class SLODisplayGroup(Base):
    """UI navigation bucket — organises SLO concepts into a collapsible hierarchy."""

    __tablename__ = 'slo_display_groups'

    # fmt: off
    id:           Mapped[uuid.UUID]        = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]              = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None]       = mapped_column(Text, nullable=True)
    parent_id:    Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('slo_display_groups.id'), nullable=True)
    sort_order:   Mapped[int]              = mapped_column(Integer, nullable=False, server_default=text('0'), default=0)
    created_at:   Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    members: Mapped[list['SLODisplayGroupMember']] = relationship('SLODisplayGroupMember', cascade='all, delete-orphan')
    # fmt: on


class SLODisplayGroupMember(Base):
    """Membership of an SLO concept (by name) in a display group."""

    __tablename__ = 'slo_display_group_members'
    __table_args__ = (Index('idx_slo_display_group_members_slo', 'slo_name'),)

    # fmt: off
    group_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('slo_display_groups.id', ondelete='CASCADE'), primary_key=True)
    slo_name: Mapped[str]       = mapped_column(Text, primary_key=True)
    # fmt: on
```

- [ ] **Step 7: Regen migration**

```bash
./scripts/db-regen-migrations.sh
```

Expected: completes without error, `api/alembic/versions/001_initial_schema.py` updated.

- [ ] **Step 8: Verify existing tests pass**

```bash
just test-env
./scripts/api-test.sh --tail 10 -m integration -v
```

Expected: all existing integration tests pass (additive changes only — nothing broken).

- [ ] **Step 9: Commit**

```bash
git add api/app/db/models.py api/alembic/versions/001_initial_schema.py
git commit -m "feat: add slo_assignments, slo_group_assignments, display_groups schema; add FK columns"
```

---

## Task 2: Add `SLIRepository.get_by_id()`

**Files:**
- Modify: `api/app/modules/sli_registry/repository.py`

The trigger resolution will load SLI definitions by UUID (from `slo_definitions.sli_definition_id`), so the repo needs a `get_by_id` method.

- [ ] **Step 1: Write the failing test**

Add to `api/tests/db/test_sli_registry.py` (or create if missing):

```python
import pytest
from app.modules.sli_registry.repository import SLIRepository

@pytest.mark.integration
async def test_get_by_id_returns_correct_definition(db_session, make_sli):
    sli = await make_sli(name='sli-cpu', adapter_type='prometheus', indicators={'cpu': 'avg(rate(cpu[5m]))'})
    repo = SLIRepository(db_session)
    fetched = await repo.get_by_id(sli.id)
    assert fetched is not None
    assert fetched.id == sli.id
    assert fetched.name == 'sli-cpu'

@pytest.mark.integration
async def test_get_by_id_returns_none_for_unknown(db_session):
    import uuid
    repo = SLIRepository(db_session)
    assert await repo.get_by_id(uuid.uuid4()) is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./scripts/api-test.sh --tail 10 -m integration tests/db/test_sli_registry.py -v
```

Expected: FAIL — `SLIRepository has no attribute 'get_by_id'`

- [ ] **Step 3: Implement `get_by_id`**

In `api/app/modules/sli_registry/repository.py`, add after `get_version`:

```python
async def get_by_id(self, sli_id: uuid.UUID) -> SLIDefinition | None:
    """Return a specific SLI definition by primary key, or None."""
    result = await self._session.execute(
        select(SLIDefinition).where(SLIDefinition.id == sli_id)
    )
    return result.scalar_one_or_none()
```

Also add `uuid` to the imports at the top if not already present.

- [ ] **Step 4: Run test to verify pass**

```bash
./scripts/api-test.sh --tail 10 -m integration tests/db/test_sli_registry.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/sli_registry/repository.py
git commit -m "feat: add SLIRepository.get_by_id for FK-based lookup"
```

---

## Task 3: Wire `sli_definition_id` into SLO creation

**Files:**
- Modify: `api/app/modules/slo_registry/params.py`
- Modify: `api/app/modules/slo_registry/repository.py`
- Modify: `api/app/modules/slo_registry/router.py`

When a user creates an SLO with `sli_name`, the router resolves it to a UUID and stores it alongside the existing text columns (which stay for now).

- [ ] **Step 1: Add `sli_definition_id` to `SLOCreateParams`**

In `api/app/modules/slo_registry/params.py`, add after `sli_version`:

```python
sli_definition_id: uuid.UUID | None = None
```

The top of the file already imports `uuid`. Full updated class:

```python
class SLOCreateParams(BaseModel):
    """Parameters for SLORepository.create()."""

    name: str
    objectives: list[SLOObjectiveParams]
    total_score_pass_threshold: float = 90.0
    total_score_warning_threshold: float = 75.0
    comparison: dict[str, object] | None = None
    display_name: str | None = None
    notes: str | None = None
    author: str | None = None
    tags: dict[str, object] = Field(default_factory=dict)
    variables: dict[str, object] = Field(default_factory=dict)
    comparable_from_version: int | None = None
    kind: str = 'standard'
    sli_name: str | None = None
    sli_version: int | None = None
    sli_definition_id: uuid.UUID | None = None
    method_criteria: dict[str, object] | None = None
    generated_by_group_id: uuid.UUID | None = None
```

- [ ] **Step 2: Store `sli_definition_id` in `SLORepository.create()`**

In `api/app/modules/slo_registry/repository.py`, update the `SLODefinition(...)` constructor call to include:

```python
slo = SLODefinition(
    id=uuid.uuid4(),
    name=params.name,
    version=next_version,
    comparable_from_version=resolved_cfv,
    total_score_pass_threshold=params.total_score_pass_threshold,
    total_score_warning_threshold=params.total_score_warning_threshold,
    comparison=params.comparison or {},
    display_name=params.display_name,
    notes=params.notes,
    author=params.author,
    tags=params.tags,
    variables=params.variables,
    kind=params.kind,
    sli_name=params.sli_name,
    sli_version=params.sli_version,
    sli_definition_id=params.sli_definition_id,
    method_criteria=params.method_criteria,
    generated_by_group_id=params.generated_by_group_id,
    active=True,
)
```

- [ ] **Step 3: Resolve FK in `create_slo_definition` router**

In `api/app/modules/slo_registry/router.py`, update `create_slo_definition` to capture the resolved `sli_def.id`:

```python
@router.post('/slo-definitions', response_model=SLODefinitionRead, status_code=201)
async def create_slo_definition(
    body: SLODefinitionCreate,
    session: AsyncSession = Depends(get_session),
) -> SLODefinitionRead:
    """Create a new SLO definition (or a new version if name already exists)."""
    resolved_sli_id: uuid.UUID | None = None
    if body.sli_name is not None:
        sli_repo = SLIRepository(session)
        if body.sli_version is not None:
            sli_def = await sli_repo.get_version(body.sli_name, body.sli_version)
        else:
            sli_def = await sli_repo.get_latest(body.sli_name)
        if sli_def is None:
            raise HTTPException(
                status_code=422,
                detail=f"sli definition '{body.sli_name}' version {body.sli_version} not found",
            )
        if sli_def.mode == 'aggregated' and sli_def.methods:
            indicator_keys = {f'{body.sli_name}.{m}' for m in sli_def.methods}
        else:
            indicator_keys = set(sli_def.indicators.keys())
        for obj in body.objectives:
            if obj.sli not in indicator_keys:
                raise HTTPException(
                    status_code=422,
                    detail=f"objective sli '{obj.sli}' not found in SLI definition '{body.sli_name}' indicators",
                )
        resolved_sli_id = sli_def.id
    repo = SLORepository(session)
    params = SLOCreateParams(
        name=body.name,
        objectives=[SLOObjectiveParams(**o.model_dump()) for o in body.objectives],
        total_score_pass_threshold=body.total_score_pass_threshold,
        total_score_warning_threshold=body.total_score_warning_threshold,
        comparison=body.comparison or None,
        display_name=body.display_name,
        notes=body.notes,
        author=body.author,
        tags=body.tags,
        variables=body.variables,
        kind=body.kind,
        sli_name=body.sli_name,
        sli_version=body.sli_version,
        sli_definition_id=resolved_sli_id,
        method_criteria=body.method_criteria,
    )
    slo = await repo.create(params)
    return SLODefinitionRead.model_validate(slo)
```

(Add `import uuid` at the top of the router if not present.)

- [ ] **Step 4: Run unit tests**

```bash
./scripts/api-test.sh --tail 10
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/slo_registry/params.py api/app/modules/slo_registry/repository.py api/app/modules/slo_registry/router.py
git commit -m "feat: store sli_definition_id FK on slo_definitions at create time"
```

---

## Task 4: Wire `template_slo_definition_id` into SLO group creation

**Files:**
- Modify: `api/app/modules/slo_groups/repository.py`
- Modify: `api/app/modules/slo_groups/router.py`

When a group is created or updated, resolve the template SLO to a UUID and store it.

- [ ] **Step 1: Update `SLOGroupRepository.create()` and `update()`**

In `api/app/modules/slo_groups/repository.py`, update `create()`:

```python
async def create(
    self,
    *,
    name: str,
    display_name: str | None = None,
    template_slo_name: str,
    template_slo_version: int,
    template_slo_definition_id: uuid.UUID | None = None,
    gen_variables: dict[str, list[str]],
    tags: dict[str, Any] | None = None,
    author: str | None = None,
) -> SLOGroup:
    """Insert a new SLO group row and return it."""
    group = SLOGroup(
        id=uuid.uuid4(),
        name=name,
        display_name=display_name,
        template_slo_name=template_slo_name,
        template_slo_version=template_slo_version,
        template_slo_definition_id=template_slo_definition_id,
        gen_variables=gen_variables,
        tags=tags or {},
        author=author,
    )
    self._session.add(group)
    await self._session.flush()
    return group
```

Also update `update()` to accept `template_slo_definition_id`:

```python
async def update(
    self,
    name: str,
    *,
    template_slo_name: str | None = None,
    template_slo_version: int | None = None,
    template_slo_definition_id: uuid.UUID | None = None,
    gen_variables: dict[str, list[str]] | None = None,
    display_name: Any = _UNSET,
    tags: dict[str, Any] | None = None,
) -> SLOGroup | None:
    """Update mutable fields on an active group; bumps version."""
    group = await self.get_by_name(name)
    if group is None:
        return None
    if template_slo_name is not None:
        group.template_slo_name = template_slo_name
    if template_slo_version is not None:
        group.template_slo_version = template_slo_version
    if template_slo_definition_id is not None:
        group.template_slo_definition_id = template_slo_definition_id
    if gen_variables is not None:
        group.gen_variables = gen_variables
    if display_name is not _UNSET:
        group.display_name = display_name
    if tags is not None:
        group.tags = tags
    group.version += 1
    group.updated_at = datetime.now(UTC)
    await self._session.flush()
    return group
```

- [ ] **Step 2: Pass `template_slo_definition_id` in `create_slo_group` router handler**

In `api/app/modules/slo_groups/router.py`, update the `create_slo_group` handler to pass the resolved FK:

```python
group = await group_repo.create(
    name=body.name,
    display_name=body.display_name,
    template_slo_name=body.template_slo_name,
    template_slo_version=body.template_slo_version,
    template_slo_definition_id=template.id,   # ← add this
    gen_variables=body.gen_variables,
    tags=body.tags,
    author=body.author,
)
```

(The `template` variable is already loaded by `_load_template_slo()`.)

- [ ] **Step 3: Pass `template_slo_definition_id` in `update_slo_group` router handler**

In `update_slo_group`, find the call to `group_repo.update(...)` and add `template_slo_definition_id=template.id`:

```python
updated_group = await group_repo.update(
    name,
    template_slo_name=eff_template_name,
    template_slo_version=eff_template_version,
    template_slo_definition_id=template.id,   # ← add this
    gen_variables=eff_gen_vars,
    display_name=body.display_name if body.display_name is not None else group.display_name,
    tags=body.tags if body.tags is not None else None,
)
```

- [ ] **Step 4: Run unit tests**

```bash
./scripts/api-test.sh --tail 10
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/slo_groups/repository.py api/app/modules/slo_groups/router.py
git commit -m "feat: store template_slo_definition_id FK on slo_groups at create/update time"
```

---

## Task 5: New assignments module

**Files:**
- Create: `api/app/modules/assignments/__init__.py`
- Create: `api/app/modules/assignments/repository.py`
- Create: `api/app/modules/assignments/schemas.py`
- Create: `api/app/modules/assignments/router.py`
- Modify: `api/app/main.py`
- Create: `api/tests/db/test_assignments.py`

### Step 1: Write failing integration tests

- [ ] **Create `api/tests/db/test_assignments.py`**

```python
"""Integration tests for AssignmentRepository and assignments routes."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.modules.assignments.repository import AssignmentRepository, ResolvedAssignment


# ---------------------------------------------------------------------------
# SLO assignment CRUD
# ---------------------------------------------------------------------------

@pytest.mark.integration
async def test_create_slo_assignment_for_asset(db_session, make_asset, make_slo, make_datasource):
    asset = await make_asset(name='vm-01')
    slo = await make_slo(name='slo-cpu', version=1)
    ds = await make_datasource(name='prom-01', adapter_type='prometheus')

    repo = AssignmentRepository(db_session)
    assignment = await repo.create_slo_assignment(
        asset_id=asset.id,
        asset_group_id=None,
        slo_definition_id=slo.id,
        slo_name=slo.name,
        data_source_id=ds.id,
    )
    assert assignment.asset_id == asset.id
    assert assignment.slo_name == 'slo-cpu'
    assert assignment.slo_definition_id == slo.id


@pytest.mark.integration
async def test_create_slo_assignment_for_group(db_session, make_asset_group, make_slo, make_datasource):
    group = await make_asset_group(name='grp-linux')
    slo = await make_slo(name='slo-mem', version=1)
    ds = await make_datasource(name='prom-01', adapter_type='prometheus')

    repo = AssignmentRepository(db_session)
    assignment = await repo.create_slo_assignment(
        asset_id=None,
        asset_group_id=group.id,
        slo_definition_id=slo.id,
        slo_name=slo.name,
        data_source_id=ds.id,
    )
    assert assignment.asset_group_id == group.id
    assert assignment.slo_name == 'slo-mem'


@pytest.mark.integration
async def test_slo_assignment_unique_per_slo_name(db_session, make_asset, make_slo, make_datasource):
    from sqlalchemy.exc import IntegrityError

    asset = await make_asset(name='vm-02')
    slo_v1 = await make_slo(name='slo-cpu', version=1)
    slo_v2 = await make_slo(name='slo-cpu', version=2)
    ds = await make_datasource(name='prom-01', adapter_type='prometheus')

    repo = AssignmentRepository(db_session)
    await repo.create_slo_assignment(
        asset_id=asset.id,
        asset_group_id=None,
        slo_definition_id=slo_v1.id,
        slo_name='slo-cpu',
        data_source_id=ds.id,
    )
    with pytest.raises(IntegrityError):
        await repo.create_slo_assignment(
            asset_id=asset.id,
            asset_group_id=None,
            slo_definition_id=slo_v2.id,
            slo_name='slo-cpu',
            data_source_id=ds.id,
        )


# ---------------------------------------------------------------------------
# Group assignment CRUD
# ---------------------------------------------------------------------------

@pytest.mark.integration
async def test_create_group_assignment(db_session, make_asset, make_slo_group, make_datasource):
    asset = await make_asset(name='vm-03')
    sg = await make_slo_group(name='grp-slos')
    ds = await make_datasource(name='prom-01', adapter_type='prometheus')

    repo = AssignmentRepository(db_session)
    ga = await repo.create_group_assignment(
        asset_id=asset.id,
        asset_group_id=None,
        slo_group_id=sg.id,
        data_source_id=ds.id,
    )
    assert ga.asset_id == asset.id
    assert ga.slo_group_id == sg.id


# ---------------------------------------------------------------------------
# Resolution query
# ---------------------------------------------------------------------------

@pytest.mark.integration
async def test_resolve_direct_asset_assignment(
    db_session, make_asset, make_slo, make_datasource
):
    asset = await make_asset(name='vm-10')
    slo = await make_slo(name='slo-latency', version=1)
    ds = await make_datasource(name='prom-01', adapter_type='prometheus')

    repo = AssignmentRepository(db_session)
    await repo.create_slo_assignment(
        asset_id=asset.id, asset_group_id=None,
        slo_definition_id=slo.id, slo_name=slo.name, data_source_id=ds.id,
    )

    resolved = await repo.resolve_for_asset(asset.id, group_ids=[])
    assert len(resolved) == 1
    assert resolved[0].slo_name == 'slo-latency'
    assert resolved[0].slo_definition_id == slo.id
    assert resolved[0].source == 'direct_asset'


@pytest.mark.integration
async def test_resolve_direct_asset_wins_over_group(
    db_session, make_asset, make_asset_group, make_slo, make_datasource
):
    """direct_asset has higher precedence than direct_group for the same slo_name."""
    asset = await make_asset(name='vm-11')
    group = await make_asset_group(name='grp-a')
    slo_v1 = await make_slo(name='slo-cpu', version=1)
    slo_v2 = await make_slo(name='slo-cpu', version=2)
    ds = await make_datasource(name='prom-01', adapter_type='prometheus')

    repo = AssignmentRepository(db_session)
    # Asset pinned to v2
    await repo.create_slo_assignment(
        asset_id=asset.id, asset_group_id=None,
        slo_definition_id=slo_v2.id, slo_name='slo-cpu', data_source_id=ds.id,
    )
    # Group pinned to v1
    await repo.create_slo_assignment(
        asset_id=None, asset_group_id=group.id,
        slo_definition_id=slo_v1.id, slo_name='slo-cpu', data_source_id=ds.id,
    )

    resolved = await repo.resolve_for_asset(asset.id, group_ids=[group.id])
    assert len(resolved) == 1
    assert resolved[0].slo_definition_id == slo_v2.id
    assert resolved[0].source == 'direct_asset'
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./scripts/api-test.sh --tail 10 -m integration tests/db/test_assignments.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.assignments'`

### Step 3: Implement the assignments module

- [ ] **Create `api/app/modules/assignments/__init__.py`**

Empty file.

- [ ] **Create `api/app/modules/assignments/repository.py`**

```python
"""Repository for slo_assignments and slo_group_assignments."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SLOAssignment, SLOGroupAssignment


@dataclass
class ResolvedAssignment:
    """One resolved (slo_definition_id, data_source_id) pair after precedence dedup."""

    slo_name: str
    slo_definition_id: uuid.UUID
    data_source_id: uuid.UUID
    comparison_rules: list[dict[str, Any]] | None
    source: str  # 'direct_asset' | 'direct_group' | 'template_asset' | 'template_group'


class AssignmentRepository:
    """CRUD and resolution logic for slo_assignments and slo_group_assignments."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # SLOAssignment CRUD
    # ------------------------------------------------------------------

    async def create_slo_assignment(
        self,
        *,
        asset_id: uuid.UUID | None,
        asset_group_id: uuid.UUID | None,
        slo_definition_id: uuid.UUID,
        slo_name: str,
        data_source_id: uuid.UUID,
        comparison_rules: list[dict[str, Any]] | None = None,
    ) -> SLOAssignment:
        """Insert a new SLO assignment. Exactly one of asset_id/asset_group_id must be set."""
        row = SLOAssignment(
            id=uuid.uuid4(),
            asset_id=asset_id,
            asset_group_id=asset_group_id,
            slo_definition_id=slo_definition_id,
            slo_name=slo_name,
            data_source_id=data_source_id,
            comparison_rules=comparison_rules,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_slo_assignments_for_asset(self, asset_id: uuid.UUID) -> list[SLOAssignment]:
        """Return all direct-asset SLO assignments ordered by slo_name."""
        result = await self._session.execute(
            select(SLOAssignment)
            .where(SLOAssignment.asset_id == asset_id)
            .order_by(SLOAssignment.slo_name)
        )
        return list(result.scalars().all())

    async def list_slo_assignments_for_group(self, asset_group_id: uuid.UUID) -> list[SLOAssignment]:
        """Return all direct-group SLO assignments ordered by slo_name."""
        result = await self._session.execute(
            select(SLOAssignment)
            .where(SLOAssignment.asset_group_id == asset_group_id)
            .order_by(SLOAssignment.slo_name)
        )
        return list(result.scalars().all())

    async def upgrade_slo_assignment(
        self,
        assignment_id: uuid.UUID,
        new_slo_definition_id: uuid.UUID,
    ) -> SLOAssignment | None:
        """Update slo_definition_id in-place (version upgrade). slo_name stays the same."""
        result = await self._session.execute(
            select(SLOAssignment).where(SLOAssignment.id == assignment_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.slo_definition_id = new_slo_definition_id
        await self._session.flush()
        return row

    async def delete_slo_assignment(self, assignment_id: uuid.UUID) -> None:
        """Hard-delete an SLO assignment by ID."""
        await self._session.execute(
            delete(SLOAssignment).where(SLOAssignment.id == assignment_id)
        )

    # ------------------------------------------------------------------
    # SLOGroupAssignment CRUD
    # ------------------------------------------------------------------

    async def create_group_assignment(
        self,
        *,
        asset_id: uuid.UUID | None,
        asset_group_id: uuid.UUID | None,
        slo_group_id: uuid.UUID,
        data_source_id: uuid.UUID,
    ) -> SLOGroupAssignment:
        """Insert a new SLO group assignment."""
        row = SLOGroupAssignment(
            id=uuid.uuid4(),
            asset_id=asset_id,
            asset_group_id=asset_group_id,
            slo_group_id=slo_group_id,
            data_source_id=data_source_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_group_assignments_for_asset(self, asset_id: uuid.UUID) -> list[SLOGroupAssignment]:
        """Return all group assignments for an asset."""
        result = await self._session.execute(
            select(SLOGroupAssignment).where(SLOGroupAssignment.asset_id == asset_id)
        )
        return list(result.scalars().all())

    async def list_group_assignments_for_group(self, asset_group_id: uuid.UUID) -> list[SLOGroupAssignment]:
        """Return all group assignments for an asset group."""
        result = await self._session.execute(
            select(SLOGroupAssignment).where(SLOGroupAssignment.asset_group_id == asset_group_id)
        )
        return list(result.scalars().all())

    async def delete_group_assignment(self, assignment_id: uuid.UUID) -> None:
        """Hard-delete a group assignment by ID."""
        await self._session.execute(
            delete(SLOGroupAssignment).where(SLOGroupAssignment.id == assignment_id)
        )

    # ------------------------------------------------------------------
    # Evaluation resolution
    # ------------------------------------------------------------------

    async def resolve_for_asset(
        self,
        asset_id: uuid.UUID,
        group_ids: list[uuid.UUID],
    ) -> list[ResolvedAssignment]:
        """Return the winning (slo_definition_id, data_source_id) per SLO concept for an asset.

        Priority: direct_asset > direct_group > template_asset > template_group.
        """
        sql = text("""
WITH all_assignments AS (
    SELECT sa.slo_definition_id, sa.data_source_id, sa.comparison_rules,
           'direct_asset'::text AS source, sd.name AS slo_name
    FROM slo_assignments sa
    JOIN slo_definitions sd ON sd.id = sa.slo_definition_id
    WHERE sa.asset_id = :asset_id

    UNION ALL

    SELECT sa.slo_definition_id, sa.data_source_id, sa.comparison_rules,
           'direct_group'::text AS source, sd.name AS slo_name
    FROM slo_assignments sa
    JOIN slo_definitions sd ON sd.id = sa.slo_definition_id
    WHERE sa.asset_group_id = ANY(:group_ids)

    UNION ALL

    SELECT sd.id AS slo_definition_id, sga.data_source_id, NULL AS comparison_rules,
           'template_asset'::text AS source, sd.name AS slo_name
    FROM slo_group_assignments sga
    JOIN slo_groups sg ON sg.id = sga.slo_group_id AND sg.active = true
    JOIN slo_definitions sd ON sd.generated_by_group_id = sg.id AND sd.active = true
    WHERE sga.asset_id = :asset_id

    UNION ALL

    SELECT sd.id AS slo_definition_id, sga.data_source_id, NULL AS comparison_rules,
           'template_group'::text AS source, sd.name AS slo_name
    FROM slo_group_assignments sga
    JOIN slo_groups sg ON sg.id = sga.slo_group_id AND sg.active = true
    JOIN slo_definitions sd ON sd.generated_by_group_id = sg.id AND sd.active = true
    WHERE sga.asset_group_id = ANY(:group_ids)
)
SELECT DISTINCT ON (slo_name)
    slo_definition_id, data_source_id, comparison_rules, slo_name, source
FROM all_assignments
ORDER BY slo_name,
    CASE source
        WHEN 'direct_asset'   THEN 4
        WHEN 'direct_group'   THEN 3
        WHEN 'template_asset' THEN 2
        WHEN 'template_group' THEN 1
    END DESC
        """)
        result = await self._session.execute(
            sql,
            {'asset_id': asset_id, 'group_ids': list(group_ids) if group_ids else []},
        )
        rows = result.mappings().all()
        return [
            ResolvedAssignment(
                slo_name=row['slo_name'],
                slo_definition_id=row['slo_definition_id'],
                data_source_id=row['data_source_id'],
                comparison_rules=row['comparison_rules'],
                source=row['source'],
            )
            for row in rows
        ]

    async def find_for_asset(
        self,
        asset_id: uuid.UUID,
        group_ids: list[uuid.UUID],
        slo_name: str,
    ) -> ResolvedAssignment | None:
        """Return the winning assignment for a specific SLO name, or None."""
        resolved = await self.resolve_for_asset(asset_id, group_ids)
        for r in resolved:
            if r.slo_name == slo_name:
                return r
        return None
```

- [ ] **Create `api/app/modules/assignments/schemas.py`**

```python
"""Pydantic schemas for SLO assignments and group assignments."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SLOAssignmentCreate(BaseModel):
    """Request body for creating an SLO assignment."""

    slo_definition_id: uuid.UUID
    data_source_name: str
    comparison_rules: list[dict[str, Any]] | None = None


class SLOAssignmentRead(BaseModel):
    """Response schema for an SLO assignment."""

    id: uuid.UUID
    asset_id: uuid.UUID | None
    asset_group_id: uuid.UUID | None
    slo_definition_id: uuid.UUID
    slo_name: str
    data_source_id: uuid.UUID
    comparison_rules: list[dict[str, Any]] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SLOAssignmentUpgrade(BaseModel):
    """Request body for upgrading an SLO assignment to a new definition version."""

    new_slo_definition_id: uuid.UUID


class SLOGroupAssignmentCreate(BaseModel):
    """Request body for creating an SLO group assignment."""

    slo_group_name: str
    data_source_name: str


class SLOGroupAssignmentRead(BaseModel):
    """Response schema for an SLO group assignment."""

    id: uuid.UUID
    asset_id: uuid.UUID | None
    asset_group_id: uuid.UUID | None
    slo_group_id: uuid.UUID
    data_source_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Create `api/app/modules/assignments/router.py`**

```python
"""FastAPI router for SLO assignments and SLO group assignments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.assignments.repository import AssignmentRepository
from app.modules.assignments.schemas import (
    SLOAssignmentCreate,
    SLOAssignmentRead,
    SLOAssignmentUpgrade,
    SLOGroupAssignmentCreate,
    SLOGroupAssignmentRead,
)
from app.modules.assets.repository import AssetGroupRepository, AssetRepository
from app.modules.common.errors import raise_not_found
from app.modules.datasource.repository import DataSourceRepository
from app.modules.slo_groups.repository import SLOGroupRepository
from app.modules.slo_registry.repository import SLORepository

router = APIRouter()


# ---------------------------------------------------------------------------
# SLO Assignments — assets
# ---------------------------------------------------------------------------


@router.get('/assets/{name}/slo-assignments', response_model=list[SLOAssignmentRead])
async def list_asset_slo_assignments(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[SLOAssignmentRead]:
    """List all SLO assignments for an asset."""
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise_not_found('asset', name)
    repo = AssignmentRepository(session)
    rows = await repo.list_slo_assignments_for_asset(asset.id)
    return [SLOAssignmentRead.model_validate(r) for r in rows]


@router.post('/assets/{name}/slo-assignments', response_model=SLOAssignmentRead, status_code=201)
async def create_asset_slo_assignment(
    name: str,
    body: SLOAssignmentCreate,
    session: AsyncSession = Depends(get_session),
) -> SLOAssignmentRead:
    """Assign a specific SLO definition version to an asset."""
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise_not_found('asset', name)

    slo_def = await SLORepository(session).get_by_id(body.slo_definition_id)
    if slo_def is None:
        raise HTTPException(status_code=422, detail=f"slo definition '{body.slo_definition_id}' not found")

    ds = await DataSourceRepository(session).get_by_name(body.data_source_name)
    if ds is None:
        raise HTTPException(status_code=422, detail=f"datasource '{body.data_source_name}' not found")

    repo = AssignmentRepository(session)
    try:
        row = await repo.create_slo_assignment(
            asset_id=asset.id,
            asset_group_id=None,
            slo_definition_id=slo_def.id,
            slo_name=slo_def.name,
            data_source_id=ds.id,
            comparison_rules=body.comparison_rules,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail='slo assignment already exists for this asset and slo name') from exc
    return SLOAssignmentRead.model_validate(row)


@router.patch('/assets/{name}/slo-assignments/{assignment_id}', response_model=SLOAssignmentRead)
async def upgrade_asset_slo_assignment(
    name: str,
    assignment_id: str,
    body: SLOAssignmentUpgrade,
    session: AsyncSession = Depends(get_session),
) -> SLOAssignmentRead:
    """Upgrade an SLO assignment to a new definition version."""
    import uuid as _uuid
    repo = AssignmentRepository(session)
    row = await repo.upgrade_slo_assignment(_uuid.UUID(assignment_id), body.new_slo_definition_id)
    if row is None:
        raise HTTPException(status_code=404, detail='assignment not found')
    return SLOAssignmentRead.model_validate(row)


@router.delete('/assets/{name}/slo-assignments/{assignment_id}', status_code=204)
async def delete_asset_slo_assignment(
    name: str,
    assignment_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an SLO assignment from an asset."""
    import uuid as _uuid
    await AssignmentRepository(session).delete_slo_assignment(_uuid.UUID(assignment_id))


# ---------------------------------------------------------------------------
# SLO Assignments — asset groups
# ---------------------------------------------------------------------------


@router.get('/asset-groups/{name}/slo-assignments', response_model=list[SLOAssignmentRead])
async def list_group_slo_assignments(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[SLOAssignmentRead]:
    """List all SLO assignments for an asset group."""
    ag = await AssetGroupRepository(session).get_by_name(name)
    if ag is None:
        raise_not_found('asset group', name)
    rows = await AssignmentRepository(session).list_slo_assignments_for_group(ag.id)
    return [SLOAssignmentRead.model_validate(r) for r in rows]


@router.post('/asset-groups/{name}/slo-assignments', response_model=SLOAssignmentRead, status_code=201)
async def create_group_slo_assignment(
    name: str,
    body: SLOAssignmentCreate,
    session: AsyncSession = Depends(get_session),
) -> SLOAssignmentRead:
    """Assign a specific SLO definition version to an asset group."""
    ag = await AssetGroupRepository(session).get_by_name(name)
    if ag is None:
        raise_not_found('asset group', name)

    slo_def = await SLORepository(session).get_by_id(body.slo_definition_id)
    if slo_def is None:
        raise HTTPException(status_code=422, detail=f"slo definition '{body.slo_definition_id}' not found")

    ds = await DataSourceRepository(session).get_by_name(body.data_source_name)
    if ds is None:
        raise HTTPException(status_code=422, detail=f"datasource '{body.data_source_name}' not found")

    repo = AssignmentRepository(session)
    try:
        row = await repo.create_slo_assignment(
            asset_id=None,
            asset_group_id=ag.id,
            slo_definition_id=slo_def.id,
            slo_name=slo_def.name,
            data_source_id=ds.id,
            comparison_rules=body.comparison_rules,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail='slo assignment already exists for this group and slo name') from exc
    return SLOAssignmentRead.model_validate(row)


@router.delete('/asset-groups/{name}/slo-assignments/{assignment_id}', status_code=204)
async def delete_group_slo_assignment(
    name: str,
    assignment_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an SLO assignment from an asset group."""
    import uuid as _uuid
    await AssignmentRepository(session).delete_slo_assignment(_uuid.UUID(assignment_id))


# ---------------------------------------------------------------------------
# SLO Group Assignments — assets
# ---------------------------------------------------------------------------


@router.get('/assets/{name}/slo-group-assignments', response_model=list[SLOGroupAssignmentRead])
async def list_asset_group_assignments(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[SLOGroupAssignmentRead]:
    """List all SLO group assignments for an asset."""
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise_not_found('asset', name)
    rows = await AssignmentRepository(session).list_group_assignments_for_asset(asset.id)
    return [SLOGroupAssignmentRead.model_validate(r) for r in rows]


@router.post('/assets/{name}/slo-group-assignments', response_model=SLOGroupAssignmentRead, status_code=201)
async def create_asset_group_assignment(
    name: str,
    body: SLOGroupAssignmentCreate,
    session: AsyncSession = Depends(get_session),
) -> SLOGroupAssignmentRead:
    """Assign an SLO group to an asset (always-latest semantics)."""
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise_not_found('asset', name)

    sg = await SLOGroupRepository(session).get_by_name(body.slo_group_name)
    if sg is None:
        raise HTTPException(status_code=422, detail=f"slo group '{body.slo_group_name}' not found")

    ds = await DataSourceRepository(session).get_by_name(body.data_source_name)
    if ds is None:
        raise HTTPException(status_code=422, detail=f"datasource '{body.data_source_name}' not found")

    repo = AssignmentRepository(session)
    try:
        row = await repo.create_group_assignment(
            asset_id=asset.id,
            asset_group_id=None,
            slo_group_id=sg.id,
            data_source_id=ds.id,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail='group assignment already exists') from exc
    return SLOGroupAssignmentRead.model_validate(row)


@router.delete('/assets/{name}/slo-group-assignments/{assignment_id}', status_code=204)
async def delete_asset_group_assignment(
    name: str,
    assignment_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an SLO group assignment from an asset."""
    import uuid as _uuid
    await AssignmentRepository(session).delete_group_assignment(_uuid.UUID(assignment_id))


# ---------------------------------------------------------------------------
# SLO Group Assignments — asset groups
# ---------------------------------------------------------------------------


@router.get('/asset-groups/{name}/slo-group-assignments', response_model=list[SLOGroupAssignmentRead])
async def list_group_group_assignments(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[SLOGroupAssignmentRead]:
    """List all SLO group assignments for an asset group."""
    ag = await AssetGroupRepository(session).get_by_name(name)
    if ag is None:
        raise_not_found('asset group', name)
    rows = await AssignmentRepository(session).list_group_assignments_for_group(ag.id)
    return [SLOGroupAssignmentRead.model_validate(r) for r in rows]


@router.post('/asset-groups/{name}/slo-group-assignments', response_model=SLOGroupAssignmentRead, status_code=201)
async def create_group_group_assignment(
    name: str,
    body: SLOGroupAssignmentCreate,
    session: AsyncSession = Depends(get_session),
) -> SLOGroupAssignmentRead:
    """Assign an SLO group to an asset group (always-latest semantics)."""
    ag = await AssetGroupRepository(session).get_by_name(name)
    if ag is None:
        raise_not_found('asset group', name)

    sg = await SLOGroupRepository(session).get_by_name(body.slo_group_name)
    if sg is None:
        raise HTTPException(status_code=422, detail=f"slo group '{body.slo_group_name}' not found")

    ds = await DataSourceRepository(session).get_by_name(body.data_source_name)
    if ds is None:
        raise HTTPException(status_code=422, detail=f"datasource '{body.data_source_name}' not found")

    repo = AssignmentRepository(session)
    try:
        row = await repo.create_group_assignment(
            asset_id=None,
            asset_group_id=ag.id,
            slo_group_id=sg.id,
            data_source_id=ds.id,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail='group assignment already exists') from exc
    return SLOGroupAssignmentRead.model_validate(row)


@router.delete('/asset-groups/{name}/slo-group-assignments/{assignment_id}', status_code=204)
async def delete_group_group_assignment(
    name: str,
    assignment_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an SLO group assignment from an asset group."""
    import uuid as _uuid
    await AssignmentRepository(session).delete_group_assignment(_uuid.UUID(assignment_id))
```

- [ ] **Step 4: Add `SLORepository.get_by_id()`**

The router uses `SLORepository.get_by_id()`. Add this to `api/app/modules/slo_registry/repository.py` after `get_version`:

```python
async def get_by_id(self, slo_id: uuid.UUID) -> SLODefinition | None:
    """Return a specific SLO definition by primary key, or None."""
    result = await self._session.execute(
        select(SLODefinition).where(SLODefinition.id == slo_id)
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 5: Register router in `api/app/main.py`**

Add to imports:
```python
from app.modules.assignments.router import router as assignments_router
```

Add after existing `app.include_router(...)` calls:
```python
app.include_router(assignments_router)
```

- [ ] **Step 6: Run integration tests**

```bash
./scripts/api-test.sh --tail 20 -m integration tests/db/test_assignments.py -v
```

Expected: all tests PASS

- [ ] **Step 7: Run full test suite**

```bash
./scripts/api-test.sh --tail 10
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add api/app/modules/assignments/ api/app/modules/slo_registry/repository.py api/app/main.py api/tests/db/test_assignments.py
git commit -m "feat: add assignments module with SLO assignment CRUD and SQL resolution query"
```

---

## Task 6: Rewire trigger resolution to use assignments

**Files:**
- Modify: `api/app/modules/quality_gate/protocols.py`
- Modify: `api/app/modules/quality_gate/trigger.py`
- Modify: `api/app/modules/quality_gate/params.py`
- Modify: `api/app/modules/quality_gate/repository.py`
- Modify: `api/app/modules/quality_gate/dependencies.py`
- Modify: `api/app/modules/quality_gate/trigger_service.py`

- [ ] **Step 1: Update `protocols.py` — add `AssignmentReader`**

Replace the contents of `api/app/modules/quality_gate/protocols.py`:

```python
"""Protocol types for repository interfaces used by trigger resolution."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from app.db.models import Asset, DataSource, SLIDefinition, SLOBinding, SLODefinition
from app.modules.assignments.repository import ResolvedAssignment


class AssetReader(Protocol):
    """Read-only protocol for asset lookup by name."""

    async def get_by_name(self, name: str) -> Asset | None:
        """Return asset by unique name, or None."""
        ...


class SLIReader(Protocol):
    """Read-only protocol for SLI definition lookup."""

    async def get_latest(self, name: str) -> SLIDefinition | None:
        ...

    async def get_version(self, name: str, version: int) -> SLIDefinition | None:
        ...

    async def get_by_id(self, sli_id: uuid.UUID) -> SLIDefinition | None:
        ...


class SLOReader(Protocol):
    """Read-only protocol for SLO definition lookup."""

    async def get_latest(self, name: str) -> SLODefinition | None:
        ...

    async def get_version(self, name: str, version: int) -> SLODefinition | None:
        ...

    async def get_by_id(self, slo_id: uuid.UUID) -> SLODefinition | None:
        ...

    async def list_by_group_id(self, group_id: uuid.UUID) -> list[SLODefinition]:
        ...


class AssignmentReader(Protocol):
    """Read-only protocol for assignment resolution."""

    async def resolve_for_asset(
        self, asset_id: uuid.UUID, group_ids: list[uuid.UUID]
    ) -> list[ResolvedAssignment]:
        ...

    async def find_for_asset(
        self, asset_id: uuid.UUID, group_ids: list[uuid.UUID], slo_name: str
    ) -> ResolvedAssignment | None:
        ...


class SLOBindingReader(Protocol):
    """Read-only protocol for SLO binding lookup (legacy — keep until Task 7 cleanup)."""

    async def find_for_asset(self, asset_id: uuid.UUID, slo_name: str) -> SLOBinding | None:
        ...

    async def list_for_asset_evaluation(self, asset_id: uuid.UUID, group_ids: list[uuid.UUID]) -> list[SLOBinding]:
        ...


class DataSourceReader(Protocol):
    """Read-only protocol for data source lookup."""

    async def get_by_name(self, name: str) -> DataSource | None:
        ...

    async def get_by_id(self, ds_id: uuid.UUID) -> DataSource | None:
        ...
```

- [ ] **Step 2: Add `DataSourceRepository.get_by_id()`**

In `api/app/modules/datasource/repository.py`, add after `get_by_name`:

```python
async def get_by_id(self, ds_id: uuid.UUID) -> DataSource | None:
    """Return datasource by primary key, or None."""
    result = await self._session.execute(select(DataSource).where(DataSource.id == ds_id))
    return result.scalar_one_or_none()
```

- [ ] **Step 3: Update `trigger.py` — new resolution using `AssignmentReader`**

Replace `api/app/modules/quality_gate/trigger.py`:

```python
"""Evaluation trigger resolution — resolves asset/SLO/SLI/datasource references."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.modules.quality_gate.exceptions import (
    AssetNotFoundError,
    DataSourceNotFoundError,
    SLONotConfiguredError,
)
from app.modules.quality_gate.protocols import (
    AssignmentReader,
    AssetReader,
    DataSourceReader,
    SLIReader,
    SLOReader,
)


@dataclass
class TriggerContext:
    """All resolved references needed to run an evaluation job."""

    asset_id: uuid.UUID
    asset_name: str
    asset_display_name: str | None
    asset_tags: dict[str, Any]
    asset_variables: dict[str, Any]
    slo_name: str
    slo_version: int
    slo_definition_id: uuid.UUID
    sli_name: str
    sli_version: int
    sli_definition_id: uuid.UUID | None
    data_source_name: str
    adapter_url: str
    adapter_type: str
    indicators: dict[str, str]


async def resolve_single_trigger(
    *,
    asset_name: str,
    slo_name: str,
    asset_repo: AssetReader,
    sli_repo: SLIReader,
    slo_repo: SLOReader,
    ds_repo: DataSourceReader,
    assignment_repo: AssignmentReader,
    group_ids: list[uuid.UUID],
) -> TriggerContext:
    """Resolve all references for a single asset+SLO pair.

    Raises domain exceptions if any reference is missing.
    """
    asset = await asset_repo.get_by_name(asset_name)
    if asset is None:
        msg = f"asset '{asset_name}' not found"
        raise AssetNotFoundError(msg)

    resolved = await assignment_repo.find_for_asset(asset.id, group_ids, slo_name)
    if resolved is None:
        msg = f"no assignment for asset '{asset_name}' with slo '{slo_name}'"
        raise SLONotConfiguredError(msg)

    slo_def = await slo_repo.get_by_id(resolved.slo_definition_id)
    if slo_def is None:
        msg = f"slo definition '{resolved.slo_definition_id}' not found"
        raise SLONotConfiguredError(msg)

    # Load SLI by FK if available, fall back to name-based lookup
    if slo_def.sli_definition_id is not None:
        sli_def = await sli_repo.get_by_id(slo_def.sli_definition_id)
    elif slo_def.sli_name is not None:
        sli_def = (
            await sli_repo.get_version(slo_def.sli_name, slo_def.sli_version)
            if slo_def.sli_version is not None
            else await sli_repo.get_latest(slo_def.sli_name)
        )
    else:
        msg = f"no sli linked to slo '{slo_def.name}'"
        raise SLONotConfiguredError(msg)

    if sli_def is None:
        msg = f"sli definition for slo '{slo_def.name}' not found"
        raise SLONotConfiguredError(msg)

    ds = await ds_repo.get_by_id(resolved.data_source_id)
    if ds is None:
        msg = f"datasource '{resolved.data_source_id}' not found"
        raise DataSourceNotFoundError(msg)

    return TriggerContext(
        asset_id=asset.id,
        asset_name=asset.name,
        asset_display_name=getattr(asset, 'display_name', None),
        asset_tags=getattr(asset, 'tags', {}),
        asset_variables=getattr(asset, 'variables', {}),
        slo_name=slo_def.name,
        slo_version=slo_def.version,
        slo_definition_id=slo_def.id,
        sli_name=sli_def.name,
        sli_version=sli_def.version,
        sli_definition_id=slo_def.sli_definition_id,
        data_source_name=ds.name,
        adapter_url=ds.adapter_url,
        adapter_type=ds.adapter_type,
        indicators=sli_def.indicators,
    )


async def resolve_all_slos_for_asset(
    *,
    asset_id: uuid.UUID,
    assignment_repo: AssignmentReader,
    group_ids: list[uuid.UUID],
) -> list[str]:
    """Collect all SLO names assigned to an asset (direct + via groups)."""
    resolved = await assignment_repo.resolve_for_asset(asset_id, group_ids)
    return sorted(r.slo_name for r in resolved)
```

- [ ] **Step 4: Update `EvalCreateParams` in `params.py`**

In `api/app/modules/quality_gate/params.py`, add after `data_source_name`:

```python
slo_definition_id: uuid.UUID | None = None
sli_definition_id: uuid.UUID | None = None
```

- [ ] **Step 5: Store FK columns in `EvaluationRepository.create_pending()`**

In `api/app/modules/quality_gate/repository.py`, update the `SLOEvaluation(...)` constructor to add:

```python
ev = SLOEvaluation(
    id=uuid.uuid4(),
    evaluation_id=params.evaluation_id,
    evaluation_name=params.evaluation_name,
    period_start=params.period_start,
    period_end=params.period_end,
    ingestion_mode=params.ingestion_mode,
    asset_snapshot=params.asset_snapshot,
    variables=merged_variables,
    asset_id=params.asset_id,
    slo_name=params.slo_name,
    slo_version=params.slo_version,
    slo_definition_id=params.slo_definition_id,   # ← add
    adapter_used=params.adapter_used,
    sli_name=params.sli_name,
    sli_version=params.sli_version,
    sli_definition_id=params.sli_definition_id,   # ← add
    data_source_name=params.data_source_name,
    status=EvaluationStatus.PENDING,
)
```

- [ ] **Step 6: Update `dependencies.py`**

In `api/app/modules/quality_gate/dependencies.py`:

Add import:
```python
from app.modules.assignments.repository import AssignmentRepository
```

Add to `QualityGateRepos`:
```python
assignment_repo: AssignmentRepository
```

Remove:
```python
binding_repo: SLOBindingRepository
```

Update `get_qg_repos`:
- Remove: `binding_repo=SLOBindingRepository(session),`
- Add: `assignment_repo=AssignmentRepository(session),`
- Remove the `SLOBindingRepository` import from `app.modules.assets.repository`

- [ ] **Step 7: Update `trigger_service.py`**

Update all calls to `resolve_single_trigger` — replace `binding_repo=self._repos.binding_repo` with `assignment_repo=self._repos.assignment_repo, group_ids=group_ids`. Update `resolve_all_slos_for_asset` calls to use `assignment_repo` instead of `binding_repo`.

In `trigger_single`:

```python
async def trigger_single(self, request: TriggerRequest) -> TriggerResponse:
    asset = await self._repos.asset_repo.get_by_name(request.asset_name)
    if asset is None:
        msg = f"asset '{request.asset_name}' not found"
        raise AssetNotFoundError(msg)
    group_ids = await self._repos.asset_group_repo.list_group_ids_for_asset(asset.id)

    ctx = await resolve_single_trigger(
        asset_name=request.asset_name,
        slo_name=request.slo_name,
        asset_repo=self._repos.asset_repo,
        sli_repo=self._repos.sli_def_repo,
        slo_repo=self._repos.slo_repo,
        ds_repo=self._repos.ds_repo,
        assignment_repo=self._repos.assignment_repo,
        group_ids=group_ids,
    )
    # ... duplicate check unchanged ...
    run_id = uuid.uuid4()
    ev = await self._repos.eval_repo.create_pending(
        EvalCreateParams(
            evaluation_id=run_id,
            evaluation_name=request.evaluation_name,
            period_start=request.period_start,
            period_end=request.period_end,
            ingestion_mode='pull',
            asset_snapshot={
                'name': ctx.asset_name,
                'display_name': ctx.asset_display_name,
                'tags': ctx.asset_tags,
                'variables': ctx.asset_variables,
            },
            variables=request.variables,
            asset_id=ctx.asset_id,
            slo_name=ctx.slo_name,
            slo_version=ctx.slo_version,
            slo_definition_id=ctx.slo_definition_id,
            sli_name=ctx.sli_name,
            sli_version=ctx.sli_version,
            sli_definition_id=ctx.sli_definition_id,
            data_source_name=ctx.data_source_name,
            adapter_used=ctx.adapter_type,
        )
    )
    await self._repos.session.commit()
    await self._pool.enqueue_job('run_evaluation_job', str(ev.id))
    return TriggerResponse(id=ev.id, status='pending')
```

Apply the same pattern (`group_ids` fetch + `assignment_repo` + `slo_definition_id`/`sli_definition_id` in `EvalCreateParams`) to `trigger_asset`, `trigger_batch`, `trigger_evaluate`, and `trigger_evaluate_batch`.

Also update the import at the top:
```python
from app.modules.quality_gate.trigger import (
    TriggerContext,
    resolve_all_slos_for_asset,
    resolve_single_trigger,
)
```

Remove the `resolve_all_bindings_for_asset` import if present.

- [ ] **Step 8: Run unit + integration tests**

```bash
./scripts/api-test.sh --tail 20
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add api/app/modules/quality_gate/ api/app/modules/datasource/repository.py
git commit -m "feat: rewire trigger resolution to use assignment_repo with FK-based SLO/SLI loading"
```

---

## Task 7: Remove old bindings code and columns

**Files:**
- Modify: `api/app/db/models.py`
- Modify: `api/app/modules/assets/repository.py`
- Modify: `api/app/modules/assets/router.py`
- Modify: `api/app/modules/slo_groups/repository.py`
- Modify: `api/app/modules/slo_groups/schemas.py`
- Modify: `api/app/modules/slo_groups/router.py`
- Delete: `api/tests/db/test_slo_bindings.py`

- [ ] **Step 1: Remove `SLOBinding` and `TemplateBinding` from `models.py`**

Delete the `SLOBinding` class (lines 335–360) and `TemplateBinding` class (lines 390–413).

Also remove from `SLODefinition`:
```python
sli_name: Mapped[str | None] = ...
sli_version: Mapped[int | None] = ...
```

And from `SLOGroup`:
```python
template_slo_name: Mapped[str] = ...
template_slo_version: Mapped[int] = ...
```

Make `template_slo_definition_id` non-nullable on `SLOGroup`:
```python
template_slo_definition_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('slo_definitions.id'), nullable=False)
```

- [ ] **Step 2: Remove `SLOBindingRepository` from `assets/repository.py`**

Delete the `SLOBindingRepository` class and remove `SLOBinding` from the imports.

- [ ] **Step 3: Remove SLO binding routes from `assets/router.py`**

Remove:
- `_validate_binding_adapter_type` function
- `GET/POST /assets/{name}/slo-bindings` routes
- `DELETE /assets/{name}/slo-bindings/{slo_name}` route
- `GET/POST /asset-groups/{name}/slo-bindings` routes
- `DELETE /asset-groups/{name}/slo-bindings/{slo_name}` route
- `SLOBindingCreate`, `SLOBindingRead`, `SLOBindingRepository`, `ComparisonRulesUpdate` imports (if unused)

- [ ] **Step 4: Remove `TemplateBindingRepository` and fan-out functions from `slo_groups/`**

In `api/app/modules/slo_groups/repository.py`:
- Delete `TemplateBindingRepository` class
- Remove `TemplateBinding` from imports

In `api/app/modules/slo_groups/router.py`:
- Delete `_fan_out_slo_bindings()` function
- Delete `_sync_template_bindings_for_group()` function
- Delete `_validate_template_binding_adapter_type()` function
- Delete all template binding route handlers (6 routes across assets + asset-groups)
- Remove `TemplateBindingRepository` import
- Remove `TemplateBindingCreate`, `TemplateBindingRead` imports
- Remove `SLOBindingRepository` import
- Remove the call to `_sync_template_bindings_for_group()` in `update_slo_group`
- Remove the binding sync calls in `delete_slo_group` and `extract_slo`

Update `_build_group_read` to populate `template_slo_name` and `template_slo_version` from the FK join (since the columns are removed from the model):

```python
async def _build_group_read(
    group_repo: SLOGroupRepository,
    group: Any,
    slo_repo: SLORepository,
) -> SLOGroupRead:
    """Build an SLOGroupRead with computed fields."""
    count = await group_repo.count_generated_slos(group.id)
    template_slo = await slo_repo.get_by_id(group.template_slo_definition_id)
    return SLOGroupRead(
        id=group.id,
        name=group.name,
        display_name=group.display_name,
        template_slo_name=template_slo.name if template_slo else '',
        template_slo_version=template_slo.version if template_slo else 0,
        template_slo_definition_id=group.template_slo_definition_id,
        gen_variables=group.gen_variables,
        tags=group.tags,
        author=group.author,
        version=group.version,
        active=group.active,
        created_at=group.created_at,
        updated_at=group.updated_at,
        generated_slo_count=count,
    )
```

Pass `slo_repo` to all `_build_group_read()` call sites.

- [ ] **Step 5: Update `slo_groups/schemas.py`**

Remove `TemplateBindingCreate` and `TemplateBindingRead` classes.

Update `SLOGroupRead` to add `template_slo_definition_id`:

```python
class SLOGroupRead(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str | None
    template_slo_name: str          # populated via FK join
    template_slo_version: int       # populated via FK join
    template_slo_definition_id: uuid.UUID
    gen_variables: dict[str, list[str]]
    tags: dict[str, Any]
    author: str | None
    version: int
    active: bool
    created_at: datetime
    updated_at: datetime
    generated_slo_count: int

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 6: Delete `api/tests/db/test_slo_bindings.py`**

```bash
rm api/tests/db/test_slo_bindings.py
```

- [ ] **Step 7: Regen migration**

```bash
./scripts/db-regen-migrations.sh
```

- [ ] **Step 8: Run full test suite**

```bash
just test-env
./scripts/api-test.sh --tail 20 -m integration -v
```

Expected: all tests PASS

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: remove slo_bindings/template_bindings tables, fan-out functions, and old binding routes"
```

---

## Task 8: Display groups module

**Files:**
- Create: `api/app/modules/display_groups/__init__.py`
- Create: `api/app/modules/display_groups/repository.py`
- Create: `api/app/modules/display_groups/schemas.py`
- Create: `api/app/modules/display_groups/router.py`
- Modify: `api/app/main.py`

- [ ] **Step 1: Write failing integration test**

Create `api/tests/db/test_display_groups.py`:

```python
"""Integration tests for SLO display groups."""

from __future__ import annotations

import pytest
from app.modules.display_groups.repository import DisplayGroupRepository


@pytest.mark.integration
async def test_create_display_group(db_session):
    repo = DisplayGroupRepository(db_session)
    group = await repo.create(name='software-xyz', display_name='Software XYZ')
    assert group.name == 'software-xyz'
    assert group.parent_id is None


@pytest.mark.integration
async def test_create_nested_display_group(db_session):
    repo = DisplayGroupRepository(db_session)
    parent = await repo.create(name='platform', display_name='Platform')
    child = await repo.create(name='platform-networking', display_name='Networking', parent_id=parent.id)
    assert child.parent_id == parent.id


@pytest.mark.integration
async def test_add_member(db_session, make_slo):
    await make_slo(name='slo-cpu', version=1)
    repo = DisplayGroupRepository(db_session)
    group = await repo.create(name='compute', display_name='Compute')
    await repo.add_member(group.id, 'slo-cpu')
    members = await repo.list_members(group.id)
    assert 'slo-cpu' in members
```

- [ ] **Step 2: Run to verify failure**

```bash
./scripts/api-test.sh --tail 10 -m integration tests/db/test_display_groups.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `DisplayGroupRepository`**

Create `api/app/modules/display_groups/__init__.py` (empty).

Create `api/app/modules/display_groups/repository.py`:

```python
"""Repository for slo_display_groups and slo_display_group_members."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SLODisplayGroup, SLODisplayGroupMember


class DisplayGroupRepository:
    """CRUD for slo_display_groups and slo_display_group_members."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        name: str,
        display_name: str | None = None,
        parent_id: uuid.UUID | None = None,
        sort_order: int = 0,
    ) -> SLODisplayGroup:
        """Insert a new display group."""
        group = SLODisplayGroup(
            id=uuid.uuid4(),
            name=name,
            display_name=display_name,
            parent_id=parent_id,
            sort_order=sort_order,
        )
        self._session.add(group)
        await self._session.flush()
        return group

    async def get_by_name(self, name: str) -> SLODisplayGroup | None:
        """Return display group by unique name, or None."""
        result = await self._session.execute(
            select(SLODisplayGroup).where(SLODisplayGroup.name == name)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[SLODisplayGroup]:
        """Return all display groups ordered by sort_order, then name."""
        result = await self._session.execute(
            select(SLODisplayGroup).order_by(SLODisplayGroup.sort_order, SLODisplayGroup.name)
        )
        return list(result.scalars().all())

    async def delete(self, name: str) -> None:
        """Hard-delete a display group by name (cascades to members)."""
        await self._session.execute(
            delete(SLODisplayGroup).where(SLODisplayGroup.name == name)
        )

    async def add_member(self, group_id: uuid.UUID, slo_name: str) -> None:
        """Add an SLO concept name to a display group. No-op if already a member."""
        row = SLODisplayGroupMember(group_id=group_id, slo_name=slo_name)
        self._session.add(row)
        try:
            await self._session.flush()
        except Exception:
            await self._session.rollback()

    async def remove_member(self, group_id: uuid.UUID, slo_name: str) -> None:
        """Remove an SLO concept name from a display group."""
        await self._session.execute(
            delete(SLODisplayGroupMember).where(
                SLODisplayGroupMember.group_id == group_id,
                SLODisplayGroupMember.slo_name == slo_name,
            )
        )

    async def list_members(self, group_id: uuid.UUID) -> list[str]:
        """Return all slo_names in a display group, sorted."""
        result = await self._session.execute(
            select(SLODisplayGroupMember.slo_name)
            .where(SLODisplayGroupMember.group_id == group_id)
            .order_by(SLODisplayGroupMember.slo_name)
        )
        return list(result.scalars().all())
```

- [ ] **Step 4: Create schemas and router**

Create `api/app/modules/display_groups/schemas.py`:

```python
"""Pydantic schemas for SLO display groups."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DisplayGroupCreate(BaseModel):
    name: str
    display_name: str | None = None
    parent_id: uuid.UUID | None = None
    sort_order: int = 0


class DisplayGroupRead(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str | None
    parent_id: uuid.UUID | None
    sort_order: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DisplayGroupMemberAdd(BaseModel):
    slo_name: str
```

Create `api/app/modules/display_groups/router.py`:

```python
"""FastAPI router for SLO display groups."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.common.errors import raise_not_found
from app.modules.display_groups.repository import DisplayGroupRepository
from app.modules.display_groups.schemas import (
    DisplayGroupCreate,
    DisplayGroupMemberAdd,
    DisplayGroupRead,
)

router = APIRouter()


@router.get('/slo-display-groups', response_model=list[DisplayGroupRead])
async def list_display_groups(session: AsyncSession = Depends(get_session)) -> list[DisplayGroupRead]:
    """List all SLO display groups."""
    repo = DisplayGroupRepository(session)
    groups = await repo.list_all()
    return [DisplayGroupRead.model_validate(g) for g in groups]


@router.post('/slo-display-groups', response_model=DisplayGroupRead, status_code=201)
async def create_display_group(
    body: DisplayGroupCreate,
    session: AsyncSession = Depends(get_session),
) -> DisplayGroupRead:
    """Create a new SLO display group."""
    repo = DisplayGroupRepository(session)
    group = await repo.create(
        name=body.name,
        display_name=body.display_name,
        parent_id=body.parent_id,
        sort_order=body.sort_order,
    )
    return DisplayGroupRead.model_validate(group)


@router.delete('/slo-display-groups/{name}', status_code=204)
async def delete_display_group(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a display group and all its memberships."""
    repo = DisplayGroupRepository(session)
    group = await repo.get_by_name(name)
    if group is None:
        raise_not_found('slo display group', name)
    await repo.delete(name)


@router.get('/slo-display-groups/{name}/members', response_model=list[str])
async def list_members(name: str, session: AsyncSession = Depends(get_session)) -> list[str]:
    """List SLO concept names in this display group."""
    repo = DisplayGroupRepository(session)
    group = await repo.get_by_name(name)
    if group is None:
        raise_not_found('slo display group', name)
    return await repo.list_members(group.id)


@router.post('/slo-display-groups/{name}/members', status_code=204)
async def add_member(
    name: str,
    body: DisplayGroupMemberAdd,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Add an SLO concept to this display group."""
    repo = DisplayGroupRepository(session)
    group = await repo.get_by_name(name)
    if group is None:
        raise_not_found('slo display group', name)
    await repo.add_member(group.id, body.slo_name)


@router.delete('/slo-display-groups/{name}/members/{slo_name}', status_code=204)
async def remove_member(
    name: str,
    slo_name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an SLO concept from this display group."""
    repo = DisplayGroupRepository(session)
    group = await repo.get_by_name(name)
    if group is None:
        raise_not_found('slo display group', name)
    await repo.remove_member(group.id, slo_name)
```

- [ ] **Step 5: Register in `main.py`**

```python
from app.modules.display_groups.router import router as display_groups_router
# ...
app.include_router(display_groups_router)
```

- [ ] **Step 6: Run tests**

```bash
./scripts/api-test.sh --tail 10 -m integration tests/db/test_display_groups.py -v
```

Expected: PASS

- [ ] **Step 7: Final full test run**

```bash
./scripts/api-test.sh --tail 20
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add api/app/modules/display_groups/ api/app/main.py api/tests/db/test_display_groups.py
git commit -m "feat: add slo_display_groups module for UI navigation hierarchy"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `slo_assignments` table with XOR FK | Task 1, 5 |
| `slo_group_assignments` table | Task 1, 5 |
| `slo_definitions.sli_definition_id FK` | Task 1, 3 |
| `slo_groups.template_slo_definition_id FK` | Task 1, 4 |
| Remove `slo_bindings`, `template_bindings` | Task 7 |
| Remove `sli_name/version` from `slo_definitions` | Task 7 |
| Remove `template_slo_name/version` from `slo_groups` | Task 7 |
| Remove fan-out functions | Task 7 |
| Evaluation resolution SQL (UNION ALL + DISTINCT ON) | Task 5 |
| `slo_evaluations.slo_definition_id/sli_definition_id` | Task 1, 6 |
| `slo_display_groups` + `slo_display_group_members` | Task 1, 8 |
| Version-pinned direct assignments | Task 5 |
| Always-latest group assignments | Task 5 |
| Precedence: direct_asset > direct_group > template_asset > template_group | Task 5 |
| SLO version upgrade via `upgrade_slo_assignment()` | Task 5 |

**Type consistency:** `ResolvedAssignment` is defined in `assignments/repository.py` and imported in `protocols.py` — consistent. `TriggerContext.slo_definition_id` populated in `trigger.py` and consumed in `trigger_service.py` — consistent. `EvalCreateParams.slo_definition_id` passed through to `SLOEvaluation` — consistent.
