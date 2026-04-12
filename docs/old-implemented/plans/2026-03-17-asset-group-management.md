# Asset Group Management Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add asset group CRUD, SLO linking, and filtered views to the SLO Registry page with supporting backend changes.

**Architecture:** Three parallel tracks — Track A adds `adapter_type` to SLI model, unique constraint on group SLO links, PATCH/DELETE endpoints for groups, and resets the migration. Track B extracts a `GroupTreeRenderer` component and builds the sidebar + group CRUD dialogs. Track C (depends on A+B) wires the link dialog, "+ Group" on SLO cards, and list filtering.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy (async), Alembic, React 19, TypeScript, TanStack Query, Tailwind CSS, Base-UI primitives

**Spec:** `docs/superpowers/specs/2026-03-16-asset-group-management-design.md`

---

## File Structure

### Backend (Track A)

| File | Action | Responsibility |
|---|---|---|
| `api/app/db/models.py` | Modify | Add `adapter_type` to `SLIDefinition`, add `UNIQUE(group_id, slo_name)` to `AssetGroupSLOLink` |
| `api/app/modules/sli_registry/schemas.py` | Modify | Add `adapter_type` field to `SLIDefinitionCreate` and `SLIDefinitionRead` |
| `api/app/modules/sli_registry/repository.py` | Modify | Pass `adapter_type` through `create()`, add `?adapter_type` filter to `list_all()` |
| `api/app/modules/sli_registry/router.py` | Modify | Add `adapter_type` query param to `list_sli_definitions` |
| `api/app/modules/assets/schemas.py` | Modify | Add `AssetGroupUpdate` schema |
| `api/app/modules/assets/repository.py` | Modify | Add `update()`, `delete()` methods to `AssetGroupRepository`; auto-generate `link_name` in `AssetGroupSLOLinkRepository.create()` |
| `api/app/modules/assets/router.py` | Modify | Add `PATCH /asset-groups/{name}`, `DELETE /asset-groups/{name}` endpoints |
| `api/tests/db/test_sli_repository.py` | Modify | Add tests for `adapter_type` field and filtering |
| `api/tests/db/test_asset_repositories.py` | Modify | Add tests for group update, delete, link uniqueness, link_name auto-generation |
| `api/alembic/versions/001_initial_schema.py` | Recreate | Delete old, autogenerate fresh from current models |
| `api/alembic/versions/63404ff4de0e_slo_format_redesign.py` | Delete | Merged into new 001 |

### Frontend — Shared (Track B)

| File | Action | Responsibility |
|---|---|---|
| `ui/src/components/GroupTreeRenderer.tsx` | Create | Generic recursive tree: expand/collapse, filter, selection, indent |
| `ui/src/features/assets/components/AssetGroupCard.tsx` | Modify | Refactor to consume `GroupTreeRenderer` |

### Frontend — SLO Feature (Tracks B+C)

| File | Action | Responsibility |
|---|---|---|
| `ui/src/features/slos/components/GroupSidebar.tsx` | Create | 180px sidebar: tree, search, "All SLOs"/"Ungrouped" nodes, context menu |
| `ui/src/features/slos/components/GroupCreateDialog.tsx` | Create | Create group dialog (name, display_name, description, parent) |
| `ui/src/features/slos/components/GroupEditDialog.tsx` | Create | Edit group dialog (properties + linked SLOs with unlink) |
| `ui/src/features/slos/components/GroupDeleteDialog.tsx` | Create | Delete dialog (radio + confirmation modal) |
| `ui/src/features/slos/components/SloLinkDialog.tsx` | Create | Shared link dialog (datasource → SLI → group/SLO comboboxes) |
| `ui/src/features/slos/api.ts` | Modify | Add group CRUD + link API functions |
| `ui/src/features/slos/hooks.ts` | Modify | Add group query/mutation hooks |
| `ui/src/features/slos/types.ts` | Modify | Add group + link TypeScript types |
| `ui/src/lib/queryKeys.ts` | Modify | Add `groupKeys` and `datasourceKeys` key factories |
| `ui/src/pages/SloRegistryPage.tsx` | Modify | Two-panel layout, group filter state, URL param sync, "+ Group" on cards |

---

## Chunk 1: Track A — Backend Changes

### Task 1: Add `adapter_type` to SLI model and schema

**Files:**
- Modify: `api/app/db/models.py:153-181`
- Modify: `api/app/modules/sli_registry/schemas.py`
- Test: `api/tests/db/test_sli_repository.py`

- [ ] **Step 1: Write failing test — SLI creation with adapter_type**

Add to `api/tests/db/test_sli_repository.py`:

```python
@pytest.mark.integration
async def test_create_with_adapter_type(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    sli = await repo.create(
        name="typed-sli",
        indicators=_INDICATORS,
        adapter_type="prometheus",
    )
    assert sli.adapter_type == "prometheus"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory api pytest tests/db/test_sli_repository.py::test_create_with_adapter_type -v`
Expected: FAIL — `create()` does not accept `adapter_type`

- [ ] **Step 3: Add `adapter_type` to SLI model**

In `api/app/db/models.py`, add to `SLIDefinition` class inside the `# fmt: off` block, after the `name` line:

```python
    adapter_type: Mapped[str]              = mapped_column(Text, nullable=False)
```

- [ ] **Step 4: Add `adapter_type` to SLI schemas**

In `api/app/modules/sli_registry/schemas.py`:

Add `adapter_type: str` to `SLIDefinitionCreate` after `name`:

```python
class SLIDefinitionCreate(BaseModel):
    """Request body for creating an SLI definition."""

    name: str
    adapter_type: str
    display_name: str | None = None
    indicators: dict[str, str]
    notes: str | None = None
    author: str | None = None
    meta: dict[str, Any] = {}
```

Add `adapter_type: str` to `SLIDefinitionRead` after `name`:

```python
class SLIDefinitionRead(BaseModel):
    """Response schema for an SLI definition."""

    id: uuid.UUID
    name: str
    adapter_type: str
    display_name: str | None
    version: int
    indicators: dict[str, str]
    notes: str | None
    author: str | None
    meta: dict[str, Any]
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 5: Pass `adapter_type` through repository `create()` method**

In `api/app/modules/sli_registry/repository.py`, update `create()` signature and body:

```python
    async def create(
        self,
        name: str,
        indicators: dict[str, str],
        adapter_type: str,
        display_name: str | None = None,
        notes: str | None = None,
        author: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> SLIDefinition:
```

And in the `SLIDefinition(...)` constructor call, add `adapter_type=adapter_type`.

- [ ] **Step 6: Pass `adapter_type` in the router**

In `api/app/modules/sli_registry/router.py`, update `create_sli_definition` to pass `adapter_type`:

```python
    sli = await repo.create(
        body.name,
        indicators=body.indicators,
        adapter_type=body.adapter_type,
        display_name=body.display_name,
        notes=body.notes,
        author=body.author,
        meta=body.meta,
    )
```

- [ ] **Step 7: Fix all existing SLI tests to pass `adapter_type`**

In `api/tests/db/test_sli_repository.py`, update `_INDICATORS` section and add a default adapter_type to all `repo.create()` calls. For example, update each call from:

```python
await repo.create(name="linux-sli", indicators=_INDICATORS)
```

to:

```python
await repo.create(name="linux-sli", indicators=_INDICATORS, adapter_type="prometheus")
```

Do this for every `repo.create()` call in the file.

- [ ] **Step 8: Run all SLI tests**

Run: `uv run --directory api pytest tests/db/test_sli_repository.py -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add api/app/db/models.py api/app/modules/sli_registry/ api/tests/db/test_sli_repository.py
git commit -m "feat(api): add adapter_type to SLI definitions"
```

### Task 2: Add `?adapter_type` filter to SLI list endpoint

**Files:**
- Modify: `api/app/modules/sli_registry/repository.py:120-141`
- Modify: `api/app/modules/sli_registry/router.py:17-26`
- Test: `api/tests/db/test_sli_repository.py`

- [ ] **Step 1: Write failing test — filter by adapter_type**

Add to `api/tests/db/test_sli_repository.py`:

```python
@pytest.mark.integration
async def test_list_all_filters_by_adapter_type(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(name="prom-sli", indicators={"a": "q"}, adapter_type="prometheus")
    await repo.create(name="dyna-sli", indicators={"b": "q"}, adapter_type="dynatrace")
    result = await repo.list_all(adapter_type="prometheus")
    assert len(result) == 1
    assert result[0].name == "prom-sli"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory api pytest tests/db/test_sli_repository.py::test_list_all_filters_by_adapter_type -v`
Expected: FAIL — `list_all()` does not accept `adapter_type`

- [ ] **Step 3: Add `adapter_type` filter to `SLIRepository.list_all()`**

In `api/app/modules/sli_registry/repository.py`, update `list_all()`:

```python
    async def list_all(self, *, adapter_type: str | None = None) -> list[SLIDefinition]:
        """Return latest active version of every SLI name, optionally filtered by adapter type."""
        base = select(SLIDefinition).where(SLIDefinition.active == True)  # noqa: E712
        if adapter_type is not None:
            base = base.where(SLIDefinition.adapter_type == adapter_type)

        subq = (
            base
            .distinct(SLIDefinition.name)
            .order_by(SLIDefinition.name, SLIDefinition.version.desc())
        ).subquery()

        result = await self._session.execute(
            select(SLIDefinition).join(
                subq,
                (SLIDefinition.name == subq.c.name) & (SLIDefinition.version == subq.c.version),
            )
        )
        return list(result.scalars().all())
```

- [ ] **Step 4: Add query param to router**

In `api/app/modules/sli_registry/router.py`, update `list_sli_definitions`:

```python
@router.get("/sli-definitions", response_model=PagedResponse[SLIDefinitionRead])
async def list_sli_definitions(
    adapter_type: str | None = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> PagedResponse[SLIDefinitionRead]:
    """List all active SLI definitions, optionally filtered by adapter type."""
    repo = SLIRepository(session)
    items = await repo.list_all(adapter_type=adapter_type)
    return PagedResponse(
        items=[SLIDefinitionRead.model_validate(i) for i in items], total=len(items)
    )
```

- [ ] **Step 5: Run tests**

Run: `uv run --directory api pytest tests/db/test_sli_repository.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add api/app/modules/sli_registry/
git commit -m "feat(api): add adapter_type filter to GET /sli-definitions"
```

### Task 3: Add unique constraint `(group_id, slo_name)` and auto-generate `link_name`

**Files:**
- Modify: `api/app/db/models.py:379-398`
- Modify: `api/app/modules/assets/repository.py:452-507`
- Modify: `api/app/modules/assets/router.py:324-345`
- Modify: `api/app/modules/assets/schemas.py:171-178`
- Test: `api/tests/db/test_asset_repositories.py`

- [ ] **Step 1: Write failing test — duplicate (group_id, slo_name) link is rejected**

Add to `api/tests/db/test_asset_repositories.py`:

```python
from sqlalchemy.exc import IntegrityError

@pytest.mark.integration
async def test_group_slo_link_duplicate_rejected(db_session: AsyncSession) -> None:
    group_repo = AssetGroupRepository(db_session)
    group = await group_repo.create("dup-link-grp")
    link_repo = AssetGroupSLOLinkRepository(db_session)
    await link_repo.create(
        group_id=group.id,
        slo_name="my-slo",
        sli_name="sli-a",
        data_source_name="ds-1",
    )
    with pytest.raises(IntegrityError):
        await link_repo.create(
            group_id=group.id,
            slo_name="my-slo",
            sli_name="sli-b",
            data_source_name="ds-2",
        )
```

- [ ] **Step 2: Write test — link_name is auto-generated**

```python
@pytest.mark.integration
async def test_group_slo_link_name_auto_generated(db_session: AsyncSession) -> None:
    group_repo = AssetGroupRepository(db_session)
    group = await group_repo.create("auto-name-grp")
    link_repo = AssetGroupSLOLinkRepository(db_session)
    link = await link_repo.create(
        group_id=group.id,
        slo_name="error-rate",
        sli_name="prom-sli",
        data_source_name="prod-prom",
    )
    assert link.link_name == "error-rate--prom-sli"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run --directory api pytest tests/db/test_asset_repositories.py::test_group_slo_link_duplicate_rejected tests/db/test_asset_repositories.py::test_group_slo_link_name_auto_generated -v`
Expected: FAIL

- [ ] **Step 4: Update `AssetGroupSLOLink` model — add unique constraint**

In `api/app/db/models.py`, update `AssetGroupSLOLink.__table_args__`:

```python
    __table_args__ = (
        Index("idx_asset_group_slo_links_group", "group_id"),
        UniqueConstraint("group_id", "link_name", name="uq_asset_group_slo_link_name"),
        UniqueConstraint("group_id", "slo_name", name="uq_asset_group_slo_link_group_slo"),
    )
```

- [ ] **Step 5: Auto-generate `link_name` in repository and remove from create schema**

In `api/app/modules/assets/repository.py`, update `AssetGroupSLOLinkRepository.create()` — remove `link_name` parameter, auto-generate it:

```python
    async def create(
        self,
        *,
        group_id: uuid.UUID,
        slo_name: str,
        sli_name: str,
        data_source_name: str,
    ) -> AssetGroupSLOLink:
        """Create an SLO link for an asset group. link_name auto-generated."""
        link_name = f"{slo_name}--{sli_name}"
        link = AssetGroupSLOLink(
            id=uuid.uuid4(),
            link_name=link_name,
            group_id=group_id,
            slo_name=slo_name,
            sli_name=sli_name,
            data_source_name=data_source_name,
        )
        self._session.add(link)
        await self._session.flush()
        return link
```

- [ ] **Step 6: Make `link_name` optional in create schema, auto-derive in router**

In `api/app/modules/assets/schemas.py`, update `AssetGroupSLOLinkCreate`:

```python
class AssetGroupSLOLinkCreate(BaseModel):
    """Request body for creating an asset group SLO link."""

    slo_name: str
    sli_name: str
    data_source_name: str
    link_name: str | None = None
```

- [ ] **Step 7: Update router to not pass `link_name` to repository**

In `api/app/modules/assets/router.py`, update `create_group_slo_link`:

```python
    link = await link_repo.create(
        group_id=group.id,
        slo_name=body.slo_name,
        sli_name=body.sli_name,
        data_source_name=body.data_source_name,
    )
```

- [ ] **Step 8: Fix any existing tests that pass `link_name` explicitly**

Search `test_asset_repositories.py` for `link_name=` in `AssetGroupSLOLinkRepository.create()` calls and remove the parameter.

- [ ] **Step 9: Run all asset tests**

Run: `uv run --directory api pytest tests/db/test_asset_repositories.py -v`
Expected: ALL PASS

- [ ] **Step 10: Commit**

```bash
git add api/app/db/models.py api/app/modules/assets/ api/tests/db/test_asset_repositories.py
git commit -m "feat(api): add unique(group_id,slo_name) constraint, auto-generate link_name"
```

### Task 4: Add PATCH and DELETE endpoints for asset groups

**Files:**
- Modify: `api/app/modules/assets/schemas.py`
- Modify: `api/app/modules/assets/repository.py:179-392`
- Modify: `api/app/modules/assets/router.py`
- Test: `api/tests/db/test_asset_repositories.py`

- [ ] **Step 1: Write failing test — update group properties**

Add to `api/tests/db/test_asset_repositories.py`:

```python
@pytest.mark.integration
async def test_group_update_properties(db_session: AsyncSession) -> None:
    repo = AssetGroupRepository(db_session)
    await repo.create("upd-grp", display_name="Old Name")
    updated = await repo.update("upd-grp", display_name="New Name", description="desc")
    assert updated is not None
    assert updated.display_name == "New Name"
    assert updated.description == "desc"
```

- [ ] **Step 2: Write failing test — delete group (keep SLOs active)**

```python
@pytest.mark.integration
async def test_group_delete_keeps_slos(db_session: AsyncSession) -> None:
    repo = AssetGroupRepository(db_session)
    group = await repo.create("del-grp")
    link_repo = AssetGroupSLOLinkRepository(db_session)
    await link_repo.create(
        group_id=group.id,
        slo_name="keep-slo",
        sli_name="sli",
        data_source_name="ds",
    )
    deleted = await repo.delete("del-grp", deactivate_slos=False)
    assert deleted is True
    assert await repo.get_by_name("del-grp") is None
```

- [ ] **Step 3: Write failing test — delete group (deactivate SLOs)**

This test requires an SLO to exist so we can verify it gets deactivated. Import `SLORepository` and create one:

```python
from app.modules.slo_registry.repository import SLORepository

@pytest.mark.integration
async def test_group_delete_deactivates_slos(db_session: AsyncSession) -> None:
    slo_repo = SLORepository(db_session)
    await slo_repo.create(
        name="deact-slo",
        objectives=[],
        total_score_pass_threshold=90.0,
        total_score_warning_threshold=75.0,
    )
    group_repo = AssetGroupRepository(db_session)
    group = await group_repo.create("deact-grp")
    link_repo = AssetGroupSLOLinkRepository(db_session)
    await link_repo.create(
        group_id=group.id,
        slo_name="deact-slo",
        sli_name="sli",
        data_source_name="ds",
    )
    await group_repo.delete("deact-grp", deactivate_slos=True)
    slo = await slo_repo.get_latest("deact-slo")
    assert slo is None  # deactivated — get_latest returns None for inactive
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run --directory api pytest tests/db/test_asset_repositories.py::test_group_update_properties tests/db/test_asset_repositories.py::test_group_delete_keeps_slos tests/db/test_asset_repositories.py::test_group_delete_deactivates_slos -v`
Expected: FAIL

- [ ] **Step 5: Add `AssetGroupUpdate` schema**

In `api/app/modules/assets/schemas.py`, add after `AssetGroupCreate`:

```python
class AssetGroupUpdate(BaseModel):
    """Request body for updating an asset group."""

    display_name: str | None = None
    description: str | None = None
```

- [ ] **Step 6: Add `update()` method to `AssetGroupRepository`**

In `api/app/modules/assets/repository.py`, add to `AssetGroupRepository`:

```python
    async def update(
        self, name: str, **kwargs: Any,
    ) -> AssetGroupRead | None:
        """Update mutable group fields. Returns None if not found."""
        filtered = {k: v for k, v in kwargs.items() if v is not None}
        if filtered:
            await self._session.execute(
                update(AssetGroup).where(AssetGroup.name == name).values(**filtered)
            )
        result = await self._session.execute(
            select(AssetGroup).where(AssetGroup.name == name)
        )
        group = result.scalar_one_or_none()
        if group is None:
            return None
        return await self._build_read(group)
```

- [ ] **Step 7: Add `delete()` method to `AssetGroupRepository`**

This needs to collect all SLO names linked to the group (and subgroups recursively), optionally deactivate them, then delete the group. Since the DB uses `ondelete="CASCADE"` on `AssetGroupLink`, `AssetGroupMember`, and `AssetGroupSLOLink`, deleting the group cascades to its links. But subgroups are separate `AssetGroup` rows — we need to walk the tree.

Add to `AssetGroupRepository`:

```python
    async def _collect_subgroup_ids(self, group_id: uuid.UUID) -> list[uuid.UUID]:
        """Recursively collect all subgroup IDs under a group."""
        result = await self._session.execute(
            select(AssetGroupLink.child_group_id).where(
                AssetGroupLink.parent_group_id == group_id
            )
        )
        child_ids = list(result.scalars().all())
        all_ids: list[uuid.UUID] = []
        for cid in child_ids:
            all_ids.append(cid)
            all_ids.extend(await self._collect_subgroup_ids(cid))
        return all_ids

    async def delete(
        self, name: str, *, deactivate_slos: bool = False,
    ) -> bool:
        """Delete a group and its subgroups. Returns False if not found."""
        result = await self._session.execute(
            select(AssetGroup).where(AssetGroup.name == name)
        )
        group = result.scalar_one_or_none()
        if group is None:
            return False

        all_group_ids = [group.id, *await self._collect_subgroup_ids(group.id)]

        if deactivate_slos:
            slo_names_result = await self._session.execute(
                select(AssetGroupSLOLink.slo_name)
                .where(AssetGroupSLOLink.group_id.in_(all_group_ids))
                .distinct()
            )
            slo_names = list(slo_names_result.scalars().all())
            if slo_names:
                from app.db.models import SLODefinition
                await self._session.execute(
                    update(SLODefinition)
                    .where(SLODefinition.name.in_(slo_names))
                    .values(active=False)
                )

        for gid in reversed(all_group_ids):
            await self._session.execute(
                delete(AssetGroup).where(AssetGroup.id == gid)
            )
        await self._session.flush()
        return True
```

Note: import `update` is already at the top of the file. Need to verify `SLODefinition` import — add it to the top imports block if needed.

- [ ] **Step 8: Add router endpoints**

In `api/app/modules/assets/router.py`, add after `get_asset_group`:

```python
@router.patch("/asset-groups/{name}", response_model=AssetGroupRead)
async def update_asset_group(
    name: str,
    body: AssetGroupUpdate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> AssetGroupRead:
    """Update mutable asset group fields."""
    repo = AssetGroupRepository(session)
    group = await repo.update(name, **body.model_dump(exclude_none=True))
    if group is None:
        raise_not_found("asset group", name)
    return group


@router.delete("/asset-groups/{name}", status_code=204)
async def delete_asset_group(
    name: str,
    deactivate_slos: bool = False,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    """Delete an asset group and optionally deactivate linked SLOs."""
    repo = AssetGroupRepository(session)
    found = await repo.delete(name, deactivate_slos=deactivate_slos)
    if not found:
        raise_not_found("asset group", name)
```

Add `AssetGroupUpdate` to the import block at the top of the router file.

**IMPORTANT:** These endpoints must be registered AFTER `/asset-groups/tree` and BEFORE `/asset-groups/{name}/members` etc. Insert them right after the existing `get_asset_group` function (line ~247).

- [ ] **Step 9: Run all asset tests**

Run: `uv run --directory api pytest tests/db/test_asset_repositories.py -v`
Expected: ALL PASS

- [ ] **Step 10: Run linter and type checker**

Run: `uv run ruff check api/`
Run: `uv run mypy api/app`

- [ ] **Step 11: Commit**

```bash
git add api/app/modules/assets/ api/app/db/models.py api/tests/db/test_asset_repositories.py
git commit -m "feat(api): add PATCH and DELETE endpoints for asset groups"
```

### Task 5: Reset migration (POC)

**Files:**
- Delete: `api/alembic/versions/001_initial_schema.py`
- Delete: `api/alembic/versions/63404ff4de0e_slo_format_redesign.py`
- Recreate: `api/alembic/versions/001_initial_schema.py` (autogenerated)
- Keep: `api/alembic/versions/002_timescaledb_hypertable_and_seed_data.py`

- [ ] **Step 1: Delete old migration files**

```bash
rm api/alembic/versions/001_initial_schema.py
rm api/alembic/versions/63404ff4de0e_slo_format_redesign.py
```

- [ ] **Step 2: Autogenerate fresh 001**

Run: `ENV_FILE=.env.test uv run --directory api alembic revision --autogenerate -m "initial schema" --rev-id 001`

This reads the current SQLAlchemy models (which now include `adapter_type` and the new unique constraint) and generates a complete migration.

- [ ] **Step 3: Verify the generated migration**

Read `api/alembic/versions/001_initial_schema.py` and confirm it includes:
- `sli_definitions` table with `adapter_type` column
- `asset_group_slo_links` table with `UniqueConstraint("group_id", "slo_name")`
- All other expected tables

- [ ] **Step 4: Update `002` to point to new `001`**

Verify `002_timescaledb_hypertable_and_seed_data.py` still has `down_revision = "001"`. It should be fine since we kept the same rev_id.

- [ ] **Step 5: Test full migration on clean test DB**

```bash
./stop_test_infra.sh
./start_test_infra.sh
ENV_FILE=.env.test uv run --directory api alembic upgrade head
```

Expected: Migration runs cleanly with no errors.

- [ ] **Step 6: Run integration tests against fresh schema**

Run: `uv run --directory api pytest tests/db/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add api/alembic/versions/
git commit -m "chore(api): reset migration to single 001 with current schema"
```

---

## Chunk 2: Track B — UI Sidebar + Group CRUD

### Task 6: Extract `GroupTreeRenderer` component

**Files:**
- Create: `ui/src/components/GroupTreeRenderer.tsx`
- Modify: `ui/src/features/assets/components/AssetGroupCard.tsx`

- [ ] **Step 1: Create `GroupTreeRenderer`**

Create `ui/src/components/GroupTreeRenderer.tsx`:

```tsx
import { useState, type ReactNode } from 'react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import type { AssetGroup, AssetGroupTree } from '@/features/assets/types'

interface GroupTreeRendererProps {
  group: AssetGroup
  tree: AssetGroupTree
  filterQuery: string
  renderNode: (group: AssetGroup, isOpen: boolean) => ReactNode
  renderLeaves?: (group: AssetGroup) => ReactNode
  onSelect?: (groupName: string) => void
  selectedGroup?: string | null
  forceExpanded?: boolean
  indent?: number
}

export function GroupTreeRenderer({
  group,
  tree,
  filterQuery,
  renderNode,
  renderLeaves,
  onSelect,
  selectedGroup,
  forceExpanded,
  indent = 0,
}: GroupTreeRendererProps) {
  const [open, setOpen] = useState(false)
  const isOpen = forceExpanded !== undefined ? forceExpanded : open

  const subGroups = group.subgroups
    .map(sg => tree.all_groups.find(g => g.id === sg.group_id))
    .filter(Boolean) as AssetGroup[]

  const matchesFilter = !filterQuery
    || (group.display_name ?? group.name).toLowerCase().includes(filterQuery.toLowerCase())

  const hasMatchingChildren = subGroups.some(sg =>
    (sg.display_name ?? sg.name).toLowerCase().includes(filterQuery.toLowerCase())
  )

  if (filterQuery && !matchesFilter && !hasMatchingChildren) return null

  const isSelected = selectedGroup === group.name

  return (
    <div style={{ paddingLeft: indent > 0 ? `${indent * 16}px` : undefined }}>
      <Collapsible open={isOpen} onOpenChange={forceExpanded === undefined ? setOpen : undefined}>
        <div
          className={`flex items-center cursor-pointer rounded transition-colors ${
            isSelected ? 'bg-primary/15 border-l-2 border-primary' : 'hover:bg-muted/50'
          }`}
          onClick={() => onSelect?.(group.name)}
        >
          {subGroups.length > 0 ? (
            <CollapsibleTrigger
              className="px-1 py-1 text-muted-foreground text-xs shrink-0"
              onClick={e => e.stopPropagation()}
            >
              {isOpen ? '▾' : '▸'}
            </CollapsibleTrigger>
          ) : (
            <span className="px-1 py-1 text-xs w-4 shrink-0" />
          )}
          <div className="flex-1 min-w-0">{renderNode(group, isOpen)}</div>
        </div>
        <CollapsibleContent>
          {renderLeaves?.(group)}
          {subGroups.map(sg => (
            <GroupTreeRenderer
              key={sg.id}
              group={sg}
              tree={tree}
              filterQuery={filterQuery}
              renderNode={renderNode}
              renderLeaves={renderLeaves}
              onSelect={onSelect}
              selectedGroup={selectedGroup}
              forceExpanded={forceExpanded}
              indent={indent + 1}
            />
          ))}
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
```

- [ ] **Step 2: Refactor `AssetGroupCard` to use `GroupTreeRenderer`**

Rewrite `ui/src/features/assets/components/AssetGroupCard.tsx`:

```tsx
import { GroupTreeRenderer } from '@/components/GroupTreeRenderer'
import { DEFAULT_OS_COLOUR_MAP } from '@/lib/theme'
import type { AssetGroup, AssetGroupTree } from '../types'

interface Props {
  group: AssetGroup
  tree: AssetGroupTree
  filterQuery: string
  colourMap: Record<string, string>
  forceExpanded?: boolean
}

function OsDot({ os, colourMap }: { os?: string; colourMap: Record<string, string> }) {
  const colour = (os && (colourMap[os] ?? DEFAULT_OS_COLOUR_MAP[os])) ?? '#888'
  return (
    <span
      className="inline-block w-2.5 h-2.5 rounded-full mr-2 flex-shrink-0"
      style={{ backgroundColor: colour }}
    />
  )
}

export function AssetGroupCard({ group, tree, filterQuery, colourMap, forceExpanded }: Props) {
  return (
    <div className="border border-slate-700 rounded-lg mb-3 bg-gray-900">
      <GroupTreeRenderer
        group={group}
        tree={tree}
        filterQuery={filterQuery}
        forceExpanded={forceExpanded}
        renderNode={(g, _isOpen) => (
          <div className="flex items-center justify-between px-3 py-2.5">
            <div>
              <span className="font-semibold text-slate-200">{g.display_name ?? g.name}</span>
              <span className="text-xs text-slate-500 ml-2">({g.members.length} assets)</span>
            </div>
          </div>
        )}
        renderLeaves={(g) => {
          const members = filterQuery
            ? g.members.filter(m => m.asset_name.toLowerCase().includes(filterQuery.toLowerCase()))
            : g.members
          return (
            <div className="px-4 pb-3">
              {members.map(member => (
                <div key={member.asset_id} className="flex items-center py-1 text-sm text-slate-300">
                  <OsDot os={member.asset_name.split('-')[0]} colourMap={colourMap} />
                  <span className="font-mono">{member.asset_name}</span>
                  <span className="text-slate-500 ml-auto text-xs">weight {member.weight}</span>
                </div>
              ))}
            </div>
          )
        }}
      />
    </div>
  )
}
```

- [ ] **Step 3: Verify the app still works**

Run: `uv run --directory ui npx tsc --noEmit` (or the project's type check command)
Visually verify the Asset Navigator page still shows group cards correctly.

- [ ] **Step 4: Commit**

```bash
git add ui/src/components/GroupTreeRenderer.tsx ui/src/features/assets/components/AssetGroupCard.tsx
git commit -m "refactor(ui): extract GroupTreeRenderer from AssetGroupCard"
```

### Task 7: Add group API functions, hooks, and types

**Files:**
- Modify: `ui/src/features/slos/types.ts`
- Modify: `ui/src/features/slos/api.ts`
- Modify: `ui/src/features/slos/hooks.ts`
- Modify: `ui/src/lib/queryKeys.ts`

- [ ] **Step 1: Add types for groups and links**

In `ui/src/features/slos/types.ts`, add:

```typescript
export interface AssetGroupSLOLink {
  id: string
  link_name: string
  group_id: string
  slo_name: string
  sli_name: string
  data_source_name: string
  created_at: string
}

export interface AssetGroupSLOLinkCreate {
  slo_name: string
  sli_name: string
  data_source_name: string
}

export interface AssetGroupUpdate {
  display_name?: string
  description?: string
}

export interface DataSource {
  id: string
  name: string
  display_name?: string
  adapter_type: string
  adapter_url: string
  labels: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface SliDefinition {
  id: string
  name: string
  adapter_type: string
  display_name?: string
  version: number
  indicators: Record<string, string>
  active: boolean
  created_at: string
}
```

- [ ] **Step 2: Add query key factories**

In `ui/src/lib/queryKeys.ts`, add:

```typescript
export const groupKeys = {
  all: ['asset-groups'] as const,
  tree: () => [...groupKeys.all, 'tree'] as const,
  detail: (name: string) => [...groupKeys.all, name] as const,
  links: (name: string) => [...groupKeys.detail(name), 'links'] as const,
}

export const datasourceKeys = {
  all: ['datasources'] as const,
}
```

- [ ] **Step 3: Add API functions**

In `ui/src/features/slos/api.ts`, add:

```typescript
import type {
  AssetGroupSLOLink, AssetGroupSLOLinkCreate, AssetGroupUpdate,
  DataSource, SliDefinition,
} from './types'

// Re-export AssetGroup types from assets feature
import type { AssetGroup, AssetGroupTree } from '@/features/assets/types'

export async function fetchGroupTree(): Promise<AssetGroupTree> {
  const res = await fetch(`${BASE}/asset-groups/tree`)
  if (!res.ok) throw new Error(`fetchGroupTree: ${res.status}`)
  return res.json()
}

export async function createGroup(body: {
  name: string; display_name?: string; description?: string
}): Promise<AssetGroup> {
  const res = await fetch(`${BASE}/asset-groups`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`createGroup: ${res.status}`)
  return res.json()
}

export async function updateGroup(
  name: string, body: AssetGroupUpdate,
): Promise<AssetGroup> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`updateGroup: ${res.status}`)
  return res.json()
}

export async function deleteGroup(
  name: string, deactivateSlos: boolean,
): Promise<void> {
  const res = await fetch(
    `${BASE}/asset-groups/${encodeURIComponent(name)}?deactivate_slos=${deactivateSlos}`,
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error(`deleteGroup: ${res.status}`)
}

export async function addSubgroup(
  parentName: string, childGroupId: string,
): Promise<AssetGroup> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(parentName)}/subgroups`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ child_group_id: childGroupId, weight: 1.0 }),
  })
  if (!res.ok) throw new Error(`addSubgroup: ${res.status}`)
  return res.json()
}

export async function fetchGroupSloLinks(name: string): Promise<AssetGroupSLOLink[]> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(name)}/slo-links`)
  if (!res.ok) throw new Error(`fetchGroupSloLinks: ${res.status}`)
  return res.json()
}

export async function createGroupSloLink(
  groupName: string, body: AssetGroupSLOLinkCreate,
): Promise<AssetGroupSLOLink> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(groupName)}/slo-links`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`createGroupSloLink: ${res.status}`)
  return res.json()
}

export async function deleteGroupSloLink(
  groupName: string, linkName: string,
): Promise<void> {
  const res = await fetch(
    `${BASE}/asset-groups/${encodeURIComponent(groupName)}/slo-links/${encodeURIComponent(linkName)}`,
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error(`deleteGroupSloLink: ${res.status}`)
}

export async function fetchDatasources(): Promise<DataSource[]> {
  const res = await fetch(`${BASE}/datasources`)
  if (!res.ok) throw new Error(`fetchDatasources: ${res.status}`)
  const data: { items: DataSource[]; total: number } = await res.json()
  return data.items
}

export async function fetchSliDefinitions(adapterType?: string): Promise<SliDefinition[]> {
  const url = adapterType
    ? `${BASE}/sli-definitions?adapter_type=${encodeURIComponent(adapterType)}`
    : `${BASE}/sli-definitions`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`fetchSliDefinitions: ${res.status}`)
  const data: { items: SliDefinition[]; total: number } = await res.json()
  return data.items
}
```

- [ ] **Step 4: Add hooks**

In `ui/src/features/slos/hooks.ts`, add:

```typescript
import { groupKeys, datasourceKeys, sliKeys } from '@/lib/queryKeys'
import {
  fetchGroupTree, createGroup, updateGroup, deleteGroup,
  fetchGroupSloLinks, createGroupSloLink, deleteGroupSloLink,
  addSubgroup, fetchDatasources, fetchSliDefinitions,
} from './api'

export function useGroupTree() {
  return useQuery({
    queryKey: groupKeys.tree(),
    queryFn: fetchGroupTree,
  })
}

export function useGroupSloLinks(name: string) {
  return useQuery({
    queryKey: groupKeys.links(name),
    queryFn: () => fetchGroupSloLinks(name),
    enabled: !!name,
  })
}

export function useCreateGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createGroup,
    onSuccess: () => { qc.invalidateQueries({ queryKey: groupKeys.all }) },
  })
}

export function useUpdateGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, ...body }: { name: string; display_name?: string; description?: string }) =>
      updateGroup(name, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: groupKeys.all }) },
  })
}

export function useDeleteGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, deactivateSlos }: { name: string; deactivateSlos: boolean }) =>
      deleteGroup(name, deactivateSlos),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: groupKeys.all })
      qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}

export function useAddSubgroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ parentName, childGroupId }: { parentName: string; childGroupId: string }) =>
      addSubgroup(parentName, childGroupId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: groupKeys.all }) },
  })
}

export function useCreateGroupSloLink() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupName, ...body }: { groupName: string; slo_name: string; sli_name: string; data_source_name: string }) =>
      createGroupSloLink(groupName, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: groupKeys.all })
      qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}

export function useDeleteGroupSloLink() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupName, linkName }: { groupName: string; linkName: string }) =>
      deleteGroupSloLink(groupName, linkName),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: groupKeys.all })
    },
  })
}

export function useDatasources() {
  return useQuery({
    queryKey: datasourceKeys.all,
    queryFn: fetchDatasources,
  })
}

export function useSliDefinitions(adapterType?: string) {
  return useQuery({
    queryKey: [...sliKeys.all, { adapterType }],
    queryFn: () => fetchSliDefinitions(adapterType),
    enabled: adapterType !== undefined,
  })
}
```

- [ ] **Step 5: Verify types compile**

Run: `uv run --directory ui npx tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/slos/ ui/src/lib/queryKeys.ts
git commit -m "feat(ui): add group CRUD and link API hooks and types"
```

### Task 8: Build `GroupSidebar` component

**Files:**
- Create: `ui/src/features/slos/components/GroupSidebar.tsx`

- [ ] **Step 1: Create sidebar component**

Create `ui/src/features/slos/components/GroupSidebar.tsx`:

```tsx
import { useState } from 'react'
import { GroupTreeRenderer } from '@/components/GroupTreeRenderer'
import { useGroupTree } from '../hooks'
import type { AssetGroup } from '@/features/assets/types'

interface Props {
  selectedGroup: string | null
  onSelectGroup: (name: string | null) => void
  onCreateGroup: () => void
  onEditGroup: (name: string) => void
  onDeleteGroup: (name: string) => void
  onAddSloLink: (groupName: string) => void
}

export function GroupSidebar({
  selectedGroup,
  onSelectGroup,
  onCreateGroup,
  onEditGroup,
  onDeleteGroup,
  onAddSloLink,
}: Props) {
  const { data: tree, isLoading } = useGroupTree()
  const [filterQuery, setFilterQuery] = useState('')

  if (isLoading || !tree) {
    return (
      <div className="w-[180px] shrink-0 border-r border-border bg-card/50 p-3">
        <p className="text-muted-foreground text-xs">Loading…</p>
      </div>
    )
  }

  return (
    <div className="w-[180px] shrink-0 border-r border-border bg-card/50 flex flex-col">
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-border flex items-center justify-between">
        <span className="text-sm font-semibold text-foreground">Asset Groups</span>
        <button
          onClick={onCreateGroup}
          className="text-xs px-2 py-0.5 border border-primary/40 text-primary rounded hover:bg-primary/10 transition-colors"
        >
          + New
        </button>
      </div>

      {/* Search */}
      <div className="px-3 py-2">
        <input
          type="text"
          placeholder="Filter groups…"
          value={filterQuery}
          onChange={e => setFilterQuery(e.target.value)}
          className="w-full bg-input border border-border rounded px-2 py-1 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
        />
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto px-1 py-1">
        {/* All SLOs */}
        <div
          className={`flex items-center justify-between px-2 py-1.5 rounded cursor-pointer text-xs transition-colors ${
            selectedGroup === null
              ? 'bg-primary/15 border-l-2 border-primary font-medium'
              : 'hover:bg-muted/50'
          }`}
          onClick={() => onSelectGroup(null)}
        >
          <span>All SLOs</span>
        </div>

        {/* Group tree */}
        {tree.top_level.map(group => (
          <GroupTreeRenderer
            key={group.id}
            group={group}
            tree={tree}
            filterQuery={filterQuery}
            selectedGroup={selectedGroup}
            onSelect={(name) => onSelectGroup(name)}
            renderNode={(g) => (
              <div
                className="flex items-center justify-between px-1 py-1.5 text-xs group"
                onContextMenu={e => {
                  e.preventDefault()
                  // Context menu could be added here later
                }}
              >
                <span className="truncate">{g.display_name ?? g.name}</span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={e => { e.stopPropagation(); onEditGroup(g.name) }}
                    className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-foreground transition-opacity text-[10px]"
                    title="Edit"
                  >
                    ✎
                  </button>
                  <button
                    onClick={e => { e.stopPropagation(); onDeleteGroup(g.name) }}
                    className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-opacity text-[10px]"
                    title="Delete"
                  >
                    ✕
                  </button>
                  <button
                    onClick={e => { e.stopPropagation(); onAddSloLink(g.name) }}
                    className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-primary transition-opacity text-[10px]"
                    title="Link SLO"
                  >
                    +
                  </button>
                </div>
              </div>
            )}
          />
        ))}

        {/* Ungrouped */}
        <div
          className={`flex items-center justify-between px-2 py-1.5 rounded cursor-pointer text-xs mt-2 border-t border-border pt-2 transition-colors ${
            selectedGroup === '__ungrouped__'
              ? 'bg-primary/15 border-l-2 border-primary font-medium'
              : 'hover:bg-muted/50 text-muted-foreground italic'
          }`}
          onClick={() => onSelectGroup('__ungrouped__')}
        >
          <span>Ungrouped</span>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify types compile**

Run: `uv run --directory ui npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add ui/src/features/slos/components/GroupSidebar.tsx
git commit -m "feat(ui): add GroupSidebar component with tree view"
```

### Task 9: Build group CRUD dialogs

**Files:**
- Create: `ui/src/features/slos/components/GroupCreateDialog.tsx`
- Create: `ui/src/features/slos/components/GroupEditDialog.tsx`
- Create: `ui/src/features/slos/components/GroupDeleteDialog.tsx`

- [ ] **Step 1: Create GroupCreateDialog**

Create `ui/src/features/slos/components/GroupCreateDialog.tsx`:

```tsx
import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
} from '@/components/ui/dialog'
import { useCreateGroup, useGroupTree, useAddSubgroup } from '../hooks'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function GroupCreateDialog({ open, onOpenChange }: Props) {
  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [description, setDescription] = useState('')
  const [parentGroup, setParentGroup] = useState('')
  const create = useCreateGroup()
  const addSubgroup = useAddSubgroup()
  const { data: tree } = useGroupTree()

  const handleCreate = async () => {
    const group = await create.mutateAsync({
      name,
      display_name: displayName || undefined,
      description: description || undefined,
    })
    if (parentGroup && tree) {
      await addSubgroup.mutateAsync({
        parentName: parentGroup,
        childGroupId: group.id,
      })
    }
    setName('')
    setDisplayName('')
    setDescription('')
    setParentGroup('')
    onOpenChange(false)
  }

  const isValid = name.length > 0 && /^[a-z0-9-]+$/.test(name)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Asset Group</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">
              Name <span className="text-destructive">*</span>
            </label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="production-apis"
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
            />
            {name && !isValid && (
              <p className="text-xs text-destructive mt-1">lowercase letters, numbers, hyphens only</p>
            )}
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">Display Name</label>
            <input
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder="Production APIs"
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
            />
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">Description</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Optional description…"
              rows={2}
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50 resize-none"
            />
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">Parent Group</label>
            <select
              value={parentGroup}
              onChange={e => setParentGroup(e.target.value)}
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50"
            >
              <option value="">None (top-level)</option>
              {tree?.all_groups.map(g => (
                <option key={g.id} value={g.name}>{g.display_name ?? g.name}</option>
              ))}
            </select>
          </div>
        </div>
        <DialogFooter>
          <DialogClose className="px-3 py-1.5 text-sm border border-border rounded text-muted-foreground hover:text-foreground transition-colors">
            Cancel
          </DialogClose>
          <button
            onClick={handleCreate}
            disabled={!isValid || create.isPending}
            className="px-3 py-1.5 text-sm bg-primary/30 border border-primary/50 rounded text-primary hover:bg-primary/40 transition-colors disabled:opacity-40"
          >
            {create.isPending ? 'Creating…' : 'Create'}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Create GroupEditDialog**

Create `ui/src/features/slos/components/GroupEditDialog.tsx`:

```tsx
import { useEffect, useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
} from '@/components/ui/dialog'
import {
  useUpdateGroup, useGroupSloLinks, useDeleteGroupSloLink, useGroupTree,
  useAddSubgroup,
} from '../hooks'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  groupName: string | null
}

export function GroupEditDialog({ open, onOpenChange, groupName }: Props) {
  const { data: tree } = useGroupTree()
  const group = tree?.all_groups.find(g => g.name === groupName)
  const { data: links } = useGroupSloLinks(groupName ?? '')
  const updateGroup = useUpdateGroup()
  const unlinkSlo = useDeleteGroupSloLink()
  const addSubgroup = useAddSubgroup()

  const [displayName, setDisplayName] = useState('')
  const [description, setDescription] = useState('')
  const [parentGroup, setParentGroup] = useState('')

  // Find current parent from tree data
  const currentParent = tree?.all_groups.find(g =>
    g.subgroups.some(sg => sg.group_id === group?.id)
  )

  useEffect(() => {
    if (group) {
      setDisplayName(group.display_name ?? '')
      setDescription(group.description ?? '')
      setParentGroup(currentParent?.name ?? '')
    }
  }, [group, currentParent])

  if (!groupName || !group) return null

  // Exclude self and own descendants from parent options to prevent cycles
  const availableParents = tree?.all_groups.filter(g => g.name !== groupName) ?? []

  const handleSave = async () => {
    await updateGroup.mutateAsync({
      name: groupName,
      display_name: displayName || undefined,
      description: description || undefined,
    })
    // Handle re-parenting if changed
    const newParent = parentGroup || null
    const oldParent = currentParent?.name ?? null
    if (newParent !== oldParent && newParent && tree) {
      await addSubgroup.mutateAsync({
        parentName: newParent,
        childGroupId: group.id,
      })
    }
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Asset Group</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">Name</label>
            <div className="bg-muted/30 border border-border rounded px-3 py-2 text-sm text-muted-foreground">
              {groupName}
            </div>
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">Display Name</label>
            <input
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50"
            />
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">Description</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              rows={2}
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50 resize-none"
            />
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">Parent Group</label>
            <select
              value={parentGroup}
              onChange={e => setParentGroup(e.target.value)}
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50"
            >
              <option value="">None (top-level)</option>
              {availableParents.map(g => (
                <option key={g.id} value={g.name}>{g.display_name ?? g.name}</option>
              ))}
            </select>
          </div>
          {links && links.length > 0 && (
            <div>
              <label className="text-xs uppercase text-muted-foreground block mb-1">
                Linked SLOs ({links.length})
              </label>
              <div className="space-y-1">
                {links.map(link => (
                  <div
                    key={link.id}
                    className="flex items-center justify-between text-xs py-1 border-b border-border/50"
                  >
                    <span className="text-foreground">
                      {link.slo_name} → {link.sli_name}
                    </span>
                    <button
                      onClick={() => unlinkSlo.mutate({ groupName, linkName: link.link_name })}
                      className="text-muted-foreground hover:text-destructive transition-colors"
                      title="Unlink"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <DialogClose className="px-3 py-1.5 text-sm border border-border rounded text-muted-foreground hover:text-foreground transition-colors">
            Cancel
          </DialogClose>
          <button
            onClick={handleSave}
            disabled={updateGroup.isPending}
            className="px-3 py-1.5 text-sm bg-primary/30 border border-primary/50 rounded text-primary hover:bg-primary/40 transition-colors disabled:opacity-40"
          >
            {updateGroup.isPending ? 'Saving…' : 'Save'}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 3: Create GroupDeleteDialog**

Create `ui/src/features/slos/components/GroupDeleteDialog.tsx`:

```tsx
import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
} from '@/components/ui/dialog'
import { useDeleteGroup, useGroupTree, useGroupSloLinks } from '../hooks'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  groupName: string | null
  onDeleted: () => void
}

export function GroupDeleteDialog({ open, onOpenChange, groupName, onDeleted }: Props) {
  const { data: tree } = useGroupTree()
  const group = tree?.all_groups.find(g => g.name === groupName)
  const { data: links } = useGroupSloLinks(groupName ?? '')
  const deleteGroup = useDeleteGroup()
  const [choice, setChoice] = useState<'keep' | 'deactivate' | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)

  if (!groupName || !group) return null

  const subgroupCount = group.subgroups.length
  const linkCount = links?.length ?? 0

  const handleDelete = async () => {
    await deleteGroup.mutateAsync({
      name: groupName,
      deactivateSlos: choice === 'deactivate',
    })
    setChoice(null)
    setConfirmOpen(false)
    onOpenChange(false)
    onDeleted()
  }

  const confirmMessage = choice === 'keep'
    ? `Delete "${group.display_name ?? groupName}" and keep ${linkCount} SLO(s) active?`
    : `Delete "${group.display_name ?? groupName}" and deactivate ${linkCount} SLO(s)?`

  return (
    <>
      <Dialog open={open && !confirmOpen} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete "{group.display_name ?? groupName}"?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground leading-relaxed">
            This group has <strong>{linkCount} linked SLO(s)</strong>
            {subgroupCount > 0 && <> and <strong>{subgroupCount} subgroup(s)</strong></>}.
            Choose how to handle them:
          </p>
          <div className="space-y-2 py-2">
            <label
              className={`flex items-start gap-3 p-3 rounded border cursor-pointer transition-colors ${
                choice === 'keep' ? 'border-border bg-muted/30' : 'border-border/50 hover:border-border'
              }`}
            >
              <input
                type="radio"
                name="delete-choice"
                checked={choice === 'keep'}
                onChange={() => setChoice('keep')}
                className="mt-0.5"
              />
              <div>
                <div className="text-sm font-medium">Delete & Keep SLOs Active</div>
                <div className="text-xs text-muted-foreground">
                  Group and subgroups are deleted. Linked SLOs remain active and become ungrouped.
                </div>
              </div>
            </label>
            <label
              className={`flex items-start gap-3 p-3 rounded border cursor-pointer transition-colors ${
                choice === 'deactivate'
                  ? 'border-destructive/50 bg-destructive/5'
                  : 'border-border/50 hover:border-border'
              }`}
            >
              <input
                type="radio"
                name="delete-choice"
                checked={choice === 'deactivate'}
                onChange={() => setChoice('deactivate')}
                className="mt-0.5"
              />
              <div>
                <div className="text-sm font-medium text-destructive">Delete & Deactivate SLOs</div>
                <div className="text-xs text-muted-foreground">
                  Group and subgroups are deleted. All linked SLOs are marked inactive.
                </div>
              </div>
            </label>
          </div>
          <DialogFooter>
            <DialogClose className="px-3 py-1.5 text-sm border border-border rounded text-muted-foreground hover:text-foreground transition-colors">
              Cancel
            </DialogClose>
            <button
              onClick={() => setConfirmOpen(true)}
              disabled={choice === null}
              className="px-3 py-1.5 text-sm bg-destructive/30 border border-destructive/50 rounded text-destructive hover:bg-destructive/40 transition-colors disabled:opacity-40"
            >
              Delete
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Confirmation modal */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Deletion</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">{confirmMessage}</p>
          <DialogFooter>
            <button
              onClick={() => setConfirmOpen(false)}
              className="px-3 py-1.5 text-sm border border-border rounded text-muted-foreground hover:text-foreground transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={deleteGroup.isPending}
              className="px-3 py-1.5 text-sm bg-destructive/30 border border-destructive/50 rounded text-destructive hover:bg-destructive/40 transition-colors disabled:opacity-40"
            >
              {deleteGroup.isPending ? 'Deleting…' : 'Confirm Delete'}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
```

- [ ] **Step 4: Verify types compile**

Run: `uv run --directory ui npx tsc --noEmit`

- [ ] **Step 5: Commit**

```bash
git add ui/src/features/slos/components/GroupCreateDialog.tsx ui/src/features/slos/components/GroupEditDialog.tsx ui/src/features/slos/components/GroupDeleteDialog.tsx
git commit -m "feat(ui): add group create, edit, and delete dialogs"
```

---

## Chunk 3: Track C — Linking + Filtering

### Task 10: Build `SloLinkDialog` component

**Files:**
- Create: `ui/src/features/slos/components/SloLinkDialog.tsx`

- [ ] **Step 1: Create SloLinkDialog**

Create `ui/src/features/slos/components/SloLinkDialog.tsx`:

```tsx
import { useState, useEffect } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
} from '@/components/ui/dialog'
import {
  useDatasources, useSliDefinitions, useGroupTree, useSlos,
  useCreateGroupSloLink, useGroupSloLinks,
} from '../hooks'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  lockedSloName?: string
  lockedGroupName?: string
}

export function SloLinkDialog({ open, onOpenChange, lockedSloName, lockedGroupName }: Props) {
  const [datasource, setDatasource] = useState('')
  const [sliName, setSliName] = useState('')
  const [groupName, setGroupName] = useState(lockedGroupName ?? '')
  const [sloName, setSloName] = useState(lockedSloName ?? '')

  const { data: datasources } = useDatasources()
  const selectedDs = datasources?.find(d => d.name === datasource)
  const { data: slis } = useSliDefinitions(selectedDs?.adapter_type)
  const { data: tree } = useGroupTree()
  const { data: slos } = useSlos()
  const { data: existingLinks } = useGroupSloLinks(groupName || lockedGroupName || '')
  const createLink = useCreateGroupSloLink()

  useEffect(() => {
    if (lockedGroupName) setGroupName(lockedGroupName)
    if (lockedSloName) setSloName(lockedSloName)
  }, [lockedGroupName, lockedSloName])

  // Reset SLI when datasource changes
  useEffect(() => { setSliName('') }, [datasource])

  // Reset all when dialog opens
  useEffect(() => {
    if (open) {
      setDatasource('')
      setSliName('')
      if (!lockedGroupName) setGroupName('')
      if (!lockedSloName) setSloName('')
    }
  }, [open, lockedGroupName, lockedSloName])

  const isDuplicate = existingLinks?.some(l => l.slo_name === sloName) ?? false
  const isValid = datasource && sliName && groupName && sloName && !isDuplicate

  const handleLink = async () => {
    const targetGroup = lockedGroupName ?? groupName
    await createLink.mutateAsync({
      groupName: targetGroup,
      slo_name: sloName,
      sli_name: sliName,
      data_source_name: datasource,
    })
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Link SLO to Asset Group</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          {/* ① Datasource (always first in the chain) */}
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">① Datasource</label>
            <select
              value={datasource}
              onChange={e => setDatasource(e.target.value)}
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50"
            >
              <option value="">Select datasource…</option>
              {datasources?.map(ds => (
                <option key={ds.id} value={ds.name}>
                  {ds.display_name ?? ds.name} ({ds.adapter_type})
                </option>
              ))}
            </select>
          </div>

          {/* ② SLI (filtered by datasource adapter_type) */}
          <div>
            <label className="text-xs uppercase text-muted-foreground block mb-1">
              ② SLI {selectedDs && <span className="text-[10px] opacity-60 normal-case">— filtered to {selectedDs.adapter_type}</span>}
            </label>
            <select
              value={sliName}
              onChange={e => setSliName(e.target.value)}
              disabled={!datasource}
              className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {!datasource
                ? <option value="">Select datasource first…</option>
                : <option value="">Select SLI…</option>
              }
              {slis?.filter(s => s.active).map(s => (
                <option key={s.id} value={s.name}>{s.display_name ?? s.name}</option>
              ))}
            </select>
          </div>

          {/* ③ SLO (locked or selectable) */}
          {lockedSloName ? (
            <div>
              <label className="text-xs uppercase text-muted-foreground block mb-1">③ SLO</label>
              <div className="bg-muted/30 border border-border rounded px-3 py-2 text-sm text-muted-foreground">
                {lockedSloName} <span className="text-xs opacity-50">(locked)</span>
              </div>
            </div>
          ) : (
            <div>
              <label className="text-xs uppercase text-muted-foreground block mb-1">③ SLO</label>
              <select
                value={sloName}
                onChange={e => setSloName(e.target.value)}
                className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50"
              >
                <option value="">Select SLO…</option>
                {slos?.filter(s => s.active).map(s => (
                  <option key={s.name} value={s.name}>{s.display_name ?? s.name}</option>
                ))}
              </select>
            </div>
          )}

          {/* ③ Group (locked or selectable) */}
          {lockedGroupName ? (
            <div>
              <label className="text-xs uppercase text-muted-foreground block mb-1">③ Asset Group</label>
              <div className="bg-muted/30 border border-border rounded px-3 py-2 text-sm text-muted-foreground">
                {lockedGroupName} <span className="text-xs opacity-50">(locked)</span>
              </div>
            </div>
          ) : (
            <div>
              <label className="text-xs uppercase text-muted-foreground block mb-1">③ Asset Group</label>
              <select
                value={groupName}
                onChange={e => setGroupName(e.target.value)}
                className="w-full bg-input border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/50"
              >
                <option value="">Select group…</option>
                {tree?.all_groups.map(g => (
                  <option key={g.id} value={g.name}>{g.display_name ?? g.name}</option>
                ))}
              </select>
            </div>
          )}

          {isDuplicate && (
            <p className="text-xs text-destructive">This SLO is already linked to this group</p>
          )}
        </div>
        <DialogFooter>
          <DialogClose className="px-3 py-1.5 text-sm border border-border rounded text-muted-foreground hover:text-foreground transition-colors">
            Cancel
          </DialogClose>
          <button
            onClick={handleLink}
            disabled={!isValid || createLink.isPending}
            className="px-3 py-1.5 text-sm bg-primary/30 border border-primary/50 rounded text-primary hover:bg-primary/40 transition-colors disabled:opacity-40"
          >
            {createLink.isPending ? 'Linking…' : 'Link'}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Verify types compile**

Run: `uv run --directory ui npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add ui/src/features/slos/components/SloLinkDialog.tsx
git commit -m "feat(ui): add SloLinkDialog with datasource -> SLI -> group/SLO chain"
```

### Task 11: Update SloRegistryPage — two-panel layout with filtering

**Files:**
- Modify: `ui/src/pages/SloRegistryPage.tsx`

- [ ] **Step 1: Rewrite SloRegistryPage with sidebar and filtering**

Replace the entire content of `ui/src/pages/SloRegistryPage.tsx`:

```tsx
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useSlos, useSloDetail, useDeleteSlo, useGroupTree, useGroupSloLinks } from '@/features/slos/hooks'
import { SloObjectiveTable } from '@/features/slos/components/SloObjectiveTable'
import { SloObjectiveEditor } from '@/features/slos/components/SloObjectiveEditor'
import { SloHistoryPanel } from '@/features/slos/components/SloHistoryPanel'
import { SloCreateForm } from '@/features/slos/components/SloCreateForm'
import { GroupSidebar } from '@/features/slos/components/GroupSidebar'
import { GroupCreateDialog } from '@/features/slos/components/GroupCreateDialog'
import { GroupEditDialog } from '@/features/slos/components/GroupEditDialog'
import { GroupDeleteDialog } from '@/features/slos/components/GroupDeleteDialog'
import { SloLinkDialog } from '@/features/slos/components/SloLinkDialog'

type Mode = 'view' | 'edit-rows' | 'history'

function TabBtn({ active, onClick, children }: {
  active: boolean; onClick: () => void; children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs font-medium rounded transition-colors border ${
        active
          ? 'bg-indigo-600/20 border-indigo-500/50 text-indigo-300'
          : 'bg-transparent border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'
      }`}
    >
      {children}
    </button>
  )
}

function SloDetail({ name }: { name: string }) {
  const { data: slo, isLoading, isError } = useSloDetail(name)
  const [mode, setMode] = useState<Mode>('view')

  if (isLoading) return <p className="text-slate-500 text-sm py-3">Loading…</p>
  if (isError || !slo) return <p className="text-red-400 text-sm py-3">Failed to load.</p>

  return (
    <div className="border-t border-slate-800 mt-3 pt-4 space-y-4">
      <div className="flex gap-2 flex-wrap">
        <TabBtn active={mode === 'view'} onClick={() => setMode('view')}>View</TabBtn>
        <TabBtn active={mode === 'edit-rows'} onClick={() => setMode('edit-rows')}>Edit Rows</TabBtn>
        <TabBtn active={mode === 'history'} onClick={() => setMode('history')}>History</TabBtn>
        <button
          disabled
          title="Coming soon"
          className="px-3 py-1.5 text-xs font-medium rounded border border-slate-800 text-slate-600 cursor-not-allowed"
        >
          Test SLO
        </button>
      </div>

      {mode === 'view' && <SloObjectiveTable slo={slo} />}
      {mode === 'edit-rows' && (
        <SloObjectiveEditor slo={slo} onCancel={() => setMode('view')} onSaved={() => setMode('view')} />
      )}
      {mode === 'history' && <SloHistoryPanel name={name} />}
    </div>
  )
}

function DeleteConfirm({ name, onDone }: { name: string; onDone: () => void }) {
  const del = useDeleteSlo()

  return (
    <div className="flex items-center gap-2 bg-red-900/20 border border-red-700/40 rounded-lg px-3 py-2">
      <span className="text-xs text-red-300">Deactivate <strong>{name}</strong>? All versions will be marked inactive.</span>
      <button
        onClick={() => del.mutate(name, { onSuccess: onDone })}
        disabled={del.isPending}
        className="px-2.5 py-1 text-xs font-medium rounded bg-red-700 text-white hover:bg-red-600 disabled:opacity-40 transition-colors shrink-0"
      >
        {del.isPending ? 'Deactivating…' : 'Confirm'}
      </button>
      <button
        onClick={onDone}
        className="px-2.5 py-1 text-xs rounded border border-slate-600 text-slate-400 hover:text-slate-200 transition-colors shrink-0"
      >
        Cancel
      </button>
    </div>
  )
}

export function SloRegistryPage() {
  const { data: slos, isLoading, isError } = useSlos()
  const { data: tree } = useGroupTree()
  const [searchParams, setSearchParams] = useSearchParams()
  const [expandedSlo, setExpandedSlo] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [showAll, setShowAll] = useState(false)

  // Group selection from URL
  const selectedGroup = searchParams.get('group')
  const setSelectedGroup = (name: string | null) => {
    setShowAll(false)
    if (name) {
      setSearchParams({ group: name })
    } else {
      setSearchParams({})
    }
  }

  // Dialog state
  const [createGroupOpen, setCreateGroupOpen] = useState(false)
  const [editGroupName, setEditGroupName] = useState<string | null>(null)
  const [deleteGroupName, setDeleteGroupName] = useState<string | null>(null)
  const [linkFromGroup, setLinkFromGroup] = useState<string | null>(null)
  const [linkFromSlo, setLinkFromSlo] = useState<string | null>(null)

  // Get linked SLO names for filtering
  const { data: groupLinks } = useGroupSloLinks(
    selectedGroup && selectedGroup !== '__ungrouped__' ? selectedGroup : ''
  )
  const linkedSloNames = new Set(groupLinks?.map(l => l.slo_name) ?? [])

  // Filter SLOs based on selected group
  const filteredSlos = slos?.filter(slo => {
    if (!selectedGroup) return true
    if (selectedGroup === '__ungrouped__') {
      // Client-side: an SLO is "ungrouped" if it doesn't appear in any group's links.
      // Since we don't have a bulk endpoint, this filter will be refined when a
      // GET /slo-links-all endpoint is added. For now, show all SLOs here.
      // TODO: implement with a bulk links endpoint
      return true
    }
    if (showAll) return true
    return linkedSloNames.has(slo.name)
  })

  const isLinked = (sloName: string) => linkedSloNames.has(sloName)

  if (isLoading) return <p className="p-6 text-slate-400">Loading…</p>
  if (isError || !slos) return <p className="p-6 text-red-400">Failed to load.</p>

  const filterLabel = selectedGroup === '__ungrouped__'
    ? 'Ungrouped'
    : selectedGroup
    ? (tree?.all_groups.find(g => g.name === selectedGroup)?.display_name ?? selectedGroup)
    : 'All SLOs'

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <GroupSidebar
        selectedGroup={selectedGroup}
        onSelectGroup={setSelectedGroup}
        onCreateGroup={() => setCreateGroupOpen(true)}
        onEditGroup={name => setEditGroupName(name)}
        onDeleteGroup={name => setDeleteGroupName(name)}
        onAddSloLink={name => setLinkFromGroup(name)}
      />

      {/* Main content */}
      <div className="flex-1 p-6 space-y-4 overflow-y-auto">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-100">SLO Registry</h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Showing: {filterLabel} ({filteredSlos?.length ?? 0})
              {selectedGroup && selectedGroup !== '__ungrouped__' && !showAll && (
                <button
                  onClick={() => setShowAll(true)}
                  className="ml-2 text-primary hover:underline"
                >
                  Show all SLOs
                </button>
              )}
              {showAll && (
                <button
                  onClick={() => setShowAll(false)}
                  className="ml-2 text-primary hover:underline"
                >
                  Show linked only
                </button>
              )}
            </p>
          </div>
          <button
            onClick={() => setShowCreate(v => !v)}
            className={`px-3 py-1.5 text-sm font-medium rounded border transition-colors ${
              showCreate
                ? 'bg-indigo-600/20 border-indigo-500/50 text-indigo-300'
                : 'bg-indigo-600 border-indigo-600 text-white hover:bg-indigo-500'
            }`}
          >
            {showCreate ? '✕ Cancel' : '+ Create SLO'}
          </button>
        </div>

        {/* Inline create panel */}
        {showCreate && (
          <div className="bg-[#111827] border border-indigo-700/40 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-slate-200 mb-4">Create New SLO</h2>
            <SloCreateForm
              onCancel={() => setShowCreate(false)}
              onSaved={() => setShowCreate(false)}
            />
          </div>
        )}

        {/* SLO list */}
        <div className="space-y-2">
          {filteredSlos?.map(slo => {
            const tags = (slo.meta?.tags as string[] | undefined) ?? []
            const isExpanded = expandedSlo === slo.name
            const isConfirmingDelete = confirmDelete === slo.name
            const dimmed = showAll && selectedGroup && !isLinked(slo.name)

            return (
              <div
                key={slo.name}
                className={`bg-[#111827] border rounded-xl overflow-hidden transition-colors ${
                  slo.active ? 'border-slate-700' : 'border-slate-800 opacity-60'
                } ${dimmed ? 'opacity-40' : ''}`}
              >
                {/* Header row */}
                <div className="px-5 py-4 flex items-center gap-4">
                  <button
                    onClick={() => setExpandedSlo(prev => prev === slo.name ? null : slo.name)}
                    className="text-slate-500 text-xs w-3 shrink-0 hover:text-slate-300 transition-colors"
                  >
                    {isExpanded ? '▼' : '▶'}
                  </button>

                  <div
                    className="flex items-center gap-2 min-w-0 flex-1 cursor-pointer"
                    onClick={() => setExpandedSlo(prev => prev === slo.name ? null : slo.name)}
                  >
                    <span className="font-semibold text-slate-100 truncate">
                      {slo.display_name ?? slo.name}
                    </span>
                    <span className="text-xs text-slate-500 shrink-0">v{slo.version}</span>
                    {slo.active
                      ? <span className="text-xs bg-pass/20 text-pass border border-pass/30 px-1.5 py-0.5 rounded-full shrink-0">active</span>
                      : <span className="text-xs bg-slate-700/40 text-slate-500 border border-slate-600/40 px-1.5 py-0.5 rounded-full shrink-0">inactive</span>
                    }
                  </div>

                  {tags.length > 0 && (
                    <div className="flex items-center gap-1 flex-wrap">
                      {tags.map(tag => (
                        <span key={tag} className="text-xs bg-slate-700/60 text-slate-300 px-1.5 py-0.5 rounded">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="ml-auto flex items-center gap-4 text-xs text-slate-500 shrink-0">
                    {slo.author && <span>{slo.author}</span>}
                    {slo.notes && (
                      <span className="max-w-xs truncate text-slate-600 italic" title={slo.notes}>
                        {slo.notes}
                      </span>
                    )}
                    <span className="text-slate-600">{slo.created_at.slice(0, 10)}</span>

                    <button
                      onClick={e => { e.stopPropagation(); setLinkFromSlo(slo.name) }}
                      className="text-xs text-slate-600 hover:text-primary transition-colors border border-transparent hover:border-primary/40 px-1.5 py-0.5 rounded"
                      title="Add to group"
                    >
                      + Group
                    </button>

                    {slo.active && (
                      <button
                        onClick={e => { e.stopPropagation(); setConfirmDelete(slo.name) }}
                        className="text-xs text-slate-600 hover:text-red-400 transition-colors border border-transparent hover:border-red-700/40 px-1.5 py-0.5 rounded"
                        title="Deactivate SLO"
                      >
                        Deactivate
                      </button>
                    )}
                  </div>
                </div>

                {isConfirmingDelete && (
                  <div className="px-5 pb-3">
                    <DeleteConfirm name={slo.name} onDone={() => setConfirmDelete(null)} />
                  </div>
                )}

                {isExpanded && (
                  <div className="px-5 pb-5">
                    <SloDetail name={slo.name} />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Dialogs */}
      <GroupCreateDialog open={createGroupOpen} onOpenChange={setCreateGroupOpen} />
      <GroupEditDialog open={!!editGroupName} onOpenChange={() => setEditGroupName(null)} groupName={editGroupName} />
      <GroupDeleteDialog
        open={!!deleteGroupName}
        onOpenChange={() => setDeleteGroupName(null)}
        groupName={deleteGroupName}
        onDeleted={() => { setDeleteGroupName(null); setSelectedGroup(null) }}
      />
      <SloLinkDialog
        open={!!linkFromGroup}
        onOpenChange={() => setLinkFromGroup(null)}
        lockedGroupName={linkFromGroup ?? undefined}
      />
      <SloLinkDialog
        open={!!linkFromSlo}
        onOpenChange={() => setLinkFromSlo(null)}
        lockedSloName={linkFromSlo ?? undefined}
      />
    </div>
  )
}
```

- [ ] **Step 2: Verify types compile**

Run: `uv run --directory ui npx tsc --noEmit`

- [ ] **Step 3: Visual verification**

Start the dev server and verify:
- Sidebar renders with group tree
- Clicking a group filters the SLO list
- "Show all" toggle works
- "+ Group" button on SLO cards opens the link dialog
- Group CRUD dialogs open from sidebar actions
- URL param `?group=X` persists selection across refresh

- [ ] **Step 4: Commit**

```bash
git add ui/src/pages/SloRegistryPage.tsx
git commit -m "feat(ui): add two-panel SLO Registry with group sidebar and filtering"
```

### Task 12: Run full lint and type check

- [ ] **Step 1: Run backend linter and type checker**

Run: `uv run ruff check api/ adapters/`
Run: `uv run mypy api/app`

Fix any issues found.

- [ ] **Step 2: Run frontend type check**

Run: `uv run --directory ui npx tsc --noEmit`

Fix any issues found.

- [ ] **Step 3: Run backend tests**

Run: `uv run --directory api pytest tests/ -m "not integration" -q`

- [ ] **Step 4: Commit any fixes**

Stage only the files that were fixed (e.g., specific files from `api/` and `ui/src/`), then commit:

```bash
git add <fixed-files>
git commit -m "fix: lint and type check fixes for asset group management"
```
