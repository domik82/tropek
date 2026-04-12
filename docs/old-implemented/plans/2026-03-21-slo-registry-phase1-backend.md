# SLO Registry Redesign — Phase 1 Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename inconsistent `labels`/`meta`/`metadata` fields to `tags`/`variables`, add new `token` and `variables` fields, add tag filtering and DELETE endpoint for datasources, and rewrite worker variable resolution to use the new three-tier merge order.

**Architecture:** Mechanical renames across models/schemas/repositories/routers, followed by new tag-filtering repository methods (reusing the existing asset label-keys pattern), a new DELETE datasource endpoint with SLO-link conflict checking, and a worker variable-resolution rewrite that merges `asset.variables` → `slo.variables` → `evaluation.variables` in priority order.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, PostgreSQL JSONB, Pydantic v2, uv, ruff, mypy, pytest

**Spec document:** `docs/superpowers/specs/2026-03-21-slo-registry-redesign.md` (Phase 1 — Backend section)

---

## File Structure

### Files to modify

| File | Changes |
|------|---------|
| `api/app/db/models.py` | Rename `labels`→`tags` (Asset:68, DataSource:147), `meta`→`tags` (SLI:180, SLO:229, Annotation:349), `evaluation_metadata`→`variables` (Evaluation:314). Add `token` to DataSource, `variables` to Asset and SLODefinition. |
| `api/app/modules/datasource/schemas.py` | Rename `labels`→`tags`. Add `token` field to create/update. Exclude `token` from read. |
| `api/app/modules/datasource/repository.py` | Rename `labels`→`tags`. Add `token` param, `get_tag_keys()`, `get_tag_values()`, tag filtering in `list_all()`, `delete_by_name()` with conflict check. |
| `api/app/modules/datasource/router.py` | Rename `labels`→`tags`. Add `tag_key`/`tag_val` params, tag-keys/tag-values endpoints, DELETE endpoint. |
| `api/app/modules/sli_registry/schemas.py` | Rename `meta`→`tags`. |
| `api/app/modules/sli_registry/repository.py` | Rename `meta`→`tags`. Add `get_tag_keys()`, `get_tag_values()`, tag filtering in `list_all()`. |
| `api/app/modules/sli_registry/router.py` | Rename `meta`→`tags`. Add `tag_key`/`tag_val` params, tag-keys/tag-values endpoints. |
| `api/app/modules/slo_registry/schemas.py` | Rename `meta`→`tags`, `metadata`→`variables` (SLOTestRequest:117). Add `variables` field to create/read. |
| `api/app/modules/slo_registry/repository.py` | Rename `meta`→`tags`. Add `variables` param. Add `get_tag_keys()`, `get_tag_values()`, tag filtering in `list_all()`. |
| `api/app/modules/slo_registry/router.py` | Rename `meta`→`tags`. Pass `variables` through. Add `tag_key`/`tag_val` params, tag-keys/tag-values endpoints. Update SLO test variable resolution. |
| `api/app/modules/quality_gate/schemas.py` | Rename `meta`→`tags` (Annotation), `evaluation_metadata`→`variables` (EvaluationSummary:115), `metadata`→`variables` (TriggerRequest:199, BatchTriggerRequest:216). |
| `api/app/modules/quality_gate/worker.py` | Rewrite variable resolution (lines 213-225) to use three-tier merge. Update `os_tag` SLI value write (line 291). |
| `api/app/modules/quality_gate/trigger.py` | Rename `TriggerContext.asset_labels`→`asset_tags`, add `asset_variables` field. Update `resolve_single_trigger()` to read `asset.tags` + `asset.variables`. |
| `api/app/modules/quality_gate/trigger_service.py` | Update `asset_snapshot` to include `variables` from `TriggerContext`. Rename `metadata=request.metadata`→`variables=request.variables`. |
| `api/app/modules/quality_gate/repository.py` | Rename `metadata` param→`variables`, `evaluation_metadata`→`variables`. Update `merged_metadata` logic: read `asset_row.tags` (not `.labels`), write to `variables` field. |
| `api/app/modules/assets/schemas.py` | Rename `labels`→`tags`, `LabelKeyCount`→`TagKeyCount`, `LabelValueCount`→`TagValueCount`. Add `variables` field. |
| `api/app/modules/assets/repository.py` | Rename `labels`→`tags`, `get_label_keys`→`get_tag_keys`, `get_label_values`→`get_tag_values`, `label_key`→`tag_key`, `label_val`→`tag_val`. |
| `api/app/modules/assets/router.py` | Rename `label_key`→`tag_key`, `label_val`→`tag_val`, `label-keys`→`tag-keys`, `label-values`→`tag-values`. Import renames. |
| `clients/python/tropek_client/models.py` | Rename `labels`→`tags` (Asset:36, DataSource:86), `meta`→`tags` (SLI:101, SLO:134, Annotation:217), `evaluation_metadata`→`variables` (EvaluationSummary:251), `metadata`→`variables` (client trigger methods). Add `variables` to Asset/SLODefinition, `token` to DataSource. |
| `clients/python/tropek_client/client.py` | Rename `labels`→`tags`, `label_key`→`tag_key`, `label_val`→`tag_val`, `metadata`→`variables`. Add `tag_keys()`/`tag_values()` to _DataSources, _SLIDefinitions, _SLODefinitions. Add `delete()` to _DataSources. |
| `clients/python/tropek_client/manifest.py` | Rename `labels`→`tags` in `_has_diff`, `_create`, `_update`. Add `variables` handling. |
| `bootstrap_mock/manifests/datasources.yaml` | Rename `labels:`→`tags:`. |
| `bootstrap_mock/manifests/assets.yaml` | Split `labels:` into `tags:` (team, env, region, tier) + `variables:` (job, namespace, instance, runtime, os, dc). |

### Test files to modify

| File | Changes |
|------|---------|
| `api/tests/db/test_datasource_repository.py` | Rename `labels`→`tags`, add tests for tag filtering + delete with conflict check. |
| `api/tests/db/test_asset_repositories.py` | Rename `labels`→`tags`, `label_key`→`tag_key`, `label_val`→`tag_val`, add `variables` field tests. |
| `api/tests/db/test_sli_repository.py` | Rename `meta`→`tags`, add tag filtering tests. |
| `api/tests/db/test_slo_repository.py` | Rename `meta`→`tags`, add `variables` field + tag filtering tests. |
| `api/tests/services/test_worker_helpers.py` | Update to test new three-tier variable merge. |
| `api/tests/services/test_trigger.py` | Update `asset_labels` → `asset_tags` + add `asset_variables` in TriggerContext tests (if exists). |
| `api/tests/test_qg_router.py` | Rename `evaluation_metadata`→`variables`, `metadata`→`variables`. |
| `api/tests/test_slo_test_endpoint.py` | Rename `metadata`→`variables`. |
| `api/tests/test_slo_validate.py` | Rename `meta`→`tags` if present. |
| `clients/python/tests/test_models.py` | Rename fields in test data. |
| `clients/python/tests/test_manifest.py` | Update manifest fixtures for tags/variables split. |
| `clients/python/tests/test_client.py` | Rename fields in test data + expectations. |

---

## Task 1: Model Field Renames

**Files:**
- Modify: `api/app/db/models.py`

This is a mechanical rename — no new behavior. All existing tests will break until schemas match, which is expected.

- [ ] **Step 1: Rename Asset.labels → Asset.tags**

In `api/app/db/models.py:68`, change:
```python
labels:       Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
```
to:
```python
tags:         Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
```

- [ ] **Step 2: Add Asset.variables field**

After the `tags` line (former line 68), add:
```python
variables:    Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
```

- [ ] **Step 3: Rename DataSource.labels → DataSource.tags and add token**

In `api/app/db/models.py:147`, change:
```python
labels:       Mapped[dict[str, Any]]   = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
```
to:
```python
tags:         Mapped[dict[str, Any]]   = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
token:        Mapped[str | None]       = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Rename SLIDefinition.meta → SLIDefinition.tags**

In `api/app/db/models.py:180`, change `meta:` → `tags:` (keep the rest identical).

- [ ] **Step 5: Rename SLODefinition.meta → SLODefinition.tags and add variables**

In `api/app/db/models.py:229`, change `meta:` → `tags:`. After it, add:
```python
variables:               Mapped[dict[str, Any]]         = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
```

- [ ] **Step 6: Rename Evaluation.evaluation_metadata → Evaluation.variables**

In `api/app/db/models.py:314`, change:
```python
evaluation_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
```
to:
```python
variables: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
```

- [ ] **Step 7: Rename EvaluationAnnotation.meta → EvaluationAnnotation.tags**

In `api/app/db/models.py:349`, change `meta:` → `tags:`.

- [ ] **Step 8: Commit**

```bash
git add api/app/db/models.py
git commit -m "refactor: rename labels/meta → tags/variables in ORM models, add token and variables fields"
```

---

## Task 2: Schema Field Renames

**Files:**
- Modify: `api/app/modules/datasource/schemas.py`
- Modify: `api/app/modules/sli_registry/schemas.py`
- Modify: `api/app/modules/slo_registry/schemas.py`
- Modify: `api/app/modules/quality_gate/schemas.py`
- Modify: `api/app/modules/assets/schemas.py`

Mechanical renames across all Pydantic schemas. No behavior change.

- [ ] **Step 1: Update datasource schemas**

In `api/app/modules/datasource/schemas.py`:

`DataSourceCreate` — rename `labels` → `tags`, add `token`:
```python
class DataSourceCreate(BaseModel):
    """Request body for creating a datasource."""

    name: str
    display_name: str | None = None
    adapter_type: str
    adapter_url: str
    tags: dict[str, str] = {}
    token: str | None = None
```

`DataSourceUpdate` — rename `labels` → `tags`, add `token`:
```python
class DataSourceUpdate(BaseModel):
    """Request body for updating a datasource."""

    display_name: str | None = None
    adapter_url: str | None = None
    tags: dict[str, str] | None = None
    token: str | None = None
```

`DataSourceRead` — rename `labels` → `tags` (no `token` field — write-only). Add `has_token` as a computed field via `@model_validator`:
```python
from pydantic import model_validator

class DataSourceRead(BaseModel):
    """Response schema for a datasource."""

    id: uuid.UUID
    name: str
    display_name: str | None
    adapter_type: str
    adapter_url: str
    tags: dict[str, Any]
    has_token: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def compute_has_token(cls, data: Any) -> Any:
        """Set has_token from the ORM token field, then exclude token from output."""
        if hasattr(data, "token"):
            # ORM object
            if isinstance(data, dict):
                data["has_token"] = data.get("token") is not None
            else:
                # For from_attributes=True, we need a dict copy
                return data  # handled below
        elif isinstance(data, dict):
            data["has_token"] = data.get("token") is not None
        return data
```

Actually, the simplest approach: since `model_validate(orm_obj)` with `from_attributes=True` reads attributes, just add a `@property` on the ORM model or use a simpler validator. The cleanest way is to just set `has_token` in the router after `model_validate` — it's 3 lines and explicit. Use a helper function to avoid repetition:

```python
def _ds_read(ds: DataSource) -> DataSourceRead:
    r = DataSourceRead.model_validate(ds)
    r.has_token = ds.token is not None
    return r
```

Place this helper in the router file and use it in all datasource endpoints (`list`, `get`, `create`, `update`).

- [ ] **Step 2: Update SLI schemas**

In `api/app/modules/sli_registry/schemas.py`:
- `SLIDefinitionCreate` line 21: `meta` → `tags`
- `SLIDefinitionRead` line 37: `meta` → `tags`

- [ ] **Step 3: Update SLO schemas**

In `api/app/modules/slo_registry/schemas.py`:
- `SLODefinitionCreate` line 44: `meta` → `tags`. Add `variables: dict[str, Any] = Field(default_factory=dict)` after it.
- `SLODefinitionRead` line 63: `meta` → `tags`. Add `variables: dict[str, Any]` after it.
- `SLOTestRequest` line 117: `metadata` → `variables`

- [ ] **Step 4: Update quality_gate schemas**

In `api/app/modules/quality_gate/schemas.py`:
- `AnnotationRead` line 28: `meta` → `tags`
- `AnnotationCreate` line 44: `meta` → `tags`
- `AnnotationUpdate` line 53: `meta` → `tags`
- `EvaluationSummary` line 115: `evaluation_metadata` → `variables`
- `TriggerRequest` line 199: `metadata` → `variables`
- `BatchTriggerRequest` line 216: `metadata` → `variables`

- [ ] **Step 5: Update asset schemas**

In `api/app/modules/assets/schemas.py`:
- `AssetCreate` line 47: `labels` → `tags`. Add `variables: dict[str, str] = {}`.
- `AssetUpdate` line 55: `labels` → `tags`. Add `variables: dict[str, str] | None = None`.
- `LabelKeyCount` class (lines 59-63): rename class to `TagKeyCount`, docstring to mention "tag".
- `LabelValueCount` class (lines 66-70): rename class to `TagValueCount`, docstring to mention "tag".
- `AssetRead` line 80: `labels` → `tags`. Add `variables: dict[str, Any]`.

- [ ] **Step 6: Verify ruff + mypy pass on schema files**

Run: `uv run ruff check api/app/modules/*/schemas.py api/app/db/models.py`
Run: `uv run mypy api/app/modules/ api/app/db/`
Expected: Clean (or only errors about downstream references not yet updated)

- [ ] **Step 7: Commit**

```bash
git add api/app/modules/datasource/schemas.py api/app/modules/sli_registry/schemas.py api/app/modules/slo_registry/schemas.py api/app/modules/quality_gate/schemas.py api/app/modules/assets/schemas.py
git commit -m "refactor: rename labels/meta/metadata → tags/variables in all Pydantic schemas"
```

---

## Task 3: Asset Module Updates (Repository + Router)

**Files:**
- Modify: `api/app/modules/assets/repository.py`
- Modify: `api/app/modules/assets/router.py`
- Modify: `api/tests/db/test_asset_repositories.py`

- [ ] **Step 1: Update asset repository**

In `api/app/modules/assets/repository.py`:
- All `labels` params/references → `tags`
- `get_label_keys()` → `get_tag_keys()` — update SQL: `jsonb_object_keys(labels)` → `jsonb_object_keys(tags)`
- `get_label_values()` → `get_tag_values()` — update SQL: `labels->>:key` → `tags->>:key`, `labels ? :key` → `tags ? :key`
- `list_all()` params: `label_key` → `tag_key`, `label_val` → `tag_val` — update filter references from `Asset.labels` to `Asset.tags`
- `create()` param: `labels` → `tags`. Add `variables` param.

- [ ] **Step 2: Update asset router**

In `api/app/modules/assets/router.py`:
- Import `TagKeyCount, TagValueCount` (was `LabelKeyCount, LabelValueCount`)
- `list_assets()` params: `label_key` → `tag_key`, `label_val` → `tag_val`
- Rename endpoint paths: `/assets/label-keys` → `/assets/tag-keys`, `/assets/label-values` → `/assets/tag-values`
- Rename functions: `list_label_keys` → `list_tag_keys`, `list_label_values` → `list_tag_values`
- Update `create_asset()` to pass `tags=body.tags, variables=body.variables`

- [ ] **Step 3: Update asset repository tests**

In `api/tests/db/test_asset_repositories.py`, rename all `labels` → `tags`, `label_key` → `tag_key`, `label_val` → `tag_val`, `get_label_keys` → `get_tag_keys`, `get_label_values` → `get_tag_values`. Add `variables` param where assets are created with identity bindings.

- [ ] **Step 4: Run asset tests**

Run: `uv run pytest api/tests/db/test_asset_repositories.py -v`
Expected: All pass (tests may not run without DB — mark as verification step).

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/assets/repository.py api/app/modules/assets/router.py api/tests/db/test_asset_repositories.py
git commit -m "refactor: rename labels → tags in asset module, add variables field"
```

---

## Task 4: Datasource Module — Renames + Tag Filtering + DELETE

**Files:**
- Modify: `api/app/modules/datasource/repository.py`
- Modify: `api/app/modules/datasource/router.py`
- Modify: `api/tests/db/test_datasource_repository.py`

### 4a: Repository renames and new methods

- [ ] **Step 1: Write failing tests for tag filtering and delete**

In `api/tests/db/test_datasource_repository.py`, add tests:

```python
@pytest.mark.integration
async def test_list_all_filters_by_tag(session: AsyncSession) -> None:
    """list_all with tag_key/tag_val filters returns matching datasources."""
    repo = DataSourceRepository(session)
    await repo.create("ds-a", "prometheus", "http://a", tags={"env": "prod"})
    await repo.create("ds-b", "prometheus", "http://b", tags={"env": "staging"})
    result = await repo.list_all(tag_key="env", tag_val="prod")
    assert len(result) == 1
    assert result[0].name == "ds-a"


@pytest.mark.integration
async def test_get_tag_keys(session: AsyncSession) -> None:
    """get_tag_keys returns distinct keys with counts."""
    repo = DataSourceRepository(session)
    await repo.create("ds-a", "prometheus", "http://a", tags={"env": "prod", "team": "a"})
    await repo.create("ds-b", "prometheus", "http://b", tags={"env": "staging"})
    keys = await repo.get_tag_keys()
    assert keys["env"] == 2
    assert keys["team"] == 1


@pytest.mark.integration
async def test_get_tag_values(session: AsyncSession) -> None:
    """get_tag_values returns distinct values for a key with counts."""
    repo = DataSourceRepository(session)
    await repo.create("ds-a", "prometheus", "http://a", tags={"env": "prod"})
    await repo.create("ds-b", "prometheus", "http://b", tags={"env": "prod"})
    await repo.create("ds-c", "mock", "http://c", tags={"env": "staging"})
    values = await repo.get_tag_values("env")
    assert values["prod"] == 2
    assert values["staging"] == 1


@pytest.mark.integration
async def test_delete_by_name_success(session: AsyncSession) -> None:
    """delete_by_name removes a datasource with no active SLO links."""
    repo = DataSourceRepository(session)
    await repo.create("ds-del", "mock", "http://d", tags={})
    deleted = await repo.delete_by_name("ds-del")
    assert deleted is True
    assert await repo.get_by_name("ds-del") is None


@pytest.mark.integration
async def test_delete_by_name_not_found(session: AsyncSession) -> None:
    """delete_by_name returns False for nonexistent datasource."""
    repo = DataSourceRepository(session)
    deleted = await repo.delete_by_name("nonexistent")
    assert deleted is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest api/tests/db/test_datasource_repository.py -v -k "tag or delete_by_name"`
Expected: FAIL — methods don't exist yet.

- [ ] **Step 3: Implement repository changes**

In `api/app/modules/datasource/repository.py`:

Rename all `labels` → `tags` in existing methods. Add `token` param to `create()` and `update()`.

Add new methods:

```python
async def list_all(
    self,
    *,
    adapter_type: str | None = None,
    tag_key: str | None = None,
    tag_val: str | None = None,
) -> list[DataSource]:
    q = select(DataSource).order_by(DataSource.name)
    if adapter_type:
        q = q.where(DataSource.adapter_type == adapter_type)
    if tag_key and tag_val:
        q = q.where(DataSource.tags[tag_key].astext == tag_val)
    elif tag_key:
        q = q.where(DataSource.tags.has_key(tag_key))
    result = await self._session.execute(q)
    return list(result.scalars().all())

async def get_tag_keys(self) -> dict[str, int]:
    result = await self._session.execute(
        text(
            "SELECT key, COUNT(*) as cnt "
            "FROM data_sources, jsonb_object_keys(tags) AS key "
            "GROUP BY key ORDER BY cnt DESC"
        )
    )
    return {row[0]: row[1] for row in result}

async def get_tag_values(self, key: str) -> dict[str, int]:
    result = await self._session.execute(
        text(
            "SELECT tags->>:key AS val, COUNT(*) as cnt "
            "FROM data_sources "
            "WHERE tags ? :key "
            "GROUP BY val ORDER BY cnt DESC"
        ),
        {"key": key},
    )
    return {row[0]: row[1] for row in result}

async def delete_by_name(self, name: str) -> bool:
    ds = await self.get_by_name(name)
    if ds is None:
        return False
    await self._session.execute(delete(DataSource).where(DataSource.id == ds.id))
    return True
```

Note: Import `text` from sqlalchemy at the top of the file (add to existing import).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest api/tests/db/test_datasource_repository.py -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/datasource/repository.py api/tests/db/test_datasource_repository.py
git commit -m "feat: add tag filtering, tag discovery, and delete-by-name to datasource repository"
```

### 4b: Router updates

- [ ] **Step 6: Update datasource router**

In `api/app/modules/datasource/router.py`:

Import `TagKeyCount, TagValueCount` from asset schemas (or create equivalent in datasource schemas — simpler to reuse from `common/schemas.py` or just define in datasource/schemas.py).

Actually, define `TagKeyCount` and `TagValueCount` in a shared location. The simplest approach: import them from `api/app/modules/assets/schemas.py` since they're the same schema. Or better, since each module should be self-contained, just reference the same shape. The asset schemas already define `TagKeyCount` and `TagValueCount` — reuse them via import from assets.

Update endpoints:

Add `_ds_read` helper (see schema section) and use it in all endpoints:

```python
from app.modules.assets.schemas import TagKeyCount, TagValueCount

def _ds_read(ds: DataSource) -> DataSourceRead:
    r = DataSourceRead.model_validate(ds)
    r.has_token = ds.token is not None
    return r

@router.get("/datasources", response_model=PagedResponse[DataSourceRead])
async def list_datasources(
    adapter_type: str | None = None,
    tag_key: str | None = None,
    tag_val: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> PagedResponse[DataSourceRead]:
    repo = DataSourceRepository(session)
    items = await repo.list_all(adapter_type=adapter_type, tag_key=tag_key, tag_val=tag_val)
    reads = [_ds_read(d) for d in items]
    return PagedResponse(items=reads, total=len(reads))
```

Update `create_datasource()` to pass `tags=body.tags, token=body.token` and return `_ds_read(ds)`.
Update `get_datasource()` and `update_datasource()` to return `_ds_read(ds)`.

Add new endpoints:

```python
@router.get("/datasources/tag-keys", response_model=list[TagKeyCount])
async def list_datasource_tag_keys(
    session: AsyncSession = Depends(get_session),
) -> list[TagKeyCount]:
    repo = DataSourceRepository(session)
    keys = await repo.get_tag_keys()
    return [TagKeyCount(key=k, count=v) for k, v in keys.items()]


@router.get("/datasources/tag-values", response_model=list[TagValueCount])
async def list_datasource_tag_values(
    key: str,
    session: AsyncSession = Depends(get_session),
) -> list[TagValueCount]:
    repo = DataSourceRepository(session)
    values = await repo.get_tag_values(key)
    return [TagValueCount(value=k, count=v) for k, v in values.items()]


@router.delete("/datasources/{name}", status_code=204)
async def delete_datasource(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    repo = DataSourceRepository(session)
    ds = await repo.get_by_name(name)
    if ds is None:
        raise_not_found("datasource", name)
    # Check for active SLO links referencing this datasource
    from app.db.models import AssetGroupSLOLink, AssetSLOLink
    from sqlalchemy import select as sa_select
    asset_links = (await session.execute(
        sa_select(AssetSLOLink).where(AssetSLOLink.data_source_name == name)
    )).scalars().all()
    group_links = (await session.execute(
        sa_select(AssetGroupSLOLink).where(AssetGroupSLOLink.data_source_name == name)
    )).scalars().all()
    if asset_links or group_links:
        link_names = [lnk.link_name for lnk in [*asset_links, *group_links]]
        raise_conflict("datasource", name, f"referenced by SLO links: {', '.join(link_names)}")
    await repo.delete_by_name(name)
```

**Important:** The `tag-keys` and `tag-values` endpoints must be registered **before** the `{name}` path parameter routes to avoid FastAPI treating "tag-keys" as a datasource name. Verify the endpoint order.

- [ ] **Step 7: Run lint**

Run: `uv run ruff check api/app/modules/datasource/`
Expected: Clean.

- [ ] **Step 8: Commit**

```bash
git add api/app/modules/datasource/router.py api/app/modules/datasource/schemas.py
git commit -m "feat: add tag filtering, tag discovery, DELETE endpoint to datasource router"
```

---

## Task 5: SLI Module — Renames + Tag Filtering

**Files:**
- Modify: `api/app/modules/sli_registry/repository.py`
- Modify: `api/app/modules/sli_registry/router.py`
- Modify: `api/tests/db/test_sli_repository.py`

- [ ] **Step 1: Write failing tests for SLI tag filtering**

In `api/tests/db/test_sli_repository.py`, add tests:

```python
@pytest.mark.integration
async def test_list_all_filters_by_tag(session: AsyncSession) -> None:
    repo = SLIRepository(session)
    await repo.create("sli-a", {"m1": "q1"}, "prometheus", tags={"team": "alpha"})
    await repo.create("sli-b", {"m2": "q2"}, "prometheus", tags={"team": "beta"})
    result = await repo.list_all(tag_key="team", tag_val="alpha")
    assert len(result) == 1
    assert result[0].name == "sli-a"


@pytest.mark.integration
async def test_get_tag_keys(session: AsyncSession) -> None:
    repo = SLIRepository(session)
    await repo.create("sli-a", {"m1": "q1"}, "prometheus", tags={"team": "a", "env": "prod"})
    await repo.create("sli-b", {"m2": "q2"}, "prometheus", tags={"env": "staging"})
    keys = await repo.get_tag_keys()
    assert keys["env"] == 2
    assert keys["team"] == 1


@pytest.mark.integration
async def test_get_tag_values(session: AsyncSession) -> None:
    repo = SLIRepository(session)
    await repo.create("sli-a", {"m1": "q1"}, "prometheus", tags={"env": "prod"})
    await repo.create("sli-b", {"m2": "q2"}, "prometheus", tags={"env": "staging"})
    values = await repo.get_tag_values("env")
    assert values["prod"] == 1
    assert values["staging"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest api/tests/db/test_sli_repository.py -v -k "tag"`
Expected: FAIL.

- [ ] **Step 3: Implement SLI repository changes**

In `api/app/modules/sli_registry/repository.py`:

Rename `meta` → `tags` in `create()` (param and assignment).

Add `tag_key`/`tag_val` params to `list_all()`:
```python
async def list_all(
    self, *, adapter_type: str | None = None, tag_key: str | None = None, tag_val: str | None = None
) -> list[SLIDefinition]:
```

Apply tag filtering to the base query (before the DISTINCT ON subquery):
```python
if tag_key and tag_val:
    base = base.where(SLIDefinition.tags[tag_key].astext == tag_val)
elif tag_key:
    base = base.where(SLIDefinition.tags.has_key(tag_key))
```

Add `get_tag_keys()` and `get_tag_values()` methods — same pattern as datasource, using table name `sli_definitions` and column `tags`.

Import `text` from sqlalchemy.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest api/tests/db/test_sli_repository.py -v`
Expected: All pass.

- [ ] **Step 5: Update SLI router**

In `api/app/modules/sli_registry/router.py`:

Rename `meta` → `tags` in `create_sli_definition()`.

Add `tag_key`/`tag_val` params to `list_sli_definitions()`.

Add tag-keys/tag-values endpoints (same pattern as datasource router). Place them **before** the `{name}` routes.

- [ ] **Step 6: Commit**

```bash
git add api/app/modules/sli_registry/repository.py api/app/modules/sli_registry/router.py api/tests/db/test_sli_repository.py
git commit -m "feat: rename meta → tags in SLI module, add tag filtering and discovery"
```

---

## Task 6: SLO Module — Renames + Variables + Tag Filtering

**Files:**
- Modify: `api/app/modules/slo_registry/repository.py`
- Modify: `api/app/modules/slo_registry/router.py`
- Modify: `api/tests/db/test_slo_repository.py`

- [ ] **Step 1: Write failing tests for SLO tag filtering and variables**

In `api/tests/db/test_slo_repository.py`, add tests:

```python
@pytest.mark.integration
async def test_create_with_variables(session: AsyncSession) -> None:
    repo = SLORepository(session)
    slo = await repo.create(
        "slo-vars",
        objectives=[{"sli": "m1", "pass_criteria": ["<600"]}],
        tags={"team": "alpha"},
        variables={"aggregation_window": "5m"},
    )
    assert slo.tags == {"team": "alpha"}
    assert slo.variables == {"aggregation_window": "5m"}


@pytest.mark.integration
async def test_list_all_filters_by_tag(session: AsyncSession) -> None:
    repo = SLORepository(session)
    await repo.create("slo-a", [{"sli": "m1", "pass_criteria": ["<600"]}], tags={"env": "prod"})
    await repo.create("slo-b", [{"sli": "m2", "pass_criteria": ["<100"]}], tags={"env": "staging"})
    result = await repo.list_all(tag_key="env", tag_val="prod")
    assert len(result) == 1
    assert result[0].name == "slo-a"


@pytest.mark.integration
async def test_get_tag_keys(session: AsyncSession) -> None:
    repo = SLORepository(session)
    await repo.create("slo-a", [{"sli": "m1", "pass_criteria": ["<600"]}], tags={"team": "a", "env": "prod"})
    await repo.create("slo-b", [{"sli": "m2", "pass_criteria": ["<100"]}], tags={"env": "staging"})
    keys = await repo.get_tag_keys()
    assert keys["env"] == 2
    assert keys["team"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest api/tests/db/test_slo_repository.py -v -k "tag or variables"`
Expected: FAIL.

- [ ] **Step 3: Implement SLO repository changes**

In `api/app/modules/slo_registry/repository.py`:

Rename `meta` → `tags` in `create()`. Add `variables` param:
```python
async def create(
    self,
    name: str,
    objectives: list[dict[str, Any]],
    ...
    tags: dict[str, Any] | None = None,
    variables: dict[str, Any] | None = None,
    comparable_from_version: int | None = None,
) -> SLODefinition:
```

In the SLODefinition constructor, set `tags=tags or {}` and `variables=variables or {}`.

Add `tag_key`/`tag_val` params to `list_all()`:
```python
async def list_all(
    self, *, tag_key: str | None = None, tag_val: str | None = None
) -> list[SLODefinition]:
```

Apply tag filtering to the base query (before subquery).

Add `get_tag_keys()` and `get_tag_values()` — same pattern, table `slo_definitions`, column `tags`.

Import `text` from sqlalchemy.

- [ ] **Step 4: Run tests**

Run: `uv run pytest api/tests/db/test_slo_repository.py -v`
Expected: All pass.

- [ ] **Step 5: Update SLO router**

In `api/app/modules/slo_registry/router.py`:

- `create_slo_definition()`: rename `meta=body.meta` → `tags=body.tags`, add `variables=body.variables`.
- `list_slo_definitions()`: add `tag_key`/`tag_val` params, pass to `repo.list_all()`.
- Add tag-keys/tag-values endpoints before `{name}` routes.
- `test_slo()` (line 161-170): update variable resolution to use new merge order.
  Replace the existing `asset_labels` + `build_variables(metadata=...)` block with:

```python
# Reserved variables (lowest priority)
variables = build_variables(
    metadata={},
    asset_name=asset.name,
    evaluation_name=body.evaluation_name,
    start=body.period_start.isoformat(),
    end=body.period_end.isoformat(),
)
# Asset variables (identity bindings)
for k, v in (getattr(asset, "variables", {}) or {}).items():
    variables.setdefault(k, str(v))
# Asset tags as fallback variables (backward compat)
for k, v in (getattr(asset, "tags", {}) or {}).items():
    variables.setdefault(k, str(v))
# Request variables (highest priority — serves as evaluation-level overrides;
# the test endpoint has no saved SLO, so there's no SLO-level variables source)
for k, v in body.variables.items():
    variables[k] = str(v)
```

- [ ] **Step 6: Commit**

```bash
git add api/app/modules/slo_registry/repository.py api/app/modules/slo_registry/router.py api/tests/db/test_slo_repository.py
git commit -m "feat: rename meta → tags in SLO module, add variables field and tag filtering"
```

---

## Task 7: Quality Gate Module — Evaluation Schemas + Worker Variable Resolution

**Files:**
- Modify: `api/app/modules/quality_gate/worker.py`
- Modify: `api/app/modules/quality_gate/schemas.py` (already done in Task 2, verify)
- Modify: `api/tests/services/test_worker_helpers.py`

- [ ] **Step 1: Read and understand current worker variable resolution**

Read `api/app/modules/quality_gate/worker.py:213-228` and `api/tests/services/test_worker_helpers.py`.

Current logic:
```python
asset_labels = asset_snapshot.get("tags", {})  # reads from snapshot "tags" key
eval_metadata = ev.evaluation_metadata or {}
variables = build_variables(metadata={k: str(v) for k, v in eval_metadata.items()}, ...)
for k, v in asset_labels.items():
    variables.setdefault(k, str(v))
```

New logic per spec:
```python
variables = build_variables(metadata={}, ...)  # reserved only
for k, v in (asset_snapshot.get("variables") or {}).items():
    variables.setdefault(k, str(v))
for k, v in (asset_snapshot.get("tags") or {}).items():
    variables.setdefault(k, str(v))
for k, v in (slo_def.variables or {}).items():
    variables[k] = str(v)  # slo overrides asset
for k, v in (ev.variables or {}).items():
    variables[k] = str(v)  # eval overrides everything
```

Note: We also need to access `slo_def` in the worker — check if it's already available. Looking at worker.py around line 191-211, `slo_def` is fetched as the SLODefinition ORM object. It has `variables` after our model changes. Good.

- [ ] **Step 2: Write/update worker variable resolution test**

In `api/tests/services/test_worker_helpers.py`, add or update test for the new merge order:

```python
def test_variable_merge_priority() -> None:
    """Variables merge with correct priority: reserved < asset.variables < asset.tags < slo.variables < eval.variables."""
    from app.modules.quality_gate.engine.variables import build_variables

    # Simulate the merge order from worker.py
    variables = build_variables(
        metadata={},
        asset_name="my-asset",
        evaluation_name="daily-check",
        start="2025-01-01T00:00:00",
        end="2025-01-01T01:00:00",
    )
    asset_variables = {"job": "checkout-api", "namespace": "ecommerce"}
    asset_tags = {"team": "payments", "namespace": "old-value"}  # namespace should NOT override
    slo_variables = {"aggregation_window": "5m", "job": "slo-override"}
    eval_variables = {"branch": "main", "job": "eval-override"}

    for k, v in asset_variables.items():
        variables.setdefault(k, str(v))
    for k, v in asset_tags.items():
        variables.setdefault(k, str(v))
    for k, v in slo_variables.items():
        variables[k] = str(v)
    for k, v in eval_variables.items():
        variables[k] = str(v)

    # Reserved variables
    assert variables["asset_name"] == "my-asset"
    assert variables["evaluation_name"] == "daily-check"
    # Asset variables (set first via setdefault)
    assert variables["namespace"] == "ecommerce"  # asset_variables wins over asset_tags
    # Asset tags (only if not already set)
    assert variables["team"] == "payments"
    # SLO overrides asset
    assert variables["aggregation_window"] == "5m"
    # Eval overrides everything
    assert variables["branch"] == "main"
    assert variables["job"] == "eval-override"  # eval wins over slo
```

- [ ] **Step 3: Run test**

Run: `uv run pytest api/tests/services/test_worker_helpers.py -v -k "merge_priority"`
Expected: PASS (this tests the merge logic directly, not the worker wiring).

- [ ] **Step 4: Update worker variable resolution**

In `api/app/modules/quality_gate/worker.py`, replace lines 213-225:

```python
# Build variables and substitute into queries
asset_snapshot: dict[str, Any] = ev.asset_snapshot or {}
variables = build_variables(
    metadata={},
    asset_name=asset_snapshot.get("name"),
    evaluation_name=ev.evaluation_name,
    start=ev.period_start.isoformat(),
    end=ev.period_end.isoformat(),
)
# Merge in priority order: asset.variables < asset.tags < slo.variables < eval.variables
for k, v in (asset_snapshot.get("variables") or {}).items():
    variables.setdefault(k, str(v))
for k, v in (asset_snapshot.get("tags") or {}).items():
    variables.setdefault(k, str(v))
for k, v in (slo_def.variables or {}).items():
    variables[k] = str(v)
for k, v in (ev.variables or {}).items():
    variables[k] = str(v)
```

Note: `slo_def` is already available in scope (fetched earlier in the function). After our model change, `slo_def.variables` exists.

- [ ] **Step 5: Update os_tag in SLI value writes**

In `api/app/modules/quality_gate/worker.py:291`, update:
```python
"os_tag": asset_snapshot.get("tags", {}).get("os") or asset_snapshot.get("variables", {}).get("os"),
```

This preserves backward compat — `os` could be in either `tags` or `variables` depending on the asset.

- [ ] **Step 6: Run lint**

Run: `uv run ruff check api/app/modules/quality_gate/worker.py`
Expected: Clean.

- [ ] **Step 7: Commit**

```bash
git add api/app/modules/quality_gate/worker.py api/tests/services/test_worker_helpers.py
git commit -m "feat: rewrite worker variable resolution to three-tier merge order"
```

---

## Task 8: Trigger Pipeline — TriggerContext, TriggerService, EvaluationRepository

**Critical:** Without this task, the worker's `asset_snapshot.get("variables")` would always return `{}` because the snapshot never included `variables`. This task ensures the full trigger→snapshot→worker pipeline uses the new field names.

**Files:**
- Modify: `api/app/modules/quality_gate/trigger.py`
- Modify: `api/app/modules/quality_gate/trigger_service.py`
- Modify: `api/app/modules/quality_gate/repository.py`

- [ ] **Step 1: Update TriggerContext dataclass**

In `api/app/modules/quality_gate/trigger.py:23-38`:

Rename `asset_labels` → `asset_tags`. Add `asset_variables`:
```python
@dataclass
class TriggerContext:
    """All resolved references needed to run an evaluation job."""

    asset_id: uuid.UUID
    asset_name: str
    asset_tags: dict[str, Any]
    asset_variables: dict[str, Any]
    slo_name: str
    slo_version: int
    sli_name: str
    sli_version: int
    data_source_name: str
    adapter_url: str
    adapter_type: str
    indicators: dict[str, str]
```

- [ ] **Step 2: Update resolve_single_trigger**

In `api/app/modules/quality_gate/trigger.py:84`, change:
```python
asset_labels=getattr(asset, "labels", {}),
```
to:
```python
asset_tags=getattr(asset, "tags", {}),
asset_variables=getattr(asset, "variables", {}),
```

- [ ] **Step 3: Update TriggerService asset_snapshot construction**

In `api/app/modules/quality_gate/trigger_service.py:69`, change:
```python
asset_snapshot={"name": ctx.asset_name, "tags": ctx.asset_labels},
```
to:
```python
asset_snapshot={"name": ctx.asset_name, "tags": ctx.asset_tags, "variables": ctx.asset_variables},
```

Apply the same change at line 112 (batch trigger path).

- [ ] **Step 4: Rename metadata → variables in TriggerService**

In `api/app/modules/quality_gate/trigger_service.py:70`, change:
```python
metadata=request.metadata,
```
to:
```python
variables=request.variables,
```

Apply the same change at line 113 (batch trigger path).

- [ ] **Step 5: Update EvaluationRepository.create_pending**

In `api/app/modules/quality_gate/repository.py`:

Rename `metadata` param → `variables` (line 33).

Update the merge logic (lines 62-67):
```python
# Merge asset tags as defaults into variables (caller values take precedence)
merged_variables = dict(variables)
asset_row = await self._session.get(Asset, asset_id)
if asset_row is not None and asset_row.tags:
    for key, value in asset_row.tags.items():
        merged_variables.setdefault(str(key), str(value))
```

Update the Evaluation constructor (line 76):
```python
variables=merged_variables,
```
(was `evaluation_metadata=merged_metadata`)

- [ ] **Step 6: Run lint**

Run: `uv run ruff check api/app/modules/quality_gate/trigger.py api/app/modules/quality_gate/trigger_service.py api/app/modules/quality_gate/repository.py`
Expected: Clean.

- [ ] **Step 7: Commit**

```bash
git add api/app/modules/quality_gate/trigger.py api/app/modules/quality_gate/trigger_service.py api/app/modules/quality_gate/repository.py
git commit -m "refactor: rename labels → tags/variables in trigger pipeline and evaluation repository"
```

---

## Task 9: Quality Gate Router — Trigger/Batch Schema Renames

**Files:**
- Modify: `api/app/modules/quality_gate/router.py` (or wherever trigger endpoints are)
- Modify: `api/tests/test_qg_router.py`
- Modify: `api/tests/test_slo_test_endpoint.py`

- [ ] **Step 1: Find and update trigger endpoint handler**

Search for where `TriggerRequest` and `BatchTriggerRequest` are consumed. The handler reads `body.metadata` — rename to `body.variables` (the schema was already renamed in Task 2, this is the handler code that references it).

Also verify that any code passing `metadata=` to `create_pending()` now passes `variables=` (done in Task 8).

- [ ] **Step 2: Update test files**

In `api/tests/test_qg_router.py`:
- All `"metadata"` keys in request bodies → `"variables"`
- All `"evaluation_metadata"` keys in response assertions → `"variables"`

In `api/tests/test_slo_test_endpoint.py`:
- All `"metadata"` keys in request bodies → `"variables"`

- [ ] **Step 3: Run tests**

Run: `uv run pytest api/tests/test_qg_router.py api/tests/test_slo_test_endpoint.py -v`
Expected: All pass after renames.

- [ ] **Step 4: Commit**

```bash
git add api/app/modules/quality_gate/ api/tests/test_qg_router.py api/tests/test_slo_test_endpoint.py
git commit -m "refactor: rename metadata → variables in trigger/batch request schemas"
```

---

## Task 10: Client Library Updates

**Files:**
- Modify: `clients/python/tropek_client/models.py`
- Modify: `clients/python/tropek_client/client.py`
- Modify: `clients/python/tropek_client/manifest.py`
- Modify: `clients/python/tests/test_models.py`
- Modify: `clients/python/tests/test_manifest.py`
- Modify: `clients/python/tests/test_client.py`

- [ ] **Step 1: Update client models**

In `clients/python/tropek_client/models.py`:

- `Asset` line 36: `labels` → `tags`. Add `variables: dict[str, str] = {}`.
- `DataSource` line 86: `labels` → `tags`. (No `token` field — write-only, never returned.)
- `SLIDefinition` line 101: `meta` → `tags`.
- `SLODefinition` line 134: `meta` → `tags`. Add `variables: dict[str, Any] = {}`.
- `Annotation` line 217: `meta` → `tags`.
- `EvaluationSummary` line 251: `evaluation_metadata` → `variables`.

- [ ] **Step 2: Update client.py**

In `clients/python/tropek_client/client.py`:

`_Assets`:
- `list()` params: `label_key` → `tag_key`, `label_val` → `tag_val`
- `create()` param: `labels` → `tags`. Add `variables` param.
- `label_keys()` → `tag_keys()` — update URL to `/assets/tag-keys`
- `label_values()` → `tag_values()` — update URL to `/assets/tag-values`

`_DataSources`:
- `create()` and `update()`: `labels` → `tags` in kwargs passthrough (already uses **kwargs, so field names change automatically if caller uses new names).
- Add `delete()` method:
  ```python
  def delete(self, name: str) -> None:
      resp = self._http.delete(f"/datasources/{name}")
      _raise_for_status(resp)
  ```
- Add `tag_keys()` and `tag_values()` methods.

`_SLIDefinitions`:
- Add `tag_keys()` and `tag_values()` methods.

`_SLODefinitions`:
- Add `tag_keys()` and `tag_values()` methods.

`_Evaluations`:
- `trigger()` line 521: `"metadata"` → `"variables"` in JSON body.
- `trigger()` param: `metadata` → `variables`.
- `trigger_batch()` line 540: `"metadata"` → `"variables"` in JSON body.
- `trigger_batch()` param: `metadata` → `variables`.

- [ ] **Step 3: Update manifest.py**

In `clients/python/tropek_client/manifest.py`:

`_has_diff()`:
- Asset case (line 294): `doc.metadata.get("labels", {})` → `doc.metadata.get("tags", {})`. Also add `variables` comparison: `or doc.metadata.get("variables", {}) != getattr(existing, "variables", {})`
- DataSource case (line 302): `doc.metadata.get("labels", {})` → `doc.metadata.get("tags", {})`

`_create()`:
- Asset case (line 362): `labels=doc.metadata.get("labels")` → `tags=doc.metadata.get("tags"), variables=doc.metadata.get("variables")`
- DataSource case (line 372): `labels=doc.metadata.get("labels")` → `tags=doc.metadata.get("tags")`

`_update()`:
- Asset case (line 425): `labels=doc.metadata.get("labels")` → `tags=doc.metadata.get("tags"), variables=doc.metadata.get("variables")`
- DataSource case (line 436): `labels=doc.metadata.get("labels")` → `tags=doc.metadata.get("tags")`

- [ ] **Step 4: Update client tests**

In `clients/python/tests/test_models.py`, `test_manifest.py`, `test_client.py`:
- All `"labels"` → `"tags"` in test data fixtures
- All `"meta"` → `"tags"` in test data fixtures
- All `"evaluation_metadata"` → `"variables"` in response fixtures
- All `"metadata"` → `"variables"` in request fixtures
- All `label_key` → `tag_key`, `label_val` → `tag_val` in method calls
- Add `variables` field where applicable

- [ ] **Step 5: Run client tests**

Run: `uv run pytest clients/python/tests/ -v`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add clients/python/
git commit -m "refactor: rename labels/meta/metadata → tags/variables in client library"
```

---

## Task 11: Bootstrap Manifest Updates

**Files:**
- Modify: `bootstrap_mock/manifests/datasources.yaml`
- Modify: `bootstrap_mock/manifests/assets.yaml`

- [ ] **Step 1: Update datasources.yaml**

Rename `labels:` → `tags:` for both datasource entries:

```yaml
api_version: tropek/v1
kind: DataSource
metadata:
  name: prometheus-local
  display_name: Local Prometheus (dev)
  tags:
    env: dev
spec:
  adapter_type: prometheus
  adapter_url: http://127.0.0.1:9082
---
api_version: tropek/v1
kind: DataSource
metadata:
  name: mock-dc-b
  display_name: "Mock DC-B"
  tags:
    env: dev
spec:
  adapter_type: mock
  adapter_url: http://127.0.0.1:9082
```

- [ ] **Step 2: Update assets.yaml — split labels into tags + variables**

For each asset, apply this mapping:
- **tags:** team, env, region, tier
- **variables:** job, namespace, instance, runtime, os, dc

Example for first asset:
```yaml
api_version: tropek/v1
kind: Asset
metadata:
  name: checkout-api
  display_name: Checkout API
  tags:
    team: payments
    env: production
    region: eu-west-1
    tier: critical
  variables:
    job: checkout-api
    namespace: ecommerce
spec:
  type_name: service
```

Apply the same split pattern to all 10 assets. Assets without variable-type labels (e.g. `payment-gateway` which only has team/env/region/tier) get `tags:` only and no `variables:` section.

Complete mapping per asset:

| Asset | tags | variables |
|-------|------|-----------|
| checkout-api | team, env, region, tier | job, namespace |
| product-catalog | team, env, region, tier | job, namespace |
| user-service | team, env, region, tier | job, namespace |
| orders-db | team, env, region, tier | runtime, instance |
| catalog-db | team, env, region, tier | runtime, instance |
| session-cache | team, env, region, tier | runtime |
| payment-gateway | team, env, region, tier | (none) |
| metrics-collector | team, env, region, tier | os |
| log-aggregator | team, env, region, tier | os |
| bastion-host | team, env, region, tier | os, dc |
| build-runner | team, env, region, tier | os |

- [ ] **Step 3: Verify bootstrap still loads**

Run: `uv run python -c "from tropek_client.manifest import load_manifests, validate_manifests; errs = validate_manifests('bootstrap_mock/manifests'); print(f'{len(errs)} errors'); [print(e) for e in errs]"`
Expected: 0 errors (or only non-breaking warnings).

- [ ] **Step 4: Commit**

```bash
git add bootstrap_mock/manifests/datasources.yaml bootstrap_mock/manifests/assets.yaml
git commit -m "refactor: split asset labels into tags + variables in bootstrap manifests"
```

---

## Task 12: Update Remaining Test Files

**Files:**
- Modify: `api/tests/db/test_datasource_repository.py` (renames in existing tests — new tests added in Task 4)
- Modify: `api/tests/db/test_sli_repository.py` (renames in existing tests — new tests added in Task 5)
- Modify: `api/tests/db/test_slo_repository.py` (renames in existing tests — new tests added in Task 6)
- Modify: `api/tests/test_slo_validate.py` (if uses `meta`)

- [ ] **Step 1: Search for remaining `labels`/`meta`/`metadata`/`evaluation_metadata` in test files**

Run grep across all test files:
```
rg "(labels|\"meta\"|metadata|evaluation_metadata)" api/tests/ clients/python/tests/
```

Fix any remaining references not yet updated.

- [ ] **Step 2: Run full test suite (unit tests)**

Run: `uv run pytest api/tests/ -m "not integration" -q`
Expected: All pass.

- [ ] **Step 3: Run lint + type check**

Run: `uv run ruff check api/ clients/ adapters/`
Run: `uv run mypy api/app`
Expected: Clean.

- [ ] **Step 4: Commit**

```bash
git add api/tests/ clients/python/tests/
git commit -m "refactor: update all test files for tags/variables renames"
```

---

## Task 13: Regenerate Migration + Integration Test

**Files:**
- Run: `scripts/db-regen-migrations.sh`

- [ ] **Step 1: Run migration regeneration**

Run: `./scripts/db-regen-migrations.sh`
Expected: Script succeeds, creates fresh `001_initial_schema.py` reflecting all model changes.

- [ ] **Step 2: Verify migration file**

Read the generated migration and verify it contains:
- `tags` column (not `labels`) on assets, data_sources tables
- `tags` column (not `meta`) on sli_definitions, slo_definitions, evaluation_annotations tables
- `variables` column (not `evaluation_metadata`) on evaluations table
- `token` column on data_sources table
- `variables` column on assets, slo_definitions tables

- [ ] **Step 3: Start test infrastructure**

Run: `./start_test_infra.sh`

- [ ] **Step 4: Apply migrations to test DB**

Run: `ENV_FILE=.env.test uv run --directory api alembic upgrade head`
Expected: Clean migration apply.

- [ ] **Step 5: Run integration tests**

Run: `uv run pytest api/tests/ -m integration -v`
Expected: All pass.

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest api/tests/ -q`
Expected: All pass.

- [ ] **Step 7: Stop test infrastructure**

Run: `./stop_test_infra.sh`

- [ ] **Step 8: Commit migration**

```bash
git add api/alembic/versions/
git commit -m "chore: regenerate migration with tags/variables schema changes"
```

---

## Task 14: Final Verification

- [ ] **Step 1: Run full lint + type check**

Run: `uv run ruff check api/ adapters/ clients/`
Run: `uv run ruff format --check api/ adapters/ clients/`
Run: `uv run mypy api/app adapters/prometheus/app`
Expected: All clean.

- [ ] **Step 2: Run all unit tests**

Run: `uv run pytest api/tests/ -m "not integration" -q`
Expected: All pass.

- [ ] **Step 3: Run client tests**

Run: `uv run pytest clients/python/tests/ -v`
Expected: All pass.

- [ ] **Step 4: Verify dev startup (optional — if dev DB available)**

Run: `docker compose up timescaledb redis -d`
Run: `uv run --directory api alembic upgrade head`
Run: `uv run python bootstrap_mock/bootstrap.py`
Expected: Bootstrap applies cleanly with new field names.
