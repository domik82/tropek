# DB Layer Redesign — Phase 1 Chunk 3 Revision

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Depends on:** Chunk 1 (scaffold), Chunk 2 (engine)
> **Supersedes:** `2026-03-12-quality-platform-phase1-chunk3-db.md`
> **Spec:** `docs/superpowers/specs/2026-03-14-tropek-domain-redesign.md`

**Goal:** Revise the DB layer to match the redesigned domain model — separating SLI from SLO, adding DataSource/AssetGroup/binding entities, fixing naming, and extracting status constants.

**Architecture:** Four passes in dependency order: (1) constants + renames on existing models/repos, (2) new ORM models, (3) Alembic migration 003, (4) new repositories and repository updates. Each pass is independently testable before the next begins.

**Tech Stack:** SQLAlchemy 2.0 async, asyncpg, Alembic 1.13, TimescaleDB, pytest-asyncio

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `api/app/modules/quality_gate/engine/constants.py` | Modify | Add `EvaluationStatus` StrEnum |
| `api/app/db/models.py` | Modify | Rename columns, add new columns, add 7 new ORM models |
| `api/app/modules/quality_gate/repository.py` | Modify | Use `EvaluationStatus.*`, rename `get`→`get_by_id`, add `sli_name` to baseline query |
| `api/app/modules/slo_registry/repository.py` | Modify | Add `display_name` param to `create()` |
| `api/app/modules/sli_registry/__init__.py` | Create | Package marker |
| `api/app/modules/sli_registry/repository.py` | Create | `SLIRepository` — versioned CRUD mirroring `SLORepository` |
| `api/app/modules/datasource/__init__.py` | Create | Package marker |
| `api/app/modules/datasource/repository.py` | Create | `DataSourceRepository` — simple CRUD |
| `api/app/modules/asset_groups/__init__.py` | Create | Package marker |
| `api/app/modules/asset_groups/repository.py` | Create | `AssetGroupRepository` — groups, members, links, bindings |
| `api/alembic/versions/003_domain_redesign.py` | Create | Rename columns, add new columns, create 7 new tables |
| `api/tests/db/test_evaluation_repository.py` | Modify | Fix `start_time`→`period_start`, `get`→`get_by_id` |
| `api/tests/db/test_slo_repository.py` | Modify | Add `display_name` coverage |
| `api/tests/db/test_sli_repository.py` | Create | Versioned CRUD integration tests for `SLIRepository` |
| `api/tests/db/test_datasource_repository.py` | Create | CRUD integration tests for `DataSourceRepository` |

---

## Chunk 1: EvaluationStatus Constants + Existing Model/Repo Fixes

### Task 1: Add EvaluationStatus to constants.py

**Files:**
- Modify: `api/app/modules/quality_gate/engine/constants.py`

- [ ] **Step 1: Add the StrEnum class after existing enums**

```python
class EvaluationStatus(StrEnum):
    """Job lifecycle status of an evaluation record."""

    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    PARTIAL   = "partial"
```

- [ ] **Step 2: Verify import works**

```bash
uv run python -c "from app.modules.quality_gate.engine.constants import EvaluationStatus; print(EvaluationStatus.PENDING)"
```

Expected output: `pending`

- [ ] **Step 3: Commit**

```bash
git add api/app/modules/quality_gate/engine/constants.py
git commit -m "feat: add EvaluationStatus StrEnum to constants"
```

---

### Task 2: Replace status string literals in EvaluationRepository

**Files:**
- Modify: `api/app/modules/quality_gate/repository.py`

- [ ] **Step 1: Add import at top of file**

```python
from app.modules.quality_gate.engine.constants import EvaluationStatus
```

- [ ] **Step 2: Replace all string literals throughout the file**

| Replace | With |
|---|---|
| `status="pending"` | `status=EvaluationStatus.PENDING` |
| `status="running"` | `status=EvaluationStatus.RUNNING` |
| `status="completed"` | `status=EvaluationStatus.COMPLETED` |
| `status="failed"` | `status=EvaluationStatus.FAILED` |
| `status="partial"` | `status=EvaluationStatus.PARTIAL` |
| `== "completed"` | `== EvaluationStatus.COMPLETED` |
| `== "running"` | `== EvaluationStatus.RUNNING` |

Also replace string comparisons in `.where()` clauses, `CheckConstraint` is in models.py
so leave that as a raw string — it is SQL, not Python.

- [ ] **Step 3: Rename `get` to `get_by_id`**

```python
# Before
async def get(self, eval_id: uuid.UUID) -> Evaluation | None:

# After
async def get_by_id(self, eval_id: uuid.UUID) -> Evaluation | None:
```

- [ ] **Step 4: Run existing tests to confirm no regressions**

```bash
uv run pytest api/tests/ -m "not integration" -q
```

Expected: all pass (unit tests do not hit the DB).

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/quality_gate/repository.py
git commit -m "refactor: use EvaluationStatus constants, rename get to get_by_id"
```

---

### Task 3: Rename start_time/end_time on Evaluation model

**Files:**
- Modify: `api/app/db/models.py`

- [ ] **Step 1: Rename the two columns on the `Evaluation` class**

```python
# Before
start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

# After
period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
period_end:   Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 2: Add new provenance columns to Evaluation (after `slo_version`)**

```python
sli_name:         Mapped[str | None] = mapped_column(Text, nullable=True)
sli_version:      Mapped[int | None] = mapped_column(Integer, nullable=True)
data_source_name: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 3: Add `display_name` to `SLODefinition` (after `name`)**

```python
display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Add `display_name` to `Asset` (after `name`)**

```python
display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 5: Add `updated_at` to `EvaluationAnnotation` (after `created_at`)**

```python
updated_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), onupdate=func.now(), nullable=True
)
```

- [ ] **Step 6: Remove the TODO comments addressed by this task**

Remove the four TODO lines for `evaluation_start_time`, `slo_yaml`, `evaluation_start_time/started_at`, `updated_at`, and the top-level docstring TODO.

- [ ] **Step 7: Update `create_pending` in `EvaluationRepository` to match renamed params**

```python
# Before
async def create_pending(
    self,
    *,
    name: str,
    start_time: datetime,
    end_time: datetime,
    ...
) -> Evaluation:
    ev = Evaluation(
        ...
        start_time=start_time,
        end_time=end_time,
        ...
    )

# After
async def create_pending(
    self,
    *,
    name: str,
    period_start: datetime,
    period_end: datetime,
    ...
) -> Evaluation:
    ev = Evaluation(
        ...
        period_start=period_start,
        period_end=period_end,
        ...
    )
```

Also add optional params to `create_pending` signature:

```python
sli_name: str | None = None,
sli_version: int | None = None,
data_source_name: str | None = None,
```

And pass them into the `Evaluation(...)` constructor.

- [ ] **Step 8: Update test_evaluation_repository.py for renamed fields**

```python
# Before
ev = await repo.create_pending(
    name="compile-test",
    start_time=_START,
    end_time=_END,
    ...
)

# After
ev = await repo.create_pending(
    name="compile-test",
    period_start=_START,
    period_end=_END,
    ...
)
```

Also rename `test_get_returns_evaluation`:
```python
# Before
fetched = await repo.get(ev.id)

# After
fetched = await repo.get_by_id(ev.id)
```

- [ ] **Step 9: Run unit tests**

```bash
uv run pytest api/tests/ -m "not integration" -q
```

Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add api/app/db/models.py api/app/modules/quality_gate/repository.py api/tests/db/test_evaluation_repository.py
git commit -m "refactor: rename start_time/end_time to period_start/period_end, add sli/datasource columns"
```

---

### Task 4: Fix baseline query — add sli_name filter + update SLORepository

**Files:**
- Modify: `api/app/modules/quality_gate/repository.py`
- Modify: `api/app/modules/slo_registry/repository.py`

- [ ] **Step 1: Find `_get_baseline_evaluations` (or equivalent) in `EvaluationRepository`**

Locate the method that fetches previous evaluations for relative-criteria comparison.
It will contain filters for `Evaluation.name`, `Evaluation.status`, `Evaluation.invalidated`.

- [ ] **Step 2: Add `sli_name` filter to that query**

```python
# Add alongside the existing name/status/invalidated filters:
if sli_name:
    q = q.where(Evaluation.sli_name == sli_name)
```

Update the method signature to accept `sli_name: str | None = None`.

- [ ] **Step 3: Add `display_name` to `SLORepository.create()`**

```python
async def create(
    self,
    name: str,
    slo_yaml: str,
    display_name: str | None = None,     # new
    notes: str | None = None,
    author: str | None = None,
    meta: dict[str, Any] | None = None,
) -> SLODefinition:
    ...
    slo = SLODefinition(
        ...
        display_name=display_name,        # new
        ...
    )
```

- [ ] **Step 4: Run unit tests**

```bash
uv run pytest api/tests/ -m "not integration" -q
```

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/quality_gate/repository.py api/app/modules/slo_registry/repository.py
git commit -m "fix: add sli_name to baseline query, add display_name to SLORepository"
```

---

## Chunk 2: New ORM Models

### Task 5: Add DataSource model

**Files:**
- Modify: `api/app/db/models.py`

- [ ] **Step 1: Add `DataSource` class (insert before `SLODefinition`)**

```python
class DataSource(Base):
    """Named pointer to a running adapter service instance.

    The adapter manages its own connection credentials via env vars.
    TROPEK stores only where to send queries (adapter_url) and free-form
    labels for discovery. Names are unique across the deployment.
    """

    __tablename__ = "data_sources"
    __table_args__ = (Index("idx_data_sources_name", "name"),)

    # fmt: off

    id:           Mapped[uuid.UUID]        = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]              = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None]       = mapped_column(Text, nullable=True)
    adapter_type: Mapped[str]              = mapped_column(Text, nullable=False)
    adapter_url:  Mapped[str]              = mapped_column(Text, nullable=False)
    labels:       Mapped[dict[str, Any]]   = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    created_at:   Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:   Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # fmt: on
```

- [ ] **Step 2: Verify import still works**

```bash
uv run python -c "from app.db.models import DataSource; print(DataSource.__tablename__)"
```

Expected: `data_sources`

---

### Task 6: Add SLIDefinition model

**Files:**
- Modify: `api/app/db/models.py`

- [ ] **Step 1: Add `SLIDefinition` class (insert after `DataSource`)**

```python
class SLIDefinition(Base):
    """Versioned set of indicator queries for one adapter type.

    Rows are immutable after insert — same versioning pattern as SLODefinition.
    Each indicator maps a name to an adapter-specific query string (PromQL, SQL, etc.).
    Variable tokens ($vm_ip, $period_start, etc.) are substituted at evaluation time.
    """

    __tablename__ = "sli_definitions"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_sli_name_version"),
        Index("idx_sli_definitions_name", "name"),
        Index("idx_sli_definitions_latest", "name", text("version DESC")),
    )

    # fmt: off

    id:           Mapped[uuid.UUID]        = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]              = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None]       = mapped_column(Text, nullable=True)
    version:      Mapped[int]              = mapped_column(Integer, nullable=False)
    indicators:   Mapped[dict[str, Any]]   = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    notes:        Mapped[str | None]       = mapped_column(Text, nullable=True)
    author:       Mapped[str | None]       = mapped_column(Text, nullable=True)
    meta:         Mapped[dict[str, Any]]   = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    active:       Mapped[bool]             = mapped_column(Boolean, nullable=False, server_default=true(), default=True)
    created_at:   Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # fmt: on
```

---

### Task 7: Add AssetGroup and membership models

**Files:**
- Modify: `api/app/db/models.py`

- [ ] **Step 1: Add `AssetGroup`, `AssetGroupMember`, `AssetGroupLink` (insert after `Asset`)**

```python
class AssetGroup(Base):
    """Named container of assets or other groups.

    Supports flat groups (linux_boxes = [vm-01, vm-02]) and
    group-of-groups (software_xyz = [linux_boxes, windows_vms]).
    """

    __tablename__ = "asset_groups"

    # fmt: off

    id:           Mapped[uuid.UUID]  = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]        = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    description:  Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at:   Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:   Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # fmt: on


class AssetGroupMember(Base):
    """Associates individual assets with an asset group, with optional weight."""

    __tablename__ = "asset_group_members"
    __table_args__ = (
        Index("idx_asset_group_members_group", "group_id"),
        Index("idx_asset_group_members_asset", "asset_id"),
    )

    # fmt: off

    group_id:  Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    asset_id:  Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    weight:    Mapped[float]     = mapped_column(Float, nullable=False, default=1.0)

    # fmt: on


class AssetGroupLink(Base):
    """Links a child group inside a parent group (group-of-groups)."""

    __tablename__ = "asset_group_links"
    __table_args__ = (Index("idx_asset_group_links_parent", "parent_group_id"),)

    # fmt: off

    parent_group_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    child_group_id:  Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    weight:          Mapped[float]     = mapped_column(Float, nullable=False, default=1.0)

    # fmt: on
```

---

### Task 8: Add binding tables and EvaluationBatch

**Files:**
- Modify: `api/app/db/models.py`

- [ ] **Step 1: Add `AssetSLOLink` and `AssetGroupSLOLink` (insert after binding table section)**

```python
class AssetSLOLink(Base):
    """Permanent named binding of an asset to a SLO + SLI + DataSource triple.

    Callers trigger evaluations by group/asset name — the system resolves which
    SLO, SLI, and DataSource to use from these bindings at trigger time.
    SLO, SLI, and DataSource names resolve to their latest active version.
    """

    __tablename__ = "asset_slo_links"
    __table_args__ = (
        Index("idx_asset_slo_links_asset", "asset_id"),
        UniqueConstraint("asset_id", "link_name", name="uq_asset_slo_link_name"),
    )

    # fmt: off

    id:               Mapped[uuid.UUID]  = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    link_name:        Mapped[str]        = mapped_column(Text, nullable=False)
    asset_id:         Mapped[uuid.UUID]  = mapped_column(UUID, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    slo_name:         Mapped[str]        = mapped_column(Text, nullable=False)
    sli_name:         Mapped[str]        = mapped_column(Text, nullable=False)
    data_source_name: Mapped[str]        = mapped_column(Text, nullable=False)
    created_at:       Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # fmt: on


class AssetGroupSLOLink(Base):
    """Same as AssetSLOLink but bound to an asset group instead of a single asset."""

    __tablename__ = "asset_group_slo_links"
    __table_args__ = (
        Index("idx_asset_group_slo_links_group", "group_id"),
        UniqueConstraint("group_id", "link_name", name="uq_asset_group_slo_link_name"),
    )

    # fmt: off

    id:               Mapped[uuid.UUID]  = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    link_name:        Mapped[str]        = mapped_column(Text, nullable=False)
    group_id:         Mapped[uuid.UUID]  = mapped_column(UUID, ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False)
    slo_name:         Mapped[str]        = mapped_column(Text, nullable=False)
    sli_name:         Mapped[str]        = mapped_column(Text, nullable=False)
    data_source_name: Mapped[str]        = mapped_column(Text, nullable=False)
    created_at:       Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # fmt: on
```

- [ ] **Step 2: Add `EvaluationBatch` (insert after `AssetGroupSLOLink`)**

```python
class EvaluationBatch(Base):
    """Groups all evaluations spawned by a single trigger call.

    When a group with N bindings across M assets is triggered, one batch is
    created containing up to N×M evaluation IDs. Callers poll batch status
    instead of tracking individual evaluation IDs.
    """

    __tablename__ = "evaluation_batches"
    __table_args__ = (Index("idx_evaluation_batches_status", "status"),)

    # fmt: off

    id:             Mapped[uuid.UUID]        = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    status:         Mapped[str]              = mapped_column(Text, nullable=False, server_default=text("'pending'"), default="pending")
    trigger_params: Mapped[dict[str, Any]]   = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    evaluation_ids: Mapped[list[Any]]        = mapped_column(JSONB, nullable=False, server_default=text("'[]'"), default=list)
    created_at:     Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # fmt: on
```

- [ ] **Step 3: Verify all models import without error**

```bash
uv run python -c "
from app.db.models import (
    DataSource, SLIDefinition, AssetGroup, AssetGroupMember,
    AssetGroupLink, AssetSLOLink, AssetGroupSLOLink, EvaluationBatch
)
print('all models OK')
"
```

- [ ] **Step 4: Run unit tests**

```bash
uv run pytest api/tests/ -m "not integration" -q
```

- [ ] **Step 5: Commit**

```bash
git add api/app/db/models.py
git commit -m "feat: add DataSource, SLIDefinition, AssetGroup, binding, and EvaluationBatch models"
```

---

## Chunk 3: Alembic Migration 003

### Task 9: Write migration 003

**Files:**
- Create: `api/alembic/versions/003_domain_redesign.py`

This migration must run after 002. It handles:
- Column renames on `evaluations` (`start_time`→`period_start`, `end_time`→`period_end`)
- New nullable columns on existing tables
- Seven new tables

- [ ] **Step 1: Create the migration file**

```python
"""Domain model redesign — rename columns, add new tables.

Revision ID: 003
Revises: 002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- evaluations: rename window columns ---
    op.alter_column("evaluations", "start_time", new_column_name="period_start")
    op.alter_column("evaluations", "end_time", new_column_name="period_end")

    # --- evaluations: new provenance columns ---
    op.add_column("evaluations", sa.Column("sli_name", sa.Text(), nullable=True))
    op.add_column("evaluations", sa.Column("sli_version", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("data_source_name", sa.Text(), nullable=True))

    # --- evaluations: update existing index that used start_time ---
    op.drop_index("idx_evaluations_start", table_name="evaluations")
    op.create_index("idx_evaluations_start", "evaluations", ["period_start"])

    # --- evaluation_annotations: add updated_at ---
    op.add_column(
        "evaluation_annotations",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- slo_definitions: add display_name ---
    op.add_column("slo_definitions", sa.Column("display_name", sa.Text(), nullable=True))

    # --- assets: add display_name ---
    op.add_column("assets", sa.Column("display_name", sa.Text(), nullable=True))

    # --- data_sources ---
    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), unique=True, nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("adapter_type", sa.Text(), nullable=False),
        sa.Column("adapter_url", sa.Text(), nullable=False),
        sa.Column("labels", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_data_sources_name", "data_sources", ["name"])

    # --- sli_definitions ---
    op.create_table(
        "sli_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("indicators", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_sli_name_version"),
    )
    op.create_index("idx_sli_definitions_name", "sli_definitions", ["name"])
    op.create_index("idx_sli_definitions_latest", "sli_definitions", ["name", sa.text("version DESC")])

    # --- asset_groups ---
    op.create_table(
        "asset_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), unique=True, nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- asset_group_members ---
    op.create_table(
        "asset_group_members",
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False, primary_key=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, primary_key=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.create_index("idx_asset_group_members_group", "asset_group_members", ["group_id"])
    op.create_index("idx_asset_group_members_asset", "asset_group_members", ["asset_id"])

    # --- asset_group_links ---
    op.create_table(
        "asset_group_links",
        sa.Column("parent_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False, primary_key=True),
        sa.Column("child_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False, primary_key=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.create_index("idx_asset_group_links_parent", "asset_group_links", ["parent_group_id"])

    # --- asset_slo_links ---
    op.create_table(
        "asset_slo_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("link_name", sa.Text(), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slo_name", sa.Text(), nullable=False),
        sa.Column("sli_name", sa.Text(), nullable=False),
        sa.Column("data_source_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("asset_id", "link_name", name="uq_asset_slo_link_name"),
    )
    op.create_index("idx_asset_slo_links_asset", "asset_slo_links", ["asset_id"])

    # --- asset_group_slo_links ---
    op.create_table(
        "asset_group_slo_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("link_name", sa.Text(), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slo_name", sa.Text(), nullable=False),
        sa.Column("sli_name", sa.Text(), nullable=False),
        sa.Column("data_source_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("group_id", "link_name", name="uq_asset_group_slo_link_name"),
    )
    op.create_index("idx_asset_group_slo_links_group", "asset_group_slo_links", ["group_id"])

    # --- evaluation_batches ---
    op.create_table(
        "evaluation_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("trigger_params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("evaluation_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_evaluation_batches_status", "evaluation_batches", ["status"])


def downgrade() -> None:
    op.drop_table("evaluation_batches")
    op.drop_table("asset_group_slo_links")
    op.drop_table("asset_slo_links")
    op.drop_table("asset_group_links")
    op.drop_table("asset_group_members")
    op.drop_table("asset_groups")
    op.drop_table("sli_definitions")
    op.drop_table("data_sources")
    op.drop_column("assets", "display_name")
    op.drop_column("slo_definitions", "display_name")
    op.drop_column("evaluation_annotations", "updated_at")
    op.drop_index("idx_evaluations_start", table_name="evaluations")
    op.create_index("idx_evaluations_start", "evaluations", ["start_time"])
    op.drop_column("evaluations", "data_source_name")
    op.drop_column("evaluations", "sli_version")
    op.drop_column("evaluations", "sli_name")
    op.alter_column("evaluations", "period_end", new_column_name="end_time")
    op.alter_column("evaluations", "period_start", new_column_name="start_time")
```

- [ ] **Step 2: Start infrastructure**

```bash
docker compose up timescaledb -d
```

- [ ] **Step 3: Run the migration**

```bash
cd api && uv run alembic upgrade head && cd ..
```

Expected: migration applies without errors.

- [ ] **Step 4: Verify tables exist**

```bash
docker compose exec timescaledb psql -U quality_gate -d quality_gate -c "\dt"
```

Expected: all new tables visible including `sli_definitions`, `data_sources`,
`asset_groups`, `asset_group_members`, `asset_group_links`,
`asset_slo_links`, `asset_group_slo_links`, `evaluation_batches`.

- [ ] **Step 5: Verify column rename on evaluations**

```bash
docker compose exec timescaledb psql -U quality_gate -d quality_gate \
  -c "\d evaluations" | grep -E "period_start|period_end|sli_name"
```

Expected: `period_start`, `period_end`, `sli_name` columns present. No `start_time` or `end_time`.

- [ ] **Step 6: Commit**

```bash
git add api/alembic/versions/003_domain_redesign.py
git commit -m "feat: migration 003 — domain redesign schema changes"
```

---

## Chunk 4: New Repositories + Integration Tests

### Task 10: Create SLIRepository

**Files:**
- Create: `api/app/modules/sli_registry/__init__.py`
- Create: `api/app/modules/sli_registry/repository.py`
- Create: `api/tests/db/test_sli_repository.py`

`SLIRepository` mirrors `SLORepository` exactly — versioned immutable rows,
`create()` / `get_latest()` / `get_version()` / `list_all()` / `deactivate()`.

- [ ] **Step 1: Create package marker**

```bash
touch api/app/modules/sli_registry/__init__.py
```

- [ ] **Step 2: Write the failing tests first**

Create `api/tests/db/test_sli_repository.py`:

```python
"""Integration tests for SLIRepository."""

from __future__ import annotations

import pytest
from app.modules.sli_registry.repository import SLIRepository
from sqlalchemy.ext.asyncio import AsyncSession


_INDICATORS = {
    "response_time_p95": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{instance=\"$vm_ip\"}[5m]))",
    "cpu_usage_avg": "avg_over_time(process_cpu_seconds_total{instance=\"$vm_ip\"}[5m])",
}


@pytest.mark.integration
async def test_create_first_version(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    sli = await repo.create(name="linux-sli", indicators=_INDICATORS)
    assert sli.version == 1
    assert sli.name == "linux-sli"
    assert sli.indicators == _INDICATORS
    assert sli.active is True


@pytest.mark.integration
async def test_create_increments_version(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(name="versioned-sli", indicators=_INDICATORS)
    v2 = await repo.create(name="versioned-sli", indicators={"cpu": "some_query"})
    assert v2.version == 2


@pytest.mark.integration
async def test_get_latest_returns_highest_version(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(name="latest-sli", indicators={"a": "q1"})
    await repo.create(name="latest-sli", indicators={"a": "q2"})
    latest = await repo.get_latest("latest-sli")
    assert latest is not None
    assert latest.version == 2
    assert latest.indicators == {"a": "q2"}


@pytest.mark.integration
async def test_get_version_returns_specific(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(name="pinned-sli", indicators={"a": "q1"})
    await repo.create(name="pinned-sli", indicators={"a": "q2"})
    v1 = await repo.get_version("pinned-sli", 1)
    assert v1 is not None
    assert v1.indicators == {"a": "q1"}


@pytest.mark.integration
async def test_get_latest_returns_none_for_unknown(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    result = await repo.get_latest("does-not-exist")
    assert result is None


@pytest.mark.integration
async def test_deactivate_hides_from_get_latest(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(name="gone-sli", indicators={"a": "q1"})
    await repo.deactivate("gone-sli")
    result = await repo.get_latest("gone-sli")
    assert result is None
```

- [ ] **Step 3: Run tests — expect FAIL (module not found)**

```bash
uv run pytest api/tests/db/test_sli_repository.py -m integration -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'app.modules.sli_registry.repository'`

- [ ] **Step 4: Implement SLIRepository**

Create `api/app/modules/sli_registry/repository.py`:

```python
"""SLI registry repository — versioned CRUD for sli_definitions table."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SLIDefinition


class SLIRepository:
    """Data access layer for versioned SLI definitions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        name: str,
        indicators: dict[str, str],
        display_name: str | None = None,
        notes: str | None = None,
        author: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> SLIDefinition:
        """Insert a new version of a named SLI.

        Version is auto-incremented using SELECT ... FOR UPDATE to prevent races.
        """
        result = await self._session.execute(
            select(SLIDefinition.version)
            .where(SLIDefinition.name == name)
            .order_by(SLIDefinition.version.desc())
            .limit(1)
            .with_for_update()
        )
        max_version = result.scalar_one_or_none()
        next_version = (max_version or 0) + 1

        sli = SLIDefinition(
            id=uuid.uuid4(),
            name=name,
            display_name=display_name,
            version=next_version,
            indicators=indicators,
            notes=notes,
            author=author,
            meta=meta or {},
            active=True,
        )
        self._session.add(sli)
        await self._session.flush()
        return sli

    async def get_latest(self, name: str) -> SLIDefinition | None:
        """Return the highest active version, or None."""
        result = await self._session.execute(
            select(SLIDefinition)
            .where(SLIDefinition.name == name, SLIDefinition.active == True)  # noqa: E712
            .order_by(SLIDefinition.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_version(self, name: str, version: int) -> SLIDefinition | None:
        """Return a specific version, or None."""
        result = await self._session.execute(
            select(SLIDefinition).where(
                SLIDefinition.name == name,
                SLIDefinition.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def list_versions(self, name: str) -> list[SLIDefinition]:
        """Return all versions newest-first."""
        result = await self._session.execute(
            select(SLIDefinition)
            .where(SLIDefinition.name == name)
            .order_by(SLIDefinition.version.desc())
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[SLIDefinition]:
        """Return latest active version of every SLI name."""
        result = await self._session.execute(
            select(SLIDefinition)
            .where(SLIDefinition.active == True)  # noqa: E712
            .distinct(SLIDefinition.name)
            .order_by(SLIDefinition.name, SLIDefinition.version.desc())
        )
        return list(result.scalars().all())

    async def deactivate(self, name: str) -> None:
        """Soft-delete all versions of a named SLI."""
        await self._session.execute(
            update(SLIDefinition)
            .where(SLIDefinition.name == name)
            .values(active=False)
        )
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
uv run pytest api/tests/db/test_sli_repository.py -m integration -v
```

Expected: all 7 tests pass.

- [ ] **Step 6: Commit**

```bash
git add api/app/modules/sli_registry/ api/tests/db/test_sli_repository.py
git commit -m "feat: add SLIRepository with versioned CRUD"
```

---

### Task 11: Create DataSourceRepository

**Files:**
- Create: `api/app/modules/datasource/__init__.py`
- Create: `api/app/modules/datasource/repository.py`
- Create: `api/tests/db/test_datasource_repository.py`

- [ ] **Step 1: Write failing tests**

Create `api/tests/db/test_datasource_repository.py`:

```python
"""Integration tests for DataSourceRepository."""

from __future__ import annotations

import pytest
from app.modules.datasource.repository import DataSourceRepository
from sqlalchemy.ext.asyncio import AsyncSession


def _ds_kwargs(**overrides: object) -> dict:
    return {
        "name": "prometheus-dc-a",
        "adapter_type": "prometheus",
        "adapter_url": "http://adapter-prometheus-dc-a:8081",
        **overrides,
    }


@pytest.mark.integration
async def test_create_and_get(db_session: AsyncSession) -> None:
    repo = DataSourceRepository(db_session)
    ds = await repo.create(**_ds_kwargs())
    fetched = await repo.get_by_name("prometheus-dc-a")
    assert fetched is not None
    assert fetched.id == ds.id
    assert fetched.adapter_type == "prometheus"


@pytest.mark.integration
async def test_get_by_name_missing_returns_none(db_session: AsyncSession) -> None:
    repo = DataSourceRepository(db_session)
    result = await repo.get_by_name("does-not-exist")
    assert result is None


@pytest.mark.integration
async def test_list_all(db_session: AsyncSession) -> None:
    repo = DataSourceRepository(db_session)
    await repo.create(**_ds_kwargs(name="ds-1"))
    await repo.create(**_ds_kwargs(name="ds-2", adapter_url="http://other:8082"))
    all_ds = await repo.list_all()
    names = {ds.name for ds in all_ds}
    assert "ds-1" in names
    assert "ds-2" in names


@pytest.mark.integration
async def test_delete_removes_record(db_session: AsyncSession) -> None:
    repo = DataSourceRepository(db_session)
    ds = await repo.create(**_ds_kwargs(name="to-delete"))
    await repo.delete(ds.id)
    result = await repo.get_by_name("to-delete")
    assert result is None
```

- [ ] **Step 2: Run — expect FAIL**

```bash
uv run pytest api/tests/db/test_datasource_repository.py -m integration -v 2>&1 | head -5
```

- [ ] **Step 3: Implement DataSourceRepository**

Create `api/app/modules/datasource/__init__.py` (empty).

Create `api/app/modules/datasource/repository.py`:

```python
"""DataSource repository — CRUD for data_sources table."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DataSource


class DataSourceRepository:
    """Data access layer for datasource registrations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        name: str,
        adapter_type: str,
        adapter_url: str,
        display_name: str | None = None,
        labels: dict[str, Any] | None = None,
    ) -> DataSource:
        """Register a new datasource."""
        ds = DataSource(
            id=uuid.uuid4(),
            name=name,
            display_name=display_name,
            adapter_type=adapter_type,
            adapter_url=adapter_url,
            labels=labels or {},
        )
        self._session.add(ds)
        await self._session.flush()
        return ds

    async def get_by_name(self, name: str) -> DataSource | None:
        """Return datasource by unique name, or None."""
        result = await self._session.execute(
            select(DataSource).where(DataSource.name == name)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[DataSource]:
        """Return all registered datasources."""
        result = await self._session.execute(
            select(DataSource).order_by(DataSource.name)
        )
        return list(result.scalars().all())

    async def delete(self, datasource_id: uuid.UUID) -> None:
        """Hard-delete a datasource record."""
        await self._session.execute(
            delete(DataSource).where(DataSource.id == datasource_id)
        )
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest api/tests/db/test_datasource_repository.py -m integration -v
```

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/datasource/ api/tests/db/test_datasource_repository.py
git commit -m "feat: add DataSourceRepository with CRUD"
```

---

### Task 12: Run full integration test suite

- [ ] **Step 1: Run all integration tests**

```bash
uv run pytest api/tests/db/ -m integration -v
```

Expected: all existing + new tests pass. If existing tests fail due to renames
(`start_time`, `get`), fix the callsites in the test files before proceeding.

- [ ] **Step 2: Run full test suite (unit + integration)**

```bash
uv run pytest api/tests/ -v
```

Expected: all pass.

- [ ] **Step 3: Run linter**

```bash
uv run ruff check api/ && uv run ruff format --check api/
```

Expected: no violations.

- [ ] **Step 4: Run type checker**

```bash
uv run mypy api/app
```

Expected: no errors.

- [ ] **Step 5: Final commit**

```bash
git add -p   # review all remaining changes
git commit -m "chore: db layer redesign complete — all tests passing"
```
