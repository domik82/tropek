# Quality Platform Phase 1 — Chunk 3: Database Layer

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Depends on:** Chunk 1 (project scaffold), Chunk 2 (engine)

**Goal:** SQLAlchemy async ORM models, Alembic initial migration, and repository classes for all DB access — evaluations, SLO registry, annotations, SLI values, and trend queries.

**Architecture:** Three layers — `app/db/session.py` owns the engine/session factory; `app/db/models.py` owns all ORM table definitions; repository classes in each module own SQL queries. No raw SQL anywhere except the TimescaleDB hypertable DDL in the migration.

**Tech Stack:** SQLAlchemy 2.0 async, asyncpg, Alembic 1.13, TimescaleDB (PostgreSQL extension)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `api/app/db/__init__.py` | Create | Package marker |
| `api/app/db/session.py` | Create | Engine + session factory, `get_session()` context manager |
| `api/app/db/models.py` | Create | All ORM declarative models (Asset, SLODefinition, Evaluation, EvaluationAnnotation, SLIValue) |
| `api/alembic.ini` | Create | Alembic configuration (generated then patched) |
| `api/alembic/env.py` | Create | Async-aware migration runner |
| `api/alembic/versions/001_initial_schema.py` | Create | Creates all tables + TimescaleDB hypertable |
| `api/app/modules/slo_registry/__init__.py` | Create | Package marker |
| `api/app/modules/slo_registry/repository.py` | Create | SLORepository: versioned CRUD for slo_definitions |
| `api/app/modules/quality_gate/repository.py` | Create | EvaluationRepository: evaluation lifecycle, annotations, SLI values, trend |
| `api/tests/db/__init__.py` | Create | Package marker |
| `api/tests/db/conftest.py` | Create | `db_session` async fixture for integration tests |
| `api/tests/db/test_slo_repository.py` | Create | Integration tests for SLORepository |
| `api/tests/db/test_evaluation_repository.py` | Create | Integration tests for EvaluationRepository |
| `api/pyproject.toml` | Modify | Add `integration` pytest marker; add sqlalchemy mypy plugin |
| `api/tropek-root/pyproject.toml` | N/A | Already has sqlalchemy, asyncpg, alembic — no changes needed |

> **All commands are run from `d:/DEV/keptn_rewrite/tropek/` (workspace root) unless stated otherwise.**

---

## Task 3.1: Pytest marker + mypy plugin setup

**Files:**
- Modify: `api/pyproject.toml`
- Modify: `pyproject.toml` (workspace root)

- [ ] **Add `integration` marker and SQLAlchemy mypy plugin to workspace `pyproject.toml`**

Open `pyproject.toml` (workspace root). Add to `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["api/tests", "adapters/prometheus/tests"]
pythonpath = ["api", "adapters/prometheus"]
markers = [
    "integration: requires a running TimescaleDB instance (deselect with -m 'not integration')",
]
```

And add to `[tool.mypy]`:

```toml
[tool.mypy]
python_version = "3.13"
strict = true
ignore_missing_imports = true
plugins = ["sqlalchemy.ext.mypy.plugin"]
```

- [ ] **Add SQLAlchemy mypy extra to `api/pyproject.toml` dev deps**

In `api/pyproject.toml` under `[tool.uv]` → `dev-dependencies`, add:

```toml
"sqlalchemy[mypy]>=2.0",
```

- [ ] **Sync dependencies**

```bash
uv sync
```

- [ ] **Verify existing tests still pass**

```bash
uv run pytest api/tests/ -m "not integration" -q
```

Expected: `83 passed`

- [ ] **Commit**

```bash
git add pyproject.toml api/pyproject.toml
git commit -m "chore: register integration marker; add sqlalchemy mypy plugin"
```

---

## Task 3.2: Database session

**Files:**
- Create: `api/app/db/__init__.py`
- Create: `api/app/db/session.py`
- Create: `api/tests/db/__init__.py`

- [ ] **Write smoke test first**

Create `api/tests/db/__init__.py` (empty).

Create `api/tests/test_db_imports.py`:

```python
from __future__ import annotations


def test_db_session_imports() -> None:
    """Verify the db session module is importable and exposes expected names."""
    from app.db.session import get_session, get_session_factory  # noqa: F401
```

- [ ] **Run test — expect ImportError (red)**

```bash
uv run pytest api/tests/test_db_imports.py -v
```

Expected: `FAILED — ModuleNotFoundError: No module named 'app.db'`

- [ ] **Create `api/app/db/__init__.py`** (empty)

- [ ] **Create `api/app/db/session.py`**

```python
"""Async SQLAlchemy session factory and session context manager."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    """Return the shared async engine, creating it on first call."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database.async_url,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            echo=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the shared session factory, creating it on first call."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            _get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that yields a session with auto commit/rollback.

    Yields:
        An AsyncSession bound to the shared engine.

    Raises:
        Exception: Re-raises any exception after rolling back the session.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Run test — expect green**

```bash
uv run pytest api/tests/test_db_imports.py -v
```

Expected: `PASSED`

- [ ] **Commit**

```bash
git add api/app/db/ api/tests/db/ api/tests/test_db_imports.py
git commit -m "feat: async SQLAlchemy session factory"
```

---

## Task 3.3: ORM models

**Files:**
- Create: `api/app/db/models.py`

- [ ] **Extend smoke test for models**

Add to `api/tests/test_db_imports.py`:

```python
def test_orm_models_importable() -> None:
    """Verify ORM models import and register expected table names."""
    from app.db.models import (  # noqa: F401
        Asset,
        Base,
        Evaluation,
        EvaluationAnnotation,
        SLIValue,
        SLODefinition,
    )

    table_names = set(Base.metadata.tables.keys())
    assert table_names == {
        "assets",
        "slo_definitions",
        "evaluations",
        "evaluation_annotations",
        "sli_values",
    }
```

- [ ] **Run test — expect ImportError (red)**

```bash
uv run pytest api/tests/test_db_imports.py::test_orm_models_importable -v
```

Expected: `FAILED — ModuleNotFoundError: No module named 'app.db.models'`

- [ ] **Create `api/app/db/models.py`**

```python
"""SQLAlchemy ORM declarative models for all Phase 1 entities."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class Asset(Base):
    """A named entity under test — VM, service, container, or endpoint."""

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    tags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SLODefinition(Base):
    """Versioned SLO definition — rows are immutable after insert."""

    __tablename__ = "slo_definitions"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_slo_name_version"),
        Index("idx_slo_definitions_name", "name"),
        Index("idx_slo_definitions_latest", "name", "version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    slo_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Evaluation(Base):
    """One evaluation run — triggered, executed, stored."""

    __tablename__ = "evaluations"
    __table_args__ = (
        Index("idx_evaluations_name", "name"),
        Index("idx_evaluations_asset", "asset_id"),
        Index("idx_evaluations_result", "result"),
        Index("idx_evaluations_start", "start_time"),
        Index("idx_evaluations_status", "status"),
        Index("idx_evaluations_slo", "slo_name", "slo_version"),
        # Partial index for watchdog: find stuck running jobs efficiently
        Index(
            "idx_evaluations_stuck",
            "status",
            "started_at",
            postgresql_where="status = 'running'",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True
    )
    asset_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)  # null while pending
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    slo_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    slo_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    slo_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    indicator_results: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    # Column named 'metadata' in DB; metadata_ avoids conflict with SQLAlchemy internals
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    ingestion_mode: Mapped[str] = mapped_column(Text, nullable=False)  # pull | push | file
    adapter_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    invalidated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invalidation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Job lifecycle
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job_stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    annotations: Mapped[list[EvaluationAnnotation]] = relationship(
        "EvaluationAnnotation", back_populates="evaluation", cascade="all, delete-orphan"
    )


class EvaluationAnnotation(Base):
    """Append-only contextual note on an evaluation."""

    __tablename__ = "evaluation_annotations"
    __table_args__ = (Index("idx_annotations_evaluation", "evaluation_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluations.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    evaluation: Mapped[Evaluation] = relationship("Evaluation", back_populates="annotations")


class SLIValue(Base):
    """TimescaleDB hypertable — one aggregated metric value per evaluation.

    Partitioned by eval_start for efficient time-range queries in Grafana.
    Composite PK required: TimescaleDB needs the partition key in the PK.
    Denormalised columns (asset_name, test_name, os_tag) avoid joins in Grafana SQL.
    """

    __tablename__ = "sli_values"
    __table_args__ = (
        Index("idx_sli_values_lookup", "test_name", "metric_name", "eval_start"),
    )

    eval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id"), nullable=False, primary_key=True
    )
    eval_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, primary_key=True
    )
    metric_name: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    aggregation: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    asset_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    os_tag: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Run tests (green)**

```bash
uv run pytest api/tests/test_db_imports.py -v
```

Expected: both tests `PASSED`

- [ ] **Run mypy**

```bash
uv run mypy api/app/db/
```

Expected: `Success: no issues found`

- [ ] **Commit**

```bash
git add api/app/db/models.py api/tests/test_db_imports.py
git commit -m "feat: SQLAlchemy ORM models for all Phase 1 entities"
```

---

## Task 3.4: Alembic migration

**Files:**
- Create: `api/alembic.ini`
- Create: `api/alembic/env.py`
- Create: `api/alembic/script.py.mako`
- Create: `api/alembic/versions/001_initial_schema.py`

> **Note:** This task involves running against a real TimescaleDB instance. Skip the migration run if the DB is not available — the code is committed regardless.

- [ ] **Initialise Alembic (run from `api/`)**

```bash
cd api && uv run alembic init alembic && cd ..
```

This creates `api/alembic.ini`, `api/alembic/env.py`, and `api/alembic/script.py.mako`.

- [ ] **Patch `api/alembic.ini`** — blank out the hardcoded URL (env.py provides it)

Find the line:
```ini
sqlalchemy.url = driver://user:pass@localhost/dbname
```

Replace with:
```ini
sqlalchemy.url =
```

- [ ] **Replace `api/alembic/env.py`** with async-aware version

```python
"""Alembic environment — async SQLAlchemy engine, URL from app config."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Return the async database URL from app settings."""
    return get_settings().database.async_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a live connection)."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    """Run migrations synchronously inside an async connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations."""
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online mode migrations."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Create `api/alembic/versions/001_initial_schema.py`**

```python
"""Initial schema: assets, slo_definitions, evaluations, annotations, sli_values hypertable.

Revision ID: 001
Revises:
Create Date: 2026-03-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all Phase 1 tables and the TimescaleDB hypertable."""
    op.create_table(
        "assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, unique=True, nullable=False),
        sa.Column("tags", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "slo_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("slo_yaml", sa.Text, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("author", sa.Text, nullable=True),
        sa.Column("meta", JSONB, nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("name", "version", name="uq_slo_name_version"),
    )
    op.create_index("idx_slo_definitions_name", "slo_definitions", ["name"])
    op.create_index(
        "idx_slo_definitions_latest", "slo_definitions", ["name", sa.text("version DESC")]
    )

    op.create_table(
        "evaluations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("asset_snapshot", JSONB, nullable=False, server_default="{}"),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.Text, nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("slo_yaml", sa.Text, nullable=True),
        sa.Column("slo_name", sa.Text, nullable=True),
        sa.Column("slo_version", sa.Integer, nullable=True),
        sa.Column("indicator_results", JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("ingestion_mode", sa.Text, nullable=False),
        sa.Column("adapter_used", sa.Text, nullable=True),
        sa.Column("invalidated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("invalidation_note", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("job_stats", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','failed','partial')",
            name="ck_evaluations_status",
        ),
    )
    op.create_index("idx_evaluations_name", "evaluations", ["name"])
    op.create_index("idx_evaluations_result", "evaluations", ["result"])
    op.create_index("idx_evaluations_start", "evaluations", ["start_time"])
    op.create_index("idx_evaluations_status", "evaluations", ["status"])
    op.create_index("idx_evaluations_slo", "evaluations", ["slo_name", "slo_version"])
    op.execute(
        "CREATE INDEX idx_evaluations_stuck ON evaluations(status, started_at) "
        "WHERE status = 'running'"
    )

    op.create_table(
        "evaluation_annotations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "evaluation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("author", sa.Text, nullable=True),
        sa.Column("category", sa.Text, nullable=True),
        sa.Column("meta", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "idx_annotations_evaluation", "evaluation_annotations", ["evaluation_id"]
    )

    # sli_values: regular table first, then converted to TimescaleDB hypertable
    op.create_table(
        "sli_values",
        sa.Column("eval_id", UUID(as_uuid=True), sa.ForeignKey("evaluations.id"), nullable=False),
        sa.Column("eval_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_name", sa.Text, nullable=False),
        sa.Column("aggregation", sa.Text, nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("asset_name", sa.Text, nullable=True),
        sa.Column("test_name", sa.Text, nullable=True),
        sa.Column("os_tag", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("eval_id", "eval_start", "metric_name", "aggregation"),
    )
    op.create_index(
        "idx_sli_values_lookup", "sli_values", ["test_name", "metric_name", "eval_start"]
    )
    # Convert to TimescaleDB hypertable — requires TimescaleDB extension installed
    op.execute(
        "SELECT create_hypertable('sli_values', 'eval_start', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("sli_values")
    op.drop_table("evaluation_annotations")
    op.drop_table("evaluations")
    op.drop_table("slo_definitions")
    op.drop_table("assets")
```

- [ ] **Verify alembic config imports without error**

```bash
cd api && uv run alembic current 2>&1 | head -5; cd ..
```

Expected: either `No connection configured` (if no DB) or `<revision>` — not a Python import error.

- [ ] **Commit**

```bash
git add api/alembic.ini api/alembic/
git commit -m "feat: Alembic async migration — all tables + TimescaleDB hypertable"
```

- [ ] **[Integration] Run migration against local TimescaleDB**

> Requires: `docker compose up timescaledb -d` and `.env` sourced.

```bash
cd api
export $(grep -v '^#' ../.env | xargs)
uv run alembic upgrade head
cd ..
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial schema...
```

- [ ] **[Integration] Verify hypertable**

```bash
docker compose exec timescaledb psql -U $QG_DB_USER -d quality_gate \
  -c "SELECT hypertable_name FROM timescaledb_information.hypertables;"
```

Expected: `sli_values` in the output.

---

## Task 3.5: Integration test fixture

**Files:**
- Create: `api/tests/db/__init__.py`
- Create: `api/tests/db/conftest.py`

> Integration tests require a running TimescaleDB. They are skipped automatically with `uv run pytest -m "not integration"`.

- [ ] **Create `api/tests/db/conftest.py`**

```python
"""Database fixtures for integration tests.

Requires TEST_DATABASE_URL env var pointing to a real TimescaleDB instance.
Tables are created fresh per test session and dropped on teardown.

Usage:
    export TEST_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/tropek_test"
    uv run pytest api/tests/db/ -m integration -v
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base


@pytest.fixture(scope="session")
def db_url() -> str:
    """Return the test database URL, skipping if not configured."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set — skipping integration tests")
    return url


@pytest_asyncio.fixture(scope="session")
async def db_engine(db_url: str):
    """Create engine and tables once per test session, drop on teardown."""
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a session that is rolled back after each test — no DB pollution."""
    from collections.abc import AsyncGenerator

    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        async with session.begin():
            yield session
            await session.rollback()
```

- [ ] **Commit**

```bash
git add api/tests/db/
git commit -m "feat: async DB fixtures for integration tests"
```

---

## Task 3.6: SLO repository

**Files:**
- Create: `api/app/modules/slo_registry/__init__.py`
- Create: `api/app/modules/slo_registry/repository.py`
- Create: `api/tests/db/test_slo_repository.py`

- [ ] **Write failing integration tests first**

Create `api/tests/db/test_slo_repository.py`:

```python
"""Integration tests for SLORepository.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: uv run pytest api/tests/db/test_slo_repository.py -m integration -v
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.slo_registry.repository import SLORepository

YAML_V1 = "spec_version: '1.0'\ntotal_score:\n  pass: '90%'\n  warning: '75%'\n"
YAML_V2 = "spec_version: '1.0'\ntotal_score:\n  pass: '95%'\n  warning: '80%'\n"


@pytest.mark.integration
async def test_create_first_version(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    slo = await repo.create("my-slo", YAML_V1, notes="Initial", author="alice")
    assert slo.version == 1
    assert slo.name == "my-slo"
    assert slo.author == "alice"


@pytest.mark.integration
async def test_create_second_version_increments(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("versioned-slo", YAML_V1)
    v2 = await repo.create("versioned-slo", YAML_V2, notes="Tightened thresholds")
    assert v2.version == 2


@pytest.mark.integration
async def test_get_latest_returns_highest_version(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("latest-slo", YAML_V1)
    await repo.create("latest-slo", YAML_V2)
    latest = await repo.get_latest("latest-slo")
    assert latest is not None
    assert latest.version == 2
    assert latest.slo_yaml == YAML_V2


@pytest.mark.integration
async def test_get_version_specific(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("specific-slo", YAML_V1)
    await repo.create("specific-slo", YAML_V2)
    v1 = await repo.get_version("specific-slo", 1)
    assert v1 is not None
    assert v1.slo_yaml == YAML_V1


@pytest.mark.integration
async def test_list_versions_newest_first(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("list-slo", YAML_V1)
    await repo.create("list-slo", YAML_V2)
    versions = await repo.list_versions("list-slo")
    assert len(versions) == 2
    assert versions[0].version == 2
    assert versions[1].version == 1


@pytest.mark.integration
async def test_soft_delete_hides_from_get_latest(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("delete-slo", YAML_V1)
    await repo.soft_delete("delete-slo")
    result = await repo.get_latest("delete-slo")
    assert result is None


@pytest.mark.integration
async def test_get_latest_nonexistent_returns_none(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    result = await repo.get_latest("does-not-exist")
    assert result is None
```

- [ ] **Run tests — expect ImportError (red)**

```bash
uv run pytest api/tests/db/test_slo_repository.py -m integration -v
```

Expected: `ERROR — ModuleNotFoundError: No module named 'app.modules.slo_registry'`

(If `TEST_DATABASE_URL` is not set, tests will be skipped — that is acceptable for now.)

- [ ] **Create `api/app/modules/slo_registry/__init__.py`** (empty)

- [ ] **Create `api/app/modules/slo_registry/repository.py`**

```python
"""SLO registry repository — versioned CRUD for slo_definitions table."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SLODefinition


class SLORepository:
    """Data access layer for versioned SLO definitions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        name: str,
        slo_yaml: str,
        notes: str | None = None,
        author: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> SLODefinition:
        """Insert a new version of a named SLO.

        Version is auto-incremented using SELECT ... FOR UPDATE to prevent races.

        Args:
            name: Stable external identifier for the SLO.
            slo_yaml: Full SLO YAML content.
            notes: Optional description of changes in this version.
            author: Optional identifier of who created this version.
            meta: Optional arbitrary key-value metadata.

        Returns:
            The newly created SLODefinition with its assigned version.
        """
        result = await self._session.execute(
            select(SLODefinition.version)
            .where(SLODefinition.name == name)
            .order_by(SLODefinition.version.desc())
            .limit(1)
            .with_for_update()
        )
        max_version = result.scalar_one_or_none()
        next_version = (max_version or 0) + 1

        slo = SLODefinition(
            id=uuid.uuid4(),
            name=name,
            version=next_version,
            slo_yaml=slo_yaml,
            notes=notes,
            author=author,
            meta=meta or {},
            active=True,
        )
        self._session.add(slo)
        await self._session.flush()
        return slo

    async def get_latest(self, name: str) -> SLODefinition | None:
        """Return the highest version of a named SLO, or None if not found or deleted.

        Args:
            name: Stable external SLO identifier.

        Returns:
            Latest active SLODefinition, or None.
        """
        result = await self._session.execute(
            select(SLODefinition)
            .where(SLODefinition.name == name, SLODefinition.active == True)  # noqa: E712
            .order_by(SLODefinition.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_version(self, name: str, version: int) -> SLODefinition | None:
        """Return a specific version of a named SLO.

        Args:
            name: Stable external SLO identifier.
            version: Integer version number.

        Returns:
            Matching SLODefinition, or None.
        """
        result = await self._session.execute(
            select(SLODefinition).where(
                SLODefinition.name == name,
                SLODefinition.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def list_versions(self, name: str) -> list[SLODefinition]:
        """Return all versions of a named SLO, newest first.

        Args:
            name: Stable external SLO identifier.

        Returns:
            All SLODefinition rows for this name, ordered by version descending.
        """
        result = await self._session.execute(
            select(SLODefinition)
            .where(SLODefinition.name == name)
            .order_by(SLODefinition.version.desc())
        )
        return list(result.scalars().all())

    async def list_all_latest(self) -> list[SLODefinition]:
        """Return the latest active version of every named SLO.

        Uses DISTINCT ON (name) ORDER BY name, version DESC — PostgreSQL-specific.

        Returns:
            One SLODefinition per active SLO name, the highest version of each.
        """
        # DISTINCT ON (name) with ORDER BY name, version DESC — PostgreSQL-specific
        subq = (
            select(SLODefinition.name, SLODefinition.version)
            .where(SLODefinition.active == True)  # noqa: E712
            .distinct(SLODefinition.name)
            .order_by(SLODefinition.name, SLODefinition.version.desc())
        ).subquery()

        result = await self._session.execute(
            select(SLODefinition).join(
                subq,
                (SLODefinition.name == subq.c.name)
                & (SLODefinition.version == subq.c.version),
            )
        )
        return list(result.scalars().all())

    async def soft_delete(self, name: str) -> int:
        """Mark all versions of a named SLO as inactive.

        Evaluations that used this SLO are unaffected — they store the resolved YAML.

        Args:
            name: Stable external SLO identifier.

        Returns:
            Number of rows affected (versions deactivated).
        """
        result = await self._session.execute(
            update(SLODefinition).where(SLODefinition.name == name).values(active=False)
        )
        return result.rowcount  # type: ignore[return-value]
```

- [ ] **Run unit tests (all non-integration tests still pass)**

```bash
uv run pytest api/tests/ -m "not integration" -q
```

Expected: `83 passed` (imports now succeed — integration tests skipped)

- [ ] **[Integration] Run SLO repository tests against real DB**

```bash
export TEST_DATABASE_URL="postgresql+asyncpg://$QG_DB_USER:$QG_DB_PASSWORD@localhost:5432/quality_gate"
uv run pytest api/tests/db/test_slo_repository.py -m integration -v
```

Expected: `7 passed`

- [ ] **Commit**

```bash
git add api/app/modules/slo_registry/ api/tests/db/test_slo_repository.py
git commit -m "feat: SLORepository — versioned SLO CRUD with auto-increment"
```

---

## Task 3.7: Evaluation repository

**Files:**
- Create: `api/app/modules/quality_gate/repository.py`
- Create: `api/tests/db/test_evaluation_repository.py`

- [ ] **Write failing integration tests first**

Create `api/tests/db/test_evaluation_repository.py`:

```python
"""Integration tests for EvaluationRepository.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: uv run pytest api/tests/db/test_evaluation_repository.py -m integration -v
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quality_gate.repository import EvaluationRepository

_START = datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc)
_END = datetime(2026, 3, 12, 10, 30, 0, tzinfo=timezone.utc)


def _make_snapshot(os: str = "windows-11", arch: str = "x64") -> dict:
    return {"name": "vm-test-01", "tags": {"os": os, "arch": arch}}


@pytest.mark.integration
async def test_create_pending_returns_evaluation(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        name="compile-test",
        start_time=_START,
        end_time=_END,
        ingestion_mode="push",
        asset_snapshot=_make_snapshot(),
        metadata={},
    )
    assert ev.status == "pending"
    assert ev.result is None
    assert ev.id is not None


@pytest.mark.integration
async def test_get_returns_evaluation(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        name="get-test",
        start_time=_START,
        end_time=_END,
        ingestion_mode="push",
        asset_snapshot=_make_snapshot(),
        metadata={},
    )
    fetched = await repo.get(ev.id)
    assert fetched is not None
    assert fetched.id == ev.id


@pytest.mark.integration
async def test_mark_completed_updates_fields(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        name="complete-test",
        start_time=_START,
        end_time=_END,
        ingestion_mode="push",
        asset_snapshot=_make_snapshot(),
        metadata={},
    )
    await repo.mark_completed(
        ev.id,
        result="pass",
        score=95.0,
        slo_yaml="spec_version: '1.0'\n",
        indicator_results=[{"metric": "cpu", "status": "pass"}],
        compared_evaluation_ids=[],
    )
    fetched = await repo.get(ev.id)
    assert fetched is not None
    assert fetched.status == "completed"
    assert fetched.result == "pass"
    assert fetched.score == 95.0


@pytest.mark.integration
async def test_mark_running_sets_status(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        name="running-test",
        start_time=_START,
        end_time=_END,
        ingestion_mode="pull",
        asset_snapshot=_make_snapshot(),
        metadata={},
    )
    await repo.mark_running(ev.id, worker_id="worker-1")
    fetched = await repo.get(ev.id)
    assert fetched is not None
    assert fetched.status == "running"


@pytest.mark.integration
async def test_list_evaluations_filters_by_name(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    for name in ("alpha", "alpha", "beta"):
        await repo.create_pending(
            name=name,
            start_time=_START,
            end_time=_END,
            ingestion_mode="push",
            asset_snapshot=_make_snapshot(),
            metadata={},
        )
    results = await repo.list_evaluations(name="alpha")
    assert len(results) == 2
    assert all(e.name == "alpha" for e in results)


@pytest.mark.integration
async def test_get_baselines_filters_by_os_tag(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    for os in ("windows-11", "windows-11", "ubuntu-22"):
        ev = await repo.create_pending(
            name="scope-test",
            start_time=_START,
            end_time=_END,
            ingestion_mode="push",
            asset_snapshot=_make_snapshot(os=os),
            metadata={},
        )
        await repo.mark_completed(
            ev.id,
            result="pass",
            score=90.0,
            slo_yaml="",
            indicator_results=[],
            compared_evaluation_ids=[],
        )
    baselines = await repo.get_baselines(
        name="scope-test",
        scope_tags=["os"],
        asset_snapshot=_make_snapshot(os="windows-11"),
        include_result_with_score="pass",
        limit=10,
    )
    assert len(baselines) == 2
    for b in baselines:
        assert b.asset_snapshot["tags"]["os"] == "windows-11"


@pytest.mark.integration
async def test_add_and_list_annotations(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        name="ann-test",
        start_time=_START,
        end_time=_END,
        ingestion_mode="push",
        asset_snapshot=_make_snapshot(),
        metadata={},
    )
    await repo.add_annotation(ev.id, content="Defender update applied", author="ops")
    fetched = await repo.get(ev.id)
    assert fetched is not None
    assert len(fetched.annotations) == 1
    assert fetched.annotations[0].content == "Defender update applied"


@pytest.mark.integration
async def test_write_and_read_sli_values(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        name="sli-test",
        start_time=_START,
        end_time=_END,
        ingestion_mode="push",
        asset_snapshot=_make_snapshot(),
        metadata={},
    )
    rows = [
        {
            "eval_id": ev.id,
            "eval_start": _START,
            "metric_name": "cpu_usage",
            "aggregation": "avg",
            "value": 72.3,
            "asset_name": "vm-test-01",
            "test_name": "sli-test",
            "os_tag": "windows-11",
        }
    ]
    await repo.write_sli_values(rows)
    stored = await repo.get_sli_values_for_eval(ev.id)
    assert len(stored) == 1
    assert stored[0].metric_name == "cpu_usage"
    assert stored[0].value == pytest.approx(72.3)
```

- [ ] **Run tests — expect ImportError (red)**

```bash
uv run pytest api/tests/db/test_evaluation_repository.py -m integration -v
```

Expected: `ERROR — ModuleNotFoundError: No module named 'app.modules.quality_gate.repository'`

- [ ] **Create `api/app/modules/quality_gate/repository.py`**

```python
"""Evaluation repository — all DB access for the quality gate module."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Evaluation, EvaluationAnnotation, SLIValue


class EvaluationRepository:
    """Data access layer for evaluations, annotations, SLI values, and trend queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_pending(
        self,
        *,
        name: str,
        start_time: datetime,
        end_time: datetime,
        ingestion_mode: str,
        asset_snapshot: dict[str, Any],
        metadata: dict[str, Any],
        slo_name: str | None = None,
        slo_version: int | None = None,
        adapter_used: str | None = None,
    ) -> Evaluation:
        """Create a new evaluation record in pending status.

        Args:
            name: Test identifier (e.g. "compilation-test").
            start_time: Evaluation window start.
            end_time: Evaluation window end.
            ingestion_mode: One of "pull", "push", "file".
            asset_snapshot: Denormalised asset state at trigger time.
            metadata: Caller-provided key-value pairs.
            slo_name: Named SLO used, if any.
            slo_version: Version of the named SLO, if any.
            adapter_used: Adapter name, if pull mode (e.g. "prometheus").

        Returns:
            Newly created Evaluation in pending status.
        """
        ev = Evaluation(
            id=uuid.uuid4(),
            name=name,
            start_time=start_time,
            end_time=end_time,
            ingestion_mode=ingestion_mode,
            asset_snapshot=asset_snapshot,
            metadata_=metadata,
            slo_name=slo_name,
            slo_version=slo_version,
            adapter_used=adapter_used,
            status="pending",
        )
        self._session.add(ev)
        await self._session.flush()
        return ev

    async def mark_running(self, eval_id: uuid.UUID, worker_id: str) -> None:
        """Transition evaluation to running status, recording worker and start time.

        Args:
            eval_id: Evaluation to update.
            worker_id: Identifier of the worker process claiming this job.
        """
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(
                status="running",
                started_at=datetime.now(tz=timezone.utc),
                job_stats={"worker_id": worker_id},
            )
        )

    async def mark_completed(
        self,
        eval_id: uuid.UUID,
        *,
        result: str,
        score: float,
        slo_yaml: str,
        indicator_results: list[Any],
        compared_evaluation_ids: list[str],
    ) -> None:
        """Write final result and transition to completed.

        Args:
            eval_id: Evaluation to update.
            result: One of "pass", "warning", "fail", "error".
            score: Weighted score 0.0–100.0.
            slo_yaml: Resolved SLO YAML (after variable substitution).
            indicator_results: Full per-SLI breakdown as serialisable list.
            compared_evaluation_ids: IDs of evaluations used for relative criteria.
        """
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(
                status="completed",
                result=result,
                score=score,
                slo_yaml=slo_yaml,
                indicator_results=indicator_results,
                job_stats={"compared_evaluation_ids": compared_evaluation_ids},
            )
        )

    async def mark_failed(
        self, eval_id: uuid.UUID, *, error: str, retry_count: int
    ) -> None:
        """Transition evaluation to failed, recording error info.

        Args:
            eval_id: Evaluation to update.
            error: Error message or exception repr.
            retry_count: How many times this job has been retried.
        """
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(
                status="failed",
                job_stats={"error": error, "retry_count": retry_count},
            )
        )

    async def mark_partial(self, eval_id: uuid.UUID, *, stats: dict[str, Any]) -> None:
        """Transition evaluation to partial — job crashed mid-execution.

        Args:
            eval_id: Evaluation to update.
            stats: Partial execution stats (indicators_attempted, _completed, etc.).
        """
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(status="partial", job_stats=stats)
        )

    async def get(self, eval_id: uuid.UUID) -> Evaluation | None:
        """Fetch a single evaluation with annotations eagerly loaded.

        Args:
            eval_id: Evaluation UUID.

        Returns:
            Evaluation with annotations, or None if not found.
        """
        result = await self._session.execute(
            select(Evaluation)
            .options(selectinload(Evaluation.annotations))
            .where(Evaluation.id == eval_id)
        )
        return result.scalar_one_or_none()

    async def list_evaluations(
        self,
        *,
        name: str | None = None,
        asset_name: str | None = None,
        result: str | None = None,
        from_: datetime | None = None,
        to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Evaluation]:
        """List evaluations with optional filters.

        Args:
            name: Filter by test name.
            asset_name: Filter by asset_snapshot name (JSONB lookup).
            result: Filter by result value ("pass", "warning", "fail", "error").
            from_: Only include evaluations starting at or after this timestamp.
            to: Only include evaluations starting at or before this timestamp.
            limit: Maximum rows to return.
            offset: Number of rows to skip (for pagination).

        Returns:
            List of Evaluation rows, newest first.
        """
        q = select(Evaluation)
        if name:
            q = q.where(Evaluation.name == name)
        if asset_name:
            q = q.where(Evaluation.asset_snapshot["name"].as_string() == asset_name)
        if result:
            q = q.where(Evaluation.result == result)
        if from_:
            q = q.where(Evaluation.start_time >= from_)
        if to:
            q = q.where(Evaluation.start_time <= to)
        q = q.order_by(Evaluation.start_time.desc()).limit(limit).offset(offset)
        rows = await self._session.execute(q)
        return list(rows.scalars().all())

    async def get_baselines(
        self,
        *,
        name: str,
        scope_tags: list[str],
        asset_snapshot: dict[str, Any],
        include_result_with_score: str,
        limit: int,
    ) -> list[Evaluation]:
        """Fetch previous completed evaluations for relative criteria comparison.

        Scoped by test name, result filter, and JSONB tag matching.

        Args:
            name: Test name to match.
            scope_tags: Asset snapshot tag keys to match (e.g. ["os", "arch"]).
            asset_snapshot: Current evaluation's asset snapshot — provides tag values to match.
            include_result_with_score: "pass", "pass_or_warn", or "all".
            limit: Maximum number of baseline evaluations to return.

        Returns:
            Matching completed evaluations ordered by start_time descending.
        """
        q = select(Evaluation).where(
            Evaluation.name == name,
            Evaluation.status == "completed",
            Evaluation.invalidated == False,  # noqa: E712
        )
        if include_result_with_score == "pass":
            q = q.where(Evaluation.result == "pass")
        elif include_result_with_score == "pass_or_warn":
            q = q.where(Evaluation.result.in_(["pass", "warning"]))
        # "all" — no result filter

        # Scope by asset snapshot tags
        current_tags = asset_snapshot.get("tags", {})
        for tag in scope_tags:
            tag_value = current_tags.get(tag)
            if tag_value:
                q = q.where(
                    Evaluation.asset_snapshot[("tags", tag)].as_string() == tag_value
                )

        q = q.order_by(Evaluation.start_time.desc()).limit(limit)
        rows = await self._session.execute(q)
        return list(rows.scalars().all())

    async def find_stuck(self, threshold_seconds: int) -> list[Evaluation]:
        """Find evaluations stuck in running status for longer than the threshold.

        Used by the watchdog to detect and reschedule crashed jobs.

        Args:
            threshold_seconds: Jobs running longer than this (in seconds) are stuck.

        Returns:
            List of stuck Evaluation rows.
        """
        cutoff = datetime.now(tz=timezone.utc) - timedelta(seconds=threshold_seconds)
        result = await self._session.execute(
            select(Evaluation).where(
                Evaluation.status == "running",
                Evaluation.started_at < cutoff,
            )
        )
        return list(result.scalars().all())

    # --- SLI Values ---

    async def write_sli_values(self, rows: list[dict[str, Any]]) -> None:
        """Batch insert SLI value rows.

        Args:
            rows: List of dicts matching SLIValue columns (eval_id, eval_start,
                  metric_name, aggregation, value, asset_name, test_name, os_tag).
        """
        if not rows:
            return
        await self._session.execute(SLIValue.__table__.insert().values(rows))

    async def delete_sli_values(self, eval_id: uuid.UUID) -> None:
        """Delete all SLI values for an evaluation (hard rerun).

        Args:
            eval_id: Evaluation whose SLI values should be deleted.
        """
        await self._session.execute(
            delete(SLIValue).where(SLIValue.eval_id == eval_id)
        )

    async def get_sli_values_for_eval(self, eval_id: uuid.UUID) -> list[SLIValue]:
        """Fetch all SLI values for a given evaluation.

        Args:
            eval_id: Evaluation UUID.

        Returns:
            All SLIValue rows for this evaluation.
        """
        result = await self._session.execute(
            select(SLIValue).where(SLIValue.eval_id == eval_id)
        )
        return list(result.scalars().all())

    async def get_trend(
        self,
        *,
        test_name: str,
        metric_name: str,
        asset_name: str | None = None,
        from_: datetime | None = None,
        to: datetime | None = None,
        result_filter: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return time-series data points for the trend endpoint.

        Args:
            test_name: Test identifier to query.
            metric_name: SLI metric name (e.g. "response_time_p99").
            asset_name: Optional filter by asset name.
            from_: Optional start of time range.
            to: Optional end of time range.
            result_filter: Optional list of result values to include.

        Returns:
            List of {timestamp, value, eval_id, result} dicts, ordered by time ascending.
        """
        q = (
            select(
                SLIValue.eval_start,
                SLIValue.value,
                SLIValue.eval_id,
                Evaluation.result,
            )
            .join(Evaluation, SLIValue.eval_id == Evaluation.id)
            .where(
                SLIValue.test_name == test_name,
                SLIValue.metric_name == metric_name,
                Evaluation.invalidated == False,  # noqa: E712
            )
        )
        if asset_name:
            q = q.where(SLIValue.asset_name == asset_name)
        if from_:
            q = q.where(SLIValue.eval_start >= from_)
        if to:
            q = q.where(SLIValue.eval_start <= to)
        if result_filter:
            q = q.where(Evaluation.result.in_(result_filter))
        q = q.order_by(SLIValue.eval_start)
        rows = await self._session.execute(q)
        return [
            {
                "timestamp": r.eval_start.isoformat(),
                "value": r.value,
                "eval_id": str(r.eval_id),
                "result": r.result,
            }
            for r in rows
        ]

    # --- Annotations ---

    async def add_annotation(
        self,
        eval_id: uuid.UUID,
        *,
        content: str,
        author: str | None = None,
        category: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> EvaluationAnnotation:
        """Append an annotation to an evaluation.

        Args:
            eval_id: Evaluation to annotate.
            content: Note text (required).
            author: Optional identifier of who wrote the annotation.
            category: Optional free label (e.g. "environment", "deployment").
            meta: Optional arbitrary metadata.

        Returns:
            Newly created EvaluationAnnotation.
        """
        ann = EvaluationAnnotation(
            id=uuid.uuid4(),
            evaluation_id=eval_id,
            content=content,
            author=author,
            category=category,
            meta=meta or {},
        )
        self._session.add(ann)
        await self._session.flush()
        return ann

    async def delete_annotation(self, annotation_id: uuid.UUID) -> bool:
        """Delete an annotation by ID.

        Args:
            annotation_id: Annotation to delete.

        Returns:
            True if a row was deleted, False if not found.
        """
        result = await self._session.execute(
            delete(EvaluationAnnotation).where(EvaluationAnnotation.id == annotation_id)
        )
        return result.rowcount > 0  # type: ignore[return-value]
```

- [ ] **Run unit tests (green)**

```bash
uv run pytest api/tests/ -m "not integration" -q
```

Expected: `83 passed` (all previous tests still pass; new tests skipped without DB)

- [ ] **Run mypy**

```bash
uv run mypy api/app/
```

Expected: `Success: no issues found`

- [ ] **[Integration] Run evaluation repository tests against real DB**

```bash
export TEST_DATABASE_URL="postgresql+asyncpg://$QG_DB_USER:$QG_DB_PASSWORD@localhost:5432/quality_gate"
uv run pytest api/tests/db/test_evaluation_repository.py -m integration -v
```

Expected: `8 passed`

- [ ] **Commit**

```bash
git add api/app/modules/quality_gate/repository.py api/tests/db/test_evaluation_repository.py
git commit -m "feat: EvaluationRepository — lifecycle, annotations, SLI values, trend"
```

---

## Task 3.8: Pre-commit and final verification

- [ ] **Run full unit test suite**

```bash
uv run pytest api/tests/ -m "not integration" -q
```

Expected: `85 passed` (83 original + 2 new import smoke tests)

- [ ] **Run pre-commit (ruff + mypy)**

```bash
uv run pre-commit run --all-files
```

Expected: all hooks pass. If ruff reformats any file, `git add` the changed files and re-run.

- [ ] **Final commit if any pre-commit fixes were applied**

```bash
git add -p
git commit -m "style: pre-commit ruff fixes on db layer"
```

---

**Plan complete.** Chunk 4 (queue + worker + reliability) can begin once this is committed.
