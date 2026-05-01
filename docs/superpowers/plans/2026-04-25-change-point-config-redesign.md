# Change Point Config Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace heuristic-based directionality detection with explicit config, re-key change point config to SLO objective, and add a general-purpose `configuration` table for system defaults.

**Architecture:** Three layers of config resolution: per-objective `change_point_config` (FK to `slo_objectives`) → system defaults in `configuration` table → hardcoded fallback constants. The `configuration` table is a general-purpose key-value store. SLO YAML gains an optional `change_point:` block per objective, with copy-forward on new versions.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async ORM, PostgreSQL, Pydantic, Alembic

**Spec:** `docs/superpowers/specs/2026-04-25-change-point-config-redesign.md`

---

### Task 1: Add `Configuration` ORM model

**Files:**
- Modify: `api/tropek/db/models.py`

- [ ] **Step 1: Add the Configuration model to models.py**

Add after the `ChangePoint` class (end of change_points section):

```python
class Configuration(Base):
    """System-wide key-value settings — general purpose."""

    __tablename__ = 'configuration'

    # fmt: off
    name:        Mapped[str]      = mapped_column(Text, primary_key=True)
    value:       Mapped[str]      = mapped_column(Text, nullable=False)
    value_type:  Mapped[str]      = mapped_column(Text, nullable=False)
    description: Mapped[str]      = mapped_column(Text, nullable=False, server_default='')
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # fmt: on
```

- [ ] **Step 2: Commit**

```
feat(models): add Configuration key-value settings table
```

---

### Task 2: Re-key `ChangePointConfig` model and add relationship

**Files:**
- Modify: `api/tropek/db/models.py`

- [ ] **Step 1: Update ChangePointConfig model**

Replace the entire `ChangePointConfig` class with:

```python
class ChangePointConfig(Base):
    """Per-objective Otava detection override — SPARSE table.

    Rows exist ONLY to override the system defaults for a specific SLO objective.
    Absence of a row = use system defaults from the configuration table.
    """

    __tablename__ = 'change_point_config'

    # fmt: off
    id:                Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    slo_objective_id:  Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('slo_objectives.id', ondelete='CASCADE'), nullable=False, unique=True)
    enabled:           Mapped[bool]      = mapped_column(Boolean, nullable=False)
    higher_is_better:  Mapped[bool]      = mapped_column(Boolean, nullable=False)
    window_size:       Mapped[int]       = mapped_column(Integer, nullable=False)
    max_pvalue:        Mapped[float]     = mapped_column(Float, nullable=False)
    min_magnitude:     Mapped[float]     = mapped_column(Float, nullable=False)
    min_sample_size:   Mapped[int]       = mapped_column(Integer, nullable=False)
    created_at:        Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:        Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # fmt: on
```

- [ ] **Step 2: Add relationship on SLOObjective**

In the `SLOObjective` class, after the `tab_group` column, add:

```python
    change_point_config: Mapped[ChangePointConfig | None] = relationship(
        'ChangePointConfig',
        uselist=False,
        cascade='all, delete-orphan',
        lazy='joined',
    )
```

Note: `ChangePointConfig` is defined after `SLOObjective` in models.py, so use the string form for the relationship target. SQLAlchemy resolves forward references via strings.

- [ ] **Step 3: Revert `higher_is_better` from SLOObjective**

Remove the `higher_is_better` column that was added to `SLOObjective` earlier in this session. It belongs in `ChangePointConfig`, not on the objective directly.

- [ ] **Step 4: Commit**

```
refactor(models): re-key ChangePointConfig to slo_objective_id FK
```

---

### Task 3: Create `configuration` module — repository and schemas

**Files:**
- Create: `api/tropek/modules/configuration/__init__.py`
- Create: `api/tropek/modules/configuration/repository.py`
- Create: `api/tropek/modules/configuration/schemas.py`

- [ ] **Step 1: Create empty `__init__.py`**

```python
```

- [ ] **Step 2: Create schemas.py**

```python
"""Pydantic schemas for the configuration API."""

from __future__ import annotations

from pydantic import BaseModel

from tropek.modules.common.schemas import StrictInput


class ConfigurationRead(BaseModel):
    """Response schema for a configuration entry."""

    name: str
    value: str
    value_type: str
    description: str

    model_config = {'from_attributes': True}


class ConfigurationUpdate(StrictInput):
    """Request body for updating a configuration value."""

    value: str
```

- [ ] **Step 3: Create repository.py**

```python
"""Configuration repository — CRUD for the key-value settings table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import Configuration


VALID_TYPES = {'bool', 'int', 'float', 'str'}

TYPE_VALIDATORS: dict[str, type] = {
    'bool': lambda v: v.lower() in ('true', 'false'),
    'int': lambda v: v.lstrip('-').isdigit(),
    'float': lambda v: _is_float(v),
    'str': lambda v: True,
}


def _is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def parse_typed_value(value: str, value_type: str) -> bool | int | float | str:
    """Parse a string value into its typed Python equivalent."""
    match value_type:
        case 'bool':
            return value.lower() == 'true'
        case 'int':
            return int(value)
        case 'float':
            return float(value)
        case _:
            return value


class ConfigurationRepository:
    """Data access layer for system-wide configuration."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self, *, prefix: str | None = None) -> list[Configuration]:
        """Return all configuration entries, optionally filtered by key prefix."""
        query = select(Configuration).order_by(Configuration.name)
        if prefix:
            query = query.where(Configuration.name.startswith(prefix))
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_by_name(self, name: str) -> Configuration | None:
        """Return a single configuration entry by name."""
        result = await self._session.execute(
            select(Configuration).where(Configuration.name == name)
        )
        return result.scalar_one_or_none()

    async def update_value(self, name: str, value: str) -> Configuration | None:
        """Update the value of an existing configuration entry.

        Validates the value against the entry's value_type before updating.
        Returns None if the entry does not exist.
        """
        entry = await self.get_by_name(name)
        if entry is None:
            return None
        validator = TYPE_VALIDATORS.get(entry.value_type, lambda v: True)
        if not validator(value):
            msg = f"value '{value}' is not a valid {entry.value_type}"
            raise ValueError(msg)
        entry.value = value
        await self._session.flush()
        return entry

    async def get_change_point_defaults(self) -> dict[str, bool | int | float | str]:
        """Load all change_point.* settings as a typed dict."""
        rows = await self.get_all(prefix='change_point.')
        return {
            row.name.removeprefix('change_point.'): parse_typed_value(row.value, row.value_type)
            for row in rows
        }
```

- [ ] **Step 4: Commit**

```
feat(configuration): add repository and schemas for key-value settings
```

---

### Task 4: Create `configuration` router and register it

**Files:**
- Create: `api/tropek/modules/configuration/router.py`
- Modify: `api/tropek/main.py`

- [ ] **Step 1: Create router.py**

```python
"""Configuration API — system-wide key-value settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.session import get_session
from tropek.modules.configuration.repository import ConfigurationRepository
from tropek.modules.configuration.schemas import ConfigurationRead, ConfigurationUpdate

router = APIRouter(tags=['configuration'])


@router.get('/configuration', response_model=list[ConfigurationRead])
async def list_configuration(
    prefix: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[ConfigurationRead]:
    """List all configuration entries, optionally filtered by key prefix."""
    repo = ConfigurationRepository(session)
    rows = await repo.get_all(prefix=prefix)
    return [ConfigurationRead.model_validate(row) for row in rows]


@router.get('/configuration/{name:path}', response_model=ConfigurationRead)
async def get_configuration(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> ConfigurationRead:
    """Get a single configuration entry by name."""
    repo = ConfigurationRepository(session)
    entry = await repo.get_by_name(name)
    if entry is None:
        raise HTTPException(status_code=404, detail='configuration entry not found')
    return ConfigurationRead.model_validate(entry)


@router.put('/configuration/{name:path}', response_model=ConfigurationRead)
async def update_configuration(
    name: str,
    body: ConfigurationUpdate,
    session: AsyncSession = Depends(get_session),
) -> ConfigurationRead:
    """Update a configuration value. The entry must already exist (seeded by migration)."""
    repo = ConfigurationRepository(session)
    try:
        entry = await repo.update_value(name, body.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if entry is None:
        raise HTTPException(status_code=404, detail='configuration entry not found')
    await session.commit()
    return ConfigurationRead.model_validate(entry)
```

- [ ] **Step 2: Register router in main.py**

Add import:
```python
from tropek.modules.configuration.router import router as configuration_router
```

Add registration after the existing `include_router` calls:
```python
app.include_router(configuration_router)
```

- [ ] **Step 3: Commit**

```
feat(configuration): add REST API endpoints for system settings
```

---

### Task 5: Write integration tests for configuration module

**Files:**
- Create: `api/tests/configuration/__init__.py`
- Create: `api/tests/configuration/db/__init__.py`
- Create: `api/tests/configuration/db/test_configuration_repository.py`

- [ ] **Step 1: Create `__init__.py` files**

Both empty.

- [ ] **Step 2: Write integration tests**

```python
"""Integration tests for ConfigurationRepository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import Configuration
from tropek.modules.configuration.repository import ConfigurationRepository


@pytest.mark.integration
async def test_get_all_returns_seeded_rows(db_session: AsyncSession) -> None:
    """Seeded change_point.* rows should be returned."""
    db_session.add(Configuration(
        name='test.enabled', value='true', value_type='bool', description='test flag',
    ))
    await db_session.flush()
    repo = ConfigurationRepository(db_session)
    rows = await repo.get_all()
    names = [r.name for r in rows]
    assert 'test.enabled' in names


@pytest.mark.integration
async def test_get_all_with_prefix(db_session: AsyncSession) -> None:
    """Prefix filter should only return matching keys."""
    db_session.add(Configuration(
        name='cp.window', value='30', value_type='int', description='window',
    ))
    db_session.add(Configuration(
        name='other.key', value='x', value_type='str', description='other',
    ))
    await db_session.flush()
    repo = ConfigurationRepository(db_session)
    rows = await repo.get_all(prefix='cp.')
    assert all(r.name.startswith('cp.') for r in rows)


@pytest.mark.integration
async def test_get_by_name(db_session: AsyncSession) -> None:
    """Should return a single entry by name."""
    db_session.add(Configuration(
        name='test.val', value='42', value_type='int', description='test',
    ))
    await db_session.flush()
    repo = ConfigurationRepository(db_session)
    entry = await repo.get_by_name('test.val')
    assert entry is not None
    assert entry.value == '42'


@pytest.mark.integration
async def test_get_by_name_missing(db_session: AsyncSession) -> None:
    """Should return None for missing key."""
    repo = ConfigurationRepository(db_session)
    assert await repo.get_by_name('nonexistent') is None


@pytest.mark.integration
async def test_update_value(db_session: AsyncSession) -> None:
    """Should update the value of an existing entry."""
    db_session.add(Configuration(
        name='test.upd', value='10', value_type='int', description='test',
    ))
    await db_session.flush()
    repo = ConfigurationRepository(db_session)
    entry = await repo.update_value('test.upd', '20')
    assert entry is not None
    assert entry.value == '20'


@pytest.mark.integration
async def test_update_value_validates_type(db_session: AsyncSession) -> None:
    """Should reject values that don't match value_type."""
    db_session.add(Configuration(
        name='test.typed', value='5', value_type='int', description='test',
    ))
    await db_session.flush()
    repo = ConfigurationRepository(db_session)
    with pytest.raises(ValueError, match='not a valid int'):
        await repo.update_value('test.typed', 'not-a-number')


@pytest.mark.integration
async def test_get_change_point_defaults(db_session: AsyncSession) -> None:
    """Should return typed dict of change_point.* settings."""
    db_session.add(Configuration(
        name='change_point.enabled', value='true', value_type='bool', description='',
    ))
    db_session.add(Configuration(
        name='change_point.window_size', value='30', value_type='int', description='',
    ))
    await db_session.flush()
    repo = ConfigurationRepository(db_session)
    defaults = await repo.get_change_point_defaults()
    assert defaults['enabled'] is True
    assert defaults['window_size'] == 30
```

- [ ] **Step 3: Run tests**

Run: `uv run --directory api pytest tests/configuration/ -v -m integration`
Expected: all pass

- [ ] **Step 4: Commit**

```
test(configuration): add integration tests for ConfigurationRepository
```

---

### Task 6: Update change point config schemas

**Files:**
- Modify: `api/tropek/modules/change_points/schemas.py`

- [ ] **Step 1: Replace config schemas**

Replace `ChangePointConfigRead` and `ChangePointConfigUpsert` with:

```python
class ChangePointConfigInput(StrictInput):
    """Optional overrides for change point detection — used in SLO YAML change_point: block."""

    enabled: bool | None = None
    higher_is_better: bool | None = None
    window_size: int | None = Field(default=None, strict=True)
    max_pvalue: float | None = None
    min_magnitude: float | None = None
    min_sample_size: int | None = Field(default=None, strict=True)


class ChangePointConfigRead(BaseModel):
    """Full resolved change point config for an objective."""

    slo_objective_id: uuid.UUID
    enabled: bool
    higher_is_better: bool
    window_size: int
    max_pvalue: float
    min_magnitude: float
    min_sample_size: int

    model_config = {'from_attributes': True}
```

- [ ] **Step 2: Commit**

```
refactor(schemas): update change point config schemas for objective-keyed design
```

---

### Task 7: Add `change_point` to SLO schemas and params

**Files:**
- Modify: `api/tropek/modules/slo_registry/schemas.py`
- Modify: `api/tropek/modules/slo_registry/params.py`

- [ ] **Step 1: Update SLOObjectiveIn and SLOObjectiveRead in schemas.py**

Add import at top of `schemas.py`:
```python
from tropek.modules.change_points.schemas import ChangePointConfigInput, ChangePointConfigRead
```

Add `change_point` field to `SLOObjectiveIn`:
```python
class SLOObjectiveIn(StrictInput):
    """SLO objective for create/validate requests."""

    sli: SafeStr
    display_name: SafeStr = ''
    pass_threshold: list[SafeStr] = Field(default_factory=list)
    warning_threshold: list[SafeStr] = Field(default_factory=list)
    weight: IntNotBool = 1
    key_sli: StrictBool = False
    change_point: ChangePointConfigInput | None = None
```

Add `change_point` field to `SLOObjectiveRead`:
```python
class SLOObjectiveRead(SLOObjectiveIn):
    """SLO objective in responses — includes sort_order for round-trip export."""

    sort_order: int
    change_point: ChangePointConfigRead | None = None

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 2: Update SLOObjectiveParams in params.py**

Replace `higher_is_better` with `change_point`:

```python
from tropek.modules.change_points.schemas import ChangePointConfigInput
```

```python
class SLOObjectiveParams(StrictInput):
    """Single objective within an SLO definition."""

    sli: str
    display_name: str | None = None
    weight: int = 1
    key_sli: bool = False
    pass_threshold: list[str] = Field(default_factory=list)
    warning_threshold: list[str] = Field(default_factory=list)
    change_point: ChangePointConfigInput | None = None
```

- [ ] **Step 3: Commit**

```
feat(slo): add change_point block to SLO objective schemas and params
```

---

### Task 8: Update SLO repository — insert config rows and copy-forward

**Files:**
- Modify: `api/tropek/modules/slo_registry/repository.py`

- [ ] **Step 1: Add imports**

```python
from tropek.db.models import ChangePointConfig
from tropek.modules.configuration.repository import ConfigurationRepository
```

- [ ] **Step 2: Update `create()` method**

After the existing objective insertion loop (after `self._session.add(orm_obj)`), add logic to:
1. Load the previous version's objectives with change_point_config (if this is a version bump).
2. For each new objective, create a `ChangePointConfig` row if the params include a `change_point:` block or the previous version had one for this SLI.

Replace the objective insertion section (the `for i, obj in enumerate(params.objectives):` loop through to `await self._session.flush()`) with:

```python
        previous_cp_configs: dict[str, ChangePointConfig] = {}
        if max_version is not None:
            previous_version = await self.get_version(params.name, max_version)
            if previous_version:
                for prev_obj in previous_version.objectives:
                    if prev_obj.change_point_config:
                        previous_cp_configs[prev_obj.sli] = prev_obj.change_point_config

        config_repo = ConfigurationRepository(self._session)
        system_defaults = await config_repo.get_change_point_defaults()

        for i, obj in enumerate(params.objectives):
            orm_obj = SLOObjectiveORM(
                id=uuid.uuid4(),
                slo_definition_id=slo.id,
                sli=obj.sli,
                display_name=obj.display_name or '',
                weight=obj.weight,
                key_sli=obj.key_sli,
                sort_order=i,
                pass_threshold=obj.pass_threshold,
                warning_threshold=obj.warning_threshold,
            )
            self._session.add(orm_obj)

            cp_input = obj.change_point
            previous_config = previous_cp_configs.get(obj.sli)

            if cp_input is not None:
                self._session.add(ChangePointConfig(
                    slo_objective_id=orm_obj.id,
                    enabled=cp_input.enabled if cp_input.enabled is not None else system_defaults.get('enabled', True),
                    higher_is_better=cp_input.higher_is_better if cp_input.higher_is_better is not None else system_defaults.get('higher_is_better', False),
                    window_size=cp_input.window_size if cp_input.window_size is not None else system_defaults.get('window_size', 30),
                    max_pvalue=cp_input.max_pvalue if cp_input.max_pvalue is not None else system_defaults.get('max_pvalue', 0.001),
                    min_magnitude=cp_input.min_magnitude if cp_input.min_magnitude is not None else system_defaults.get('min_magnitude', 0.0),
                    min_sample_size=cp_input.min_sample_size if cp_input.min_sample_size is not None else system_defaults.get('min_sample_size', 10),
                ))
            elif previous_config is not None:
                self._session.add(ChangePointConfig(
                    slo_objective_id=orm_obj.id,
                    enabled=previous_config.enabled,
                    higher_is_better=previous_config.higher_is_better,
                    window_size=previous_config.window_size,
                    max_pvalue=previous_config.max_pvalue,
                    min_magnitude=previous_config.min_magnitude,
                    min_sample_size=previous_config.min_sample_size,
                ))
```

- [ ] **Step 3: Remove the `higher_is_better=obj.higher_is_better` line from objective creation**

This was added earlier and should be removed now.

- [ ] **Step 4: Commit**

```
feat(slo): insert change_point_config rows on SLO create with copy-forward
```

---

### Task 9: Update change point repository — resolve from objective relationship

**Files:**
- Modify: `api/tropek/modules/change_points/repository.py`

- [ ] **Step 1: Update ResolvedConfig to include `higher_is_better`**

```python
class ResolvedConfig(BaseModel):
    """Config for a single metric after merging DB override with defaults."""

    enabled: bool
    higher_is_better: bool
    window_size: int
    max_pvalue: float
    min_magnitude: float
    min_sample_size: int
```

- [ ] **Step 2: Remove old config resolution methods**

Remove `resolve_config()`, `resolve_configs_for_metrics()`, `get_configs_for_slo()`, `upsert_config()`, `delete_config()`, `_default_resolved_config()`, and `_resolve_from_row()`.

These are replaced by direct relationship access in the worker step.

- [ ] **Step 3: Add a method to resolve config from an objective**

```python
    @staticmethod
    def resolve_from_objective(
        objective: Any,
        system_defaults: dict[str, bool | int | float | str],
    ) -> ResolvedConfig:
        """Resolve config for an objective — per-objective override or system defaults."""
        config = objective.change_point_config
        if config is not None:
            return ResolvedConfig(
                enabled=config.enabled,
                higher_is_better=config.higher_is_better,
                window_size=config.window_size,
                max_pvalue=config.max_pvalue,
                min_magnitude=config.min_magnitude,
                min_sample_size=config.min_sample_size,
            )
        return ResolvedConfig(
            enabled=system_defaults.get('enabled', True),
            higher_is_better=system_defaults.get('higher_is_better', False),
            window_size=system_defaults.get('window_size', 30),
            max_pvalue=system_defaults.get('max_pvalue', 0.001),
            min_magnitude=system_defaults.get('min_magnitude', 0.0),
            min_sample_size=system_defaults.get('min_sample_size', 10),
        )
```

- [ ] **Step 4: Add upsert and delete methods keyed by objective_id**

```python
    async def upsert_config_for_objective(
        self,
        *,
        slo_objective_id: uuid.UUID,
        enabled: bool,
        higher_is_better: bool,
        window_size: int,
        max_pvalue: float,
        min_magnitude: float,
        min_sample_size: int,
    ) -> ChangePointConfig:
        """Create or update change point config for an objective."""
        query = select(ChangePointConfig).where(
            ChangePointConfig.slo_objective_id == slo_objective_id,
        )
        result = await self._session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            existing.enabled = enabled
            existing.higher_is_better = higher_is_better
            existing.window_size = window_size
            existing.max_pvalue = max_pvalue
            existing.min_magnitude = min_magnitude
            existing.min_sample_size = min_sample_size
            await self._session.flush()
            return existing

        config = ChangePointConfig(
            slo_objective_id=slo_objective_id,
            enabled=enabled,
            higher_is_better=higher_is_better,
            window_size=window_size,
            max_pvalue=max_pvalue,
            min_magnitude=min_magnitude,
            min_sample_size=min_sample_size,
        )
        self._session.add(config)
        await self._session.flush()
        return config

    async def delete_config_for_objective(self, slo_objective_id: uuid.UUID) -> bool:
        """Delete change point config for an objective. Returns True if deleted."""
        cursor = cast(
            'CursorResult[Any]',
            await self._session.execute(
                delete(ChangePointConfig).where(
                    ChangePointConfig.slo_objective_id == slo_objective_id,
                )
            ),
        )
        await self._session.flush()
        return cursor.rowcount > 0

    async def get_config_for_objective(
        self, slo_objective_id: uuid.UUID,
    ) -> ChangePointConfig | None:
        """Return change point config for an objective, if any."""
        result = await self._session.execute(
            select(ChangePointConfig).where(
                ChangePointConfig.slo_objective_id == slo_objective_id,
            )
        )
        return result.scalar_one_or_none()
```

- [ ] **Step 5: Remove the `ChangePointInsertParams`, `ChangePointListParams` classes**

These were added as part of the lint fix. `ChangePointListParams` is still needed — keep it. `ChangePointInsertParams` stays too — it's used by `insert_change_point`.

Actually, keep both. Only remove the old config-resolution methods.

- [ ] **Step 6: Commit**

```
refactor(repository): resolve change point config from objective relationship
```

---

### Task 10: Update worker step — use objective relationship for config

**Files:**
- Modify: `api/tropek/modules/change_points/worker_step.py`

- [ ] **Step 1: Update imports**

Remove:
```python
from tropek.modules.change_points.directionality import is_higher_better
```

(Already done earlier in session — verify it's removed.)

Add:
```python
from tropek.modules.configuration.repository import ConfigurationRepository
```

- [ ] **Step 2: Rewrite `run_change_point_detection`**

Replace the config resolution section. The function currently builds `objective_lookup`, `indicator_lookup`, then calls `resolve_configs_for_metrics()`. Replace with:

```python
async def run_change_point_detection(
    *,
    session: AsyncSession,
    snapshot: Any,
    slo_def: SLODefinition,
    indicator_rows: list[IndicatorResultRow],
    cache: Any | None = None,
) -> None:
    """Run Otava change point detection for each enabled metric."""
    log = logger.bind(
        evaluation_id=str(snapshot.eval_id),
        slo_name=snapshot.slo_name,
    )

    indicator_lookup = {
        row.objective.sli: row
        for row in indicator_rows
        if row.objective
    }

    config_repo = ConfigurationRepository(session)
    system_defaults = await config_repo.get_change_point_defaults()

    change_point_repo = ChangePointRepository(session)
    baseline_repo = BaselineRepository(session, cache=cache)

    for objective in slo_def.objectives:
        indicator_row = indicator_lookup.get(objective.sli)
        if not indicator_row:
            continue

        resolved = ChangePointRepository.resolve_from_objective(objective, system_defaults)
        if not resolved.enabled:
            continue

        try:
            await _detect_for_metric(
                log=log,
                baseline_repo=baseline_repo,
                change_point_repo=change_point_repo,
                snapshot=snapshot,
                metric_name=objective.sli,
                indicator_result_id=indicator_row.id,
                higher_is_better=resolved.higher_is_better,
                config=resolved,
            )
        except (OSError, ValueError, TypeError, RuntimeError, LookupError):
            log.warning(
                "change point detection failed for metric",
                metric=objective.sli,
                exc_info=True,
            )
```

- [ ] **Step 3: Commit**

```
refactor(worker): resolve change point config from objective relationship
```

---

### Task 11: Update change points router — re-key config endpoints

**Files:**
- Modify: `api/tropek/modules/change_points/router.py`

- [ ] **Step 1: Remove old config endpoints**

Remove: `get_default_config()`, `list_config_overrides()`, `upsert_config_override()`, `delete_config_override()`.

Remove the detector default imports (`DEFAULT_ENABLED`, etc.) since they are no longer needed in the router.

- [ ] **Step 2: Add new config endpoints keyed by `objective_id`**

Add import:
```python
from tropek.modules.configuration.repository import ConfigurationRepository
```

Add endpoints:

```python
@router.get('/change-points/config/{objective_id}', response_model=ChangePointConfigRead)
async def get_change_point_config(
    objective_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ChangePointConfigRead:
    """Get resolved change point config for an objective."""
    repo = ChangePointRepository(session)
    config = await repo.get_config_for_objective(objective_id)
    if config is not None:
        return ChangePointConfigRead.model_validate(config)
    config_repo = ConfigurationRepository(session)
    system_defaults = await config_repo.get_change_point_defaults()
    return ChangePointConfigRead(
        slo_objective_id=objective_id,
        enabled=system_defaults.get('enabled', True),
        higher_is_better=system_defaults.get('higher_is_better', False),
        window_size=system_defaults.get('window_size', 30),
        max_pvalue=system_defaults.get('max_pvalue', 0.001),
        min_magnitude=system_defaults.get('min_magnitude', 0.0),
        min_sample_size=system_defaults.get('min_sample_size', 10),
    )


@router.put('/change-points/config/{objective_id}', response_model=ChangePointConfigRead)
async def upsert_change_point_config(
    objective_id: uuid.UUID,
    body: ChangePointConfigInput,
    session: AsyncSession = Depends(get_session),
) -> ChangePointConfigRead:
    """Create or update change point config for an objective."""
    config_repo = ConfigurationRepository(session)
    system_defaults = await config_repo.get_change_point_defaults()
    repo = ChangePointRepository(session)
    config = await repo.upsert_config_for_objective(
        slo_objective_id=objective_id,
        enabled=body.enabled if body.enabled is not None else system_defaults.get('enabled', True),
        higher_is_better=body.higher_is_better if body.higher_is_better is not None else system_defaults.get('higher_is_better', False),
        window_size=body.window_size if body.window_size is not None else system_defaults.get('window_size', 30),
        max_pvalue=body.max_pvalue if body.max_pvalue is not None else system_defaults.get('max_pvalue', 0.001),
        min_magnitude=body.min_magnitude if body.min_magnitude is not None else system_defaults.get('min_magnitude', 0.0),
        min_sample_size=body.min_sample_size if body.min_sample_size is not None else system_defaults.get('min_sample_size', 10),
    )
    await session.commit()
    return ChangePointConfigRead.model_validate(config)


@router.delete('/change-points/config/{objective_id}', status_code=204)
async def delete_change_point_config(
    objective_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove per-objective config override. Detection falls back to system defaults."""
    repo = ChangePointRepository(session)
    deleted = await repo.delete_config_for_objective(objective_id)
    if not deleted:
        raise HTTPException(status_code=404, detail='change point config not found')
    await session.commit()
```

- [ ] **Step 3: Commit**

```
refactor(router): re-key change point config endpoints to objective_id
```

---

### Task 12: Delete directionality module and tests

**Files:**
- Delete: `api/tropek/modules/change_points/directionality.py`
- Delete: `api/tests/change_points/test_directionality.py`

- [ ] **Step 1: Delete files**

```bash
rm api/tropek/modules/change_points/directionality.py
rm api/tests/change_points/test_directionality.py
```

- [ ] **Step 2: Verify no remaining imports**

```bash
grep -rn "directionality" api/ --include="*.py"
```

Expected: no results (the worker_step import was already removed in Task 10).

- [ ] **Step 3: Commit**

```
refactor: delete directionality module — higher_is_better is now explicit config
```

---

### Task 13: Update worker step tests

**Files:**
- Modify: `api/tests/change_points/test_worker_step.py`

- [ ] **Step 1: Update test mocks**

The tests currently mock `ChangePointRepository` and its `resolve_configs_for_metrics` method. Update them to:
1. Mock `ConfigurationRepository` and its `get_change_point_defaults` method.
2. Set up objectives on `slo_def` mock with `change_point_config` attribute.
3. Remove `resolve_configs_for_metrics` mocking.

Update the `_make_slo_def` helper to return objectives with `change_point_config`:

```python
def _make_slo_def() -> MagicMock:
    config = MagicMock()
    config.enabled = True
    config.higher_is_better = False
    config.window_size = 30
    config.max_pvalue = 0.001
    config.min_magnitude = 0.0
    config.min_sample_size = 10

    objective = MagicMock()
    objective.sli = "response_time_p95"
    objective.display_name = "Response Time P95"
    objective.pass_threshold = ["<600"]
    objective.warning_threshold = ["<1000"]
    objective.change_point_config = config

    slo = MagicMock()
    slo.objectives = [objective]
    slo.comparable_from_version = 1
    return slo
```

Update each test to mock `ConfigurationRepository` instead of `resolve_configs_for_metrics`:

```python
with (
    patch(
        "tropek.modules.change_points.worker_step.ChangePointRepository"
    ) as mock_repo_cls,
    patch(
        "tropek.modules.change_points.worker_step.ConfigurationRepository"
    ) as mock_config_cls,
):
    mock_config = mock_config_cls.return_value
    mock_config.get_change_point_defaults = AsyncMock(return_value={
        'enabled': True,
        'higher_is_better': False,
        'window_size': 30,
        'max_pvalue': 0.001,
        'min_magnitude': 0.0,
        'min_sample_size': 10,
    })
    mock_repo = mock_repo_cls.return_value
    # ... rest of test setup
```

- [ ] **Step 2: Update test for disabled metric**

Set `config.enabled = False` on the objective's `change_point_config` mock.

- [ ] **Step 3: Run tests**

Run: `uv run --directory api pytest tests/change_points/test_worker_step.py -v`
Expected: all pass

- [ ] **Step 4: Commit**

```
test(worker): update mocks for objective-based config resolution
```

---

### Task 14: Update integration tests for change point repository

**Files:**
- Modify: `api/tests/change_points/db/test_repository.py`

- [ ] **Step 1: Update config-related integration tests**

The tests `test_get_configs_for_slo`, `test_resolve_config_*` reference the old `(slo_name, metric_name)` keying. Replace them with tests for the new `get_config_for_objective`, `upsert_config_for_objective`, and `delete_config_for_objective` methods.

Create helper to set up an SLO with objectives:

```python
async def _create_slo_with_objective(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Create an SLO definition with one objective, return (slo_id, objective_id)."""
    slo_id = uuid.uuid4()
    obj_id = uuid.uuid4()
    session.add(SLODefinition(
        id=slo_id, name=f'test-slo-{uuid.uuid4().hex[:8]}', version=1,
        comparable_from_version=1,
    ))
    await session.flush()
    session.add(SLOObjective(
        id=obj_id, slo_definition_id=slo_id, sli='test_metric',
        display_name='Test', weight=1, sort_order=0,
    ))
    await session.flush()
    return slo_id, obj_id
```

Add imports for `SLODefinition`, `SLOObjective` from `tropek.db.models`.

Replace the old config tests with:

```python
@pytest.mark.integration
async def test_upsert_config_creates_new(db_session: AsyncSession) -> None:
    _, obj_id = await _create_slo_with_objective(db_session)
    repo = ChangePointRepository(db_session)
    config = await repo.upsert_config_for_objective(
        slo_objective_id=obj_id, enabled=True, higher_is_better=False,
        window_size=30, max_pvalue=0.001, min_magnitude=0.0, min_sample_size=10,
    )
    assert config.slo_objective_id == obj_id
    assert config.higher_is_better is False


@pytest.mark.integration
async def test_upsert_config_updates_existing(db_session: AsyncSession) -> None:
    _, obj_id = await _create_slo_with_objective(db_session)
    repo = ChangePointRepository(db_session)
    await repo.upsert_config_for_objective(
        slo_objective_id=obj_id, enabled=True, higher_is_better=False,
        window_size=30, max_pvalue=0.001, min_magnitude=0.0, min_sample_size=10,
    )
    updated = await repo.upsert_config_for_objective(
        slo_objective_id=obj_id, enabled=False, higher_is_better=True,
        window_size=60, max_pvalue=0.01, min_magnitude=0.05, min_sample_size=20,
    )
    assert updated.enabled is False
    assert updated.higher_is_better is True
    assert updated.window_size == 60


@pytest.mark.integration
async def test_delete_config(db_session: AsyncSession) -> None:
    _, obj_id = await _create_slo_with_objective(db_session)
    repo = ChangePointRepository(db_session)
    await repo.upsert_config_for_objective(
        slo_objective_id=obj_id, enabled=True, higher_is_better=False,
        window_size=30, max_pvalue=0.001, min_magnitude=0.0, min_sample_size=10,
    )
    assert await repo.delete_config_for_objective(obj_id) is True
    assert await repo.get_config_for_objective(obj_id) is None
```

- [ ] **Step 2: Run integration tests**

Run: `uv run --directory api pytest tests/change_points/db/ -v -m integration`
Expected: all pass

- [ ] **Step 3: Commit**

```
test(repository): update integration tests for objective-keyed config
```

---

### Task 15: Update client library and bootstrap manifests

**Files:**
- Modify: `clients/python/tropek_client/models.py`
- Modify: `bootstrap_mock/manifests/slo-definitions.yaml`

- [ ] **Step 1: Add `change_point` to client SLOObjective model**

```python
class SLOObjective(BaseModel):
    """SLO objective in client responses."""

    sli: str
    display_name: str = ''
    pass_threshold: list[str] = []
    warning_threshold: list[str] = []
    weight: int = 1
    key_sli: bool = False
    sort_order: int = 0
    change_point: dict[str, Any] | None = None
```

Add `Any` to the typing imports if not already present.

- [ ] **Step 2: Update bootstrap SLO definitions**

Add `change_point:` blocks where the default `higher_is_better: false` is wrong. For `http-availability-slo`:

```yaml
    - sli: availability
      display_name: "Availability"
      pass_threshold: [">=0.999"]
      warning_threshold: [">=0.99"]
      weight: 2
      change_point:
        higher_is_better: true
```

For `vm-health-slo`, check metrics like `cpu_usage_pct`, `memory_usage_pct` — these are "lower is better" so the default is correct, no block needed.

Check all bootstrap SLO files for metrics where higher is better (availability, throughput) and add the block.

- [ ] **Step 3: Commit**

```
feat(client): add change_point to SLOObjective, update bootstrap manifests
```

---

### Task 16: Regenerate migration and run full test suite

**Files:**
- Modify: `api/alembic/versions/001_initial_schema.py` (regenerated)

- [ ] **Step 1: Regenerate migration**

Run: `./scripts/db-regen-migrations.sh`
Expected: clean regeneration with new `configuration` table and re-keyed `change_point_config`.

- [ ] **Step 2: Run all change point tests**

Run: `uv run --directory api pytest tests/change_points/ -v`
Expected: all pass

- [ ] **Step 3: Run configuration tests**

Run: `uv run --directory api pytest tests/configuration/ -v -m integration`
Expected: all pass

- [ ] **Step 4: Run lint**

Run: `uv run ruff check api/tropek/modules/change_points/ api/tropek/modules/configuration/ api/tropek/modules/slo_registry/`
Expected: no new errors

- [ ] **Step 5: Run typecheck**

Run: `uv run mypy api/tropek/modules/change_points/ api/tropek/modules/configuration/ api/tropek/modules/slo_registry/`
Expected: no errors

- [ ] **Step 6: Commit**

```
chore: regenerate migration for change point config redesign
```

---

### Task 17: Final cleanup — remove stale code

**Files:**
- Verify: no remaining references to `directionality`, `slo_name`/`metric_name` keying in change_point_config, or `higher_is_better` on `SLOObjective`

- [ ] **Step 1: Search for stale references**

```bash
grep -rn "directionality\|is_higher_better" api/ --include="*.py"
grep -rn "slo_name.*metric_name.*change_point_config\|cp_config.*slo_name" api/ --include="*.py"
```

Expected: no results (or only in the spec/plan docs).

- [ ] **Step 2: Run full unit test suite**

Run: `./scripts/api-test.sh --tail 10`
Expected: all unit tests pass

- [ ] **Step 3: Commit any cleanup**

```
chore: remove stale references from change point config redesign
```
