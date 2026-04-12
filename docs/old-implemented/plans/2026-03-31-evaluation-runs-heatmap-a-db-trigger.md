# Evaluation Runs — Part A: DB Migration + Trigger Layer

> **Prerequisite:** `docs/superpowers/plans/2026-03-31-binding-model-hard-cut.md` must be fully merged before starting this plan. This plan assumes `slo_bindings` is the only binding source (`slo_link_repo` and `group_link_repo` are already removed).
> **Part B:** `docs/superpowers/plans/2026-03-31-evaluation-runs-heatmap-b-heatmap-frontend.md` covers the heatmap API and all frontend changes.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `evaluations` as a parent table (one per asset+eval_name+period), rename old `evaluations` → `slo_evaluations`, drop `evaluation_batches`, and replace the trigger API with `POST /evaluate` and `POST /evaluate/batch`.

**Architecture:** Hard-cut migration — all existing evaluation data is dropped (not migrated). Old flat `evaluations` table becomes `slo_evaluations` (one per SLO). New `evaluations` parent table aggregates N child SLO evaluations. Each worker job still evaluates one SLO; on completion it checks if all siblings are done and rolls up the parent. New endpoints live under `/evaluate`; old `/evaluations/trigger` etc. can be removed.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async ORM, Alembic, asyncpg, arq, pytest.

---

## File Map

| File | Change |
|---|---|
| `api/alembic/versions/002_evaluation_runs.py` | Create: hard-cut migration |
| `api/app/db/models.py` | Rename `Evaluation` → `SLOEvaluation`; add `EvaluationRun`; remove `EvaluationBatch`; rename child FK columns; rename asset group FK columns |
| `api/app/modules/quality_gate/params.py` | Add `evaluation_id` field to `EvalCreateParams` |
| `api/app/modules/quality_gate/repository.py` | Rename all `Evaluation` → `SLOEvaluation`; update FK column names |
| `api/app/modules/quality_gate/indicator_repository.py` | Rename `evaluation_id` → `slo_evaluation_id` |
| `api/app/modules/quality_gate/sli_repository.py` | Rename `eval_id` → `slo_evaluation_id` |
| `api/app/modules/quality_gate/annotation_repository.py` | Rename `evaluation_id` → `slo_evaluation_id` |
| `api/app/modules/quality_gate/baseline_repository.py` | Rename `Evaluation` → `SLOEvaluation` |
| `api/app/modules/quality_gate/trend_repository.py` | Rename `Evaluation` → `SLOEvaluation` |
| `api/app/modules/quality_gate/presenter.py` | Rename `Evaluation` → `SLOEvaluation` |
| `api/app/modules/quality_gate/re_evaluator.py` | Add `evaluation_id` to `create_pending` calls; rename `Evaluation` → `SLOEvaluation` |
| `api/app/modules/quality_gate/worker.py` | Rename `Evaluation` → `SLOEvaluation`; set `achieved_points`/`total_points`; add `_try_rollup_parent()` |
| Create: `api/app/modules/quality_gate/evaluation_run_repository.py` | CRUD for parent `EvaluationRun` rows |
| `api/app/modules/quality_gate/schemas.py` | Add `EvaluateSingleRequest/Response`, `EvaluateBatchRequest/Response`; remove old batch schemas |
| `api/app/modules/quality_gate/trigger_service.py` | Add `trigger_evaluate()` and `trigger_evaluate_batch()` |
| `api/app/modules/quality_gate/dependencies.py` | Add `eval_run_repo: EvaluationRunRepository` |
| `api/app/modules/quality_gate/router.py` | Add `POST /evaluate`, `POST /evaluate/batch`; remove old trigger endpoints |
| `api/app/modules/assets/repository.py` | Rename `AssetGroupMember.group_id` → `asset_group_id` in queries |
| `clients/python/tropek_client/models.py` | Add `EvaluationRun`; rename trigger methods |
| `clients/python/tropek_client/client.py` | Add `evaluate()` and `evaluate_batch()` replacing old trigger |
| `api/tests/db/test_evaluation_run_repository.py` | New: integration tests for `EvaluationRunRepository` |
| `api/tests/services/test_trigger_evaluate.py` | New: integration tests for new trigger endpoints |

---

## Task 1: DB Migration

**Files:**
- Create: `api/alembic/versions/002_evaluation_runs.py`

- [ ] **Step 1: Write the migration file**

```python
"""evaluation runs — rename evaluations→slo_evaluations, create parent evaluations table.

Revision ID: 002
Revises: 001
Create Date: 2026-03-31

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '002'
down_revision: str | Sequence[str] | None = '001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Hard-cut migration: rename tables, create parent evaluations, drop batches."""
    # Drop evaluation_batches first (no FKs from other tables into it)
    op.drop_index('idx_evaluation_batches_status', table_name='evaluation_batches')
    op.drop_table('evaluation_batches')

    # Hard cut: delete all child rows before schema changes (FK constraints prevent
    # renaming/dropping with data present in some configurations)
    op.execute('DELETE FROM indicator_results')
    op.execute('DELETE FROM evaluation_annotations')
    op.execute('TRUNCATE sli_values')  # hypertable: TRUNCATE cascades to chunks

    # Rename FK columns in child tables BEFORE renaming the parent table.
    # PostgreSQL RENAME COLUMN is safe for FK columns — the constraint stays valid.
    op.execute('ALTER TABLE indicator_results RENAME COLUMN evaluation_id TO slo_evaluation_id')
    op.execute('ALTER TABLE evaluation_annotations RENAME COLUMN evaluation_id TO slo_evaluation_id')
    op.execute('ALTER TABLE sli_values RENAME COLUMN eval_id TO slo_evaluation_id')

    # Rename asset group FK columns (FK naming convention cleanup)
    op.execute('ALTER TABLE asset_group_members RENAME COLUMN group_id TO asset_group_id')
    op.execute('ALTER TABLE asset_group_links RENAME COLUMN parent_group_id TO parent_asset_group_id')
    op.execute('ALTER TABLE asset_group_links RENAME COLUMN child_group_id TO child_asset_group_id')

    # Drop all rows from old evaluations (hard cut — backfill not feasible)
    op.execute('DELETE FROM evaluations')

    # Rename old evaluations → slo_evaluations.
    # FK constraints from child tables auto-update to reference new table name.
    op.rename_table('evaluations', 'slo_evaluations')

    # Rename indexes so new evaluations table can reuse the idx_evaluations_* namespace.
    # Use IF EXISTS to be safe in case some were auto-named differently.
    op.execute('ALTER INDEX IF EXISTS idx_evaluations_evaluation_name RENAME TO idx_slo_evaluations_evaluation_name')
    op.execute('ALTER INDEX IF EXISTS idx_evaluations_asset RENAME TO idx_slo_evaluations_asset')
    op.execute('ALTER INDEX IF EXISTS idx_evaluations_result RENAME TO idx_slo_evaluations_result')
    op.execute('ALTER INDEX IF EXISTS idx_evaluations_start RENAME TO idx_slo_evaluations_start')
    op.execute('ALTER INDEX IF EXISTS idx_evaluations_status RENAME TO idx_slo_evaluations_status')
    op.execute('ALTER INDEX IF EXISTS idx_evaluations_slo RENAME TO idx_slo_evaluations_slo')
    op.execute('ALTER INDEX IF EXISTS idx_evaluations_baseline_lookup RENAME TO idx_slo_evaluations_baseline_lookup')
    op.execute('ALTER INDEX IF EXISTS idx_evaluations_stuck RENAME TO idx_slo_evaluations_stuck')
    op.execute('ALTER INDEX IF EXISTS uq_evaluations_identity RENAME TO uq_slo_evaluations_identity')

    # Create new parent evaluations table (one per asset × eval_name × period)
    op.create_table(
        'evaluations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('asset_id', sa.UUID(), nullable=False),
        sa.Column('eval_name', sa.Text(), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('achieved_points', sa.Integer(), nullable=True),
        sa.Column('total_points', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='RESTRICT'),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','failed')",
            name='ck_evaluations_status',
        ),
        sa.CheckConstraint(
            "result IN ('pass','warning','fail','error') OR result IS NULL",
            name='ck_evaluations_result',
        ),
    )
    op.create_index('idx_evaluations_asset', 'evaluations', ['asset_id'])
    op.create_index('idx_evaluations_status', 'evaluations', ['status'])
    op.create_index(
        'idx_evaluations_period',
        'evaluations',
        ['asset_id', sa.literal_column('period_start DESC')],
    )

    # Add evaluation_id FK + point columns to slo_evaluations.
    # Table is empty (hard cut above), so we can add NOT NULL immediately.
    op.add_column('slo_evaluations', sa.Column('evaluation_id', sa.UUID(), nullable=True))
    op.add_column('slo_evaluations', sa.Column('achieved_points', sa.Integer(), nullable=True))
    op.add_column('slo_evaluations', sa.Column('total_points', sa.Integer(), nullable=True))
    op.execute('ALTER TABLE slo_evaluations ALTER COLUMN evaluation_id SET NOT NULL')
    op.create_foreign_key(
        'fk_slo_evaluations_evaluation_id',
        'slo_evaluations', 'evaluations',
        ['evaluation_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_index('idx_slo_evaluations_evaluation', 'slo_evaluations', ['evaluation_id'])


def downgrade() -> None:
    raise NotImplementedError('downgrade not supported — hard-cut migration, data cannot be restored')
```

- [ ] **Step 2: Start test environment and run migration**

```bash
just test-env
just migrate-test
```

Expected: Alembic reports `Running upgrade 001 -> 002`.

- [ ] **Step 3: Verify schema in test DB**

```bash
uv run --directory api python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os
os.environ['QG_DB_USER'] = 'tropek'
os.environ['QG_DB_PASSWORD'] = 'tropek'
async def check():
    e = create_async_engine('postgresql+asyncpg://tropek:tropek@localhost:5433/tropek_test')
    async with e.connect() as c:
        r = await c.execute(text(\"SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name\"))
        for row in r: print(row[0])
asyncio.run(check())
"
```

Expected output includes: `asset_group_links`, `asset_group_members`, `evaluations`, `slo_evaluations` — but NOT `evaluation_batches`.

- [ ] **Step 4: Commit**

```bash
git add api/alembic/versions/002_evaluation_runs.py
git commit -m "feat(db): add evaluations parent table, rename evaluations→slo_evaluations, drop batches"
```

---

## Task 2: ORM Model Updates

**Files:**
- Modify: `api/app/db/models.py`
- Test: `api/tests/test_db_imports.py`

This task renames the Python class `Evaluation` → `SLOEvaluation`, adds `EvaluationRun` (parent), removes `EvaluationBatch`, renames FK columns on child models, and renames asset group FK columns. All changes must mirror the migration.

- [ ] **Step 1: Write the failing model import tests**

In `api/tests/test_db_imports.py` (or create it if it doesn't exist), add:

```python
def test_slo_evaluation_model_exists():
    from app.db.models import SLOEvaluation
    col_names = {c.name for c in SLOEvaluation.__table__.columns}
    assert 'evaluation_id' in col_names
    assert 'evaluation_name' in col_names
    assert 'slo_name' in col_names
    assert 'achieved_points' in col_names
    assert 'total_points' in col_names
    assert SLOEvaluation.__tablename__ == 'slo_evaluations'


def test_evaluation_run_model_exists():
    from app.db.models import EvaluationRun
    col_names = {c.name for c in EvaluationRun.__table__.columns}
    assert 'id' in col_names
    assert 'asset_id' in col_names
    assert 'eval_name' in col_names
    assert 'status' in col_names
    assert 'result' in col_names
    assert 'achieved_points' in col_names
    assert 'total_points' in col_names
    assert EvaluationRun.__tablename__ == 'evaluations'


def test_evaluation_batch_removed():
    from app.db import models
    assert not hasattr(models, 'EvaluationBatch')


def test_indicator_result_uses_slo_evaluation_id():
    from app.db.models import IndicatorResultRow
    col_names = {c.name for c in IndicatorResultRow.__table__.columns}
    assert 'slo_evaluation_id' in col_names
    assert 'evaluation_id' not in col_names


def test_sli_value_uses_slo_evaluation_id():
    from app.db.models import SLIValue
    col_names = {c.name for c in SLIValue.__table__.columns}
    assert 'slo_evaluation_id' in col_names
    assert 'eval_id' not in col_names


def test_annotation_uses_slo_evaluation_id():
    from app.db.models import EvaluationAnnotation
    col_names = {c.name for c in EvaluationAnnotation.__table__.columns}
    assert 'slo_evaluation_id' in col_names
    assert 'evaluation_id' not in col_names


def test_asset_group_member_uses_asset_group_id():
    from app.db.models import AssetGroupMember
    col_names = {c.name for c in AssetGroupMember.__table__.columns}
    assert 'asset_group_id' in col_names
    assert 'group_id' not in col_names


def test_asset_group_link_uses_renamed_fk_cols():
    from app.db.models import AssetGroupLink
    col_names = {c.name for c in AssetGroupLink.__table__.columns}
    assert 'parent_asset_group_id' in col_names
    assert 'child_asset_group_id' in col_names
    assert 'parent_group_id' not in col_names
    assert 'child_group_id' not in col_names
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
./scripts/api-test.sh --tail 15 tests/test_db_imports.py -v
```

Expected: several FAILED — models not yet updated.

- [ ] **Step 3: Update `api/app/db/models.py`**

Make the following changes (replace the `Evaluation`, `EvaluationAnnotation`, `IndicatorResultRow`, `SLIValue`, `AssetGroupMember`, `AssetGroupLink`, `EvaluationBatch` classes):

**Remove `EvaluationBatch` class entirely** (lines 568–590 in current file).

**Replace `AssetGroupMember`** — rename `group_id` → `asset_group_id`:
```python
class AssetGroupMember(Base):
    """Associates individual assets with an asset group, with optional weight."""

    __tablename__ = 'asset_group_members'
    __table_args__ = (
        Index('idx_asset_group_members_group', 'asset_group_id'),
        Index('idx_asset_group_members_asset', 'asset_id'),
    )

    # fmt: off

    asset_group_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('asset_groups.id', ondelete='CASCADE'), nullable=False, primary_key=True)
    asset_id:       Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('assets.id', ondelete='CASCADE'), nullable=False, primary_key=True)
    weight:         Mapped[float]     = mapped_column(Float, nullable=False, default=1.0)

    # fmt: on
```

**Replace `AssetGroupLink`** — rename `parent_group_id` → `parent_asset_group_id`, `child_group_id` → `child_asset_group_id`:
```python
class AssetGroupLink(Base):
    """Links a child group inside a parent group (group-of-groups)."""

    __tablename__ = 'asset_group_links'
    __table_args__ = (Index('idx_asset_group_links_parent', 'parent_asset_group_id'),)

    # fmt: off

    parent_asset_group_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('asset_groups.id', ondelete='CASCADE'), nullable=False, primary_key=True)
    child_asset_group_id:  Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('asset_groups.id', ondelete='CASCADE'), nullable=False, primary_key=True)
    weight:                Mapped[float]     = mapped_column(Float, nullable=False, default=1.0)

    # fmt: on
```

**Replace `IndicatorResultRow`** — rename `evaluation_id` → `slo_evaluation_id`, FK target → `slo_evaluations`:
```python
class IndicatorResultRow(Base):
    """Normalized indicator result — one row per SLI per SLO evaluation."""

    __tablename__ = 'indicator_results'
    __table_args__ = (
        Index('idx_indicator_results_slo_evaluation', 'slo_evaluation_id'),
        Index('idx_indicator_results_objective_status', 'slo_objective_id', 'status'),
        UniqueConstraint(
            'slo_evaluation_id',
            'slo_objective_id',
            name='uq_indicator_results_eval_objective',
        ),
    )

    # fmt: off
    id:                 Mapped[uuid.UUID]    = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    slo_evaluation_id:  Mapped[uuid.UUID]    = mapped_column(UUID, ForeignKey('slo_evaluations.id', ondelete='CASCADE'), nullable=False)
    slo_objective_id:   Mapped[uuid.UUID]    = mapped_column(UUID, ForeignKey('slo_objectives.id', ondelete='CASCADE'), nullable=False)
    value:              Mapped[float | None] = mapped_column(Float, nullable=True)
    compared_value:     Mapped[float | None] = mapped_column(Float, nullable=True)
    change_absolute:    Mapped[float | None] = mapped_column(Float, nullable=True)
    change_relative_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    status:             Mapped[str]          = mapped_column(Text, nullable=False)
    score:              Mapped[float]        = mapped_column(Float, nullable=False, server_default=text('0'))
    # fmt: on

    objective: Mapped[SLOObjective] = relationship('SLOObjective', lazy='joined')
```

**Replace `SLIValue`** — rename `eval_id` → `slo_evaluation_id`, FK target → `slo_evaluations`:
```python
class SLIValue(Base):
    """TimescaleDB hypertable — one aggregated metric value per SLO evaluation.

    Partitioned by eval_start for efficient time-range queries in Grafana.
    Composite PK required: TimescaleDB needs the partition key in the PK.
    Denormalised columns (asset_name, evaluation_name, os_tag) avoid joins in Grafana SQL.
    """

    __tablename__ = 'sli_values'
    __table_args__ = (Index('idx_sli_values_lookup', 'evaluation_name', 'metric_name', 'eval_start'),)

    # fmt: off
    slo_evaluation_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('slo_evaluations.id'), nullable=False, primary_key=True)
    eval_start:        Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=False, primary_key=True)
    metric_name:       Mapped[str]       = mapped_column(Text, nullable=False, primary_key=True)
    aggregation:       Mapped[str]       = mapped_column(Text, nullable=False, primary_key=True)
    value:             Mapped[float]     = mapped_column(Float, nullable=False)
    asset_name:        Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_name:   Mapped[str | None] = mapped_column(Text, nullable=True)
    os_tag:            Mapped[str | None] = mapped_column(Text, nullable=True)
    # fmt: on
```

**Replace `EvaluationAnnotation`** — rename `evaluation_id` → `slo_evaluation_id`, FK target → `slo_evaluations`, update back_populates:
```python
class EvaluationAnnotation(Base):
    """Append-only contextual note on an SLO evaluation."""

    __tablename__ = 'evaluation_annotations'
    __table_args__ = (Index('idx_annotations_slo_evaluation', 'slo_evaluation_id'),)

    # fmt: off

    id:                Mapped[uuid.UUID]      = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    slo_evaluation_id: Mapped[uuid.UUID]      = mapped_column(UUID, ForeignKey('slo_evaluations.id', ondelete='CASCADE'), nullable=False)
    content:           Mapped[str]            = mapped_column(Text, nullable=False)
    author:            Mapped[str | None]     = mapped_column(Text, nullable=True)
    category:          Mapped[str | None]     = mapped_column(Text, nullable=True)
    tags:              Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    hidden_at:         Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hidden_by:         Mapped[str | None]     = mapped_column(Text, nullable=True)
    hidden_reason:     Mapped[str | None]     = mapped_column(Text, nullable=True)
    created_at:        Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:        Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    slo_evaluation:    Mapped['SLOEvaluation'] = relationship('SLOEvaluation', back_populates='annotations')

    # fmt: on
```

**Replace `Evaluation` with `SLOEvaluation`** — rename class, update `__tablename__`, add `evaluation_id`/`achieved_points`/`total_points`, fix relationships, rename indexes to `slo_evaluations_*`:

```python
class SLOEvaluation(Base):
    """One SLO evaluation — triggered, executed, stored. Child of EvaluationRun."""

    __tablename__ = 'slo_evaluations'
    __table_args__ = (
        Index('idx_slo_evaluations_evaluation_name', 'evaluation_name'),
        Index('idx_slo_evaluations_asset', 'asset_id'),
        Index('idx_slo_evaluations_result', 'result'),
        Index('idx_slo_evaluations_start', 'period_start'),
        Index('idx_slo_evaluations_status', 'status'),
        Index('idx_slo_evaluations_slo', 'slo_name', 'slo_version'),
        Index(
            'idx_slo_evaluations_baseline_lookup',
            'asset_id',
            'slo_name',
            text('period_start DESC'),
            postgresql_where=text("status = 'completed' AND invalidated = false"),
        ),
        Index(
            'idx_slo_evaluations_stuck',
            'status',
            'started_at',
            postgresql_where=text("status = 'running'"),
        ),
        Index(
            'uq_slo_evaluations_identity',
            'asset_id',
            'slo_name',
            'evaluation_name',
            'period_start',
            'period_end',
            unique=True,
            postgresql_where=text("status != 'failed'"),
        ),
        CheckConstraint(
            "status IN ('pending','running','completed','failed','partial')",
            name='ck_slo_evaluations_status',
        ),
        CheckConstraint(
            "ingestion_mode IN ('pull','push','file')",
            name='ck_slo_evaluations_ingestion_mode',
        ),
        CheckConstraint(
            "result IN ('pass','warning','fail','error') OR result IS NULL",
            name='ck_slo_evaluations_result',
        ),
    )

    # fmt: off

    id:                   Mapped[uuid.UUID]      = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    evaluation_id:        Mapped[uuid.UUID]      = mapped_column(UUID, ForeignKey('evaluations.id', ondelete='CASCADE'), nullable=False)
    evaluation_name:      Mapped[str]            = mapped_column(Text, nullable=False)
    asset_id:             Mapped[uuid.UUID]      = mapped_column(UUID, ForeignKey('assets.id', ondelete='RESTRICT'), nullable=False)
    asset_snapshot:       Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    period_start:         Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    period_end:           Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    result:               Mapped[str | None]     = mapped_column(Text, nullable=True)
    score:                Mapped[float | None]   = mapped_column(Float, nullable=True)
    achieved_points:      Mapped[int | None]     = mapped_column(Integer, nullable=True)
    total_points:         Mapped[int | None]     = mapped_column(Integer, nullable=True)
    slo_name:             Mapped[str]            = mapped_column(Text, nullable=False)
    slo_version:          Mapped[int | None]     = mapped_column(Integer, nullable=True)
    sli_name:             Mapped[str | None]     = mapped_column(Text, nullable=True)
    sli_version:          Mapped[int | None]     = mapped_column(Integer, nullable=True)
    data_source_name:     Mapped[str | None]     = mapped_column(Text, nullable=True)
    variables:            Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    ingestion_mode:       Mapped[str]            = mapped_column(Text, nullable=False)
    adapter_used:         Mapped[str | None]     = mapped_column(Text, nullable=True)
    invalidated:          Mapped[bool]           = mapped_column(Boolean, nullable=False, server_default=false(), default=False)
    invalidation_note:    Mapped[str | None]     = mapped_column(Text, nullable=True)
    baseline_pinned_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_unpinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_pin_reason:  Mapped[str | None]     = mapped_column(Text, nullable=True)
    baseline_pin_author:  Mapped[str | None]     = mapped_column(Text, nullable=True)
    original_result:      Mapped[str | None]     = mapped_column(Text, nullable=True)
    override_reason:      Mapped[str | None]     = mapped_column(Text, nullable=True)
    override_author:      Mapped[str | None]     = mapped_column(Text, nullable=True)
    status:               Mapped[str]            = mapped_column(Text, nullable=False, server_default=text("'pending'"), default='pending')
    started_at:           Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job_stats:            Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    created_at:           Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    annotations:          Mapped[list[EvaluationAnnotation]] = relationship('EvaluationAnnotation', back_populates='slo_evaluation', cascade='all, delete-orphan')
    indicator_rows:       Mapped[list[IndicatorResultRow]]   = relationship('IndicatorResultRow', cascade='all, delete-orphan', lazy='selectin')

    # fmt: on
```

**Add `EvaluationRun` class** (new parent, add after `SLOEvaluation`):

```python
class EvaluationRun(Base):
    """Parent evaluation run — one per asset × eval_name × period.

    Aggregates N child SLOEvaluation rows (one per SLO bound to the asset).
    result = worst-case of children; achieved/total points = sum of children.
    """

    __tablename__ = 'evaluations'
    __table_args__ = (
        Index('idx_evaluations_asset', 'asset_id'),
        Index('idx_evaluations_status', 'status'),
        Index('idx_evaluations_period', 'asset_id', text('period_start DESC')),
        CheckConstraint(
            "status IN ('pending','running','completed','failed')",
            name='ck_evaluations_status',
        ),
        CheckConstraint(
            "result IN ('pass','warning','fail','error') OR result IS NULL",
            name='ck_evaluations_result',
        ),
    )

    # fmt: off

    id:              Mapped[uuid.UUID]      = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    asset_id:        Mapped[uuid.UUID]      = mapped_column(UUID, ForeignKey('assets.id', ondelete='RESTRICT'), nullable=False)
    eval_name:       Mapped[str]            = mapped_column(Text, nullable=False)
    period_start:    Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    period_end:      Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    status:          Mapped[str]            = mapped_column(Text, nullable=False, server_default=text("'pending'"), default='pending')
    result:          Mapped[str | None]     = mapped_column(Text, nullable=True)
    achieved_points: Mapped[int | None]     = mapped_column(Integer, nullable=True)
    total_points:    Mapped[int | None]     = mapped_column(Integer, nullable=True)
    created_at:      Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    slo_evaluations: Mapped[list[SLOEvaluation]] = relationship('SLOEvaluation', back_populates='evaluation_run', cascade='all, delete-orphan')

    # fmt: on
```

Also add `evaluation_run` back-reference to `SLOEvaluation` (after the `indicator_rows` field):
```python
    evaluation_run: Mapped['EvaluationRun'] = relationship('EvaluationRun', back_populates='slo_evaluations')
```

- [ ] **Step 4: Run the model tests**

```bash
./scripts/api-test.sh --tail 20 tests/test_db_imports.py -v
```

Expected: all new assertions PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/db/models.py api/tests/test_db_imports.py
git commit -m "feat(models): rename Evaluation→SLOEvaluation, add EvaluationRun parent, remove EvaluationBatch, rename FK columns"
```

---

## Task 3: Update Child Repositories

**Files:**
- Modify: `api/app/modules/quality_gate/indicator_repository.py`
- Modify: `api/app/modules/quality_gate/sli_repository.py`
- Modify: `api/app/modules/quality_gate/annotation_repository.py`

These files reference the old column names. They are small and mechanical to update.

- [ ] **Step 1: Update `indicator_repository.py`**

Replace every occurrence of `evaluation_id` with `slo_evaluation_id`, and `Evaluation` import with `SLOEvaluation`:

```python
"""Repository for normalized indicator_results table."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IndicatorResultRow


class IndicatorRepository:
    """CRUD for per-SLI evaluation results (normalized table)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_insert(
        self,
        slo_evaluation_id: uuid.UUID,
        rows: list[dict[str, Any]],
    ) -> None:
        """Insert indicator result rows for a single SLO evaluation."""
        for row in rows:
            self._session.add(
                IndicatorResultRow(
                    slo_evaluation_id=slo_evaluation_id,
                    slo_objective_id=row['slo_objective_id'],
                    value=row.get('value'),
                    compared_value=row.get('compared_value'),
                    change_absolute=row.get('change_absolute'),
                    change_relative_pct=row.get('change_relative_pct'),
                    status=row['status'],
                    score=row.get('score', 0.0),
                )
            )
        await self._session.flush()

    async def delete_for_evaluation(self, slo_evaluation_id: uuid.UUID) -> None:
        """Delete all indicator rows for a SLO evaluation (used by re-evaluation)."""
        await self._session.execute(
            delete(IndicatorResultRow).where(IndicatorResultRow.slo_evaluation_id == slo_evaluation_id)
        )
        await self._session.flush()
```

- [ ] **Step 2: Update `sli_repository.py`**

Replace `eval_id` with `slo_evaluation_id` in all column references and parameter names. The file currently writes rows like:
```python
{'eval_id': eval_id, 'eval_start': ..., ...}
```
Change to:
```python
{'slo_evaluation_id': slo_evaluation_id, 'eval_start': ..., ...}
```

Also rename any `eval_id` parameter in method signatures to `slo_evaluation_id`.

- [ ] **Step 3: Update `annotation_repository.py`**

Replace `evaluation_id` with `slo_evaluation_id` in all queries and `EvaluationAnnotation` construction. Replace any `Evaluation` import with `SLOEvaluation` if referenced.

- [ ] **Step 4: Run unit tests to catch compilation errors**

```bash
./scripts/api-test.sh --tail 15 tests/ -x -q
```

Expected: tests pass or fail only on missing `evaluation_id` in `create_pending` (not yet updated — that's Task 4).

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/quality_gate/indicator_repository.py api/app/modules/quality_gate/sli_repository.py api/app/modules/quality_gate/annotation_repository.py
git commit -m "feat(repos): rename eval FK columns to slo_evaluation_id in child repositories"
```

---

## Task 4: Update Main Evaluation Repository + Other References

**Files:**
- Modify: `api/app/modules/quality_gate/repository.py`
- Modify: `api/app/modules/quality_gate/baseline_repository.py`
- Modify: `api/app/modules/quality_gate/trend_repository.py`
- Modify: `api/app/modules/quality_gate/presenter.py`
- Modify: `api/app/modules/quality_gate/re_evaluator.py`
- Modify: `api/app/modules/assets/repository.py`

- [ ] **Step 1: Update `repository.py` (EvaluationRepository)**

Replace `from app.db.models import ... Evaluation ...` import with `SLOEvaluation`. Replace all usages of `Evaluation` with `SLOEvaluation`. Example for the `create_pending` method — it constructs `Evaluation(...)` → change to `SLOEvaluation(...)`.

- [ ] **Step 2: Update `baseline_repository.py`**

Replace `Evaluation` import and all usages with `SLOEvaluation`. The queries that reference `Evaluation.asset_id`, `Evaluation.slo_name`, `Evaluation.period_start` etc. should all become `SLOEvaluation.*`.

- [ ] **Step 3: Update `trend_repository.py`**

Replace `Evaluation` import and all usages with `SLOEvaluation`:
```python
from app.db.models import SLOEvaluation, IndicatorResultRow, SLIValue, SLOObjective
```

```python
    async def get_metric_heatmap(self, ...) -> list[SLOEvaluation]:
        q = (
            select(SLOEvaluation)
            .options(
                selectinload(SLOEvaluation.indicator_rows).joinedload(IndicatorResultRow.objective),
            )
            .where(
                SLOEvaluation.asset_id == asset_id,
                SLOEvaluation.status == EvaluationStatus.COMPLETED,
            )
            ...
        )
```

- [ ] **Step 4: Update `presenter.py`**

Replace `Evaluation` type hint with `SLOEvaluation`. The `build_detail()` and `build_summary()` functions accept `ev: Evaluation` — change signature to `ev: SLOEvaluation`.

- [ ] **Step 5: Update `re_evaluator.py`**

Replace `Evaluation` import/usage with `SLOEvaluation`. The re-evaluator also calls `eval_repo.create_pending()` — that will need `evaluation_id` once Task 5 is done. For now, search for and note all `create_pending` call sites that need updating.

- [ ] **Step 6: Update `api/app/modules/assets/repository.py`**

Search for any reference to `AssetGroupMember.group_id` or `AssetGroupLink.parent_group_id`/`child_group_id` and rename to `asset_group_id`/`parent_asset_group_id`/`child_asset_group_id`.

```bash
grep -n "group_id\|parent_group_id\|child_group_id" api/app/modules/assets/repository.py
```

Update each reference found.

- [ ] **Step 7: Run tests**

```bash
./scripts/api-test.sh --tail 20 tests/ -x -q
```

Expected: compilation errors resolved; some tests may fail because `create_pending` still needs `evaluation_id`. Note which tests fail and why.

- [ ] **Step 8: Commit**

```bash
git add api/app/modules/quality_gate/repository.py api/app/modules/quality_gate/baseline_repository.py api/app/modules/quality_gate/trend_repository.py api/app/modules/quality_gate/presenter.py api/app/modules/quality_gate/re_evaluator.py api/app/modules/assets/repository.py
git commit -m "feat(repos): rename Evaluation→SLOEvaluation throughout repository layer"
```

---

## Task 5: Update EvalCreateParams + EvaluationRepository.create_pending

**Files:**
- Modify: `api/app/modules/quality_gate/params.py`
- Modify: `api/app/modules/quality_gate/repository.py`
- Modify: `api/app/modules/quality_gate/worker.py` (update `_write_indicator_rows` call)
- Modify: `api/app/modules/quality_gate/re_evaluator.py` (update `create_pending` call)

`SLOEvaluation` now requires `evaluation_id`. Every `create_pending()` call must supply it.

- [ ] **Step 1: Write failing test**

In `api/tests/engine/test_params.py` (or create it):

```python
def test_eval_create_params_requires_evaluation_id():
    from app.modules.quality_gate.params import EvalCreateParams
    import uuid
    from datetime import datetime, timezone
    p = EvalCreateParams(
        evaluation_id=uuid.uuid4(),
        evaluation_name='daily',
        period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ingestion_mode='pull',
        asset_snapshot={},
        asset_id=uuid.uuid4(),
        slo_name='my-slo',
    )
    assert p.evaluation_id is not None
```

- [ ] **Step 2: Run test to confirm failure**

```bash
./scripts/api-test.sh --tail 10 tests/engine/test_params.py -v
```

Expected: FAILED — `evaluation_id` field doesn't exist yet.

- [ ] **Step 3: Update `params.py`**

Add `evaluation_id` as a required field:

```python
class EvalCreateParams(BaseModel):
    """Parameters for EvaluationRepository.create_pending()."""

    evaluation_id: uuid.UUID
    evaluation_name: str
    period_start: datetime
    period_end: datetime
    ingestion_mode: str
    asset_snapshot: dict[str, object]
    variables: dict[str, str] = Field(default_factory=dict)
    asset_id: uuid.UUID
    slo_name: str
    slo_version: int | None = None
    adapter_used: str | None = None
    sli_name: str | None = None
    sli_version: int | None = None
    data_source_name: str | None = None
```

- [ ] **Step 4: Update `repository.py` — create_pending uses evaluation_id**

In `EvaluationRepository.create_pending()`, set `evaluation_id=params.evaluation_id` on the `SLOEvaluation` constructor:

```python
ev = SLOEvaluation(
    id=uuid.uuid4(),
    evaluation_id=params.evaluation_id,
    evaluation_name=params.evaluation_name,
    ...  # rest unchanged
)
```

- [ ] **Step 5: Update worker.py `_write_indicator_rows`**

The call site in `worker.py`:
```python
await indicator_repo.bulk_insert(eval_id, rows)
```
Change to:
```python
await indicator_repo.bulk_insert(eval_id, rows)  # eval_id is now slo_evaluation_id
```

Also update `_write_indicator_rows` signature:
```python
async def _write_indicator_rows(
    log: structlog.stdlib.BoundLogger,
    session: AsyncSession,
    slo_evaluation_id: uuid.UUID,
    slo_def: SLODefinition,
    indicator_results: list[Any],
) -> None:
    indicator_repo = IndicatorRepository(session)
    obj_lookup = {obj.sli: obj.id for obj in slo_def.objectives}
    rows = []
    for ir in indicator_results:
        obj_id = obj_lookup.get(ir.metric)
        if obj_id is None:
            log.warning('no objective match for metric', metric=ir.metric)
            continue
        rows.append({
            'slo_objective_id': obj_id,
            'value': ir.value,
            'compared_value': ir.compared_value,
            'change_absolute': ir.change_absolute,
            'change_relative_pct': ir.change_relative_pct,
            'status': ir.status,
            'score': ir.score,
        })
    if rows:
        await indicator_repo.bulk_insert(slo_evaluation_id, rows)
```

And in `run_evaluation()`, the call becomes:
```python
await _write_indicator_rows(log, session, eval_id, slo_def, eval_result.indicator_results)
```

(The variable `eval_id` in the worker refers to the SLO evaluation ID — rename it to `slo_eval_id` for clarity.)

- [ ] **Step 6: Update re_evaluator.py**

The re-evaluator creates a new `SLOEvaluation` via `create_pending`. It must supply `evaluation_id`. For now, create a new `EvaluationRun` inline or look up the existing one. The spec doesn't cover re-evaluation of the new model — pass a placeholder UUID for now and add a TODO comment:

```python
# TODO: re_evaluator should create a new EvaluationRun parent first.
# For now create a transient run_id — re_evaluate will be reworked in a follow-on.
run_id = uuid.uuid4()
params = EvalCreateParams(
    evaluation_id=run_id,
    ...
)
```

- [ ] **Step 7: Run tests**

```bash
./scripts/api-test.sh --tail 20 tests/ -x -q
```

Expected: test_params.py passes; no import errors.

- [ ] **Step 8: Commit**

```bash
git add api/app/modules/quality_gate/params.py api/app/modules/quality_gate/repository.py api/app/modules/quality_gate/worker.py api/app/modules/quality_gate/re_evaluator.py
git commit -m "feat(params): add evaluation_id to EvalCreateParams, update create_pending and worker"
```

---

## Task 6: Create EvaluationRunRepository

**Files:**
- Create: `api/app/modules/quality_gate/evaluation_run_repository.py`
- Test: `api/tests/db/test_evaluation_run_repository.py`

- [ ] **Step 1: Write the failing integration test**

```python
"""Integration tests for EvaluationRunRepository."""

import uuid
from datetime import datetime, timezone

import pytest

from app.db.models import Asset, AssetType, EvaluationRun
from app.modules.quality_gate.evaluation_run_repository import EvaluationRunRepository


@pytest.fixture
async def asset(db_session):
    asset_type = AssetType(name='vm', is_default=True)
    db_session.add(asset_type)
    a = Asset(name='test-asset', type_name='vm')
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.integration
async def test_create_and_get(db_session, asset):
    repo = EvaluationRunRepository(db_session)
    start = datetime(2026, 1, 15, tzinfo=timezone.utc)
    end = datetime(2026, 1, 16, tzinfo=timezone.utc)

    run = await repo.create(
        asset_id=asset.id,
        eval_name='daily',
        period_start=start,
        period_end=end,
    )
    await db_session.flush()

    fetched = await repo.get_by_id(run.id)
    assert fetched is not None
    assert fetched.eval_name == 'daily'
    assert fetched.status == 'pending'
    assert fetched.result is None


@pytest.mark.integration
async def test_rollup_worst_case_result(db_session, asset):
    from app.db.models import SLOEvaluation
    repo = EvaluationRunRepository(db_session)
    start = datetime(2026, 1, 15, tzinfo=timezone.utc)
    end = datetime(2026, 1, 16, tzinfo=timezone.utc)

    run = await repo.create(asset_id=asset.id, eval_name='daily', period_start=start, period_end=end)
    await db_session.flush()

    # Add two child SLO evaluations: pass + warning
    for result, pts_a, pts_t in [('pass', 10, 10), ('warning', 8, 10)]:
        slo_ev = SLOEvaluation(
            evaluation_id=run.id,
            evaluation_name='daily',
            asset_id=asset.id,
            asset_snapshot={},
            period_start=start,
            period_end=end,
            slo_name=f'slo-{result}',
            ingestion_mode='pull',
            status='completed',
            result=result,
            score=float(pts_a),
            achieved_points=pts_a,
            total_points=pts_t,
        )
        db_session.add(slo_ev)
    await db_session.flush()

    rolled_up = await repo.rollup_if_all_done(run.id)
    assert rolled_up is not None
    assert rolled_up.status == 'completed'
    assert rolled_up.result == 'warning'   # worst-case
    assert rolled_up.achieved_points == 18
    assert rolled_up.total_points == 20


@pytest.mark.integration
async def test_rollup_skips_when_not_all_done(db_session, asset):
    from app.db.models import SLOEvaluation
    repo = EvaluationRunRepository(db_session)
    start = datetime(2026, 1, 15, tzinfo=timezone.utc)
    end = datetime(2026, 1, 16, tzinfo=timezone.utc)

    run = await repo.create(asset_id=asset.id, eval_name='daily', period_start=start, period_end=end)
    await db_session.flush()

    # One done, one still running
    for status, result in [('completed', 'pass'), ('running', None)]:
        slo_ev = SLOEvaluation(
            evaluation_id=run.id,
            evaluation_name='daily',
            asset_id=asset.id,
            asset_snapshot={},
            period_start=start,
            period_end=end,
            slo_name=f'slo-{status}',
            ingestion_mode='pull',
            status=status,
            result=result,
        )
        db_session.add(slo_ev)
    await db_session.flush()

    result = await repo.rollup_if_all_done(run.id)
    assert result is None  # not all done
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
./scripts/api-test.sh --tail 10 tests/db/test_evaluation_run_repository.py -v -m integration
```

Expected: ImportError — `evaluation_run_repository` module not found.

- [ ] **Step 3: Create `evaluation_run_repository.py`**

```python
"""Repository for parent EvaluationRun CRUD and child result rollup."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvaluationRun, SLOEvaluation

_RESULT_RANK: dict[str, int] = {'pass': 0, 'warning': 1, 'fail': 2, 'error': 3}


class EvaluationRunRepository:
    """Data access for parent EvaluationRun rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        asset_id: uuid.UUID,
        eval_name: str,
        period_start: datetime,
        period_end: datetime,
    ) -> EvaluationRun:
        """Create a new pending EvaluationRun."""
        run = EvaluationRun(
            id=uuid.uuid4(),
            asset_id=asset_id,
            eval_name=eval_name,
            period_start=period_start,
            period_end=period_end,
            status='pending',
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_by_id(self, run_id: uuid.UUID) -> EvaluationRun | None:
        """Fetch an EvaluationRun by primary key."""
        return await self._session.get(EvaluationRun, run_id)

    async def mark_running(self, run_id: uuid.UUID) -> None:
        """Transition status to running (first child started)."""
        await self._session.execute(
            update(EvaluationRun)
            .where(EvaluationRun.id == run_id)
            .values(status='running')
        )

    async def rollup_if_all_done(self, run_id: uuid.UUID) -> EvaluationRun | None:
        """Aggregate child results if all SLO evaluations are completed or failed.

        Returns the updated EvaluationRun if rollup happened, None if children
        are still in progress.
        """
        q = select(SLOEvaluation).where(SLOEvaluation.evaluation_id == run_id)
        result = await self._session.execute(q)
        children = list(result.scalars().all())

        if not children:
            return None

        pending_statuses = {'pending', 'running', 'partial'}
        if any(c.status in pending_statuses for c in children):
            return None  # not all done yet

        worst_result: str | None = None
        achieved = 0
        total = 0
        for child in children:
            if child.result:
                if worst_result is None or _RESULT_RANK.get(child.result, 0) > _RESULT_RANK.get(worst_result, 0):
                    worst_result = child.result
            achieved += child.achieved_points or 0
            total += child.total_points or 0

        await self._session.execute(
            update(EvaluationRun)
            .where(EvaluationRun.id == run_id)
            .values(
                status='completed',
                result=worst_result,
                achieved_points=achieved or None,
                total_points=total or None,
            )
        )
        return await self.get_by_id(run_id)
```

- [ ] **Step 4: Run the integration tests**

```bash
./scripts/api-test.sh --tail 20 tests/db/test_evaluation_run_repository.py -v -m integration
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/quality_gate/evaluation_run_repository.py api/tests/db/test_evaluation_run_repository.py
git commit -m "feat(repo): add EvaluationRunRepository with rollup_if_all_done"
```

---

## Task 7: Add Worker Rollup + achieved_points

**Files:**
- Modify: `api/app/modules/quality_gate/worker.py`

The worker now needs to:
1. Set `achieved_points` and `total_points` on the `SLOEvaluation` when marking complete
2. Call `rollup_if_all_done` on the parent `EvaluationRun` after each child finishes

- [ ] **Step 1: Write the failing unit test**

In `api/tests/engine/test_worker_rollup.py`:

```python
"""Unit tests for worker rollup logic."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.quality_gate.worker import _try_rollup_parent


@pytest.mark.asyncio
async def test_try_rollup_parent_calls_repository():
    mock_session = MagicMock()
    mock_repo = AsyncMock()
    mock_repo.rollup_if_all_done.return_value = None  # not all done

    with patch(
        'app.modules.quality_gate.worker.EvaluationRunRepository',
        return_value=mock_repo,
    ):
        run_id = uuid.uuid4()
        await _try_rollup_parent(mock_session, run_id, MagicMock())
        mock_repo.rollup_if_all_done.assert_awaited_once_with(run_id)
```

- [ ] **Step 2: Run test to confirm failure**

```bash
./scripts/api-test.sh --tail 10 tests/engine/test_worker_rollup.py -v
```

Expected: FAILED — `_try_rollup_parent` not found.

- [ ] **Step 3: Update `worker.py`**

Add import at top:
```python
from app.modules.quality_gate.evaluation_run_repository import EvaluationRunRepository
```

Add the `_try_rollup_parent` function:
```python
async def _try_rollup_parent(
    session: AsyncSession,
    evaluation_id: uuid.UUID,
    log: structlog.stdlib.BoundLogger,
) -> None:
    """Rollup parent EvaluationRun if all child SLOEvaluations are done."""
    run_repo = EvaluationRunRepository(session)
    rolled = await run_repo.rollup_if_all_done(evaluation_id)
    if rolled is not None:
        log.info(
            'parent evaluation run completed',
            evaluation_id=str(evaluation_id),
            result=rolled.result,
            achieved_points=rolled.achieved_points,
            total_points=rolled.total_points,
        )
```

Update `run_evaluation()` — rename `eval_id` variable to `slo_eval_id` and add `achieved_points`/`total_points` to `mark_completed`. Also add the rollup call at the end. Find the section that marks the evaluation complete:

```python
# Compute achieved/total points from indicator results
achieved_points = sum(int(ir.score) for ir in eval_result.indicator_results)
total_points = sum(obj.weight for obj in slo.objectives)

await repo.mark_completed(
    slo_eval_id,
    result=eval_result.result,
    score=eval_result.score,
    achieved_points=achieved_points,
    total_points=total_points,
    slo_name=ev.slo_name,
    slo_version=ev.slo_version,
    job_stats={
        'fetch_errors': fetch_errors,
        'total_score_pass_threshold': slo_def.total_score_pass_threshold,
        'total_score_warning_threshold': slo_def.total_score_warning_threshold,
        **({'sli_metadata': sli_metadata} if sli_metadata else {}),
    },
    compared_evaluation_ids=compared_eval_ids,
)
```

Also update `repo.mark_completed` signature in `repository.py` to accept `achieved_points` and `total_points` and write them to the row.

After all writes and the final `log.info('evaluation completed', ...)`, add:
```python
# Rollup parent EvaluationRun if all siblings are done
await _try_rollup_parent(session, ev.evaluation_id, log)
```

- [ ] **Step 4: Update `repository.py` mark_completed signature**

Add `achieved_points: int | None = None` and `total_points: int | None = None` parameters to `mark_completed()`. Include them in the `update()` values:
```python
.values(
    status=EvaluationStatus.COMPLETED,
    result=result,
    score=score,
    achieved_points=achieved_points,
    total_points=total_points,
    ...
)
```

- [ ] **Step 5: Run the rollup test**

```bash
./scripts/api-test.sh --tail 10 tests/engine/test_worker_rollup.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app/modules/quality_gate/worker.py api/app/modules/quality_gate/repository.py api/tests/engine/test_worker_rollup.py
git commit -m "feat(worker): add achieved_points/total_points to mark_completed, add parent evaluation rollup"
```

---

## Task 8: New Trigger Schemas

**Files:**
- Modify: `api/app/modules/quality_gate/schemas.py`

- [ ] **Step 1: Write the failing test**

In `api/tests/engine/test_trigger_schemas.py`:

```python
from datetime import datetime, timezone
import uuid


def test_evaluate_single_request_schema():
    from app.modules.quality_gate.schemas import EvaluateSingleRequest
    req = EvaluateSingleRequest(
        asset_name='checkout-api',
        eval_name='daily-evaluation',
        period_start=datetime(2026, 1, 15, tzinfo=timezone.utc),
        period_end=datetime(2026, 1, 15, 23, 59, 59, tzinfo=timezone.utc),
    )
    assert req.asset_name == 'checkout-api'
    assert req.eval_name == 'daily-evaluation'
    assert req.variables == {}


def test_evaluate_single_response_schema():
    from app.modules.quality_gate.schemas import EvaluateSingleResponse
    r = EvaluateSingleResponse(
        evaluation_id=uuid.uuid4(),
        slo_evaluation_ids=[uuid.uuid4(), uuid.uuid4()],
    )
    assert len(r.slo_evaluation_ids) == 2


def test_evaluate_batch_request_by_date():
    from app.modules.quality_gate.schemas import EvaluateBatchRequest, BatchPeriod
    req = EvaluateBatchRequest(
        mode='by_date',
        asset_name='checkout-api',
        eval_name='daily',
        periods=[
            BatchPeriod(
                period_start=datetime(2026, 1, 15, tzinfo=timezone.utc),
                period_end=datetime(2026, 1, 16, tzinfo=timezone.utc),
            ),
        ],
    )
    assert req.mode == 'by_date'
    assert req.asset_name == 'checkout-api'
    assert req.asset_names is None


def test_evaluate_batch_request_by_asset():
    from app.modules.quality_gate.schemas import EvaluateBatchRequest
    from datetime import timezone
    req = EvaluateBatchRequest(
        mode='by_asset',
        asset_names=['vm-01', 'vm-02'],
        eval_name='post-deploy',
        period_start=datetime(2026, 1, 15, 14, tzinfo=timezone.utc),
        period_end=datetime(2026, 1, 15, 15, tzinfo=timezone.utc),
    )
    assert req.mode == 'by_asset'
    assert len(req.asset_names) == 2


def test_evaluate_batch_response():
    from app.modules.quality_gate.schemas import EvaluateBatchResponse
    r = EvaluateBatchResponse(
        evaluation_ids=[uuid.uuid4(), uuid.uuid4()],
        slo_evaluation_ids=[uuid.uuid4()],
    )
    assert len(r.evaluation_ids) == 2
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
./scripts/api-test.sh --tail 10 tests/engine/test_trigger_schemas.py -v
```

Expected: ImportError.

- [ ] **Step 3: Add new schemas to `schemas.py`**

Add after the existing schemas (keep old schemas for backward compatibility of GET endpoints etc.):

```python
class EvaluateSingleRequest(BaseModel):
    """Request body for POST /evaluate."""

    asset_name: str
    eval_name: str
    period_start: datetime
    period_end: datetime
    variables: dict[str, str] = {}


class EvaluateSingleResponse(BaseModel):
    """Response from POST /evaluate."""

    evaluation_id: uuid.UUID
    slo_evaluation_ids: list[uuid.UUID]


class BatchPeriod(BaseModel):
    """A single period window for by_date batch mode."""

    period_start: datetime
    period_end: datetime


class EvaluateBatchRequest(BaseModel):
    """Request body for POST /evaluate/batch.

    mode='by_date': same asset, multiple time windows (asset_name + periods required)
    mode='by_asset': same window, multiple assets (asset_names + period_start/end required)
    """

    mode: str  # 'by_date' | 'by_asset'
    # by_date fields
    asset_name: str | None = None
    periods: list[BatchPeriod] | None = None
    # by_asset fields
    asset_names: list[str] | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    # common
    eval_name: str
    variables: dict[str, str] = {}


class EvaluateBatchResponse(BaseModel):
    """Response from POST /evaluate/batch."""

    evaluation_ids: list[uuid.UUID]
    slo_evaluation_ids: list[uuid.UUID]
```

- [ ] **Step 4: Run tests**

```bash
./scripts/api-test.sh --tail 10 tests/engine/test_trigger_schemas.py -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/quality_gate/schemas.py api/tests/engine/test_trigger_schemas.py
git commit -m "feat(schemas): add EvaluateSingleRequest/Response, EvaluateBatchRequest/Response"
```

---

## Task 9: New Trigger Methods in TriggerService

**Files:**
- Modify: `api/app/modules/quality_gate/trigger_service.py`
- Modify: `api/app/modules/quality_gate/dependencies.py`

- [ ] **Step 1: Add `eval_run_repo` to QualityGateRepos**

In `dependencies.py`:

```python
from app.modules.quality_gate.evaluation_run_repository import EvaluationRunRepository

@dataclass
class QualityGateRepos:
    """Bundle of all repositories needed by quality gate endpoints."""

    eval_repo: EvaluationRepository
    eval_run_repo: EvaluationRunRepository   # NEW
    annotation_repo: AnnotationRepository
    sli_repo: SLIValueRepository
    trend_repo: TrendRepository
    baseline_repo: BaselineRepository
    asset_repo: AssetRepository
    asset_group_repo: AssetGroupRepository
    binding_repo: SLOBindingRepository
    sli_def_repo: SLIRepository
    slo_repo: SLORepository
    ds_repo: DataSourceRepository
    session: AsyncSession
```

In `get_qg_repos()`, add:
```python
eval_run_repo=EvaluationRunRepository(session),
```

Also remove `slo_link_repo` and `group_link_repo` if still present (should be gone after binding hard-cut plan).

- [ ] **Step 2: Add `trigger_evaluate` and `trigger_evaluate_batch` to TriggerService**

In `trigger_service.py`, add imports:
```python
from app.modules.quality_gate.evaluation_run_repository import EvaluationRunRepository
from app.modules.quality_gate.schemas import (
    EvaluateBatchRequest,
    EvaluateBatchResponse,
    EvaluateSingleRequest,
    EvaluateSingleResponse,
)
```

Add `trigger_evaluate` method:
```python
async def trigger_evaluate(self, request: EvaluateSingleRequest) -> EvaluateSingleResponse:
    """Create parent EvaluationRun + one SLOEvaluation per SLO binding. Enqueue all."""
    asset = await self._repos.asset_repo.get_by_name(request.asset_name)
    if asset is None:
        raise AssetNotFoundError(f"asset '{request.asset_name}' not found")

    group_ids = await self._repos.asset_group_repo.list_group_ids_for_asset(asset.id)
    slo_names = await resolve_all_slos_for_asset(
        asset_id=asset.id,
        binding_repo=self._repos.binding_repo,
        group_ids=group_ids,
    )
    if not slo_names:
        raise EvaluationError(f"no slo bindings found for asset '{request.asset_name}'")

    run = await self._repos.eval_run_repo.create(
        asset_id=asset.id,
        eval_name=request.eval_name,
        period_start=request.period_start,
        period_end=request.period_end,
    )

    slo_eval_ids: list[uuid.UUID] = []
    for slo_name in slo_names:
        try:
            ctx = await resolve_single_trigger(
                asset_name=request.asset_name,
                slo_name=slo_name,
                asset_repo=self._repos.asset_repo,
                sli_repo=self._repos.sli_def_repo,
                slo_repo=self._repos.slo_repo,
                ds_repo=self._repos.ds_repo,
                binding_repo=self._repos.binding_repo,
            )
        except EvaluationError:
            continue

        slo_ev = await self._repos.eval_repo.create_pending(
            EvalCreateParams(
                evaluation_id=run.id,
                evaluation_name=request.eval_name,
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
                sli_name=ctx.sli_name,
                sli_version=ctx.sli_version,
                data_source_name=ctx.data_source_name,
                adapter_used=ctx.adapter_type,
            )
        )
        slo_eval_ids.append(slo_ev.id)

    await self._repos.session.commit()

    for eid in slo_eval_ids:
        await self._pool.enqueue_job('run_evaluation_job', str(eid))

    return EvaluateSingleResponse(evaluation_id=run.id, slo_evaluation_ids=slo_eval_ids)
```

Add `trigger_evaluate_batch` method:
```python
async def trigger_evaluate_batch(self, request: EvaluateBatchRequest) -> EvaluateBatchResponse:
    """Batch evaluation: by_date (one asset, many periods) or by_asset (many assets, one period)."""
    if request.mode == 'by_date':
        if not request.asset_name or not request.periods:
            raise EvaluationError("by_date mode requires asset_name and periods")
        pairs: list[tuple[str, datetime, datetime]] = [
            (request.asset_name, p.period_start, p.period_end)
            for p in request.periods
        ]
    elif request.mode == 'by_asset':
        if not request.asset_names or not request.period_start or not request.period_end:
            raise EvaluationError("by_asset mode requires asset_names, period_start, period_end")
        pairs = [
            (name, request.period_start, request.period_end)
            for name in request.asset_names
        ]
    else:
        raise EvaluationError(f"unknown batch mode '{request.mode}'")

    all_run_ids: list[uuid.UUID] = []
    all_slo_eval_ids: list[uuid.UUID] = []

    for asset_name, period_start, period_end in pairs:
        single_req = EvaluateSingleRequest(
            asset_name=asset_name,
            eval_name=request.eval_name,
            period_start=period_start,
            period_end=period_end,
            variables=request.variables,
        )
        resp = await self.trigger_evaluate(single_req)
        all_run_ids.append(resp.evaluation_id)
        all_slo_eval_ids.extend(resp.slo_evaluation_ids)

    return EvaluateBatchResponse(
        evaluation_ids=all_run_ids,
        slo_evaluation_ids=all_slo_eval_ids,
    )
```

- [ ] **Step 3: Run existing trigger tests**

```bash
./scripts/api-test.sh --tail 20 tests/services/test_trigger_service.py -v
```

Expected: tests that rely on old `TriggerRequest` schemas may fail — note which and update them next step.

- [ ] **Step 4: Commit**

```bash
git add api/app/modules/quality_gate/trigger_service.py api/app/modules/quality_gate/dependencies.py
git commit -m "feat(trigger): add trigger_evaluate and trigger_evaluate_batch to TriggerService"
```

---

## Task 10: New Router Endpoints

**Files:**
- Modify: `api/app/modules/quality_gate/router.py`
- Test: `api/tests/services/test_trigger_evaluate.py`

- [ ] **Step 1: Write the failing integration test**

```python
"""Integration tests for POST /evaluate and POST /evaluate/batch."""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_evaluate_single_creates_run_and_children(client: AsyncClient, seeded_asset_with_slo_binding):
    """POST /evaluate creates one EvaluationRun + one SLOEvaluation per bound SLO."""
    asset_name, slo_names = seeded_asset_with_slo_binding

    resp = await client.post('/api/evaluate', json={
        'asset_name': asset_name,
        'eval_name': 'ci-check',
        'period_start': '2026-01-15T00:00:00Z',
        'period_end': '2026-01-15T23:59:59Z',
    })
    assert resp.status_code == 201
    body = resp.json()
    assert 'evaluation_id' in body
    assert len(body['slo_evaluation_ids']) == len(slo_names)


@pytest.mark.integration
async def test_evaluate_batch_by_date(client: AsyncClient, seeded_asset_with_slo_binding):
    asset_name, _ = seeded_asset_with_slo_binding

    resp = await client.post('/api/evaluate/batch', json={
        'mode': 'by_date',
        'asset_name': asset_name,
        'eval_name': 'daily',
        'periods': [
            {'period_start': '2026-01-15T00:00:00Z', 'period_end': '2026-01-15T23:59:59Z'},
            {'period_start': '2026-01-16T00:00:00Z', 'period_end': '2026-01-16T23:59:59Z'},
        ],
    })
    assert resp.status_code == 201
    body = resp.json()
    assert len(body['evaluation_ids']) == 2


@pytest.mark.integration
async def test_evaluate_unknown_asset_returns_404(client: AsyncClient):
    resp = await client.post('/api/evaluate', json={
        'asset_name': 'no-such-asset',
        'eval_name': 'test',
        'period_start': '2026-01-15T00:00:00Z',
        'period_end': '2026-01-15T23:59:59Z',
    })
    assert resp.status_code == 404
```

Note: `seeded_asset_with_slo_binding` is a test fixture you'll need to add to `conftest.py` that creates an asset + at least one `SLOBinding` + all the required SLO/SLI/DataSource definitions. Model it on the existing seeding fixtures in `api/tests/db/conftest.py`.

- [ ] **Step 2: Add endpoints to `router.py`**

Add these two endpoints (keep existing endpoints for backward compat on GET routes):

```python
@router.post('/evaluate', response_model=EvaluateSingleResponse, status_code=201)
async def evaluate_asset(
    body: EvaluateSingleRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> EvaluateSingleResponse:
    """Trigger evaluation for all SLOs bound to an asset."""
    service = TriggerService(repos, arq_pool)
    return await service.trigger_evaluate(body)


@router.post('/evaluate/batch', response_model=EvaluateBatchResponse, status_code=201)
async def evaluate_batch(
    body: EvaluateBatchRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> EvaluateBatchResponse:
    """Trigger batch evaluations (by_date or by_asset mode)."""
    service = TriggerService(repos, arq_pool)
    return await service.trigger_evaluate_batch(body)
```

Add the new schema imports at the top of `router.py`:
```python
from app.modules.quality_gate.schemas import (
    ...existing imports...,
    EvaluateSingleRequest,
    EvaluateSingleResponse,
    EvaluateBatchRequest,
    EvaluateBatchResponse,
)
```

Remove old endpoints that are no longer needed:
- `POST /evaluations` (`trigger_evaluation` — uses old `TriggerRequest`)
- `POST /evaluations/asset` (`trigger_asset`)
- `POST /evaluations/batch` (`trigger_batch`)

Keep all GET and PATCH endpoints under `/evaluations/{eval_id}`.

- [ ] **Step 3: Run the integration tests**

```bash
just test-env
./scripts/api-test.sh --tail 30 tests/services/test_trigger_evaluate.py -v -m integration
```

Expected: PASS.

- [ ] **Step 4: Run full test suite**

```bash
./scripts/api-test.sh --tail 20
```

Expected: all tests pass (or note any pre-existing failures unrelated to this work).

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/quality_gate/router.py api/tests/services/test_trigger_evaluate.py
git commit -m "feat(api): add POST /evaluate and POST /evaluate/batch endpoints, remove old trigger endpoints"
```

---

## Task 11: Python Client Update

**Files:**
- Modify: `clients/python/tropek_client/models.py`
- Modify: `clients/python/tropek_client/client.py`
- Modify: `clients/python/tests/test_client.py`

- [ ] **Step 1: Add `EvaluationRun` model to `models.py`**

```python
@dataclass
class EvaluationRun:
    """Parent evaluation run — aggregates N SLO evaluations."""
    evaluation_id: str
    slo_evaluation_ids: list[str]
```

Remove `EvaluationBatch` model if present.

- [ ] **Step 2: Update `client.py`**

Replace the old trigger methods (`trigger()`, `trigger_asset()`, `trigger_batch()`) with:

```python
async def evaluate(
    self,
    asset_name: str,
    eval_name: str,
    period_start: str,
    period_end: str,
    variables: dict[str, str] | None = None,
) -> dict:
    """POST /evaluate — trigger all SLOs for an asset."""
    return await self._post('/evaluate', {
        'asset_name': asset_name,
        'eval_name': eval_name,
        'period_start': period_start,
        'period_end': period_end,
        'variables': variables or {},
    })

async def evaluate_batch(
    self,
    mode: str,
    eval_name: str,
    *,
    asset_name: str | None = None,
    periods: list[dict] | None = None,
    asset_names: list[str] | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    variables: dict[str, str] | None = None,
) -> dict:
    """POST /evaluate/batch — by_date or by_asset batch trigger."""
    payload: dict = {'mode': mode, 'eval_name': eval_name, 'variables': variables or {}}
    if mode == 'by_date':
        payload['asset_name'] = asset_name
        payload['periods'] = periods or []
    elif mode == 'by_asset':
        payload['asset_names'] = asset_names or []
        payload['period_start'] = period_start
        payload['period_end'] = period_end
    return await self._post('/evaluate/batch', payload)
```

- [ ] **Step 3: Update client tests and run them**

```bash
./scripts/api-test.sh --tail 15 clients/python/tests/ -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add clients/python/tropek_client/models.py clients/python/tropek_client/client.py clients/python/tests/test_client.py
git commit -m "feat(client): add evaluate() and evaluate_batch() replacing old trigger methods"
```

---

## Task 12: Full Integration Verification

- [ ] **Step 1: Start test environment and run all tests**

```bash
just test-env
./scripts/api-test.sh --tail 30 -m integration -v
```

Expected: all integration tests pass.

- [ ] **Step 2: Run full test suite**

```bash
./scripts/api-test.sh --tail 30
```

Expected: all unit tests pass.

- [ ] **Step 3: Verify schema integrity against test DB**

```bash
uv run --directory api alembic -x env_type=test current
```

Expected: `002 (head)`.

- [ ] **Step 4: Tear down test environment**

```bash
just test-env-down
```

- [ ] **Step 5: Final commit if any cleanup needed**

If any minor fixes were made during verification:
```bash
git add -p
git commit -m "fix: integration verification cleanup for evaluation runs"
```

---

*Continue with `docs/superpowers/plans/2026-03-31-evaluation-runs-heatmap-b-heatmap-frontend.md` for the heatmap API and frontend changes.*
