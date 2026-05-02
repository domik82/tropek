# API Schema Consistency & Client DX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 CRUD schema inconsistencies in the API layer, mirror them in the Python client, and add client DX improvements (simplified config update, SLI/SLO `new_version` helpers).

**Architecture:** Each API schema fix adds missing optional fields to the relevant Update/Create Pydantic schema, threads them through the repository, and updates the router if needed. Client models mirror the API. DX helpers are client-only convenience methods. Integration tests validate API fixes; unit tests validate client helpers.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Pydantic v2, httpx, respx (test mocking), pytest

---

## File Structure

**API files (modify):**
- `api/tropek/modules/datasource/schemas.py` — add `name`, `adapter_type` to `DataSourceUpdate`
- `api/tropek/modules/datasource/repository.py` — handle `name`, `adapter_type` in update method
- `api/tropek/modules/datasource/router.py` — handle rename conflict (commit before return)
- `api/tropek/modules/assets/schemas.py` — add `heatmap_config` to `AssetCreate`, add `is_default` to `AssetTypeUpdate`
- `api/tropek/modules/assets/params.py` — add `heatmap_config` to `AssetCreateParams`
- `api/tropek/modules/assets/repository.py` — pass `heatmap_config` in create, handle `is_default` in asset type update
- `api/tropek/modules/assets/router.py` — pass `heatmap_config` in create, handle `is_default` in asset type update
- `api/tropek/modules/slo_groups/schemas.py` — add `author` to `SLOGroupUpdate`
- `api/tropek/modules/slo_groups/repository.py` — handle `author` in update method
- `api/tropek/modules/slo_groups/router.py` — pass `author` through in update
- `api/openapi.json` — regenerated

**Client files (modify):**
- `clients/python/tropek_client/models/datasources.py` — add `name`, `adapter_type` to `DataSourceUpdate`
- `clients/python/tropek_client/models/assets.py` — add `heatmap_config` to `AssetCreate`
- `clients/python/tropek_client/models/asset_types.py` — add `is_default` to `AssetTypeUpdate`
- `clients/python/tropek_client/models/slo_groups.py` — add `author` to `SLOGroupUpdate`
- `clients/python/tropek_client/client.py` — simplify `_Configuration.update`, add `_SLIs.new_version`, add `_SLOs.new_version`
- `clients/python/README.md` — add asset name uniqueness note, update method signatures

**Test files (modify/create):**
- `api/tests/db/test_schema_consistency.py` — integration tests for API fixes
- `clients/python/tests/test_client.py` — unit tests for DX improvements

---

### Task 1: DataSource — add `name` and `adapter_type` to Update

**Files:**
- Modify: `api/tropek/modules/datasource/schemas.py:25-31`
- Modify: `api/tropek/modules/datasource/repository.py:88-120`
- Modify: `api/tropek/modules/datasource/router.py:93-104`

- [ ] **Step 1: Add fields to DataSourceUpdate schema**

In `api/tropek/modules/datasource/schemas.py`, add `name` and `adapter_type` to `DataSourceUpdate`:

```python
class DataSourceUpdate(StrictInput):
    """Request body for updating a datasource."""

    name: SafeStr | None = None
    display_name: SafeStr | None = None
    adapter_type: SafeStr | None = None
    adapter_url: SafeStr | None = None
    tags: Tags | None = None
    token: SafeStr | None = None
```

- [ ] **Step 2: Update the repository update method**

In `api/tropek/modules/datasource/repository.py`, update the `update` method to handle `name` and `adapter_type`. For `name`, check uniqueness before applying (same pattern as `AssetTypeRepository.rename`):

```python
async def update(
    self,
    name: str,
    *,
    new_name: str | None = None,
    display_name: str | None = None,
    adapter_type: str | None = None,
    adapter_url: str | None = None,
    tags: dict[str, Any] | None = None,
    token: str | None = None,
) -> DataSource | None:
    """Update mutable fields on an existing DataSource. Returns None if not found."""
    if new_name is not None and new_name != name:
        conflict = await self.get_by_name(new_name)
        if conflict is not None:
            raise ConflictError('datasource', new_name, 'already exists')

    values: dict[str, Any] = {}
    if new_name is not None:
        values['name'] = new_name
    if display_name is not None:
        values['display_name'] = display_name
    if adapter_type is not None:
        values['adapter_type'] = adapter_type
    if adapter_url is not None:
        values['adapter_url'] = adapter_url
    if tags is not None:
        values['tags'] = tags
    if token is not None:
        values['token'] = token
    if values:
        await self._session.execute(update(DataSource).where(DataSource.name == name).values(**values))
    return await self.get_by_name(new_name or name)
```

Add the `ConflictError` import at the top of the file:

```python
from tropek.modules.common.exceptions import ConflictError
```

- [ ] **Step 3: Update the router to map `name` → `new_name`**

In `api/tropek/modules/datasource/router.py`, the router currently does `repo.update(name, **body.model_dump(exclude_none=True))`. The schema field is `name` but the repo parameter is `new_name`, so we need to remap:

```python
@router.patch('/datasources/{name}', response_model=DataSourceRead)
async def update_datasource(
    name: str,
    body: DataSourceUpdate,
    session: AsyncSession = Depends(get_session),
) -> DataSourceRead:
    """Update mutable datasource fields."""
    repo = DataSourceRepository(session)
    fields = body.model_dump(exclude_none=True)
    new_name = fields.pop('name', None)
    ds = await repo.update(name, new_name=new_name, **fields)
    if ds is None:
        raise NotFoundError('datasource', name)
    return _ds_read(ds)
```

- [ ] **Step 4: Run existing tests to check for regressions**

Run: `./scripts/api-test.sh --tail 10`
Expected: All existing tests pass (no regressions from optional field additions).

- [ ] **Step 5: Commit**

```bash
git add api/tropek/modules/datasource/schemas.py api/tropek/modules/datasource/repository.py api/tropek/modules/datasource/router.py
git commit -m "fix(api): add name and adapter_type to DataSourceUpdate schema"
```

---

### Task 2: Asset — add `heatmap_config` to Create

**Files:**
- Modify: `api/tropek/modules/assets/schemas.py:43-51`
- Modify: `api/tropek/modules/assets/params.py:13-22`
- Modify: `api/tropek/modules/assets/repository.py:126-146`
- Modify: `api/tropek/modules/assets/router.py:130-148`

- [ ] **Step 1: Add `heatmap_config` to `AssetCreate` schema**

In `api/tropek/modules/assets/schemas.py`, add `heatmap_config` to `AssetCreate`. The `SafeJsonAny` type is already used in `AssetUpdate` in the same file:

```python
class AssetCreate(StrictInput):
    """Request body for creating an asset."""

    name: SafeStr
    display_name: SafeStr | None = None
    type_name: SafeStr
    tags: Tags = {}
    variables: dict[IdentifierKey, SafeStr] = {}
    color: SafeStr | None = None
    heatmap_config: SafeJsonAny | None = None
```

- [ ] **Step 2: Add `heatmap_config` to `AssetCreateParams`**

In `api/tropek/modules/assets/params.py`:

```python
class AssetCreateParams(StrictInput):
    """Parameters for AssetRepository.create()."""

    name: str
    type_name: str = 'vm'
    display_name: str | None = None
    color: str | None = None
    tags: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    heatmap_config: dict[str, Any] | None = None
```

- [ ] **Step 3: Pass `heatmap_config` through repository create**

In `api/tropek/modules/assets/repository.py`, update the `create` method to pass `heatmap_config`:

```python
async def create(self, params: AssetCreateParams) -> Asset:
    """Create a new asset."""
    asset = Asset(
        id=uuid.uuid4(),
        name=params.name,
        display_name=params.display_name,
        color=params.color,
        type_name=params.type_name,
        tags=params.tags,
        variables=params.variables,
        heatmap_config=params.heatmap_config,
    )
    self._session.add(asset)
    await self._session.flush()
    return asset
```

- [ ] **Step 4: Pass `heatmap_config` through router create**

In `api/tropek/modules/assets/router.py`, update the `create_asset` handler to include `heatmap_config`:

```python
@router.post('/assets', response_model=AssetRead, status_code=201)
async def create_asset(
    body: AssetCreate,
    session: AsyncSession = Depends(get_session),
    cache: RedisCache | None = Depends(get_cache),
) -> AssetRead:
    """Create a new asset."""
    repo = AssetRepository(session, cache=cache)
    asset = await repo.create(
        AssetCreateParams(
            name=body.name,
            type_name=body.type_name,
            display_name=body.display_name,
            color=body.color,
            tags=body.tags or {},
            variables=body.variables or {},
            heatmap_config=body.heatmap_config,
        ),
    )
    return AssetRead.model_validate(asset)
```

- [ ] **Step 5: Run existing tests**

Run: `./scripts/api-test.sh --tail 10`
Expected: All existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add api/tropek/modules/assets/schemas.py api/tropek/modules/assets/params.py api/tropek/modules/assets/repository.py api/tropek/modules/assets/router.py
git commit -m "fix(api): add heatmap_config to AssetCreate schema"
```

---

### Task 3: AssetType — add `is_default` to Update

**Files:**
- Modify: `api/tropek/modules/assets/schemas.py:23-26`
- Modify: `api/tropek/modules/assets/router.py:97-110`

- [ ] **Step 1: Add `is_default` to `AssetTypeUpdate` schema**

In `api/tropek/modules/assets/schemas.py`:

```python
class AssetTypeUpdate(StrictInput):
    """Request body for updating an asset type."""

    name: SafeStr | None = None
    is_default: bool | None = None
```

- [ ] **Step 2: Update the router to handle `is_default`**

In `api/tropek/modules/assets/router.py`, the current `rename_asset_type` endpoint only handles renaming. Generalize it to handle both rename and `is_default`:

```python
@router.patch('/asset-types/{name}', response_model=AssetTypeRead)
async def update_asset_type(
    name: str,
    body: AssetTypeUpdate,
    session: AsyncSession = Depends(get_session),
) -> AssetTypeRead:
    """Update an asset type (rename and/or set as default)."""
    repo = AssetTypeRepository(session)
    result_at: AssetType | None = None

    if body.is_default is True:
        result_at = await repo.set_default(name)
        if result_at is None:
            raise NotFoundError('asset type', name)

    if body.name is not None:
        effective_name = result_at.name if result_at else name
        result_at = await repo.rename(effective_name, body.name)
        if result_at is None:
            raise NotFoundError('asset type', name)

    if result_at is None:
        existing = await repo.get_by_name(name)
        if existing is None:
            raise NotFoundError('asset type', name)
        result_at = existing

    return AssetTypeRead.model_validate(result_at)
```

Import `AssetType` from `tropek.db.models` at the top if not already imported. Check existing imports first.

- [ ] **Step 3: Run existing tests**

Run: `./scripts/api-test.sh --tail 10`
Expected: All existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add api/tropek/modules/assets/schemas.py api/tropek/modules/assets/router.py
git commit -m "fix(api): add is_default to AssetTypeUpdate schema"
```

---

### Task 4: SLOGroup — add `author` to Update

**Files:**
- Modify: `api/tropek/modules/slo_groups/schemas.py:26-33`
- Modify: `api/tropek/modules/slo_groups/repository.py:74-98`
- Modify: `api/tropek/modules/slo_groups/router.py:302-309`

- [ ] **Step 1: Add `author` to `SLOGroupUpdate` schema**

In `api/tropek/modules/slo_groups/schemas.py`:

```python
class SLOGroupUpdate(StrictInput):
    """Request body for updating an SLO group (triggers regeneration)."""

    template_slo_name: SafeStr | None = None
    template_slo_version: int | None = None
    gen_variables: dict[IdentifierKey, list[SafeStr]] | None = None
    display_name: SafeStr | None = None
    tags: Tags | None = None
    author: SafeStr | None = None
```

- [ ] **Step 2: Update the repository update method**

In `api/tropek/modules/slo_groups/repository.py`, add `author` parameter to the `update` method:

```python
async def update(
    self,
    name: str,
    *,
    template_slo_definition_id: uuid.UUID | None = None,
    gen_variables: dict[str, list[str]] | None = None,
    display_name: Any = _UNSET,
    tags: dict[str, Any] | None = None,
    author: Any = _UNSET,
) -> SLOGroup | None:
    """Update mutable fields on an active group; bumps version. Returns None if not found."""
    group = await self.get_by_name(name)
    if group is None:
        return None
    if template_slo_definition_id is not None:
        group.template_slo_definition_id = template_slo_definition_id
    if gen_variables is not None:
        group.gen_variables = gen_variables
    if display_name is not _UNSET:
        group.display_name = display_name
    if tags is not None:
        group.tags = tags
    if author is not _UNSET:
        group.author = author
    group.version += 1
    group.updated_at = datetime.now(UTC)
    await self._session.flush()
    return group
```

- [ ] **Step 3: Update the router to pass `author`**

In `api/tropek/modules/slo_groups/router.py`, update the `group_repo.update()` call around line 303 to include `author`:

```python
    # Update group row
    updated_group = await group_repo.update(
        name,
        template_slo_definition_id=template.id,
        gen_variables=eff_gen_vars,
        display_name=body.display_name if body.display_name is not None else group.display_name,
        tags=body.tags if body.tags is not None else None,
        author=body.author if body.author is not None else group.author,
    )
```

- [ ] **Step 4: Run existing tests**

Run: `./scripts/api-test.sh --tail 10`
Expected: All existing tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/tropek/modules/slo_groups/schemas.py api/tropek/modules/slo_groups/repository.py api/tropek/modules/slo_groups/router.py
git commit -m "fix(api): add author to SLOGroupUpdate schema"
```

---

### Task 5: Regenerate openapi.json

**Files:**
- Modify: `api/openapi.json` (regenerated)

- [ ] **Step 1: Regenerate the OpenAPI schema**

Run: `just export-schema`

This imports the FastAPI app and writes the current schema to `api/openapi.json`.

- [ ] **Step 2: Verify the new fields appear**

Run: `grep -A5 '"DataSourceUpdate"' api/openapi.json | head -20`

Expected: `name` and `adapter_type` fields should appear in the `DataSourceUpdate` schema properties.

Run: `grep -c '"heatmap_config"' api/openapi.json`

Expected: Should appear in both `AssetCreate` and `AssetUpdate` schemas (count should increase by 1 from before).

- [ ] **Step 3: Commit**

```bash
git add api/openapi.json
git commit -m "chore: regenerate openapi.json after schema fixes"
```

---

### Task 6: Client model updates

**Files:**
- Modify: `clients/python/tropek_client/models/datasources.py`
- Modify: `clients/python/tropek_client/models/assets.py`
- Modify: `clients/python/tropek_client/models/asset_types.py`
- Modify: `clients/python/tropek_client/models/slo_groups.py`

- [ ] **Step 1: Add fields to client `DataSourceUpdate`**

In `clients/python/tropek_client/models/datasources.py`, add `name` and `adapter_type`:

```python
class DataSourceUpdate(BaseModel):
    """Data source update request."""

    name: str | None = None
    display_name: str | None = None
    adapter_type: str | None = None
    adapter_url: str | None = None
    tags: dict[str, str] | None = None
    token: str | None = None
```

- [ ] **Step 2: Add `heatmap_config` to client `AssetCreate`**

In `clients/python/tropek_client/models/assets.py`, add `heatmap_config`. Add `Any` to the imports from `typing`:

```python
class AssetCreate(BaseModel):
    """Asset creation request."""

    name: str
    display_name: str | None = None
    type_name: str
    tags: dict[str, Any] | None = None
    variables: dict[str, Any] | None = None
    color: str | None = None
    heatmap_config: dict[str, Any] | None = None
```

- [ ] **Step 3: Add `is_default` to client `AssetTypeUpdate`**

In `clients/python/tropek_client/models/asset_types.py`:

```python
class AssetTypeUpdate(BaseModel):
    """Asset type update request."""

    name: str | None = None
    is_default: bool | None = None
```

- [ ] **Step 4: Add `author` to client `SLOGroupUpdate`**

In `clients/python/tropek_client/models/slo_groups.py`:

```python
class SLOGroupUpdate(BaseModel):
    """Input model for updating an SLO group."""

    template_slo_name: str | None = None
    template_slo_version: int | None = None
    gen_variables: dict[str, Any] | None = None
    display_name: str | None = None
    tags: dict[str, str] | None = None
    author: str | None = None
```

- [ ] **Step 5: Run drift tests to verify alignment**

Run: `uv run --directory /home/domik/projects/tropek pytest clients/python/tests/test_drift.py -v 2>&1 | tail -20`

Expected: All drift tests pass (client models now match updated openapi.json).

- [ ] **Step 6: Commit**

```bash
git add clients/python/tropek_client/models/datasources.py clients/python/tropek_client/models/assets.py clients/python/tropek_client/models/asset_types.py clients/python/tropek_client/models/slo_groups.py
git commit -m "fix(client): mirror API schema fixes in client models"
```

---

### Task 7: Simplify Configuration.update client DX

**Files:**
- Modify: `clients/python/tropek_client/client.py` (the `_Configuration` class)
- Modify: `clients/python/tests/test_client.py` (the `TestConfiguration` class)

- [ ] **Step 1: Write the failing test**

In `clients/python/tests/test_client.py`, add a test to the `TestConfiguration` class:

```python
    @respx.mock
    def test_update(self, client):
        config_json = {
            'name': 'change_point.window_size',
            'value': '50',
            'value_type': 'int',
            'description': 'sliding window length',
        }
        route = respx.put(f'{BASE_URL}/configuration/change_point.window_size').mock(
            return_value=httpx.Response(200, json=config_json)
        )
        result = client.configuration.update('change_point.window_size', '50')
        assert isinstance(result, ConfigurationRead)
        assert result.value == '50'
        assert b'"value":"50"' in route.calls[0].request.content
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --directory /home/domik/projects/tropek pytest clients/python/tests/test_client.py::TestConfiguration::test_update -v`

Expected: FAIL — `update()` currently takes `(name, body)` not `(name, value)`.

- [ ] **Step 3: Update the `_Configuration.update` method**

In `clients/python/tropek_client/client.py`, find the `_Configuration` class and change the `update` method:

```python
    def update(self, name: str, value: str) -> ConfigurationRead:
        response = self._http.put(f'/configuration/{name}', json={'value': value})
        return ConfigurationRead.model_validate(response.json())
```

Remove `ConfigurationUpdate` from the imports at the top of `client.py` (it's no longer used in this file). Check if it's used elsewhere before removing.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --directory /home/domik/projects/tropek pytest clients/python/tests/test_client.py::TestConfiguration -v`

Expected: All Configuration tests pass.

- [ ] **Step 5: Run all client tests**

Run: `uv run --directory /home/domik/projects/tropek pytest clients/python/tests/ -v 2>&1 | tail -10`

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add clients/python/tropek_client/client.py clients/python/tests/test_client.py
git commit -m "feat(client): simplify Configuration.update to take name and value args"
```

---

### Task 8: SLI `new_version` helper

**Files:**
- Modify: `clients/python/tropek_client/client.py` (the `_SLIs` class)
- Modify: `clients/python/tests/test_client.py` (the `TestSLIs` class)

- [ ] **Step 1: Write the failing test**

In `clients/python/tests/test_client.py`, add a test to the `TestSLIs` class (find it — it should be around line 275). Add the `SLIDefinitionCreate` import at the top if not already present:

```python
    @respx.mock
    def test_new_version(self, client):
        current_sli = {
            **_SLI_JSON,
            'display_name': 'Response Time P95',
            'notes': 'original notes',
            'author': 'alice',
        }
        created_sli = {**current_sli, 'version': 2, 'id': _UUID2}

        respx.get(f'{BASE_URL}/sli-definitions/response-time').mock(
            return_value=httpx.Response(200, json=current_sli)
        )
        route = respx.post(f'{BASE_URL}/sli-definitions').mock(
            return_value=httpx.Response(201, json=created_sli)
        )

        result = client.slis.new_version(
            'response-time',
            indicators={'p99': 'new_query(rate(http_duration[5m]))'},
        )
        assert result.version == 2
        body = route.calls[0].request.content
        assert b'"p99"' in body
        assert b'"new_query' in body
        assert b'"response-time"' in body
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --directory /home/domik/projects/tropek pytest clients/python/tests/test_client.py::TestSLIs::test_new_version -v`

Expected: FAIL — `_SLIs` has no `new_version` method.

- [ ] **Step 3: Implement `new_version` on `_SLIs`**

In `clients/python/tropek_client/client.py`, add the `new_version` method to the `_SLIs` class (after the existing methods, before the class ends). Add `Any` to the existing `typing` import at the top if not already present:

```python
    def new_version(self, name: str, **overrides: Any) -> SLIDefinitionRead:
        """Create a new version of an SLI based on the current active version.

        Fetches the current version, copies all create-compatible fields,
        applies overrides, and POSTs as a new version.
        """
        current = self.get(name)
        base = SLIDefinitionCreate(
            name=current.name,
            adapter_type=current.adapter_type,
            display_name=current.display_name,
            mode=current.mode,
            indicators=current.indicators or None,
            query_template=current.query_template,
            interval=current.interval,
            methods=current.methods,
            notes=current.notes,
            author=current.author,
            tags=dict(current.tags) if current.tags else None,
        )
        body = base.model_copy(update=overrides)
        return self.create(body)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --directory /home/domik/projects/tropek pytest clients/python/tests/test_client.py::TestSLIs -v`

Expected: All SLI tests pass.

- [ ] **Step 5: Commit**

```bash
git add clients/python/tropek_client/client.py clients/python/tests/test_client.py
git commit -m "feat(client): add slis.new_version() helper for versioned updates"
```

---

### Task 9: SLO `new_version` helper

**Files:**
- Modify: `clients/python/tropek_client/client.py` (the `_SLOs` class)
- Modify: `clients/python/tests/test_client.py` (the `TestSLOs` class)

- [ ] **Step 1: Write the failing test**

In `clients/python/tests/test_client.py`, add a test to the `TestSLOs` class. The SLO JSON fixture `_SLO_JSON` has empty objectives, so create a richer one for this test:

```python
    @respx.mock
    def test_new_version(self, client):
        current_slo = {
            **_SLO_JSON,
            'display_name': 'My SLO',
            'notes': 'original',
            'author': 'alice',
            'objectives': [
                {
                    'sli': 'response_time_p95',
                    'display_name': 'P95 Latency',
                    'pass_threshold': ['<600'],
                    'warning_threshold': ['<800'],
                    'weight': 1,
                    'key_sli': False,
                    'sort_order': 0,
                },
            ],
        }
        created_slo = {**current_slo, 'version': 2, 'id': _UUID2}

        respx.get(f'{BASE_URL}/slo-definitions/my-slo').mock(
            return_value=httpx.Response(200, json=current_slo)
        )
        route = respx.post(f'{BASE_URL}/slo-definitions').mock(
            return_value=httpx.Response(201, json=created_slo)
        )

        result = client.slos.new_version(
            'my-slo',
            total_score_pass_threshold=95.0,
        )
        assert result.version == 2
        body = route.calls[0].request.content
        assert b'"total_score_pass_threshold":95.0' in body
        assert b'"my-slo"' in body
        assert b'sort_order' not in body
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --directory /home/domik/projects/tropek pytest clients/python/tests/test_client.py::TestSLOs::test_new_version -v`

Expected: FAIL — `_SLOs` has no `new_version` method.

- [ ] **Step 3: Implement `new_version` on `_SLOs`**

In `clients/python/tropek_client/client.py`, add the `new_version` method to the `_SLOs` class. The key complexity is converting `SLOObjectiveRead` (which has `sort_order` and `ChangePointConfigRead`) to `SLOObjectiveIn` format, and `ComparisonConfigRead` to `ComparisonConfig` format. Use `model_dump(exclude=...)` for clean conversion:

```python
    def new_version(self, name: str, **overrides: Any) -> SLODefinitionRead:
        """Create a new version of an SLO based on the current active version.

        Fetches the current version, copies all create-compatible fields,
        applies overrides, and POSTs as a new version. Strips read-only
        fields (sort_order, slo_objective_id) from nested objects.
        """
        current = self.get(name)
        objectives_for_create = [
            SLOObjectiveIn.model_validate(
                objective.model_dump(exclude={'sort_order', 'change_point'})
                | (
                    {'change_point': objective.change_point.model_dump(exclude={'slo_objective_id'})}
                    if objective.change_point
                    else {}
                )
            )
            for objective in current.objectives
        ]
        comparison_for_create = (
            ComparisonConfig.model_validate(current.comparison.model_dump())
            if current.comparison
            else None
        )
        method_criteria_for_create = (
            {
                key: MethodCriteriaOverride.model_validate(override.model_dump())
                for key, override in current.method_criteria.items()
            }
            if current.method_criteria
            else None
        )
        base = SLODefinitionCreate(
            name=current.name,
            display_name=current.display_name,
            objectives=objectives_for_create,
            total_score_pass_threshold=current.total_score_pass_threshold,
            total_score_warning_threshold=current.total_score_warning_threshold,
            comparison=comparison_for_create,
            notes=current.notes,
            author=current.author,
            tags=dict(current.tags) if current.tags else None,
            variables=dict(current.variables) if current.variables else None,
            kind=current.kind,
            sli_name=current.sli_name,
            sli_version=current.sli_version,
            method_criteria=method_criteria_for_create,
        )
        body = base.model_copy(update=overrides)
        return self.create(body)
```

Add the necessary imports at the top of `client.py`. Check what's already imported — you'll need `ComparisonConfig`, `MethodCriteriaOverride`, and `SLOObjectiveIn` from the models:

```python
from tropek_client.models import (
    ...
    ComparisonConfig,
    MethodCriteriaOverride,
    SLOObjectiveIn,
    ...
)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --directory /home/domik/projects/tropek pytest clients/python/tests/test_client.py::TestSLOs -v`

Expected: All SLO tests pass.

- [ ] **Step 5: Run all client tests**

Run: `uv run --directory /home/domik/projects/tropek pytest clients/python/tests/ -v 2>&1 | tail -10`

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add clients/python/tropek_client/client.py clients/python/tests/test_client.py
git commit -m "feat(client): add slos.new_version() helper for versioned updates"
```

---

### Task 10: API integration tests

**Files:**
- Create: `api/tests/db/test_schema_consistency.py`

- [ ] **Step 1: Write integration tests for all 4 API fixes**

Create `api/tests/db/test_schema_consistency.py`. Follow the pattern from `test_note_category_router.py` — use `AsyncClient` with `ASGITransport`, override `get_session`, mark with `pytestmark = pytest.mark.integration`:

```python
"""Integration tests for API schema consistency fixes."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.session import get_session
from tropek.main import app

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def _override_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def test_datasource_update_name(client: AsyncClient) -> None:
    """DataSource can be renamed via PATCH."""
    create_response = await client.post(
        '/datasources',
        json={'name': 'ds-original', 'adapter_type': 'prometheus', 'adapter_url': 'http://prom:9090'},
    )
    assert create_response.status_code == 201

    rename_response = await client.patch('/datasources/ds-original', json={'name': 'ds-renamed'})
    assert rename_response.status_code == 200
    assert rename_response.json()['name'] == 'ds-renamed'

    get_response = await client.get('/datasources/ds-renamed')
    assert get_response.status_code == 200


async def test_datasource_update_adapter_type(client: AsyncClient) -> None:
    """DataSource adapter_type can be changed via PATCH."""
    await client.post(
        '/datasources',
        json={'name': 'ds-adapter-test', 'adapter_type': 'prometheus', 'adapter_url': 'http://prom:9090'},
    )
    response = await client.patch('/datasources/ds-adapter-test', json={'adapter_type': 'datadog'})
    assert response.status_code == 200
    assert response.json()['adapter_type'] == 'datadog'


async def test_datasource_rename_conflict(client: AsyncClient) -> None:
    """Renaming a DataSource to an existing name returns 409."""
    await client.post(
        '/datasources',
        json={'name': 'ds-a', 'adapter_type': 'prometheus', 'adapter_url': 'http://a:9090'},
    )
    await client.post(
        '/datasources',
        json={'name': 'ds-b', 'adapter_type': 'prometheus', 'adapter_url': 'http://b:9090'},
    )
    response = await client.patch('/datasources/ds-b', json={'name': 'ds-a'})
    assert response.status_code == 409


async def test_asset_create_with_heatmap_config(client: AsyncClient) -> None:
    """Asset can be created with heatmap_config."""
    config = {'columns': 30, 'cell_size': 'medium'}
    response = await client.post(
        '/assets',
        json={'name': 'heatmap-asset', 'type_name': 'vm', 'heatmap_config': config},
    )
    assert response.status_code == 201
    assert response.json()['heatmap_config'] == config


async def test_asset_type_update_is_default(client: AsyncClient) -> None:
    """AssetType is_default can be set via PATCH."""
    await client.post('/asset-types', json={'name': 'custom-type'})
    response = await client.patch('/asset-types/custom-type', json={'is_default': True})
    assert response.status_code == 200
    assert response.json()['is_default'] is True
```

Note: The SLOGroup `author` update test requires a full SLO group setup (template SLO, SLI, etc.), which is complex. Skip it in integration tests — the schema and repository changes are straightforward field pass-through, covered by the unit-level drift tests and client tests.

- [ ] **Step 2: Run integration tests**

First ensure test infrastructure is running:

Run: `just test-env`

Then run the new tests:

Run: `./scripts/api-test.sh --tail 20 tests/db/test_schema_consistency.py -v -m integration`

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add api/tests/db/test_schema_consistency.py
git commit -m "test(api): add integration tests for schema consistency fixes"
```

---

### Task 11: Update README and re-run audit

**Files:**
- Modify: `clients/python/README.md`

- [ ] **Step 1: Add asset name uniqueness note to README**

In `clients/python/README.md`, add a "Known Limitations" section before the "Error Handling" section (before line 312):

```markdown
## Known Limitations

- **Asset names are globally unique.** There is no per-group scoping — two groups
  cannot each contain an asset named `load_test`. Assets are identified by name
  across the entire TROPEK instance.
```

- [ ] **Step 2: Update README method signatures**

The README still references the old v1 API signatures (e.g., `client.sli_definitions`, `client.slo_definitions`, `evaluate()` instead of `trigger()`). Update the SLI and SLO sections to include the new `new_version` method:

In the SLI Definitions table, add:

```markdown
| `new_version(name, **overrides)` | `SLIDefinition` | Create new version with overrides |
```

In the SLO Definitions table, add:

```markdown
| `new_version(name, **overrides)` | `SLODefinition` | Create new version with overrides |
```

- [ ] **Step 3: Re-run the audit script**

Run: `uv run python scripts/audit_api_schemas.py`

Expected: The 4 bug findings (DataSource SET-ONCE, Asset heatmap_config asymmetry, AssetType SPARSE-UPDATE, SLOGroup author SET-ONCE) should be resolved. Some intentional findings will remain (AssetGroup name set-once, Configuration sparse update, etc.).

- [ ] **Step 4: Commit**

```bash
git add clients/python/README.md
git commit -m "docs: add new_version helpers to README, document asset name uniqueness"
```

---

### Task 12: Final verification

- [ ] **Step 1: Run all client tests**

Run: `uv run --directory /home/domik/projects/tropek pytest clients/python/tests/ -v 2>&1 | tail -20`

Expected: All tests pass (including new tests from Tasks 7-9).

- [ ] **Step 2: Run all API unit tests**

Run: `./scripts/api-test.sh --tail 10`

Expected: All pass.

- [ ] **Step 3: Run API integration tests**

Run: `./scripts/api-test.sh --tail 20 -m integration -v`

Expected: All pass (including new tests from Task 10).

- [ ] **Step 4: Run drift tests**

Run: `uv run --directory /home/domik/projects/tropek pytest clients/python/tests/test_drift.py -v 2>&1 | tail -20`

Expected: All drift tests pass.

- [ ] **Step 5: Run lint and typecheck**

Run: `just check`

Expected: No new violations.
