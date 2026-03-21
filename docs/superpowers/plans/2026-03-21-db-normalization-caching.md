# DB Normalization + Redis Caching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `indicator_results` JSONB into a relational table with FK to `slo_objectives`, then add a Redis caching layer for immutable/infrequently-changing entities to offset join cost.

**Architecture:** Phase A (tasks 1-11) normalizes the database: new `indicator_results` table, rewrite all read/write paths, data migration, drop JSONB. Phase B (tasks 12-17) adds Redis caching with three tiers. API response shapes are preserved — the normalization is storage-internal. All changes are TDD.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, PostgreSQL, Alembic, Redis (aioredis via arq), Pydantic v2, pytest

**Spec:** `docs/superpowers/specs/2026-03-20-db-normalization-caching-design.md`

**Commands:**
- Run unit tests: `uv run --directory api pytest api/tests/ -m "not integration" -q`
- Run integration tests: `uv run --directory api pytest api/tests/ -m integration -v`
- Run single test: `uv run --directory api pytest api/tests/path/test.py::test_name -v`
- Start test infra: `./start_test_infra.sh`
- Regenerate migrations: `./scripts/db-regen-migrations.sh`
- Apply migrations (test DB): `ENV_FILE=.env.test uv run --directory api alembic upgrade head`
- Lint: `uv run ruff check api/`
- Type check: `uv run mypy api/app`
- Run UI tests: `cd ui && npx vitest run`

---

## File Structure

### New files
| File | Responsibility |
|------|----------------|
| `api/app/modules/quality_gate/indicator_repository.py` | CRUD for the new `indicator_results` relational table |
| `api/app/modules/quality_gate/target_resolver.py` | Compute `pass_targets`/`warning_targets` from criteria strings + compared_value at read time |
| `api/app/cache/redis_cache.py` | Generic read-through cache utility wrapping Redis |
| `api/app/cache/__init__.py` | Package init |
| `api/tests/db/test_indicator_repository.py` | Integration tests for indicator CRUD |
| `api/tests/services/test_target_resolver.py` | Unit tests for target resolution |
| `api/tests/cache/test_redis_cache.py` | Unit tests for cache utility |
| `api/tests/cache/__init__.py` | Package init |

### Modified files
| File | Changes |
|------|---------|
| `api/app/db/models.py` | New `IndicatorResultRow` model, add `tab_group` to `SLOObjective`, drop `indicator_results` JSONB from `Evaluation` |
| `api/app/modules/quality_gate/engine/result_models.py` | No change — engine continues returning current `IndicatorResult` model |
| `api/app/modules/quality_gate/engine/evaluator.py` | No change — engine is pure, storage-agnostic |
| `api/app/modules/quality_gate/repository.py` | `mark_completed()` writes to indicator_results table instead of JSONB, `get_by_id()` eager-loads indicator rows |
| `api/app/modules/quality_gate/presenter.py` | `build_summary()` and `build_detail()` accept ORM indicator rows + SLO objectives instead of JSONB dicts |
| `api/app/modules/quality_gate/trend_repository.py` | `get_trend_by_domain()` joins `indicator_results` table instead of JSONB extraction |
| `api/app/modules/quality_gate/baseline_repository.py` | `update_reeval_result()` deletes + inserts indicator rows instead of JSONB overwrite |
| `api/app/modules/quality_gate/re_evaluator.py` | `_metrics_from_indicator_results()` reads from ORM rows instead of JSONB dicts |
| `api/app/modules/quality_gate/router.py` | Heatmap cell construction reads from joined indicator rows |
| `api/app/modules/quality_gate/worker.py` | Writes `IndicatorResultRow` objects instead of serialized dicts |
| `api/app/modules/quality_gate/schemas.py` | `IndicatorResult` response schema unchanged, `FailingIndicator.threshold` derived from joined objectives |
| `api/app/modules/quality_gate/dependencies.py` | Add `IndicatorRepository` to `QualityGateRepos` bundle |
| `api/app/config.py` | Add cache DB index for caching (separate from queue) |

---

### Task 1: Add `tab_group` column to `SLOObjective` model

**Files:**
- Modify: `api/app/db/models.py:189-205`

Prerequisite from the spec: the SLOObjective model lacks a `tab_group` column. Add it before creating the indicator_results table that references objectives.

- [ ] **Step 1: Add tab_group column**

In `api/app/db/models.py`, add after the `warning_criteria` line (204):

```python
tab_group:         Mapped[str | None]    = mapped_column(Text, nullable=True)
```

The full `SLOObjective` model should now have columns: `id`, `slo_definition_id`, `sli`, `display_name`, `weight`, `key_sli`, `sort_order`, `pass_criteria`, `warning_criteria`, `tab_group`.

- [ ] **Step 2: Regenerate migrations**

Run: `./scripts/db-regen-migrations.sh`

- [ ] **Step 3: Apply migration to test DB**

Run: `ENV_FILE=.env.test uv run --directory api alembic upgrade head`

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `uv run --directory api pytest api/tests/ -m integration -v`

Expected: All pass — adding a nullable column is backwards-compatible.

- [ ] **Step 5: Commit**

```
git add api/app/db/models.py
git commit -m "feat: add tab_group column to slo_objectives"
```

---

### Task 2: Create `IndicatorResultRow` ORM model

**Files:**
- Modify: `api/app/db/models.py`

Add the new relational table that will replace the JSONB column. At this point, both exist side by side — the JSONB column is NOT dropped yet.

- [ ] **Step 1: Add the model**

Add after the `SLOObjective` class in `api/app/db/models.py`:

```python
class IndicatorResultRow(Base):
    """Normalized indicator result — one row per SLI per evaluation."""

    __tablename__ = "indicator_results"
    __table_args__ = (
        Index("idx_indicator_results_evaluation", "evaluation_id"),
        Index("idx_indicator_results_objective_status", "slo_objective_id", "status"),
        UniqueConstraint(
            "evaluation_id", "slo_objective_id",
            name="uq_indicator_results_eval_objective",
        ),
    )

    # fmt: off
    id:               Mapped[uuid.UUID]      = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    evaluation_id:    Mapped[uuid.UUID]      = mapped_column(UUID, ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False)
    slo_objective_id: Mapped[uuid.UUID]      = mapped_column(UUID, ForeignKey("slo_objectives.id", ondelete="CASCADE"), nullable=False)
    value:            Mapped[float | None]   = mapped_column(Float, nullable=True)
    compared_value:   Mapped[float | None]   = mapped_column(Float, nullable=True)
    change_absolute:  Mapped[float | None]   = mapped_column(Float, nullable=True)
    change_relative_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    status:           Mapped[str]            = mapped_column(Text, nullable=False)
    score:            Mapped[float]          = mapped_column(Float, nullable=False, server_default=text("0"))
    # fmt: on

    # Relationships for eager loading
    objective: Mapped[SLOObjective] = relationship("SLOObjective", lazy="joined")
```

Also add to `Evaluation` model a relationship:

```python
indicator_rows: Mapped[list[IndicatorResultRow]] = relationship(
    "IndicatorResultRow", cascade="all, delete-orphan", lazy="selectin",
)
```

Add necessary imports at the top of models.py if not already present: `UniqueConstraint`, `relationship`.

- [ ] **Step 2: Regenerate migrations**

Run: `./scripts/db-regen-migrations.sh`

- [ ] **Step 3: Apply migration to test DB**

Run: `ENV_FILE=.env.test uv run --directory api alembic upgrade head`

- [ ] **Step 4: Run existing tests**

Run: `uv run --directory api pytest api/tests/ -m integration -v`

Expected: All pass — new table exists but nothing writes to it yet.

- [ ] **Step 5: Commit**

```
git add api/app/db/models.py
git commit -m "feat: add indicator_results relational table"
```

---

### Task 3: Target resolver utility

**Files:**
- Create: `api/app/modules/quality_gate/target_resolver.py`
- Create: `api/tests/services/test_target_resolver.py`

Compute `pass_targets`/`warning_targets` at read time from criteria strings + compared_value. This replaces what was previously stored in the JSONB blob.

- [ ] **Step 1: Write failing tests**

Create `api/tests/services/test_target_resolver.py`:

```python
"""Unit tests for target resolution from criteria strings."""

from __future__ import annotations

from app.modules.quality_gate.target_resolver import resolve_targets


def test_fixed_threshold_not_violated():
    result = resolve_targets(["<600"], value=580.0, compared_value=None)
    assert len(result) == 1
    assert result[0]["criteria"] == "<600"
    assert result[0]["target_value"] == 600.0
    assert result[0]["violated"] is False


def test_fixed_threshold_violated():
    result = resolve_targets(["<600"], value=610.0, compared_value=None)
    assert result[0]["violated"] is True


def test_relative_percent_not_violated():
    result = resolve_targets(["<=+10%"], value=105.0, compared_value=100.0)
    assert result[0]["target_value"] == 110.0
    assert result[0]["violated"] is False


def test_relative_percent_violated():
    result = resolve_targets(["<=+10%"], value=115.0, compared_value=100.0)
    assert result[0]["violated"] is True


def test_relative_no_percent_sign():
    """<=+50 is parsed as <=+50% (relative percent) by the engine — no separate 'absolute' mode."""
    result = resolve_targets(["<=+50"], value=700.0, compared_value=500.0)
    # +50 means +50% of compared_value → 500 + 250 = 750
    assert result[0]["target_value"] == 750.0
    assert result[0]["violated"] is False


def test_null_value_always_violated():
    result = resolve_targets(["<600"], value=None, compared_value=None)
    assert result[0]["violated"] is True


def test_empty_criteria_returns_empty():
    result = resolve_targets([], value=100.0, compared_value=None)
    assert result == []


def test_none_criteria_returns_none():
    result = resolve_targets(None, value=100.0, compared_value=None)
    assert result is None
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `uv run --directory api pytest api/tests/services/test_target_resolver.py -v`

Expected: ImportError — module doesn't exist

- [ ] **Step 3: Implement target resolver**

Create `api/app/modules/quality_gate/target_resolver.py`:

```python
"""Resolve pass/warning targets from criteria strings at read time.

Replaces the pre-computed pass_targets/warning_targets that were stored
in the indicator_results JSONB. Uses the same criteria parsing logic
from the engine.
"""

from __future__ import annotations

from typing import Any

from app.modules.quality_gate.engine.criteria import evaluate_criteria, parse_criteria_string


def resolve_targets(
    criteria: list[str] | None,
    *,
    value: float | None,
    compared_value: float | None,
) -> list[dict[str, Any]] | None:
    """Compute target list from raw criteria strings.

    Returns None if criteria is None (info-only objective).
    Returns [] if criteria is an empty list.
    """
    if criteria is None:
        return None
    targets: list[dict[str, Any]] = []
    for raw in criteria:
        c = parse_criteria_string(raw)
        target_value = c.compute_target_value(compared_value)
        violated = not evaluate_criteria(c, value, compared_value) if value is not None else True
        targets.append({
            "criteria": raw,
            "target_value": target_value,
            "violated": violated,
        })
    return targets
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `uv run --directory api pytest api/tests/services/test_target_resolver.py -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```
git add api/app/modules/quality_gate/target_resolver.py api/tests/services/test_target_resolver.py
git commit -m "feat: add target resolver for read-time criteria computation"
```

---

### Task 4: Indicator repository (write path)

**Files:**
- Create: `api/app/modules/quality_gate/indicator_repository.py`
- Create: `api/tests/db/test_indicator_repository.py`

Repository that writes `IndicatorResultRow` objects from engine output. This is the write side — Task 5 covers reads.

- [ ] **Step 1: Write failing test for bulk insert**

Create `api/tests/db/test_indicator_repository.py`:

```python
"""Integration tests for IndicatorRepository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.db.models import (
    Asset,
    AssetType,
    Evaluation,
    IndicatorResultRow,
    SLIDefinition,
    SLODefinition,
    SLOObjective,
)
from app.modules.quality_gate.indicator_repository import IndicatorRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_START = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)


async def _seed_slo_with_objectives(session: AsyncSession) -> tuple[str, int, list[SLOObjective]]:
    """Create an SLO definition with two objectives. Return (slo_name, version, objectives)."""
    sli = SLIDefinition(
        id=uuid.uuid4(), name="test-sli", version=1, adapter_type="prometheus",
        indicators={"response_time": {"query": "histogram_quantile(0.95, ...)"}, "error_rate": {"query": "rate(...)"}},
        tags={},
    )
    session.add(sli)

    slo_id = uuid.uuid4()
    slo = SLODefinition(
        id=slo_id, name="test-slo", version=1, display_name="Test SLO",
        comparison={"compare_with": "single_result", "number_of_comparison_results": 3},
        total_score_pass_pct=90.0, total_score_warning_pct=75.0,
        tags={}, variables={},
    )
    session.add(slo)

    obj1 = SLOObjective(
        id=uuid.uuid4(), slo_definition_id=slo_id, sli="response_time",
        display_name="Response Time P95", weight=1, key_sli=True,
        sort_order=0, pass_criteria=["<600"], warning_criteria=["<800"],
        tab_group="latency",
    )
    obj2 = SLOObjective(
        id=uuid.uuid4(), slo_definition_id=slo_id, sli="error_rate",
        display_name="Error Rate", weight=2, key_sli=False,
        sort_order=1, pass_criteria=["<2"], warning_criteria=["<5"],
        tab_group=None,
    )
    session.add_all([obj1, obj2])
    await session.flush()
    return "test-slo", 1, [obj1, obj2]


async def _create_asset(session: AsyncSession) -> uuid.UUID:
    type_name = f"vm-{uuid.uuid4().hex[:8]}"
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=f"asset-{asset_id.hex[:8]}", type_name=type_name, tags={}, variables={}))
    await session.flush()
    return asset_id


async def _create_eval(session: AsyncSession, asset_id: uuid.UUID) -> uuid.UUID:
    eval_id = uuid.uuid4()
    session.add(Evaluation(
        id=eval_id, evaluation_name="test", asset_id=asset_id,
        period_start=_START, period_end=_END,
        slo_name="test-slo", slo_version=1,
        ingestion_mode="push", status="completed", result="pass", score=90.0,
        indicator_results=[],  # JSONB column still exists during migration
    ))
    await session.flush()
    return eval_id


@pytest.mark.integration
async def test_bulk_insert_and_read_back(db_session: AsyncSession) -> None:
    """Write indicator rows, read them back, verify fields match."""
    slo_name, slo_version, objectives = await _seed_slo_with_objectives(db_session)
    asset_id = await _create_asset(db_session)
    eval_id = await _create_eval(db_session, asset_id)

    repo = IndicatorRepository(db_session)

    rows_to_insert = [
        {
            "evaluation_id": eval_id,
            "slo_objective_id": objectives[0].id,
            "value": 580.0,
            "compared_value": 500.0,
            "change_absolute": 80.0,
            "change_relative_pct": 16.0,
            "status": "pass",
            "score": 1.0,
        },
        {
            "evaluation_id": eval_id,
            "slo_objective_id": objectives[1].id,
            "value": 5.2,
            "compared_value": 1.0,
            "change_absolute": 4.2,
            "change_relative_pct": 420.0,
            "status": "fail",
            "score": 0.0,
        },
    ]
    await repo.bulk_insert(eval_id, rows_to_insert)

    result = await db_session.execute(
        select(IndicatorResultRow).where(IndicatorResultRow.evaluation_id == eval_id)
    )
    rows = list(result.scalars().all())
    assert len(rows) == 2

    pass_row = next(r for r in rows if r.status == "pass")
    assert pass_row.value == 580.0
    assert pass_row.compared_value == 500.0
    assert pass_row.slo_objective_id == objectives[0].id

    fail_row = next(r for r in rows if r.status == "fail")
    assert fail_row.value == 5.2
    assert fail_row.score == 0.0


@pytest.mark.integration
async def test_delete_and_reinsert(db_session: AsyncSession) -> None:
    """Re-evaluation pattern: delete old rows, insert new set."""
    slo_name, slo_version, objectives = await _seed_slo_with_objectives(db_session)
    asset_id = await _create_asset(db_session)
    eval_id = await _create_eval(db_session, asset_id)

    repo = IndicatorRepository(db_session)

    # Initial insert
    await repo.bulk_insert(eval_id, [{
        "evaluation_id": eval_id,
        "slo_objective_id": objectives[0].id,
        "value": 580.0, "compared_value": None,
        "change_absolute": None, "change_relative_pct": None,
        "status": "pass", "score": 1.0,
    }])

    # Delete + reinsert (re-evaluation)
    await repo.delete_for_evaluation(eval_id)
    await repo.bulk_insert(eval_id, [{
        "evaluation_id": eval_id,
        "slo_objective_id": objectives[0].id,
        "value": 620.0, "compared_value": None,
        "change_absolute": None, "change_relative_pct": None,
        "status": "fail", "score": 0.0,
    }])

    result = await db_session.execute(
        select(IndicatorResultRow).where(IndicatorResultRow.evaluation_id == eval_id)
    )
    rows = list(result.scalars().all())
    assert len(rows) == 1
    assert rows[0].value == 620.0
    assert rows[0].status == "fail"
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `uv run --directory api pytest api/tests/db/test_indicator_repository.py -v`

Expected: ImportError

- [ ] **Step 3: Implement IndicatorRepository**

Create `api/app/modules/quality_gate/indicator_repository.py`:

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
        evaluation_id: uuid.UUID,
        rows: list[dict[str, Any]],
    ) -> None:
        """Insert indicator result rows for a single evaluation."""
        for row in rows:
            self._session.add(IndicatorResultRow(
                evaluation_id=evaluation_id,
                slo_objective_id=row["slo_objective_id"],
                value=row.get("value"),
                compared_value=row.get("compared_value"),
                change_absolute=row.get("change_absolute"),
                change_relative_pct=row.get("change_relative_pct"),
                status=row["status"],
                score=row.get("score", 0.0),
            ))
        await self._session.flush()

    async def delete_for_evaluation(self, evaluation_id: uuid.UUID) -> None:
        """Delete all indicator rows for an evaluation (used by re-evaluation)."""
        await self._session.execute(
            delete(IndicatorResultRow).where(
                IndicatorResultRow.evaluation_id == evaluation_id
            )
        )
        await self._session.flush()
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `uv run --directory api pytest api/tests/db/test_indicator_repository.py -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```
git add api/app/modules/quality_gate/indicator_repository.py api/tests/db/test_indicator_repository.py
git commit -m "feat: add IndicatorRepository for normalized indicator results"
```

---

### Task 5: Rewrite presenter to accept ORM rows

**Files:**
- Modify: `api/app/modules/quality_gate/presenter.py`
- Modify: `api/tests/services/test_presenter.py`

The presenter is the central transformation layer. Rewrite it to accept either JSONB dicts (backwards-compatible during migration) or ORM `IndicatorResultRow` objects with joined objectives.

- [ ] **Step 1: Read current test helpers**

Read `api/tests/services/test_presenter.py` to understand `_make_evaluation` and `_make_annotation` helper signatures. The tests currently pass JSONB dicts via `indicator_results=[{...}]`.

- [ ] **Step 2: Write tests for the new ORM-based path**

Add to `api/tests/services/test_presenter.py`. Create a helper that builds fake `IndicatorResultRow`-like objects:

```python
def _make_indicator_row(
    *,
    sli: str = "response_time",
    display_name: str = "Response Time",
    tab_group: str | None = None,
    value: float | None = 580.0,
    compared_value: float | None = 500.0,
    change_absolute: float | None = 80.0,
    change_relative_pct: float | None = 16.0,
    status: str = "pass",
    score: float = 1.0,
    weight: int = 1,
    key_sli: bool = False,
    pass_criteria: list[str] | None = None,
    warning_criteria: list[str] | None = None,
) -> SimpleNamespace:
    """Build a fake ORM IndicatorResultRow with joined objective."""
    objective = SimpleNamespace(
        sli=sli,
        display_name=display_name,
        tab_group=tab_group,
        weight=weight,
        key_sli=key_sli,
        pass_criteria=pass_criteria or ["<600"],
        warning_criteria=warning_criteria or [],
    )
    return SimpleNamespace(
        value=value,
        compared_value=compared_value,
        change_absolute=change_absolute,
        change_relative_pct=change_relative_pct,
        status=status,
        score=score,
        objective=objective,
    )


def test_build_detail_from_orm_rows():
    """build_detail works with ORM indicator rows (new path)."""
    row_pass = _make_indicator_row(status="pass", value=580.0)
    row_fail = _make_indicator_row(
        sli="error_rate", display_name="Error Rate", status="fail",
        value=5.2, score=0.0, weight=2, pass_criteria=["<2"],
    )
    ev = _make_evaluation(indicator_results=[])
    ev.indicator_rows = [row_pass, row_fail]
    detail = build_detail(ev)
    assert len(detail.indicator_results) == 2
    assert detail.indicator_results[0].metric == "response_time"
    assert detail.indicator_results[1].status == "fail"
    assert len(detail.top_failures) == 1
    assert detail.top_failures[0].metric == "error_rate"


def test_build_summary_from_orm_rows():
    """build_summary works with ORM indicator rows (new path)."""
    row_fail = _make_indicator_row(
        sli="error_rate", display_name="Error Rate", status="fail",
        value=5.2, score=0.0, pass_criteria=["<2"],
    )
    ev = _make_evaluation(indicator_results=[])
    ev.indicator_rows = [row_fail]
    summary = build_summary(ev, annotation_count=0, latest_ann=None)
    assert len(summary.top_failures) == 1
    assert summary.top_failures[0].threshold == "<2"
```

- [ ] **Step 3: Run tests — verify they fail**

Run: `uv run --directory api pytest api/tests/services/test_presenter.py::test_build_detail_from_orm_rows -v`

Expected: FAIL — `indicator_rows` attribute not used yet

- [ ] **Step 4: Rewrite presenter**

Modify `api/app/modules/quality_gate/presenter.py` to check for `indicator_rows` (ORM path) first, fall back to `indicator_results` (JSONB path):

```python
"""Evaluation presenter — transform ORM models into API response schemas."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.quality_gate.schemas import (
    AnnotationRead,
    EvaluationDetail,
    EvaluationSummary,
    FailingIndicator,
    IndicatorResult,
)
from app.modules.quality_gate.target_resolver import resolve_targets


def _indicators_from_orm_rows(rows: list) -> list[IndicatorResult]:
    """Build IndicatorResult schema objects from ORM IndicatorResultRow with joined objectives."""
    results: list[IndicatorResult] = []
    for row in rows:
        obj = row.objective
        results.append(IndicatorResult(
            metric=obj.sli,
            display_name=obj.display_name,
            tab_group=getattr(obj, "tab_group", None),
            value=row.value,
            compared_value=row.compared_value,
            change_absolute=row.change_absolute,
            change_relative_pct=row.change_relative_pct,
            aggregation=None,  # not stored on indicator_results; derivable from SLI def
            status=row.status,
            score=row.score,
            weight=obj.weight,
            key_sli=obj.key_sli,
            pass_targets=resolve_targets(
                list(obj.pass_criteria) if obj.pass_criteria else None,
                value=row.value,
                compared_value=row.compared_value,
            ),
            warning_targets=resolve_targets(
                list(obj.warning_criteria) if obj.warning_criteria else None,
                value=row.value,
                compared_value=row.compared_value,
            ),
        ))
    return results


def _indicators_from_jsonb(dicts: list[dict[str, Any]]) -> list[IndicatorResult]:
    """Build IndicatorResult schema objects from JSONB dicts (legacy path)."""
    return [IndicatorResult(**ir) for ir in dicts]


def _get_indicator_results(ev: object) -> list[IndicatorResult]:
    """Get indicator results from either ORM rows (new) or JSONB dicts (legacy)."""
    orm_rows = getattr(ev, "indicator_rows", None)
    if orm_rows:
        return _indicators_from_orm_rows(orm_rows)
    jsonb = getattr(ev, "indicator_results", []) or []
    if jsonb:
        return _indicators_from_jsonb(jsonb)
    return []


def _top_failures(indicators: list[IndicatorResult]) -> list[FailingIndicator]:
    """Extract failing indicators into top_failures list."""
    return [
        FailingIndicator(
            metric=ind.metric,
            display_name=ind.display_name,
            value=ind.value,
            threshold=(ind.pass_targets or [{}])[0].get("criteria", ""),
        )
        for ind in indicators
        if ind.status == "fail"
    ]


def build_summary(
    ev: object, annotation_count: int, latest_ann: object | None
) -> EvaluationSummary:
    """Transform ORM Evaluation into API summary schema."""
    indicators = _get_indicator_results(ev)
    job_stats = getattr(ev, "job_stats", None) or {}
    return EvaluationSummary.model_validate(
        {
            **ev.__dict__,
            "original_score": job_stats.get("original_score"),
            "annotation_count": annotation_count,
            "latest_annotation": latest_ann,
            "top_failures": _top_failures(indicators),
        }
    )


def build_detail(ev: Any) -> EvaluationDetail:
    """Transform ORM Evaluation with annotations into API detail schema."""
    annotations = [
        AnnotationRead.model_validate(a) for a in (ev.annotations or []) if a.hidden_at is None
    ]
    indicators = _get_indicator_results(ev)
    job_stats_detail = ev.job_stats or {}
    compared_ids = job_stats_detail.get("compared_evaluation_ids", [])
    sorted_annotations = sorted(annotations, key=lambda a: a.created_at)
    return EvaluationDetail.model_validate(
        {
            **ev.__dict__,
            "original_score": job_stats_detail.get("original_score"),
            "annotation_count": len(annotations),
            "latest_annotation": sorted_annotations[-1] if sorted_annotations else None,
            "top_failures": _top_failures(indicators),
            "compared_evaluation_ids": [uuid.UUID(eid) for eid in compared_ids],
            "annotations": sorted_annotations,
            "indicator_results": indicators,
        }
    )
```

Note: The `_top_failures` function handles both dict-based `pass_targets` (from JSONB path where targets are dicts) and the ORM path (where targets are also dicts from `resolve_targets`).

- [ ] **Step 5: Run all presenter tests**

Run: `uv run --directory api pytest api/tests/services/test_presenter.py -v`

Expected: All PASS — both old JSONB-based tests and new ORM-based tests

- [ ] **Step 6: Commit**

```
git add api/app/modules/quality_gate/presenter.py api/tests/services/test_presenter.py
git commit -m "feat: rewrite presenter to support ORM indicator rows"
```

---

### Task 6: Rewrite worker write path

**Files:**
- Modify: `api/app/modules/quality_gate/worker.py:278-320`
- Modify: `api/app/modules/quality_gate/repository.py:150-190`

The worker currently serializes engine `IndicatorResult` to dicts and writes them as JSONB. Change it to also write to the `indicator_results` relational table. During migration, write to BOTH (dual-write) so the JSONB column still works for any code not yet migrated.

- [ ] **Step 1: Read current worker write path**

Read `api/app/modules/quality_gate/worker.py` lines 270-320 to understand the exact flow.

- [ ] **Step 2: Add objective lookup to worker**

The worker needs to match each engine `IndicatorResult.metric` to the corresponding `SLOObjective.id`. The SLO objectives are loaded when the worker fetches the SLO definition. Read `worker.py` to find where the SLO definition is loaded and how to access its objectives.

- [ ] **Step 3: Modify worker to dual-write**

After the existing `mark_completed()` call, add a call to `IndicatorRepository.bulk_insert()`:

Add at the top of `worker.py` (file-level import):
```python
from app.modules.quality_gate.indicator_repository import IndicatorRepository
```

Then after the existing `mark_completed()` call:
```python
# After mark_completed — write to normalized table
indicator_repo = IndicatorRepository(session)

# Build objective lookup: metric_name -> SLOObjective.id
# slo_def is the ORM SLODefinition loaded earlier in the worker
obj_lookup = {obj.sli: obj.id for obj in slo_def.objectives}

indicator_rows = []
for ir in eval_result.indicator_results:
    obj_id = obj_lookup.get(ir.metric)
    if obj_id is None:
        continue  # should not happen — log warning
    indicator_rows.append({
        "evaluation_id": eval_id,
        "slo_objective_id": obj_id,
        "value": ir.value,
        "compared_value": ir.compared_value,
        "change_absolute": ir.change_absolute,
        "change_relative_pct": ir.change_relative_pct,
        "status": ir.status,
        "score": ir.score,
    })

if indicator_rows:
    await indicator_repo.bulk_insert(eval_id, indicator_rows)
```

Note: This must happen WITHIN the same database session/transaction as `mark_completed()` for write atomicity.

- [ ] **Step 4: Run integration tests**

Run: `uv run --directory api pytest api/tests/ -m integration -v`

Expected: All PASS — dual-write doesn't break existing reads

- [ ] **Step 5: Commit**

```
git add api/app/modules/quality_gate/worker.py
git commit -m "feat: dual-write indicator results to normalized table"
```

---

### Task 7: Rewrite repository read path

**Files:**
- Modify: `api/app/modules/quality_gate/repository.py`

Change `get_by_id()` to eager-load `indicator_rows` with joined objectives. The presenter (Task 5) already handles both paths, so this switch is transparent.

- [ ] **Step 1: Modify get_by_id to eager-load indicator_rows**

In `repository.py`, find `get_by_id()` and add eager loading for `indicator_rows`:

```python
from sqlalchemy.orm import selectinload, joinedload
from app.db.models import IndicatorResultRow

# In get_by_id:
result = await self._session.execute(
    select(Evaluation)
    .options(
        selectinload(Evaluation.annotations),
        selectinload(Evaluation.indicator_rows).joinedload(IndicatorResultRow.objective),
    )
    .where(Evaluation.id == eval_id)
)
```

- [ ] **Step 2: Run round-trip integration tests**

Run: `uv run --directory api pytest api/tests/db/test_indicator_round_trip.py -v`

Expected: All PASS — the presenter sees `indicator_rows` populated and uses the ORM path

- [ ] **Step 3: Run all integration tests**

Run: `uv run --directory api pytest api/tests/ -m integration -v`

Expected: All PASS

- [ ] **Step 4: Commit**

```
git add api/app/modules/quality_gate/repository.py
git commit -m "feat: eager-load indicator rows in get_by_id"
```

---

### Task 8: Rewrite trend and heatmap queries

**Files:**
- Modify: `api/app/modules/quality_gate/trend_repository.py`
- Modify: `api/app/modules/quality_gate/router.py:140-170`

Trend query currently extracts `compared_value` from JSONB. Heatmap iterates JSONB dicts. Both must join `indicator_results` + `slo_objectives`.

- [ ] **Step 1: Read current trend query**

Read `api/app/modules/quality_gate/trend_repository.py` lines 44-95 to understand the JSONB extraction pattern.

- [ ] **Step 2: Rewrite get_trend_by_domain**

Replace the JSONB extraction with a join to `indicator_results`:

```python
# Instead of selecting Evaluation.indicator_results JSONB and extracting in Python,
# join IndicatorResultRow and filter by metric_name via the objective:
inner = (
    select(
        Evaluation.period_start,
        SLIValue.value,
        SLIValue.eval_id,
        Evaluation.result,
        IndicatorResultRow.compared_value,  # direct column access
    )
    .join(Evaluation, SLIValue.eval_id == Evaluation.id)
    .join(
        IndicatorResultRow,
        IndicatorResultRow.evaluation_id == Evaluation.id,
    )
    .join(
        SLOObjective,
        IndicatorResultRow.slo_objective_id == SLOObjective.id,
    )
    .where(
        SLOObjective.sli == metric_name,
        # ... existing filters
    )
)
```

Then remove the Python loop that extracts `compared_value` from JSONB.

- [ ] **Step 3: Rewrite heatmap cell construction in router**

In `router.py` lines 140-170, replace the JSONB iteration with a query that joins indicator_rows:

The heatmap endpoint currently loads full evaluations with JSONB, then iterates `ev.indicator_results`. Change to use `ev.indicator_rows` (eager-loaded via the `lazy="selectin"` on the relationship defined in Task 2, with `objective` sub-joined via `lazy="joined"`) and read fields from the joined objective. If the heatmap query uses a custom `select()` that doesn't trigger the relationship, add explicit `selectinload(Evaluation.indicator_rows).joinedload(IndicatorResultRow.objective)` options.

- [ ] **Step 4: Run heatmap and trend tests**

Run: `uv run --directory api pytest api/tests/db/test_heatmap_query.py api/tests/db/test_trend_query.py -v`

Expected: All PASS

- [ ] **Step 5: Run endpoint tests for heatmap**

Run: `uv run --directory api pytest api/tests/endpoints/test_heatmap_endpoints.py -v`

Expected: All PASS

- [ ] **Step 6: Commit**

```
git add api/app/modules/quality_gate/trend_repository.py api/app/modules/quality_gate/router.py
git commit -m "feat: rewrite trend and heatmap queries to use normalized table"
```

---

### Task 9: Rewrite re-evaluator and baseline repository

**Files:**
- Modify: `api/app/modules/quality_gate/re_evaluator.py`
- Modify: `api/app/modules/quality_gate/baseline_repository.py`

Re-evaluator reads old indicator_results to extract metrics, and baseline_repository writes new results. Both must use the normalized table.

- [ ] **Step 1: Rewrite _metrics_from_indicator_results**

In `re_evaluator.py`, change to read from ORM rows:

```python
def _metrics_from_indicator_rows(
    indicator_rows: list,
) -> dict[str, float | None]:
    """Extract metric name -> value mapping from normalized indicator rows."""
    return {row.objective.sli: row.value for row in indicator_rows}
```

Update callers to use `ev.indicator_rows` instead of `ev.indicator_results`.

- [ ] **Step 2: Rewrite _compute_baselines**

Change to iterate `ev.indicator_rows` instead of JSONB dicts.

- [ ] **Step 3: Rewrite update_reeval_result in baseline_repository**

Change from JSONB overwrite to DELETE + INSERT pattern:

```python
async def update_reeval_result(self, eval_id, *, new_indicator_rows, ...):
    # Delete old indicator rows
    indicator_repo = IndicatorRepository(self._session)
    await indicator_repo.delete_for_evaluation(eval_id)
    # Insert new rows
    await indicator_repo.bulk_insert(eval_id, new_indicator_rows)
    # Update evaluation result/score (no JSONB write)
    ...
```

- [ ] **Step 4: Run re-evaluation tests**

Run: `uv run --directory api pytest api/tests/db/test_re_evaluation.py -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```
git add api/app/modules/quality_gate/re_evaluator.py api/app/modules/quality_gate/baseline_repository.py
git commit -m "feat: rewrite re-evaluator and baseline repo for normalized indicators"
```

---

### Task 10: Migrate existing JSONB indicator data to normalized table

**Files:**
- Create: `scripts/migrate_indicator_results.py`

Existing evaluations have indicator data only in the JSONB column. This script migrates that data into the new `indicator_results` table by matching each JSONB entry's `metric` field to the corresponding `slo_objective`.

- [ ] **Step 1: Write migration script**

Create `scripts/migrate_indicator_results.py`:

```python
"""One-time data migration: indicator_results JSONB → normalized table.

Run with: uv run python scripts/migrate_indicator_results.py
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Evaluation, IndicatorResultRow, SLODefinition, SLOObjective
from app.config import get_settings

logger = logging.getLogger(__name__)


async def _resolve_objectives(
    session: AsyncSession,
    slo_name: str,
    slo_version: int | None,
    created_at,
) -> dict[str, uuid.UUID]:
    """Build metric_name -> objective_id lookup for this evaluation's SLO."""
    if slo_version is not None:
        q = (
            select(SLOObjective)
            .join(SLODefinition)
            .where(SLODefinition.name == slo_name, SLODefinition.version == slo_version)
        )
    else:
        # Fallback: latest version at or before evaluation creation time
        version_q = (
            select(func.max(SLODefinition.version))
            .where(SLODefinition.name == slo_name, SLODefinition.created_at <= created_at)
        )
        version = (await session.execute(version_q)).scalar_one_or_none()
        if version is None:
            # Last resort: current latest version
            version_q = (
                select(func.max(SLODefinition.version))
                .where(SLODefinition.name == slo_name)
            )
            version = (await session.execute(version_q)).scalar_one_or_none()
            if version is None:
                return {}
            logger.warning("No SLO version found at eval time for %s, using latest v%d", slo_name, version)
        q = (
            select(SLOObjective)
            .join(SLODefinition)
            .where(SLODefinition.name == slo_name, SLODefinition.version == version)
        )

    rows = await session.execute(q)
    return {obj.sli: obj.id for obj in rows.scalars().all()}


async def migrate(session: AsyncSession) -> tuple[int, int]:
    """Migrate all evaluations with JSONB indicator_results to normalized table.

    Returns (migrated_count, skipped_count).
    """
    # Only migrate evaluations that have JSONB data but no normalized rows yet
    q = (
        select(Evaluation)
        .where(
            Evaluation.indicator_results.isnot(None),
            Evaluation.indicator_results != [],
        )
        .outerjoin(IndicatorResultRow, IndicatorResultRow.evaluation_id == Evaluation.id)
        .group_by(Evaluation.id)
        .having(func.count(IndicatorResultRow.id) == 0)
        .order_by(Evaluation.created_at)
    )
    result = await session.execute(q)
    evals = list(result.scalars().all())

    migrated = 0
    skipped = 0
    obj_cache: dict[tuple[str, int | None], dict[str, uuid.UUID]] = {}

    for ev in evals:
        cache_key = (ev.slo_name, ev.slo_version)
        if cache_key not in obj_cache:
            obj_cache[cache_key] = await _resolve_objectives(
                session, ev.slo_name, ev.slo_version, ev.created_at,
            )
        obj_lookup = obj_cache[cache_key]

        if not obj_lookup:
            logger.warning("No objectives found for eval %s (slo=%s, v=%s)", ev.id, ev.slo_name, ev.slo_version)
            skipped += 1
            continue

        for ir in ev.indicator_results:
            metric = ir.get("metric", "")
            obj_id = obj_lookup.get(metric)
            if obj_id is None:
                logger.warning("No objective match for metric %r in eval %s", metric, ev.id)
                continue
            session.add(IndicatorResultRow(
                evaluation_id=ev.id,
                slo_objective_id=obj_id,
                value=ir.get("value"),
                compared_value=ir.get("compared_value"),
                change_absolute=ir.get("change_absolute"),
                change_relative_pct=ir.get("change_relative_pct"),
                status=ir.get("status", "error"),
                score=ir.get("score", 0.0),
            ))
        migrated += 1

        # Flush in batches of 100
        if migrated % 100 == 0:
            await session.flush()
            logger.info("Migrated %d evaluations...", migrated)

    await session.flush()
    return migrated, skipped


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    engine = create_async_engine(settings.db.url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        async with session.begin():
            migrated, skipped = await migrate(session)
            logger.info("Migration complete: %d migrated, %d skipped", migrated, skipped)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run migration against test DB**

First seed some test data, then run:
```
uv run python scripts/migrate_indicator_results.py
```

Verify by checking row counts:
```
uv run python -c "
import asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import IndicatorResultRow
from app.config import get_settings

async def check():
    settings = get_settings()
    engine = create_async_engine(settings.db.url)
    async with sessionmaker(engine, class_=AsyncSession)() as s:
        count = (await s.execute(select(func.count(IndicatorResultRow.id)))).scalar()
        print(f'indicator_results rows: {count}')
    await engine.dispose()

asyncio.run(check())
"
```

- [ ] **Step 3: Commit**

```
git add scripts/migrate_indicator_results.py
git commit -m "feat: add data migration script for indicator_results JSONB to normalized table"
```

---

### Task 11: Drop JSONB column and clean up dual-write

**Files:**
- Modify: `api/app/db/models.py` — remove `indicator_results` column from Evaluation
- Modify: `api/app/modules/quality_gate/repository.py` — remove JSONB from `mark_completed()`
- Modify: `api/app/modules/quality_gate/worker.py` — remove dict serialization, only write to normalized table
- Modify: `api/app/modules/quality_gate/presenter.py` — remove JSONB fallback path

This is the point of no return. All read/write paths must use the normalized table before this step.

- [ ] **Step 1: Remove indicator_results column from model**

In `api/app/db/models.py`, remove:
```python
indicator_results: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"), default=list)
```

- [ ] **Step 2: Remove JSONB from mark_completed**

In `repository.py`, remove `indicator_results` from the `mark_completed()` values dict. Remove the `indicator_results` parameter entirely.

- [ ] **Step 3: Remove JSONB serialization from worker**

In `worker.py`, remove the `indicator_dicts = [ir.model_dump() ...]` line and the `indicator_results=indicator_dicts` parameter to `mark_completed()`.

- [ ] **Step 4: Remove JSONB fallback from presenter**

In `presenter.py`, remove `_indicators_from_jsonb()` and the fallback in `_get_indicator_results()`. Only keep the ORM row path.

- [ ] **Step 5: Remove JSONB from baseline_repository**

In `baseline_repository.py`, remove `"indicator_results": new_indicator_results` from `update_reeval_result()` values dict.

- [ ] **Step 6: Regenerate migrations**

Run: `./scripts/db-regen-migrations.sh`

- [ ] **Step 7: Apply migration to test DB**

Run: `ENV_FILE=.env.test uv run --directory api alembic upgrade head`

- [ ] **Step 8: Run ALL tests**

Run: `uv run --directory api pytest api/tests/ -m integration -v`
Run: `uv run --directory api pytest api/tests/ -m "not integration" -v`

Expected: All PASS. Any test that referenced `indicator_results` JSONB directly will need updating — check test fixtures.

- [ ] **Step 9: Lint and type check**

Run: `uv run ruff check api/`
Run: `uv run mypy api/app`

- [ ] **Step 10: Commit**

```
git add api/app/db/models.py api/app/modules/quality_gate/repository.py api/app/modules/quality_gate/worker.py api/app/modules/quality_gate/presenter.py api/app/modules/quality_gate/baseline_repository.py
git commit -m "feat: drop indicator_results JSONB column, use normalized table exclusively"
```

---

### Task 12: Redis cache utility

**Files:**
- Create: `api/app/cache/__init__.py`
- Create: `api/app/cache/redis_cache.py`
- Create: `api/tests/cache/__init__.py`
- Create: `api/tests/cache/test_redis_cache.py`

Generic read-through cache utility. Tier 1 (immutable, no TTL), Tier 2 (event invalidation), Tier 3 (TTL + event invalidation).

- [ ] **Step 1: Write failing tests**

Create `api/tests/cache/__init__.py` (empty).

Create `api/tests/cache/test_redis_cache.py`:

```python
"""Unit tests for Redis cache utility (uses fakeredis)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from app.cache.redis_cache import RedisCache


@pytest.fixture()
def mock_redis():
    """Provide a mock Redis client."""
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock()
    r.delete = AsyncMock()
    return r


async def test_cache_miss_calls_loader(mock_redis) -> None:
    cache = RedisCache(mock_redis)
    loader = AsyncMock(return_value='{"name": "test-slo", "version": 1}')

    result = await cache.get_or_load("slo:test:v1", loader)

    assert result == '{"name": "test-slo", "version": 1}'
    loader.assert_called_once()
    mock_redis.set.assert_called_once_with("slo:test:v1", '{"name": "test-slo", "version": 1}')


async def test_cache_hit_skips_loader(mock_redis) -> None:
    mock_redis.get = AsyncMock(return_value=b'{"cached": true}')
    cache = RedisCache(mock_redis)
    loader = AsyncMock()

    result = await cache.get_or_load("key", loader)

    assert result == '{"cached": true}'
    loader.assert_not_called()


async def test_cache_with_ttl(mock_redis) -> None:
    cache = RedisCache(mock_redis)
    loader = AsyncMock(return_value='{"data": 1}')

    await cache.get_or_load("key", loader, ttl_seconds=300)

    mock_redis.set.assert_called_once_with("key", '{"data": 1}', ex=300)


async def test_invalidate_key(mock_redis) -> None:
    cache = RedisCache(mock_redis)
    await cache.invalidate("slo:test:latest")
    mock_redis.delete.assert_called_once_with("slo:test:latest")


async def test_cache_miss_loader_returns_none(mock_redis) -> None:
    """If loader returns None, don't cache it."""
    cache = RedisCache(mock_redis)
    loader = AsyncMock(return_value=None)

    result = await cache.get_or_load("key", loader)

    assert result is None
    mock_redis.set.assert_not_called()
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `uv run --directory api pytest api/tests/cache/test_redis_cache.py -v`

Expected: ImportError

- [ ] **Step 3: Implement RedisCache**

Create `api/app/cache/__init__.py` (empty).

Create `api/app/cache/redis_cache.py`:

```python
"""Generic read-through Redis cache utility."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class RedisCache:
    """Read-through cache with optional TTL and manual invalidation."""

    def __init__(self, redis: Any) -> None:
        self._redis = redis

    async def get_or_load(
        self,
        key: str,
        loader: Callable[[], Awaitable[str | None]],
        ttl_seconds: int | None = None,
    ) -> str | None:
        """Return cached value or call loader, cache result, and return it."""
        cached = await self._redis.get(key)
        if cached is not None:
            return cached.decode() if isinstance(cached, bytes) else cached

        value = await loader()
        if value is None:
            return None

        if ttl_seconds is not None:
            await self._redis.set(key, value, ex=ttl_seconds)
        else:
            await self._redis.set(key, value)
        return value

    async def invalidate(self, key: str) -> None:
        """Remove a cached entry."""
        await self._redis.delete(key)
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `uv run --directory api pytest api/tests/cache/test_redis_cache.py -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```
git add api/app/cache/ api/tests/cache/
git commit -m "feat: add Redis read-through cache utility"
```

---

### Task 13: Cache SLO/SLI definitions (Tier 1 — immutable)

**Files:**
- Modify: `api/app/modules/slo_registry/repository.py`
- Modify: `api/app/modules/sli_registry/repository.py`

Add caching to SLO and SLI definition lookups. These are versioned and immutable — cache permanently (no TTL). A new version creates a new cache key.

- [ ] **Step 1: Read SLO repository**

Read `api/app/modules/slo_registry/repository.py` to find the `get_by_name_and_version()` and `get_latest()` methods.

- [ ] **Step 2: Add cache to SLO repository**

Wrap the existing query methods with `RedisCache.get_or_load()`:

```python
# In SLORepository:
async def get_by_name_and_version(self, name: str, version: int) -> SLODefinition | None:
    key = f"slo:{name}:v{version}"
    cached = await self._cache.get_or_load(key, lambda: self._load_slo(name, version))
    ...
```

The cache instance should be passed via constructor or accessed from a singleton. For simplicity, add a `_cache: RedisCache | None` parameter to the repository constructor, defaulting to `None` (no caching when running without Redis, e.g. in tests).

- [ ] **Step 3: Add cache invalidation on version create**

In the SLO create method, after inserting a new version:
```python
if self._cache:
    await self._cache.invalidate(f"slo:{slo.name}:latest")
```

- [ ] **Step 4: Repeat for SLI repository**

Same pattern: cache `sli:{name}:v{version}` permanently, invalidate `sli:{name}:latest` on new version.

- [ ] **Step 5: Run existing SLO/SLI tests**

Run: `uv run --directory api pytest api/tests/db/test_slo_repository.py api/tests/db/test_sli_repository.py -v`

Expected: All PASS — cache is None in tests, so no caching logic executes.

- [ ] **Step 6: Commit**

```
git add api/app/modules/slo_registry/repository.py api/app/modules/sli_registry/repository.py
git commit -m "feat: add Redis caching for SLO/SLI definitions (Tier 1)"
```

---

### Task 14: Cache assets and tags (Tier 2 — event invalidation)

**Files:**
- Modify: `api/app/modules/assets/repository.py`

Cache asset lookups by ID and by name. Invalidate on asset update/delete.

- [ ] **Step 1: Read asset repository**

Read `api/app/modules/assets/repository.py` to find `get_by_id()`, `get_by_name()` methods.

- [ ] **Step 2: Add cache to asset reads**

```python
# Cache keys: asset:{id}, asset:name:{name}, asset:{id}:tags
async def get_by_id(self, asset_id: uuid.UUID) -> Asset | None:
    key = f"asset:{asset_id}"
    # read-through with no TTL
    ...
```

- [ ] **Step 3: Add cache invalidation on asset writes**

On update/delete, invalidate both `asset:{id}` and `asset:name:{name}` and `asset:{id}:tags`.

- [ ] **Step 4: Run asset tests**

Run: `uv run --directory api pytest api/tests/db/test_asset_repositories.py -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```
git add api/app/modules/assets/repository.py
git commit -m "feat: add Redis caching for assets (Tier 2)"
```

---

### Task 15: Cache baselines and annotations (Tier 3 — TTL)

**Files:**
- Modify: `api/app/modules/quality_gate/baseline_repository.py`
- Modify: `api/app/modules/quality_gate/annotation_repository.py`

Baseline aggregates and annotation counts have 5-minute TTL + event invalidation.

- [ ] **Step 1: Add TTL cache to baseline queries**

```python
# Cache key: baseline:{asset_id}:{slo_name}, TTL 300s
# Invalidate on new eval completed
```

- [ ] **Step 2: Add TTL cache to annotation counts**

```python
# Cache keys: annot_count:{eval_id}, annot_latest:{eval_id}, TTL 300s
# Invalidate on annotation create/hide
```

- [ ] **Step 3: Run tests**

Run: `uv run --directory api pytest api/tests/ -m integration -v`

Expected: All PASS

- [ ] **Step 4: Commit**

```
git add api/app/modules/quality_gate/baseline_repository.py api/app/modules/quality_gate/annotation_repository.py
git commit -m "feat: add Redis caching for baselines and annotations (Tier 3)"
```

---

### Task 16: Wire cache into FastAPI lifespan + worker

**Files:**
- Modify: `api/app/main.py` — create Redis cache pool on startup, close on shutdown
- Modify: `api/app/modules/quality_gate/dependencies.py` — pass cache to repositories
- Modify: `api/app/queue.py` — pass cache to worker repositories

- [ ] **Step 1: Add Redis cache pool to lifespan**

In `api/app/main.py`, alongside the existing arq pool creation:

```python
import redis.asyncio as aioredis

# In lifespan:
cache_redis = await aioredis.from_url(settings.cache.url, db=settings.cache.db)
app.state.cache = RedisCache(cache_redis)
# On shutdown:
await cache_redis.close()
```

- [ ] **Step 2: Pass cache through dependencies**

In `dependencies.py`, update `get_qg_repos()` to accept the cache and pass it to repositories.

- [ ] **Step 3: Cache warming on worker startup**

In `queue.py` worker settings, add a startup hook that pre-loads all latest SLO/SLI versions and active assets.

- [ ] **Step 4: Run all tests**

Run: `uv run --directory api pytest api/tests/ -m integration -v`
Run: `uv run --directory api pytest api/tests/ -m "not integration" -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```
git add api/app/main.py api/app/modules/quality_gate/dependencies.py api/app/queue.py
git commit -m "feat: wire Redis cache into FastAPI lifespan and worker"
```

---

### Task 17: Full suite verification

This is a verification task — no new code.

- [ ] **Step 1: Run all backend unit tests**

Run: `uv run --directory api pytest api/tests/ -m "not integration" -v`

Expected: All pass

- [ ] **Step 2: Run all integration tests**

Run: `uv run --directory api pytest api/tests/ -m integration -v`

Expected: All pass

- [ ] **Step 3: Run UI tests**

Run: `cd ui && npx vitest run`

Expected: All pass — API response shapes are preserved

- [ ] **Step 4: Lint and type check**

Run: `uv run ruff check api/`
Run: `uv run mypy api/app`

Expected: Clean
