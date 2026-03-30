# Refetch from Source — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `refetch_from_source` toggle to re-evaluate that re-fetches SLI data from the adapter, superseding original evaluations while preserving history.

**Architecture:** New `superseded` boolean + `supersedes_id` FK on `Evaluation`. When refetching, the re-evaluator marks originals as superseded, then delegates to `TriggerService` (with `skip_dedup=True`) to create replacement evaluations that go through the normal worker pipeline. No worker changes needed.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Alembic, React 19, TypeScript

---

### Task 1: Alembic migration — add `superseded` and `supersedes_id` columns

**Files:**
- Create: `api/alembic/versions/003_add_superseded_columns.py`

- [ ] **Step 1: Generate migration file**

```python
"""Add superseded and supersedes_id columns to evaluations."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'evaluations',
        sa.Column('superseded', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.add_column(
        'evaluations',
        sa.Column('supersedes_id', UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_evaluations_supersedes',
        'evaluations',
        'evaluations',
        ['supersedes_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'idx_evaluations_supersedes_id',
        'evaluations',
        ['supersedes_id'],
        postgresql_where=sa.text('supersedes_id IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('idx_evaluations_supersedes_id', table_name='evaluations')
    op.drop_constraint('fk_evaluations_supersedes', 'evaluations', type_='foreignkey')
    op.drop_column('evaluations', 'supersedes_id')
    op.drop_column('evaluations', 'superseded')
```

- [ ] **Step 2: Run migration against test DB**

Run: `just migrate-test`
Expected: Migration applies cleanly.

- [ ] **Step 3: Verify columns exist**

Run: `uv run --directory api python -c "from app.db.models import Evaluation; print([c.name for c in Evaluation.__table__.columns if 'supersed' in c.name])"`

This will fail until we update the model (Task 2). For now, verify migration applied via:

Run: `just test-env` (if not running), then check the DB directly:
```
PGPASSWORD=testpass psql -h localhost -p 5433 -U testuser -d tropek_test -c "\d evaluations" | grep supersed
```

Expected: Two columns listed — `superseded` (boolean) and `supersedes_id` (uuid).

- [ ] **Step 4: Commit**

```
git add api/alembic/versions/003_add_superseded_columns.py
git commit -m "migrate: add superseded and supersedes_id columns to evaluations"
```

---

### Task 2: Update Evaluation model with new columns

**Files:**
- Modify: `api/app/db/models.py:361` (after `invalidation_note`)

- [ ] **Step 1: Add columns to Evaluation model**

In `api/app/db/models.py`, add after the `invalidation_note` line (line 362):

```python
    superseded:           Mapped[bool]                   = mapped_column(Boolean, nullable=False, server_default=false(), default=False)
    supersedes_id:        Mapped[uuid.UUID | None]       = mapped_column(UUID, ForeignKey('evaluations.id', ondelete='SET NULL'), nullable=True)
```

- [ ] **Step 2: Update the `uq_evaluations_identity` partial index**

The duplicate prevention index currently excludes only `status != 'failed'`. Superseded evaluations should also be excluded so the replacement eval doesn't violate the unique constraint. In `api/app/db/models.py`, update the `uq_evaluations_identity` index (around line 319):

Change:
```python
        Index(
            'uq_evaluations_identity',
            'asset_id',
            'slo_name',
            'evaluation_name',
            'period_start',
            'period_end',
            unique=True,
            postgresql_where=text("status != 'failed'"),
        ),
```

To:
```python
        Index(
            'uq_evaluations_identity',
            'asset_id',
            'slo_name',
            'evaluation_name',
            'period_start',
            'period_end',
            unique=True,
            postgresql_where=text("status != 'failed' AND superseded = false"),
        ),
```

- [ ] **Step 3: Add a migration step to recreate the index**

Add to the `upgrade()` in the migration from Task 1:

```python
    # Recreate unique index to exclude superseded evaluations
    op.drop_index('uq_evaluations_identity', table_name='evaluations')
    op.create_index(
        'uq_evaluations_identity',
        'evaluations',
        ['asset_id', 'slo_name', 'evaluation_name', 'period_start', 'period_end'],
        unique=True,
        postgresql_where=sa.text("status != 'failed' AND superseded = false"),
    )
```

And in `downgrade()`, before dropping the superseded column:

```python
    op.drop_index('uq_evaluations_identity', table_name='evaluations')
    op.create_index(
        'uq_evaluations_identity',
        'evaluations',
        ['asset_id', 'slo_name', 'evaluation_name', 'period_start', 'period_end'],
        unique=True,
        postgresql_where=sa.text("status != 'failed'"),
    )
```

- [ ] **Step 4: Update the `idx_evaluations_baseline_lookup` partial index**

The baseline lookup index should also exclude superseded evaluations. Update it (around line 298):

Change:
```python
        Index(
            'idx_evaluations_baseline_lookup',
            'asset_id',
            'slo_name',
            text('period_start DESC'),
            postgresql_where=text("status = 'completed' AND invalidated = false"),
        ),
```

To:
```python
        Index(
            'idx_evaluations_baseline_lookup',
            'asset_id',
            'slo_name',
            text('period_start DESC'),
            postgresql_where=text("status = 'completed' AND invalidated = false AND superseded = false"),
        ),
```

Add the corresponding index recreation to the migration:

```python
    # Recreate baseline lookup index to exclude superseded evaluations
    op.drop_index('idx_evaluations_baseline_lookup', table_name='evaluations')
    op.create_index(
        'idx_evaluations_baseline_lookup',
        'evaluations',
        ['asset_id', 'slo_name', sa.text('period_start DESC')],
        postgresql_where=sa.text("status = 'completed' AND invalidated = false AND superseded = false"),
    )
```

- [ ] **Step 5: Run typecheck**

Run: `./scripts/api-test.sh --tail 5`
Expected: Tests pass (model changes are additive, defaults cover existing data).

- [ ] **Step 6: Commit**

```
git add api/app/db/models.py api/alembic/versions/003_add_superseded_columns.py
git commit -m "feat: add superseded and supersedes_id to Evaluation model"
```

---

### Task 3: Add `superseded` filtering to queries

**Files:**
- Modify: `api/app/modules/quality_gate/trend_repository.py:103,158`
- Modify: `api/app/modules/quality_gate/trend_repository.py:38-41` (heatmap query)
- Modify: `api/app/modules/quality_gate/baseline_repository.py:137,192`
- Modify: `api/app/modules/quality_gate/repository.py:293` (list_with_counts)

- [ ] **Step 1: Write integration test for superseded filtering**

Create test in `api/tests/db/test_superseded_filtering.py`:

```python
"""Integration tests — superseded evaluations are excluded from queries."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Evaluation
from app.modules.quality_gate.baseline_repository import BaselineRepository
from app.modules.quality_gate.trend_repository import TrendRepository


@pytest.mark.integration
async def test_superseded_excluded_from_heatmap(
    session: AsyncSession,
    seed_asset: uuid.UUID,
) -> None:
    """Superseded evaluations must not appear in heatmap queries."""
    now = datetime.now(UTC)
    # Create a superseded eval and a normal eval
    superseded_ev = Evaluation(
        evaluation_name='daily',
        asset_id=seed_asset,
        period_start=now - timedelta(hours=2),
        period_end=now - timedelta(hours=1),
        slo_name='perf',
        status='completed',
        result='fail',
        score=50.0,
        ingestion_mode='pull',
        superseded=True,
    )
    normal_ev = Evaluation(
        evaluation_name='daily',
        asset_id=seed_asset,
        period_start=now - timedelta(hours=1),
        period_end=now,
        slo_name='perf',
        status='completed',
        result='pass',
        score=95.0,
        ingestion_mode='pull',
    )
    session.add_all([superseded_ev, normal_ev])
    await session.flush()

    repo = TrendRepository(session)
    evals = await repo.get_metric_heatmap(asset_id=seed_asset)
    eval_ids = {ev.id for ev in evals}
    assert superseded_ev.id not in eval_ids
    assert normal_ev.id in eval_ids


@pytest.mark.integration
async def test_superseded_excluded_from_baselines(
    session: AsyncSession,
    seed_asset: uuid.UUID,
) -> None:
    """Superseded evaluations must not be selected as baseline candidates."""
    now = datetime.now(UTC)
    superseded_ev = Evaluation(
        evaluation_name='daily',
        asset_id=seed_asset,
        period_start=now - timedelta(hours=2),
        period_end=now - timedelta(hours=1),
        slo_name='perf',
        status='completed',
        result='pass',
        score=95.0,
        ingestion_mode='pull',
        superseded=True,
    )
    session.add(superseded_ev)
    await session.flush()

    repo = BaselineRepository(session)
    baselines = await repo.get_evaluation_baselines(
        asset_id=seed_asset,
        slo_name='perf',
        period_start_before=now,
        include_result_with_score='all',
        limit=10,
    )
    baseline_ids = {ev.id for ev in baselines}
    assert superseded_ev.id not in baseline_ids


@pytest.mark.integration
async def test_superseded_excluded_from_reeval_scope(
    session: AsyncSession,
    seed_asset: uuid.UUID,
) -> None:
    """Superseded evaluations must not be loaded for re-evaluation."""
    now = datetime.now(UTC)
    superseded_ev = Evaluation(
        evaluation_name='daily',
        asset_id=seed_asset,
        period_start=now - timedelta(hours=2),
        period_end=now - timedelta(hours=1),
        slo_name='perf',
        status='completed',
        result='pass',
        score=95.0,
        ingestion_mode='pull',
        superseded=True,
    )
    session.add(superseded_ev)
    await session.flush()

    repo = BaselineRepository(session)
    evals = await repo.load_evaluations_for_reeval(
        asset_id=seed_asset,
        slo_name='perf',
        from_date=now - timedelta(hours=3),
    )
    eval_ids = {ev.id for ev in evals}
    assert superseded_ev.id not in eval_ids
```

Note: The `seed_asset` fixture should already exist in the integration test conftest. If not, the agent will need to add one — check `api/tests/db/conftest.py` for existing asset fixtures.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/api-test.sh --tail 20 tests/db/test_superseded_filtering.py -v -m integration`
Expected: Tests fail because superseded evals are not yet filtered out.

- [ ] **Step 3: Add `superseded == False` to `get_metric_heatmap`**

In `api/app/modules/quality_gate/trend_repository.py`, add to the `.where()` clause of `get_metric_heatmap` (after line 40, `Evaluation.status == EvaluationStatus.COMPLETED`):

```python
                Evaluation.superseded == False,  # noqa: E712
```

- [ ] **Step 4: Add `superseded == False` to `get_trend_by_domain`**

In `api/app/modules/quality_gate/trend_repository.py`, add to the `.where()` clause at line 103 (after `Evaluation.invalidated == False`):

```python
                Evaluation.superseded == False,  # noqa: E712
```

- [ ] **Step 5: Add `superseded == False` to `get_trend`**

In `api/app/modules/quality_gate/trend_repository.py`, add to the `.where()` clause at line 158 (after `Evaluation.invalidated == False`):

```python
                Evaluation.superseded == False,  # noqa: E712
```

- [ ] **Step 6: Add `superseded == False` to baseline `_build_base_query`**

In `api/app/modules/quality_gate/baseline_repository.py`, add to the `.where()` clause at line 137 (after `Evaluation.invalidated == False`):

```python
            Evaluation.superseded == False,  # noqa: E712
```

- [ ] **Step 7: Add `superseded == False` to `load_evaluations_for_reeval`**

In `api/app/modules/quality_gate/baseline_repository.py`, add to the `.where()` clause at line 192 (after `Evaluation.invalidated == False`):

```python
                Evaluation.superseded == False,  # noqa: E712
```

- [ ] **Step 8: Add `superseded == False` to `list_with_counts`**

In `api/app/modules/quality_gate/repository.py`, add a default filter in `list_with_counts` after line 293 (`q = select(Evaluation)`):

```python
        q = q.where(Evaluation.superseded == False)  # noqa: E712
```

- [ ] **Step 9: Run tests**

Run: `./scripts/api-test.sh --tail 20 tests/db/test_superseded_filtering.py -v -m integration`
Expected: All 3 tests pass.

Run: `./scripts/api-test.sh --tail 5`
Expected: All existing unit tests still pass.

- [ ] **Step 10: Commit**

```
git add api/app/modules/quality_gate/trend_repository.py api/app/modules/quality_gate/baseline_repository.py api/app/modules/quality_gate/repository.py api/tests/db/test_superseded_filtering.py
git commit -m "feat: exclude superseded evaluations from heatmap, baseline, and list queries"
```

---

### Task 4: Add `supersede` and `clear_baseline_pin` to EvaluationRepository

**Files:**
- Modify: `api/app/modules/quality_gate/repository.py`
- Test: `api/tests/db/test_supersede.py`

- [ ] **Step 1: Write integration test**

Create `api/tests/db/test_supersede.py`:

```python
"""Integration tests — supersede evaluation."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Evaluation
from app.modules.quality_gate.repository import EvaluationRepository


@pytest.mark.integration
async def test_supersede_marks_eval_and_clears_pin(
    session: AsyncSession,
    seed_asset: uuid.UUID,
) -> None:
    """Superseding an eval sets superseded=True and clears baseline pin."""
    now = datetime.now(UTC)
    ev = Evaluation(
        evaluation_name='daily',
        asset_id=seed_asset,
        period_start=now - timedelta(hours=1),
        period_end=now,
        slo_name='perf',
        status='completed',
        result='pass',
        score=95.0,
        ingestion_mode='pull',
        baseline_pinned_at=now - timedelta(hours=1),
        baseline_pin_reason='good baseline',
        baseline_pin_author='test',
    )
    session.add(ev)
    await session.flush()

    repo = EvaluationRepository(session)
    updated = await repo.supersede(ev.id)

    assert updated is not None
    assert updated.superseded is True
    assert updated.baseline_pinned_at is None
    assert updated.baseline_unpinned_at is not None
    assert updated.baseline_pin_reason is None
    assert updated.baseline_pin_author is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/api-test.sh --tail 10 tests/db/test_supersede.py -v -m integration`
Expected: Fails with `AttributeError: 'EvaluationRepository' object has no attribute 'supersede'`.

- [ ] **Step 3: Implement `supersede` method**

Add to `api/app/modules/quality_gate/repository.py`, after the `restore` method (around line 358):

```python
    async def supersede(self, eval_id: uuid.UUID) -> Evaluation | None:
        """Mark an evaluation as superseded, clearing any baseline pin."""
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(
                superseded=True,
                baseline_pinned_at=None,
                baseline_unpinned_at=func.now(),
                baseline_pin_reason=None,
                baseline_pin_author=None,
            )
        )
        return await self.get_by_id(eval_id)
```

Ensure `func` is imported from sqlalchemy (it should already be).

- [ ] **Step 4: Run test**

Run: `./scripts/api-test.sh --tail 10 tests/db/test_supersede.py -v -m integration`
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add api/app/modules/quality_gate/repository.py api/tests/db/test_supersede.py
git commit -m "feat: add EvaluationRepository.supersede() method"
```

---

### Task 5: Extend TriggerService with `supersedes_id` and `skip_dedup`

**Files:**
- Modify: `api/app/modules/quality_gate/params.py`
- Modify: `api/app/modules/quality_gate/trigger_service.py`
- Test: `api/tests/test_trigger_supersede.py`

- [ ] **Step 1: Add `supersedes_id` to `EvalCreateParams`**

In `api/app/modules/quality_gate/params.py`, add to `EvalCreateParams` (after `data_source_name`):

```python
    supersedes_id: uuid.UUID | None = None
```

- [ ] **Step 2: Update `create_pending` to pass `supersedes_id`**

In `api/app/modules/quality_gate/repository.py`, in `create_pending` (around line 56, after `data_source_name=params.data_source_name`), add:

```python
            supersedes_id=params.supersedes_id,
```

- [ ] **Step 3: Add `skip_dedup` parameter to `trigger_single`**

In `api/app/modules/quality_gate/trigger_service.py`, change the `trigger_single` signature (line 35):

Change:
```python
    async def trigger_single(self, request: TriggerRequest) -> TriggerResponse:
```

To:
```python
    async def trigger_single(
        self,
        request: TriggerRequest,
        *,
        skip_dedup: bool = False,
        supersedes_id: uuid.UUID | None = None,
    ) -> TriggerResponse:
```

- [ ] **Step 4: Conditionally skip dedup check**

In `trigger_single`, wrap the existing duplicate check (lines 50-62) in a conditional:

Change:
```python
        # Duplicate prevention: app-level check for clean error messages.
        # The DB partial unique index is the safety net for races.
        existing = await self._repos.eval_repo.find_duplicate(
            asset_id=ctx.asset_id,
            slo_name=ctx.slo_name,
            evaluation_name=request.evaluation_name,
            period_start=request.period_start,
            period_end=request.period_end,
        )
        if existing is not None:
            if existing.status in ('pending', 'running'):
                msg = 'evaluation is already in progress for this period'
                raise DuplicateEvaluationError(msg)
            msg = 'evaluation already exists for this asset/SLO/period — use re-evaluate to re-score'
            raise DuplicateEvaluationError(msg)
```

To:
```python
        if not skip_dedup:
            # Duplicate prevention: app-level check for clean error messages.
            # The DB partial unique index is the safety net for races.
            existing = await self._repos.eval_repo.find_duplicate(
                asset_id=ctx.asset_id,
                slo_name=ctx.slo_name,
                evaluation_name=request.evaluation_name,
                period_start=request.period_start,
                period_end=request.period_end,
            )
            if existing is not None:
                if existing.status in ('pending', 'running'):
                    msg = 'evaluation is already in progress for this period'
                    raise DuplicateEvaluationError(msg)
                msg = 'evaluation already exists for this asset/SLO/period — use re-evaluate to re-score'
                raise DuplicateEvaluationError(msg)
```

- [ ] **Step 5: Pass `supersedes_id` to `create_pending`**

In the `EvalCreateParams(...)` call inside `trigger_single` (around line 65), add after `adapter_used=ctx.adapter_type`:

```python
                supersedes_id=supersedes_id,
```

- [ ] **Step 6: Write unit test**

Create `api/tests/test_trigger_supersede.py`:

```python
"""Unit tests — TriggerService skip_dedup and supersedes_id params."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.quality_gate.params import EvalCreateParams
from app.modules.quality_gate.trigger_service import TriggerService


def _make_trigger_context() -> MagicMock:
    ctx = MagicMock()
    ctx.asset_id = uuid.uuid4()
    ctx.asset_name = 'test-asset'
    ctx.asset_display_name = 'Test Asset'
    ctx.asset_tags = {}
    ctx.asset_variables = {}
    ctx.slo_name = 'perf'
    ctx.slo_version = 1
    ctx.sli_name = 'metrics'
    ctx.sli_version = 1
    ctx.data_source_name = 'prom'
    ctx.adapter_type = 'prometheus'
    return ctx


@pytest.fixture
def repos() -> MagicMock:
    r = MagicMock()
    r.eval_repo = AsyncMock()
    r.eval_repo.create_pending = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))
    r.eval_repo.find_duplicate = AsyncMock(return_value=None)
    r.session = AsyncMock()
    return r


@pytest.fixture
def pool() -> AsyncMock:
    return AsyncMock()


async def test_skip_dedup_bypasses_duplicate_check(
    repos: MagicMock,
    pool: AsyncMock,
) -> None:
    """When skip_dedup=True, find_duplicate should not be called."""
    ctx = _make_trigger_context()
    service = TriggerService(repos, pool)

    request = MagicMock()
    request.asset_name = 'test-asset'
    request.slo_name = 'perf'
    request.evaluation_name = 'daily'
    request.period_start = datetime.now(UTC) - timedelta(hours=1)
    request.period_end = datetime.now(UTC)
    request.variables = {}

    with patch(
        'app.modules.quality_gate.trigger_service.resolve_single_trigger',
        return_value=ctx,
    ):
        await service.trigger_single(request, skip_dedup=True)

    repos.eval_repo.find_duplicate.assert_not_called()


async def test_supersedes_id_passed_to_create_pending(
    repos: MagicMock,
    pool: AsyncMock,
) -> None:
    """When supersedes_id is provided, it must appear in EvalCreateParams."""
    ctx = _make_trigger_context()
    original_id = uuid.uuid4()
    service = TriggerService(repos, pool)

    request = MagicMock()
    request.asset_name = 'test-asset'
    request.slo_name = 'perf'
    request.evaluation_name = 'daily'
    request.period_start = datetime.now(UTC) - timedelta(hours=1)
    request.period_end = datetime.now(UTC)
    request.variables = {}

    with patch(
        'app.modules.quality_gate.trigger_service.resolve_single_trigger',
        return_value=ctx,
    ):
        await service.trigger_single(
            request,
            skip_dedup=True,
            supersedes_id=original_id,
        )

    call_args = repos.eval_repo.create_pending.call_args
    params: EvalCreateParams = call_args[0][0]
    assert params.supersedes_id == original_id
```

- [ ] **Step 7: Run tests**

Run: `./scripts/api-test.sh --tail 10 tests/test_trigger_supersede.py -v`
Expected: Both tests pass.

- [ ] **Step 8: Commit**

```
git add api/app/modules/quality_gate/params.py api/app/modules/quality_gate/trigger_service.py api/app/modules/quality_gate/repository.py api/tests/test_trigger_supersede.py
git commit -m "feat: add skip_dedup and supersedes_id to TriggerService.trigger_single"
```

---

### Task 6: Implement refetch path in re-evaluator

**Files:**
- Modify: `api/app/modules/quality_gate/re_evaluation_schemas.py`
- Modify: `api/app/modules/quality_gate/re_evaluator.py`
- Modify: `api/app/modules/quality_gate/router.py:203-212`
- Test: `api/tests/test_refetch_reevaluator.py`

- [ ] **Step 1: Update request/response schemas**

In `api/app/modules/quality_gate/re_evaluation_schemas.py`:

Add to `ReEvaluateRequest` (after `dry_run`, line 24):

```python
    refetch_from_source: bool = False
```

Add to `ReEvaluateResponse` (after `results`, line 60):

```python
    queued: int | None = None
```

- [ ] **Step 2: Update UI types**

In `ui/src/features/evaluations/types.ts`:

Add to `ReEvaluatePayload` (after `dry_run`):

```typescript
  refetch_from_source?: boolean
```

Add to `ReEvaluateResponse` (after `results`):

```typescript
  queued?: number
```

- [ ] **Step 3: Write unit test for refetch path**

Create `api/tests/test_refetch_reevaluator.py`:

```python
"""Unit tests — re-evaluator refetch_from_source path."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.quality_gate.re_evaluation_schemas import (
    ReEvaluateRequest,
    ReEvaluateResponse,
)
from app.modules.quality_gate.re_evaluator import re_evaluate


def _make_eval(
    *,
    asset_id: uuid.UUID,
    slo_name: str = 'perf',
    evaluation_name: str = 'daily',
    hours_ago: int = 1,
) -> MagicMock:
    ev = MagicMock()
    ev.id = uuid.uuid4()
    ev.evaluation_name = evaluation_name
    ev.asset_id = asset_id
    ev.asset_snapshot = {'name': 'test-asset', 'tags': {}, 'variables': {}}
    ev.slo_name = slo_name
    ev.slo_version = 1
    ev.sli_name = 'metrics'
    ev.sli_version = 1
    ev.data_source_name = 'prom'
    ev.adapter_used = 'prometheus'
    ev.ingestion_mode = 'pull'
    ev.variables = {}
    ev.period_start = datetime.now(UTC) - timedelta(hours=hours_ago + 1)
    ev.period_end = datetime.now(UTC) - timedelta(hours=hours_ago)
    ev.baseline_pinned_at = None
    ev.baseline_unpinned_at = None
    ev.indicator_rows = []
    ev.result = 'pass'
    ev.score = 90.0
    return ev


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


async def test_refetch_supersedes_and_queues(session: AsyncMock) -> None:
    """refetch_from_source=True should supersede originals and queue new evals."""
    asset_id = uuid.uuid4()
    eval1 = _make_eval(asset_id=asset_id, hours_ago=2)
    eval2 = _make_eval(asset_id=asset_id, hours_ago=1)

    asset_mock = MagicMock()
    asset_mock.id = asset_id
    asset_mock.name = 'test-asset'

    slo_def_mock = MagicMock()
    slo_def_mock.version = 1

    request = ReEvaluateRequest(
        asset_name='test-asset',
        slo_name='perf',
        from_date=datetime.now(UTC) - timedelta(hours=3),
        refetch_from_source=True,
    )

    repos_mock = MagicMock()
    repos_mock.session = session

    with (
        patch('app.modules.quality_gate.re_evaluator.AssetRepository') as asset_repo_cls,
        patch('app.modules.quality_gate.re_evaluator.SLORepository') as slo_repo_cls,
        patch('app.modules.quality_gate.re_evaluator.EvaluationRepository') as eval_repo_cls,
        patch('app.modules.quality_gate.re_evaluator.BaselineRepository') as baseline_repo_cls,
        patch('app.modules.quality_gate.re_evaluator.TriggerService') as trigger_cls,
    ):
        asset_repo_cls.return_value.get_by_name = AsyncMock(return_value=asset_mock)
        slo_repo_cls.return_value.get_latest = AsyncMock(return_value=slo_def_mock)
        eval_repo_cls.return_value.supersede = AsyncMock()
        baseline_repo_cls.return_value.load_evaluations_for_reeval = AsyncMock(
            return_value=[eval1, eval2],
        )
        trigger_response = MagicMock()
        trigger_response.id = uuid.uuid4()
        trigger_response.status = 'pending'
        trigger_cls.return_value.trigger_single = AsyncMock(return_value=trigger_response)

        result = await re_evaluate(
            request, session, repos=repos_mock, arq_pool=AsyncMock(),
        )

    assert isinstance(result, ReEvaluateResponse)
    assert result.queued == 2
    assert result.affected_evaluations == 2
    assert result.results == []
    assert eval_repo_cls.return_value.supersede.call_count == 2
    assert trigger_cls.return_value.trigger_single.call_count == 2
```

- [ ] **Step 4: Run test to verify it fails**

Run: `./scripts/api-test.sh --tail 10 tests/test_refetch_reevaluator.py -v`
Expected: Fails — `re_evaluate` doesn't accept `arq_pool` parameter yet.

- [ ] **Step 5: Implement refetch path in `re_evaluator.py`**

Add imports at the top of `api/app/modules/quality_gate/re_evaluator.py`:

```python
from arq.connections import ArqRedis

from app.modules.quality_gate.schemas import TriggerRequest
from app.modules.quality_gate.trigger_service import TriggerService
```

Change the `re_evaluate` function signature to accept repos bundle + arq_pool:

Change:
```python
async def re_evaluate(
    request: ReEvaluateRequest,
    session: AsyncSession,
) -> ReEvaluateResponse:
```

To:
```python
async def re_evaluate(
    request: ReEvaluateRequest,
    session: AsyncSession,
    *,
    repos: QualityGateRepos | None = None,
    arq_pool: ArqRedis | None = None,
) -> ReEvaluateResponse:
```

Also add the import for `QualityGateRepos`:

```python
from app.modules.quality_gate.dependencies import QualityGateRepos
```

After loading evaluations to process (after line 241, the early return for empty evals), add the refetch branch:

```python
    if request.refetch_from_source:
        if arq_pool is None or repos is None:
            raise ValueError('repos and arq_pool are required for refetch_from_source')
        return await _refetch_and_supersede(
            evals_to_process=evals_to_process,
            slo_version=slo_def.version,
            eval_repo=eval_repo,
            repos=repos,
            session=session,
            arq_pool=arq_pool,
        )
```

Add the `_refetch_and_supersede` function before `re_evaluate`:

```python
async def _refetch_and_supersede(
    *,
    evals_to_process: list[Evaluation],
    slo_version: int,
    eval_repo: EvaluationRepository,
    repos: QualityGateRepos,
    session: AsyncSession,
    arq_pool: ArqRedis,
) -> ReEvaluateResponse:
    """Supersede each evaluation and enqueue a fresh replacement via TriggerService."""
    trigger_service = TriggerService(repos, arq_pool)
    queued = 0

    for ev in evals_to_process:
        await eval_repo.supersede(ev.id)

        trigger_request = TriggerRequest(
            asset_name=ev.asset_snapshot.get('name', ''),
            slo_name=ev.slo_name,
            evaluation_name=ev.evaluation_name,
            period_start=ev.period_start,
            period_end=ev.period_end,
            variables=ev.variables,
        )
        await trigger_service.trigger_single(
            trigger_request,
            skip_dedup=True,
            supersedes_id=ev.id,
        )
        queued += 1

    await session.commit()

    return ReEvaluateResponse(
        affected_evaluations=queued,
        slo_version_used=slo_version,
        results=[],
        queued=queued,
    )
```

- [ ] **Step 6: Update router to pass repos and arq_pool**

In `api/app/modules/quality_gate/router.py`, update the `re_evaluate_evaluations` endpoint (around line 203). The `get_arq_pool` and `get_qg_repos` dependencies are already imported and used by the trigger endpoints. Add them to the re-evaluate endpoint:

```python
@router.post('/evaluations/re-evaluate', response_model=ReEvaluateResponse)
async def re_evaluate_evaluations(
    body: ReEvaluateRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> ReEvaluateResponse:
    """Re-evaluate completed evaluations, optionally re-fetching from source."""
    try:
        return await re_evaluate(body, repos.session, repos=repos, arq_pool=arq_pool)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
```

Note: `repos.session` replaces the previous bare `session` parameter. The existing non-refetch path still only uses `session` internally, so this is backward compatible.

- [ ] **Step 7: Run tests**

Run: `./scripts/api-test.sh --tail 10 tests/test_refetch_reevaluator.py -v`
Expected: PASS.

Run: `./scripts/api-test.sh --tail 5`
Expected: All tests pass.

- [ ] **Step 8: Commit**

```
git add api/app/modules/quality_gate/re_evaluation_schemas.py api/app/modules/quality_gate/re_evaluator.py api/app/modules/quality_gate/router.py ui/src/features/evaluations/types.ts api/tests/test_refetch_reevaluator.py
git commit -m "feat: implement refetch_from_source path in re-evaluator"
```

---

### Task 7: Update evaluation summary schema and API response

**Files:**
- Modify: `api/app/modules/quality_gate/schemas.py:105`
- Modify: `api/app/modules/quality_gate/router.py` (build_summary helper)

- [ ] **Step 1: Add `superseded` and `supersedes_id` to response schema**

In `api/app/modules/quality_gate/schemas.py`, add after `invalidated: bool` (line 105):

```python
    superseded: bool
    supersedes_id: uuid.UUID | None = None
```

- [ ] **Step 2: Update `build_summary` or wherever the response is built**

Find the `build_summary` function in the router and ensure it maps the new fields from the Evaluation model. Since these are direct model fields and the schema is likely built via `model_validate` or direct assignment, verify the mapping includes them. The agent should check how `build_summary` works and add the fields if they're not auto-mapped.

- [ ] **Step 3: Run tests and typecheck**

Run: `./scripts/api-test.sh --tail 5`
Expected: PASS.

Run: `uv run --directory api mypy app/`
or: `./scripts/api-test.sh --tail 5` (if typecheck is included)

- [ ] **Step 4: Commit**

```
git add api/app/modules/quality_gate/schemas.py api/app/modules/quality_gate/router.py
git commit -m "feat: expose superseded and supersedes_id in evaluation API response"
```

---

### Task 8: UI — add refetch toggle to ReEvaluateForm

**Files:**
- Modify: `ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx`

- [ ] **Step 1: Add refetch state and toggle**

In `ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx`:

Add state after `reEvalResult` state (line 28):

```typescript
  const [refetchFromSource, setRefetchFromSource] = useState(false)
```

Update `ACTION_DEF` description to be dynamic — or simpler, just update the description text in the JSX. In the form body (around line 112), after the existing description paragraph, add:

```tsx
      <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
        <input
          type="checkbox"
          checked={refetchFromSource}
          onChange={(e) => setRefetchFromSource(e.target.checked)}
          className="rounded border-border accent-[var(--entity-sli)]"
        />
        Refetch data from source
      </label>
      {refetchFromSource && (
        <p className="text-xs text-muted-foreground/70 pl-6">
          SLI data will be re-fetched from the adapter. Original evaluations will be superseded.
        </p>
      )}
```

- [ ] **Step 2: Pass `refetch_from_source` in the mutation payload**

Update the `handleConfirm` callback. In the `reEvaluate.mutate()` call (around line 36), add `refetch_from_source` to the payload:

Change:
```typescript
    reEvaluate.mutate(
      {
        asset_name: assetName,
        slo_name: sloName,
        ...(fromBaseline ? { from_baseline: true } : { from_date: new Date(fromDate).toISOString() }),
      },
```

To:
```typescript
    reEvaluate.mutate(
      {
        asset_name: assetName,
        slo_name: sloName,
        ...(fromBaseline ? { from_baseline: true } : { from_date: new Date(fromDate).toISOString() }),
        ...(refetchFromSource && { refetch_from_source: true }),
      },
```

- [ ] **Step 3: Handle async response (queued path)**

In the results view (around line 46, `if (reEvalResult)`), handle the `queued` case. Before the existing results rendering:

```tsx
  if (reEvalResult) {
    const isQueued = reEvalResult.queued != null && reEvalResult.queued > 0

    return (
      <ActionFormShell
        actionDef={ACTION_DEF}
        onClose={onComplete}
        onConfirm={onComplete}
        canConfirm={false}
        isPending={false}
        hideButtons
      >
        <div className="space-y-2">
          {isQueued ? (
            <p className="text-sm text-foreground">
              {reEvalResult.queued} evaluation{reEvalResult.queued !== 1 ? 's' : ''}{' '}
              queued for re-evaluation from source (SLO v{reEvalResult.slo_version_used})
            </p>
          ) : (
            <>
              <p className="text-sm text-foreground">
                {reEvalResult.affected_evaluations} evaluation{reEvalResult.affected_evaluations !== 1 ? 's' : ''}{' '}
                re-evaluated (SLO v{reEvalResult.slo_version_used})
              </p>
              <div className="max-h-48 overflow-y-auto space-y-1">
                {reEvalResult.results.map((r) => (
                  <div key={r.id} className="flex items-center justify-between text-xs px-3 py-1.5 bg-muted/50 rounded">
                    <span className="text-muted-foreground">
                      {new Date(r.period_start).toLocaleDateString()}
                    </span>
                    <span>
                      <span className="text-muted-foreground">{r.old_result}</span>
                      <span className="text-muted-foreground/60 mx-1">{'\u2192'}</span>
                      <span className={
                        r.new_result === 'pass' ? 'text-pass'
                          : r.new_result === 'warning' ? 'text-warning'
                            : 'text-fail'
                      }>
                        {r.new_result}
                      </span>
                    </span>
                    <span className="text-muted-foreground">
                      {r.old_score.toFixed(1)} {'\u2192'} {r.new_score.toFixed(1)}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
          <div className="flex justify-end">
            <button
              onClick={onComplete}
              className="px-3 py-1.5 text-xs rounded-md border border-border text-muted-foreground hover:text-foreground transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </ActionFormShell>
    )
  }
```

- [ ] **Step 4: Run UI tests**

Run: `./scripts/ui-test.sh --tail 10`
Expected: Existing tests pass.

- [ ] **Step 5: Commit**

```
git add ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx
git commit -m "feat(ui): add refetch-from-source toggle to ReEvaluateForm"
```

---

### Task 9: UI — superseded indicator on evaluations

**Files:**
- Modify: `ui/src/features/evaluations/types.ts` (add `superseded` and `supersedes_id` to evaluation type)
- Modify: UI components that display evaluation status (AssetPanel, heatmap, eval list)

- [ ] **Step 1: Add fields to UI evaluation type**

In `ui/src/features/evaluations/types.ts`, find the main evaluation interface (the one with `invalidated: boolean`) and add:

```typescript
  superseded: boolean
  supersedes_id: string | null
```

- [ ] **Step 2: Add superseded indicator in AssetPanel**

In `ui/src/features/navigator/components/AssetPanel.tsx`, find where `invalidated` is displayed (around line 128 where `displayResult` is computed). Add a similar indicator for `supersedes_id`:

After the invalidated handling, add a small indicator when `ev.supersedes_id` is set. This could be a tooltip-bearing icon next to the evaluation. The exact placement depends on the current layout — the agent should find where evaluation metadata badges are rendered and add a small "Refetched" indicator there.

A simple approach: near the evaluation score/result display, add:

```tsx
{ev?.supersedes_id && (
  <span
    className="text-[10px] text-muted-foreground/60 ml-1"
    title="Re-fetched from source — replaces earlier evaluation"
  >
    (refetched)
  </span>
)}
```

- [ ] **Step 3: Run UI tests**

Run: `./scripts/ui-test.sh --tail 10`
Expected: Tests pass.

- [ ] **Step 4: Commit**

```
git add ui/src/features/evaluations/types.ts ui/src/features/navigator/components/AssetPanel.tsx
git commit -m "feat(ui): show superseded indicator on refetched evaluations"
```

---

### Task 10: Integration test — full refetch flow

**Files:**
- Create: `api/tests/db/test_refetch_flow.py`

- [ ] **Step 1: Write end-to-end integration test**

Create `api/tests/db/test_refetch_flow.py`:

```python
"""Integration test — full refetch-from-source flow."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Evaluation
from app.modules.quality_gate.re_evaluation_schemas import ReEvaluateRequest
from app.modules.quality_gate.re_evaluator import re_evaluate


@pytest.mark.integration
async def test_refetch_supersedes_original_and_creates_pending(
    session: AsyncSession,
    seed_asset: uuid.UUID,
    arq_pool_mock,
) -> None:
    """Refetch flow: original eval becomes superseded, new pending eval created."""
    now = datetime.now(UTC)
    original = Evaluation(
        evaluation_name='daily',
        asset_id=seed_asset,
        period_start=now - timedelta(hours=2),
        period_end=now - timedelta(hours=1),
        slo_name='perf',
        slo_version=1,
        sli_name='metrics',
        sli_version=1,
        data_source_name='prom',
        adapter_used='prometheus',
        status='completed',
        result='pass',
        score=95.0,
        ingestion_mode='pull',
        asset_snapshot={'name': 'test-asset', 'tags': {}, 'variables': {}},
    )
    session.add(original)
    await session.flush()

    request = ReEvaluateRequest(
        asset_name='test-asset',
        slo_name='perf',
        from_date=now - timedelta(hours=3),
        refetch_from_source=True,
    )

    # Build repos bundle from session — the agent should construct QualityGateRepos
    # using the same pattern as get_qg_repos() in dependencies.py, or mock it.
    # Simplest approach: mock TriggerService at module level instead.
    result = await re_evaluate(request, session, repos=repos_mock, arq_pool=arq_pool_mock)

    assert result.queued == 1
    assert result.affected_evaluations == 1

    # Verify original is superseded
    await session.refresh(original)
    assert original.superseded is True

    # Verify new eval was created
    q = select(Evaluation).where(
        Evaluation.supersedes_id == original.id,
    )
    rows = await session.execute(q)
    new_eval = rows.scalar_one()
    assert new_eval.status == 'pending'
    assert new_eval.evaluation_name == 'daily'
    assert new_eval.period_start == original.period_start
    assert new_eval.period_end == original.period_end
    assert new_eval.slo_name == 'perf'
    assert new_eval.supersedes_id == original.id
```

Note: The `arq_pool_mock` fixture may need to be added to `api/tests/db/conftest.py` if it doesn't exist. It should be an `AsyncMock` that accepts `enqueue_job` calls. The `seed_asset` fixture should also provide an asset with `name='test-asset'`. The agent should check existing fixtures and adapt.

This test also requires that the SLO definition, SLI definition, and datasource exist in the test DB for `TriggerService.resolve_single_trigger` to succeed. The agent may need to seed these or mock the trigger resolution. If the test setup is too complex, the agent can use a simpler approach: mock `TriggerService` at the module level and verify the calls, similar to the unit test in Task 6.

- [ ] **Step 2: Run integration test**

Run: `./scripts/api-test.sh --tail 20 tests/db/test_refetch_flow.py -v -m integration`
Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run: `./scripts/api-test.sh --tail 5`
Run: `./scripts/ui-test.sh --tail 10`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```
git add api/tests/db/test_refetch_flow.py
git commit -m "test: add integration test for refetch-from-source flow"
```

---

### Task 11: Final verification

- [ ] **Step 1: Run linter**

Run: `uv run ruff check api/ adapters/`
Expected: No violations.

- [ ] **Step 2: Run typecheck**

Run: `uv run mypy api/app adapters/prometheus/app`
Expected: No errors.

- [ ] **Step 3: Run all tests**

Run: `./scripts/api-test.sh --tail 5`
Run: `./scripts/ui-test.sh --tail 10`
Expected: All pass.

- [ ] **Step 4: Run integration tests**

Run: `just test-env` (if not running)
Run: `./scripts/api-test.sh --tail 10 -m integration -v`
Expected: All pass including new superseded filtering and refetch flow tests.
