# Otava Change Point Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect distributional shifts (change points) in per-metric time series using Apache Otava's E-Divisive algorithm, surface them as indicators on heatmaps and trend charts, and provide a triage workflow for acknowledged/hidden change points.

**Architecture:** Change point detection runs as a fault-isolated step in the evaluation worker after SLO scoring. It reuses the existing pin-aware, version-aware `BaselineRepository` for history scoping — no separate history management. Detected change points are stored in a denormalized `change_points` table (identity fields on the row itself). Configuration is per-indicator via a separate `change_point_config` table keyed by `(slo_name, metric_name)`. The backend attaches change point markers to heatmap cells and trend points so the frontend just renders what it receives.

**Tech Stack:** Python 3.13, Apache Otava (`apache-otava` PyPI package), FastAPI, SQLAlchemy async, PostgreSQL, Redis (arq), React 19, ECharts, Tailwind CSS.

**Depends on:** `comparable_from_version` fix — baseline queries must filter by SLO version compatibility, not just `(asset_id, slo_name)`. This plan assumes that fix has landed.

**Design spec:** `docs/superpowers/specs/2026-03-20-otava-change-point-detection-design.md` (original, now superseded by this plan for implementation details).

---

## Key Decisions (Updated from Original Spec)

1. **Otava is indicator-only** — never gates the build. Change points are supplementary markers.
2. **Per-indicator config** — each metric gets its own `window_size`, `min_sample_size`, and `enabled` flag via `change_point_config` table, keyed by `(slo_name, metric_name)`. This is decoupled from versioned SLO definitions.
3. **Reuse `BaselineRepository`** — the detector's history window respects baseline pins and `comparable_from_version` automatically.
4. **Baseline pin resets Otava** — when a pin is active, Otava only sees evaluations from the pin onward. A shift at the pin boundary is intentional, not a regression.
5. **Denormalized `change_points` table** — `asset_id`, `slo_name`, `metric_name`, `period_start` stored directly on the row (same pattern as `sli_values`). No complex join chains.
6. **Dedup by ordinal proximity** — before inserting, check `change_points` for the same `(asset_id, slo_name, metric_name)` within ±2 evaluations by `period_start` order. Single-table query.
7. **Backend provides markers** — heatmap cells and trend points include `change_point: {direction, magnitude} | null`. Frontend renders diamonds if present, nothing if null. No frontend filtering logic.

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `api/tropek/modules/change_points/__init__.py` | Package init |
| `api/tropek/modules/change_points/models.py` | `ChangePoint` and `ChangePointConfig` ORM models (will be added to `tropek/db/models.py` directly per project convention) |
| `api/tropek/modules/change_points/repository.py` | CRUD + dedup queries for `change_points` and `change_point_config` |
| `api/tropek/modules/change_points/schemas.py` | Pydantic request/response schemas |
| `api/tropek/modules/change_points/router.py` | FastAPI endpoints: list, detail, triage, bulk triage, config CRUD |
| `api/tropek/modules/change_points/detector.py` | Pure function wrapping Otava's E-Divisive API |
| `api/tropek/modules/change_points/worker_step.py` | Fault-isolated worker integration: history query → detect → dedup → insert |
| `api/alembic/versions/003_change_points.py` | Migration: `change_points` + `change_point_config` tables |
| `api/tests/change_points/` | Unit + integration tests |

### Modified Files

| File | Change |
|------|--------|
| `api/tropek/db/models.py` | Add `ChangePoint` and `ChangePointConfig` ORM classes |
| `api/tropek/queue.py` | Add phase 4 (change point detection) after SLI values write |
| `api/tropek/modules/quality_gate/schemas/heatmap.py` | Add `change_point` field to `HeatmapCellGrouped` |
| `api/tropek/modules/quality_gate/schemas/evaluations.py` | Add `change_point` field to `TrendPoint` and `IndicatorResult` |
| `api/tropek/modules/quality_gate/workflows/presentation/presenter.py` | Attach change point data to heatmap cells and indicator results |
| `api/tropek/modules/quality_gate/repositories/trend.py` | Join change points into trend query |
| `api/tropek/app.py` | Register change points router |
| `api/pyproject.toml` | Add `apache-otava` dependency |

---

## Task 1: Add `apache-otava` Dependency

**Files:**
- Modify: `api/pyproject.toml`

- [ ] **Step 1: Add dependency**

In `api/pyproject.toml`, add `apache-otava` to the `[project.dependencies]` list:

```toml
"apache-otava>=0.1",
```

- [ ] **Step 2: Install and verify import**

```bash
uv sync
uv run python -c "from otava.analysis import compute_change_points; print('ok')"
```

Expected: `ok` — confirms the library is importable and the `compute_change_points` function exists.

- [ ] **Step 3: Commit**

```bash
git add api/pyproject.toml uv.lock
git commit -m "feat(otava): add apache-otava dependency"
```

---

## Task 2: ORM Models — `ChangePoint` and `ChangePointConfig`

**Files:**
- Modify: `api/tropek/db/models.py`

- [ ] **Step 1: Add `ChangePointConfig` model**

Add after the `SLOObjective` class in `models.py`:

```python
class ChangePointConfig(Base):
    """Per-indicator Otava detection config — operational, not versioned with SLO."""

    __tablename__ = 'change_point_config'
    __table_args__ = (
        UniqueConstraint('slo_name', 'metric_name', name='uq_cp_config_slo_metric'),
    )

    # fmt: off
    id:              Mapped[uuid.UUID]      = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    slo_name:        Mapped[str]            = mapped_column(Text, nullable=False)
    metric_name:     Mapped[str]            = mapped_column(Text, nullable=False)
    enabled:         Mapped[bool]           = mapped_column(Boolean, nullable=False, server_default=false())
    window_size:     Mapped[int]            = mapped_column(Integer, nullable=False, server_default=text('30'))
    min_sample_size: Mapped[int]            = mapped_column(Integer, nullable=False, server_default=text('10'))
    created_at:      Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:      Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # fmt: on
```

- [ ] **Step 2: Add `ChangePoint` model**

Add after `ChangePointConfig`:

```python
class ChangePoint(Base):
    """Detected distributional shift for a single metric — denormalized identity."""

    __tablename__ = 'change_points'
    __table_args__ = (
        Index('idx_change_points_indicator', 'indicator_result_id'),
        Index('idx_change_points_identity', 'asset_id', 'slo_name', 'metric_name', 'period_start'),
        Index('idx_change_points_unprocessed', 'status', postgresql_where=text("status = 'unprocessed'")),
        Index('idx_change_points_created', 'created_at'),
    )

    # fmt: off
    id:                   Mapped[uuid.UUID]      = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    indicator_result_id:  Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('indicator_results.id', ondelete='SET NULL'), nullable=True)
    asset_id:             Mapped[uuid.UUID]      = mapped_column(UUID, nullable=False)
    slo_name:             Mapped[str]            = mapped_column(Text, nullable=False)
    metric_name:          Mapped[str]            = mapped_column(Text, nullable=False)
    period_start:         Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    direction:            Mapped[str]            = mapped_column(Text, nullable=False)  # "regression" | "improvement"
    change_relative_pct:  Mapped[float]          = mapped_column(Float, nullable=False)
    change_absolute:      Mapped[float]          = mapped_column(Float, nullable=False)
    t_statistic:          Mapped[float]          = mapped_column(Float, nullable=False)
    pre_segment_mean:     Mapped[float]          = mapped_column(Float, nullable=False)
    post_segment_mean:    Mapped[float]          = mapped_column(Float, nullable=False)
    status:               Mapped[str]            = mapped_column(Text, nullable=False, server_default=text("'unprocessed'"))
    triage_author:        Mapped[str | None]     = mapped_column(Text, nullable=True)
    triage_note:          Mapped[str | None]     = mapped_column(Text, nullable=True)
    triage_at:            Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    linked_ticket:        Mapped[str | None]     = mapped_column(Text, nullable=True)
    created_at:           Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:           Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # fmt: on
```

- [ ] **Step 3: Verify model compiles**

```bash
uv run python -c "from tropek.db.models import ChangePoint, ChangePointConfig; print('ok')"
```

- [ ] **Step 4: Commit**

```bash
git add api/tropek/db/models.py
git commit -m "feat(otava): add ChangePoint and ChangePointConfig ORM models"
```

---

## Task 3: Alembic Migration

**Files:**
- Create: `api/alembic/versions/003_change_points.py`

**Important:** Follow the project's migration workflow. Per the memory file `feedback_migration_workflow.md`, never write manual migrations — use `scripts/db-regen-migrations.sh` to regenerate from models. After Task 2 lands the models, run the regeneration script.

- [ ] **Step 1: Regenerate migration**

```bash
./scripts/db-regen-migrations.sh
```

This should produce a migration file that creates both `change_points` and `change_point_config` tables with all indexes and constraints from the model definitions.

- [ ] **Step 2: Review the generated migration**

Read the generated file and verify it creates:
- `change_point_config` table with `uq_cp_config_slo_metric` unique constraint
- `change_points` table with all 4 indexes (`idx_change_points_indicator`, `idx_change_points_identity`, `idx_change_points_unprocessed` partial, `idx_change_points_created`)
- FK from `change_points.indicator_result_id` → `indicator_results.id` with `ON DELETE SET NULL`

- [ ] **Step 3: Apply migration to test DB**

```bash
just test-env
just migrate-test
```

- [ ] **Step 4: Commit**

```bash
git add api/alembic/versions/
git commit -m "feat(otava): add migration for change_points and change_point_config tables"
```

---

## Task 4: Pure Detector — Otava Wrapper

**Files:**
- Create: `api/tropek/modules/change_points/__init__.py`
- Create: `api/tropek/modules/change_points/detector.py`
- Create: `api/tests/change_points/__init__.py`
- Create: `api/tests/change_points/test_detector.py`

This is a pure function with no I/O — wraps Otava's `compute_change_points` and translates results into domain objects.

- [ ] **Step 1: Write the test file**

```python
"""Unit tests for the Otava change point detector — pure function, no DB."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tropek.modules.change_points.detector import ChangePointResult, detect_change_points

_BASE = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)


def _timestamps(count: int) -> list[datetime]:
    return [_BASE + timedelta(hours=i) for i in range(count)]


class TestDetectChangePoints:
    """Tests for the detect_change_points pure function."""

    def test_no_change_in_flat_series(self) -> None:
        values = [10.0] * 30
        results = detect_change_points(
            values=values,
            timestamps=_timestamps(30),
            higher_is_better=False,
        )
        assert results == []

    def test_detects_step_regression_lower_is_better(self) -> None:
        # Clear step up from 10 → 50 at position 15 — regression when lower is better
        values = [10.0] * 15 + [50.0] * 15
        results = detect_change_points(
            values=values,
            timestamps=_timestamps(30),
            higher_is_better=False,
        )
        assert len(results) >= 1
        cp = results[0]
        assert cp.direction == 'regression'
        assert cp.change_absolute > 0
        assert cp.pre_segment_mean < cp.post_segment_mean

    def test_detects_step_improvement_lower_is_better(self) -> None:
        # Step down from 50 → 10 — improvement when lower is better
        values = [50.0] * 15 + [10.0] * 15
        results = detect_change_points(
            values=values,
            timestamps=_timestamps(30),
            higher_is_better=False,
        )
        assert len(results) >= 1
        assert results[0].direction == 'improvement'

    def test_detects_regression_higher_is_better(self) -> None:
        # Step down from 100 → 50 — regression when higher is better (throughput)
        values = [100.0] * 15 + [50.0] * 15
        results = detect_change_points(
            values=values,
            timestamps=_timestamps(30),
            higher_is_better=True,
        )
        assert len(results) >= 1
        assert results[0].direction == 'regression'

    def test_too_few_samples_returns_empty(self) -> None:
        values = [10.0, 50.0, 50.0]
        results = detect_change_points(
            values=values,
            timestamps=_timestamps(3),
            higher_is_better=False,
            min_sample_size=10,
        )
        assert results == []

    def test_result_has_all_fields(self) -> None:
        values = [10.0] * 15 + [50.0] * 15
        results = detect_change_points(
            values=values,
            timestamps=_timestamps(30),
            higher_is_better=False,
        )
        assert len(results) >= 1
        cp = results[0]
        assert isinstance(cp, ChangePointResult)
        assert isinstance(cp.position, int)
        assert isinstance(cp.timestamp, datetime)
        assert cp.direction in ('regression', 'improvement')
        assert isinstance(cp.change_relative_pct, float)
        assert isinstance(cp.change_absolute, float)
        assert isinstance(cp.t_statistic, float)
        assert isinstance(cp.pre_segment_mean, float)
        assert isinstance(cp.post_segment_mean, float)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./scripts/api-test.sh --tail 20 tests/change_points/test_detector.py -v
```

Expected: FAIL — module does not exist yet.

- [ ] **Step 3: Create the `__init__.py` files**

Create empty `api/tropek/modules/change_points/__init__.py` and `api/tests/change_points/__init__.py`.

- [ ] **Step 4: Implement the detector**

```python
"""Pure change point detector — wraps Apache Otava's E-Divisive algorithm.

No I/O. Takes a list of values + timestamps, returns detected change points
with direction, magnitude, and statistical significance.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from statistics import mean

from pydantic import BaseModel

from otava.analysis import compute_change_points


class ChangePointResult(BaseModel):
    """A single detected change point with direction and magnitude."""

    position: int
    timestamp: datetime
    direction: str  # "regression" | "improvement"
    change_relative_pct: float
    change_absolute: float
    t_statistic: float
    pre_segment_mean: float
    post_segment_mean: float


def detect_change_points(
    *,
    values: Sequence[float],
    timestamps: Sequence[datetime],
    higher_is_better: bool = False,
    window_size: int = 30,
    min_sample_size: int = 10,
    max_pvalue: float = 0.001,
) -> list[ChangePointResult]:
    """Run E-Divisive change point detection on a single metric time series.

    Args:
        values: Metric values in chronological order.
        timestamps: Corresponding timestamps (same length as values).
        higher_is_better: If True, a decrease is a regression (throughput).
                          If False, an increase is a regression (latency).
        window_size: Sliding window length for the algorithm.
        min_sample_size: Skip detection if fewer values than this.
        max_pvalue: Significance threshold for the t-test.

    Returns:
        List of detected change points, ordered by position.
    """
    if len(values) < min_sample_size:
        return []

    detected, _ = compute_change_points(
        series=list(values),
        window_len=min(window_size, len(values)),
        max_pvalue=max_pvalue,
    )

    results: list[ChangePointResult] = []
    for cp in detected:
        position = cp.index
        if position <= 0 or position >= len(values):
            continue

        pre_values = list(values[:position])
        post_values = list(values[position:])
        pre_mean = mean(pre_values)
        post_mean = mean(post_values)
        absolute_change = post_mean - pre_mean
        relative_change = (
            (absolute_change / pre_mean * 100) if pre_mean != 0 else 0.0
        )

        # Direction depends on metric polarity
        if higher_is_better:
            direction = 'regression' if post_mean < pre_mean else 'improvement'
        else:
            direction = 'regression' if post_mean > pre_mean else 'improvement'

        results.append(
            ChangePointResult(
                position=position,
                timestamp=timestamps[position],
                direction=direction,
                change_relative_pct=round(relative_change, 2),
                change_absolute=round(absolute_change, 4),
                t_statistic=round(getattr(cp, 'qhat', 0.0), 4),
                pre_segment_mean=round(pre_mean, 4),
                post_segment_mean=round(post_mean, 4),
            )
        )

    return sorted(results, key=lambda r: r.position)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
./scripts/api-test.sh --tail 20 tests/change_points/test_detector.py -v
```

Expected: All tests pass. If Otava's API differs from what we expect (e.g., `cp.index` attribute name), adjust the detector accordingly — the tests will tell you what to fix.

- [ ] **Step 6: Commit**

```bash
git add api/tropek/modules/change_points/ api/tests/change_points/
git commit -m "feat(otava): add pure change point detector wrapping E-Divisive"
```

---

## Task 5: Metric Directionality Helper

**Files:**
- Create: `api/tropek/modules/change_points/directionality.py`
- Create: `api/tests/change_points/test_directionality.py`

Derives `higher_is_better` from the SLO objective's `pass_threshold` criteria.

- [ ] **Step 1: Write tests**

```python
"""Unit tests for metric directionality derivation from SLO criteria."""

from __future__ import annotations

from tropek.modules.change_points.directionality import is_higher_better


class TestDirectionality:
    """Tests for is_higher_better derivation from pass_threshold criteria."""

    def test_less_than_means_lower_is_better(self) -> None:
        assert is_higher_better(['<600']) is False

    def test_less_equal_means_lower_is_better(self) -> None:
        assert is_higher_better(['<=1000']) is False

    def test_greater_than_means_higher_is_better(self) -> None:
        assert is_higher_better(['>95']) is True

    def test_greater_equal_means_higher_is_better(self) -> None:
        assert is_higher_better(['>=99.9']) is True

    def test_relative_increase_means_lower_is_better(self) -> None:
        assert is_higher_better(['<=+10%']) is False

    def test_relative_absolute_means_lower_is_better(self) -> None:
        assert is_higher_better(['<=+50']) is False

    def test_empty_threshold_defaults_false(self) -> None:
        assert is_higher_better([]) is False

    def test_multiple_criteria_uses_first(self) -> None:
        assert is_higher_better(['<600', '<=+10%']) is False
        assert is_higher_better(['>95', '<=100']) is True
```

- [ ] **Step 2: Run tests — expect failure**

```bash
./scripts/api-test.sh --tail 10 tests/change_points/test_directionality.py -v
```

- [ ] **Step 3: Implement**

```python
"""Derive metric polarity from SLO pass_threshold criteria.

Used by the change point detector to determine whether an increase
in metric value is a regression or improvement.
"""

from __future__ import annotations

import re


def is_higher_better(pass_threshold: list[str]) -> bool:
    """Determine if higher values are better based on the first criterion.

    Args:
        pass_threshold: List of criteria strings from the SLO objective,
            e.g. ['<600'], ['>=99.9'], ['<=+10%'].

    Returns:
        True if higher is better (throughput, availability).
        False if lower is better (latency, error rate) or cannot determine.
    """
    if not pass_threshold:
        return False

    first = pass_threshold[0].strip()
    # Match the leading operator: <=, >=, <, >
    match = re.match(r'^(<=|>=|<|>)', first)
    if not match:
        return False

    operator = match.group(1)
    return operator in ('>', '>=')
```

- [ ] **Step 4: Run tests — expect pass**

```bash
./scripts/api-test.sh --tail 10 tests/change_points/test_directionality.py -v
```

- [ ] **Step 5: Commit**

```bash
git add api/tropek/modules/change_points/directionality.py api/tests/change_points/test_directionality.py
git commit -m "feat(otava): add metric directionality helper for polarity detection"
```

---

## Task 6: Change Point Repository — Config CRUD + Dedup + Insert

**Files:**
- Create: `api/tropek/modules/change_points/repository.py`
- Create: `api/tests/change_points/test_repository.py`

- [ ] **Step 1: Write the integration test file**

```python
"""Integration tests for ChangePointRepository — dedup and config queries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import Asset, AssetType, ChangePoint, ChangePointConfig
from tropek.modules.change_points.repository import ChangePointRepository

_BASE = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)


async def _create_asset(session: AsyncSession) -> uuid.UUID:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name='cp-test-asset', type_name=type_name))
    await session.flush()
    return asset_id


@pytest.mark.integration
async def test_dedup_skips_nearby_change_point(db_session: AsyncSession) -> None:
    """A change point within ±2 ordinal positions should be deduped."""
    asset_id = await _create_asset(db_session)
    repo = ChangePointRepository(db_session)

    # Insert an existing change point at period_start = _BASE + 2h
    existing = ChangePoint(
        asset_id=asset_id,
        slo_name='perf-slo',
        metric_name='response_time_p95',
        period_start=_BASE + timedelta(hours=2),
        direction='regression',
        change_relative_pct=15.0,
        change_absolute=30.0,
        t_statistic=5.2,
        pre_segment_mean=200.0,
        post_segment_mean=230.0,
    )
    db_session.add(existing)
    await db_session.flush()

    # Nearby timestamps for the same metric — should all be deduped
    nearby_timestamps = [_BASE + timedelta(hours=h) for h in [1, 2, 3, 4]]
    for ts in nearby_timestamps:
        has_nearby = await repo.has_nearby_change_point(
            asset_id=asset_id,
            slo_name='perf-slo',
            metric_name='response_time_p95',
            period_start=ts,
            nearby_timestamps=nearby_timestamps,
        )
        assert has_nearby is True


@pytest.mark.integration
async def test_dedup_allows_distant_change_point(db_session: AsyncSession) -> None:
    """A change point far from existing ones should not be deduped."""
    asset_id = await _create_asset(db_session)
    repo = ChangePointRepository(db_session)

    existing = ChangePoint(
        asset_id=asset_id,
        slo_name='perf-slo',
        metric_name='response_time_p95',
        period_start=_BASE,
        direction='regression',
        change_relative_pct=15.0,
        change_absolute=30.0,
        t_statistic=5.2,
        pre_segment_mean=200.0,
        post_segment_mean=230.0,
    )
    db_session.add(existing)
    await db_session.flush()

    distant_timestamps = [_BASE + timedelta(hours=h) for h in [10, 11, 12, 13, 14]]
    has_nearby = await repo.has_nearby_change_point(
        asset_id=asset_id,
        slo_name='perf-slo',
        metric_name='response_time_p95',
        period_start=_BASE + timedelta(hours=12),
        nearby_timestamps=distant_timestamps,
    )
    assert has_nearby is False


@pytest.mark.integration
async def test_get_configs_for_slo(db_session: AsyncSession) -> None:
    """Fetching configs returns a dict keyed by metric name."""
    repo = ChangePointRepository(db_session)

    db_session.add(ChangePointConfig(
        slo_name='perf-slo',
        metric_name='response_time_p95',
        enabled=True,
        window_size=50,
        min_sample_size=15,
    ))
    db_session.add(ChangePointConfig(
        slo_name='perf-slo',
        metric_name='error_rate',
        enabled=False,
    ))
    await db_session.flush()

    configs = await repo.get_configs_for_slo('perf-slo')
    assert 'response_time_p95' in configs
    assert configs['response_time_p95'].enabled is True
    assert configs['response_time_p95'].window_size == 50
    assert 'error_rate' in configs
    assert configs['error_rate'].enabled is False


@pytest.mark.integration
async def test_dedup_respects_hidden_status(db_session: AsyncSession) -> None:
    """Hidden (triaged) change points still block dedup — no re-detection."""
    asset_id = await _create_asset(db_session)
    repo = ChangePointRepository(db_session)

    existing = ChangePoint(
        asset_id=asset_id,
        slo_name='perf-slo',
        metric_name='latency',
        period_start=_BASE + timedelta(hours=5),
        direction='regression',
        change_relative_pct=10.0,
        change_absolute=20.0,
        t_statistic=3.1,
        pre_segment_mean=100.0,
        post_segment_mean=120.0,
        status='hidden',
    )
    db_session.add(existing)
    await db_session.flush()

    nearby_timestamps = [_BASE + timedelta(hours=h) for h in [4, 5, 6]]
    has_nearby = await repo.has_nearby_change_point(
        asset_id=asset_id,
        slo_name='perf-slo',
        metric_name='latency',
        period_start=_BASE + timedelta(hours=5),
        nearby_timestamps=nearby_timestamps,
    )
    assert has_nearby is True
```

- [ ] **Step 2: Run tests — expect failure**

```bash
./scripts/api-test.sh --tail 20 tests/change_points/test_repository.py -v -m integration
```

- [ ] **Step 3: Implement the repository**

```python
"""Change point repository — CRUD, dedup, and config queries."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import ChangePoint, ChangePointConfig


class ChangePointRepository:
    """Data access layer for change points and detection config."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Config ---

    async def get_configs_for_slo(self, slo_name: str) -> dict[str, ChangePointConfig]:
        """Return all change point configs for an SLO, keyed by metric_name."""
        query = select(ChangePointConfig).where(ChangePointConfig.slo_name == slo_name)
        result = await self._session.execute(query)
        return {config.metric_name: config for config in result.scalars().all()}

    async def upsert_config(
        self,
        *,
        slo_name: str,
        metric_name: str,
        enabled: bool,
        window_size: int = 30,
        min_sample_size: int = 10,
    ) -> ChangePointConfig:
        """Create or update detection config for a specific SLO+metric."""
        query = select(ChangePointConfig).where(
            ChangePointConfig.slo_name == slo_name,
            ChangePointConfig.metric_name == metric_name,
        )
        result = await self._session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            existing.enabled = enabled
            existing.window_size = window_size
            existing.min_sample_size = min_sample_size
            await self._session.flush()
            return existing

        config = ChangePointConfig(
            slo_name=slo_name,
            metric_name=metric_name,
            enabled=enabled,
            window_size=window_size,
            min_sample_size=min_sample_size,
        )
        self._session.add(config)
        await self._session.flush()
        return config

    # --- Dedup ---

    async def has_nearby_change_point(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        metric_name: str,
        period_start: datetime,
        nearby_timestamps: list[datetime],
    ) -> bool:
        """Check if a change point exists for this metric within the nearby window.

        The nearby_timestamps list represents the ±2 ordinal evaluation positions
        around the candidate change point. If any existing change point (any status)
        falls on one of these timestamps, return True to skip insertion.
        """
        query = select(ChangePoint.id).where(
            ChangePoint.asset_id == asset_id,
            ChangePoint.slo_name == slo_name,
            ChangePoint.metric_name == metric_name,
            ChangePoint.period_start.in_(nearby_timestamps),
        ).limit(1)
        result = await self._session.execute(query)
        return result.scalar_one_or_none() is not None

    # --- Insert ---

    async def insert_change_point(
        self,
        *,
        indicator_result_id: uuid.UUID | None,
        asset_id: uuid.UUID,
        slo_name: str,
        metric_name: str,
        period_start: datetime,
        direction: str,
        change_relative_pct: float,
        change_absolute: float,
        t_statistic: float,
        pre_segment_mean: float,
        post_segment_mean: float,
    ) -> ChangePoint:
        """Insert a new change point row."""
        change_point = ChangePoint(
            indicator_result_id=indicator_result_id,
            asset_id=asset_id,
            slo_name=slo_name,
            metric_name=metric_name,
            period_start=period_start,
            direction=direction,
            change_relative_pct=change_relative_pct,
            change_absolute=change_absolute,
            t_statistic=t_statistic,
            pre_segment_mean=pre_segment_mean,
            post_segment_mean=post_segment_mean,
        )
        self._session.add(change_point)
        await self._session.flush()
        return change_point

    # --- Read ---

    async def list_change_points(
        self,
        *,
        status: str | None = None,
        direction: str | None = None,
        asset_id: uuid.UUID | None = None,
        slo_name: str | None = None,
        metric_name: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChangePoint]:
        """List change points with optional filters, newest first."""
        query = select(ChangePoint).order_by(ChangePoint.created_at.desc())
        if status:
            query = query.where(ChangePoint.status == status)
        if direction:
            query = query.where(ChangePoint.direction == direction)
        if asset_id:
            query = query.where(ChangePoint.asset_id == asset_id)
        if slo_name:
            query = query.where(ChangePoint.slo_name == slo_name)
        if metric_name:
            query = query.where(ChangePoint.metric_name == metric_name)
        if from_ts:
            query = query.where(ChangePoint.created_at >= from_ts)
        if to_ts:
            query = query.where(ChangePoint.created_at <= to_ts)
        query = query.limit(limit).offset(offset)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, change_point_id: uuid.UUID) -> ChangePoint | None:
        """Return a single change point by ID."""
        result = await self._session.execute(
            select(ChangePoint).where(ChangePoint.id == change_point_id)
        )
        return result.scalar_one_or_none()

    # --- Triage ---

    async def triage(
        self,
        change_point_id: uuid.UUID,
        *,
        status: str,
        triage_note: str | None = None,
        linked_ticket: str | None = None,
        triage_author: str | None = None,
    ) -> ChangePoint | None:
        """Update triage state of a change point."""
        from sqlalchemy import func as sa_func

        await self._session.execute(
            update(ChangePoint)
            .where(ChangePoint.id == change_point_id)
            .values(
                status=status,
                triage_note=triage_note,
                linked_ticket=linked_ticket,
                triage_author=triage_author,
                triage_at=sa_func.now(),
            )
        )
        await self._session.flush()
        return await self.get_by_id(change_point_id)

    async def bulk_triage(
        self,
        ids: list[uuid.UUID],
        *,
        status: str,
        triage_note: str | None = None,
        triage_author: str | None = None,
    ) -> int:
        """Bulk-update triage state. Returns number of rows affected."""
        from sqlalchemy import func as sa_func
        from sqlalchemy.engine import CursorResult
        from typing import Any, cast

        cursor = cast(
            'CursorResult[Any]',
            await self._session.execute(
                update(ChangePoint)
                .where(ChangePoint.id.in_(ids))
                .values(
                    status=status,
                    triage_note=triage_note,
                    triage_author=triage_author,
                    triage_at=sa_func.now(),
                )
            ),
        )
        await self._session.flush()
        return cursor.rowcount

    # --- For presenter enrichment ---

    async def get_change_points_for_evaluations(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        period_starts: list[datetime],
    ) -> dict[tuple[str, datetime], ChangePoint]:
        """Batch-load change points for a set of evaluation timestamps.

        Returns a dict keyed by (metric_name, period_start) for O(1) lookup
        in the heatmap/trend presenters.
        """
        if not period_starts:
            return {}
        query = select(ChangePoint).where(
            ChangePoint.asset_id == asset_id,
            ChangePoint.slo_name == slo_name,
            ChangePoint.period_start.in_(period_starts),
            ChangePoint.status != 'hidden',
        )
        result = await self._session.execute(query)
        return {
            (cp.metric_name, cp.period_start): cp
            for cp in result.scalars().all()
        }
```

- [ ] **Step 4: Run integration tests**

```bash
just test-env
./scripts/api-test.sh --tail 20 tests/change_points/test_repository.py -v -m integration
```

- [ ] **Step 5: Commit**

```bash
git add api/tropek/modules/change_points/repository.py api/tests/change_points/test_repository.py
git commit -m "feat(otava): add change point repository with dedup and config queries"
```

---

## Task 7: Worker Integration — Fault-Isolated Detection Step

**Files:**
- Create: `api/tropek/modules/change_points/worker_step.py`
- Modify: `api/tropek/queue.py`
- Create: `api/tests/change_points/test_worker_step.py`

- [ ] **Step 1: Write unit test for the worker step**

```python
"""Unit tests for the change point worker step orchestration logic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tropek.modules.change_points.worker_step import run_change_point_detection


class TestWorkerStep:
    """Tests for the fault-isolated worker step."""

    @pytest.fixture()
    def snapshot(self) -> MagicMock:
        snap = MagicMock()
        snap.asset_id = uuid.uuid4()
        snap.slo_name = 'perf-slo'
        snap.period_start = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
        snap.period_end = datetime(2026, 4, 10, 12, 30, tzinfo=UTC)
        snap.slo_version = 3
        return snap

    @pytest.fixture()
    def slo_def(self) -> MagicMock:
        objective = MagicMock()
        objective.sli = 'response_time_p95'
        objective.display_name = 'Response Time P95'
        objective.pass_threshold = ['<600']
        objective.warning_threshold = ['<1000']

        slo = MagicMock()
        slo.objectives = [objective]
        slo.comparable_from_version = 1
        return slo

    async def test_skips_when_no_config(self, snapshot: MagicMock, slo_def: MagicMock) -> None:
        """No change_point_config → no detection runs."""
        session = AsyncMock()
        with patch(
            'tropek.modules.change_points.worker_step.ChangePointRepository'
        ) as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_configs_for_slo = AsyncMock(return_value={})

            await run_change_point_detection(
                session=session,
                snapshot=snapshot,
                slo_def=slo_def,
                indicator_rows=[],
            )

            mock_repo.has_nearby_change_point.assert_not_called()

    async def test_skips_disabled_metrics(self, snapshot: MagicMock, slo_def: MagicMock) -> None:
        """Config exists but enabled=False → skip."""
        session = AsyncMock()
        config = MagicMock()
        config.enabled = False

        with patch(
            'tropek.modules.change_points.worker_step.ChangePointRepository'
        ) as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_configs_for_slo = AsyncMock(
                return_value={'response_time_p95': config}
            )

            await run_change_point_detection(
                session=session,
                snapshot=snapshot,
                slo_def=slo_def,
                indicator_rows=[],
            )

            mock_repo.has_nearby_change_point.assert_not_called()
```

- [ ] **Step 2: Run tests — expect failure**

```bash
./scripts/api-test.sh --tail 10 tests/change_points/test_worker_step.py -v
```

- [ ] **Step 3: Implement the worker step**

```python
"""Fault-isolated change point detection step for the evaluation worker.

Runs after SLO scoring and SLI value writes. If this step fails,
the evaluation result is already saved — detection failure is non-fatal.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import IndicatorResultRow, SLODefinition
from tropek.modules.change_points.detector import detect_change_points
from tropek.modules.change_points.directionality import is_higher_better
from tropek.modules.change_points.repository import ChangePointRepository
from tropek.modules.quality_gate.repositories.baseline import BaselineRepository

logger = structlog.get_logger()


async def run_change_point_detection(
    *,
    session: AsyncSession,
    snapshot: Any,
    slo_def: SLODefinition,
    indicator_rows: list[IndicatorResultRow],
    cache: Any | None = None,
) -> None:
    """Run Otava change point detection for each enabled metric.

    Uses BaselineRepository for history scoping (pin-aware, version-aware).
    Dedup-checks against existing change_points before inserting.

    Args:
        session: Active async DB session.
        snapshot: EvaluationSnapshot with asset_id, slo_name, period_start, etc.
        slo_def: SLO definition with objectives (for criteria polarity).
        indicator_rows: ORM rows from this evaluation's indicator_results.
        cache: Optional Redis cache for baseline lookups.
    """
    log = logger.bind(
        evaluation_id=str(snapshot.eval_id),
        slo_name=snapshot.slo_name,
    )

    cp_repo = ChangePointRepository(session)
    configs = await cp_repo.get_configs_for_slo(snapshot.slo_name)
    if not configs:
        return

    # Build objective lookup for polarity and indicator_result_id mapping
    objective_lookup = {obj.sli: obj for obj in slo_def.objectives}
    indicator_lookup = {row.objective.sli: row for row in indicator_rows if row.objective}

    baseline_repo = BaselineRepository(session, cache=cache)

    for metric_name, config in configs.items():
        if not config.enabled:
            continue

        objective = objective_lookup.get(metric_name)
        if not objective:
            continue

        indicator_row = indicator_lookup.get(metric_name)
        if not indicator_row:
            continue

        try:
            await _detect_for_metric(
                log=log,
                baseline_repo=baseline_repo,
                cp_repo=cp_repo,
                snapshot=snapshot,
                slo_def=slo_def,
                metric_name=metric_name,
                indicator_result_id=indicator_row.id,
                pass_threshold=list(objective.pass_threshold),
                config=config,
            )
        except Exception:
            log.warning(
                'change point detection failed for metric',
                metric=metric_name,
                exc_info=True,
            )


async def _detect_for_metric(
    *,
    log: Any,
    baseline_repo: BaselineRepository,
    cp_repo: ChangePointRepository,
    snapshot: Any,
    slo_def: Any,
    metric_name: str,
    indicator_result_id: uuid.UUID,
    pass_threshold: list[str],
    config: Any,
) -> None:
    """Run detection for a single metric using baseline-scoped history."""
    # Fetch history using same pin-aware, version-aware query as the evaluator
    history_evals = await baseline_repo.get_evaluation_baselines(
        asset_id=snapshot.asset_id,
        slo_name=snapshot.slo_name,
        period_start_before=snapshot.period_end,
        include_result_with_score='all',
        limit=config.window_size,
    )

    # Extract per-metric time series from baseline evaluations
    values: list[float] = []
    timestamps: list[datetime] = []
    eval_period_starts: list[datetime] = []

    for evaluation in sorted(history_evals, key=lambda e: e.period_start):
        for row in evaluation.indicator_rows or []:
            if row.objective and row.objective.sli == metric_name and row.value is not None:
                values.append(float(row.value))
                timestamps.append(evaluation.period_start)
                eval_period_starts.append(evaluation.period_start)

    # Also include the current evaluation's value
    if snapshot.period_start not in eval_period_starts:
        current_indicator = None
        for row in (getattr(snapshot, '_indicator_rows', None) or []):
            if hasattr(row, 'objective') and row.objective.sli == metric_name:
                current_indicator = row
                break
        # The current value was already written — it might be in history_evals
        # if period_start_before includes it. If not, we skip — the next eval
        # will pick it up.

    if len(values) < config.min_sample_size:
        log.debug(
            'insufficient history for change point detection',
            metric=metric_name,
            sample_count=len(values),
            min_required=config.min_sample_size,
        )
        return

    higher_is_better = is_higher_better(pass_threshold)

    detected = detect_change_points(
        values=values,
        timestamps=timestamps,
        higher_is_better=higher_is_better,
        window_size=config.window_size,
        min_sample_size=config.min_sample_size,
    )

    if not detected:
        return

    # Only consider the latest change point (closest to current evaluation)
    latest_cp = detected[-1]

    # Check if the latest change point is near the current evaluation's position
    # (within the last 3 positions of the series)
    if latest_cp.position < len(values) - 3:
        return

    # Dedup: build the ±2 ordinal window of timestamps around the detection point
    detection_index = latest_cp.position
    nearby_indices = range(
        max(0, detection_index - 2),
        min(len(eval_period_starts), detection_index + 3),
    )
    nearby_timestamps = [eval_period_starts[i] for i in nearby_indices]

    has_existing = await cp_repo.has_nearby_change_point(
        asset_id=snapshot.asset_id,
        slo_name=snapshot.slo_name,
        metric_name=metric_name,
        period_start=latest_cp.timestamp,
        nearby_timestamps=nearby_timestamps,
    )

    if has_existing:
        log.debug('change point deduped', metric=metric_name, position=latest_cp.position)
        return

    await cp_repo.insert_change_point(
        indicator_result_id=indicator_result_id,
        asset_id=snapshot.asset_id,
        slo_name=snapshot.slo_name,
        metric_name=metric_name,
        period_start=latest_cp.timestamp,
        direction=latest_cp.direction,
        change_relative_pct=latest_cp.change_relative_pct,
        change_absolute=latest_cp.change_absolute,
        t_statistic=latest_cp.t_statistic,
        pre_segment_mean=latest_cp.pre_segment_mean,
        post_segment_mean=latest_cp.post_segment_mean,
    )

    log.info(
        'change point detected',
        metric=metric_name,
        direction=latest_cp.direction,
        magnitude_pct=latest_cp.change_relative_pct,
    )
```

- [ ] **Step 4: Run tests**

```bash
./scripts/api-test.sh --tail 20 tests/change_points/test_worker_step.py -v
```

- [ ] **Step 5: Wire into `queue.py`**

In `api/tropek/queue.py`, after the phase 3b SLI values write (around line 212), add:

```python
    # Phase 4: Change point detection (fault-isolated, separate txn)
    try:
        async with session_factory() as session:
            from tropek.modules.change_points.worker_step import run_change_point_detection

            await run_change_point_detection(
                session=session,
                snapshot=snapshot,
                slo_def=slo_def,
                indicator_rows=fetch_result.eval_result.indicator_results,
                cache=cache,
            )
            await session.commit()
    except Exception:
        log.warning('change point detection step failed, skipping', exc_info=True)
```

Note: this import is at the top of the function body to keep the import lazy — the change_points module is optional. Move it to the file-level imports if preferred.

- [ ] **Step 6: Commit**

```bash
git add api/tropek/modules/change_points/worker_step.py api/tests/change_points/test_worker_step.py api/tropek/queue.py
git commit -m "feat(otava): add fault-isolated worker step for change point detection"
```

---

## Task 8: Schemas — Change Point Markers on Existing Responses

**Files:**
- Modify: `api/tropek/modules/quality_gate/schemas/heatmap.py`
- Modify: `api/tropek/modules/quality_gate/schemas/evaluations.py`
- Create: `api/tropek/modules/change_points/schemas.py`

- [ ] **Step 1: Create change point schemas**

```python
"""Pydantic schemas for change point API requests and responses."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from tropek.modules.common.schemas import StrictInput


class ChangePointMarker(BaseModel):
    """Lightweight marker attached to heatmap cells and trend points."""

    direction: str  # "regression" | "improvement"
    change_relative_pct: float


class ChangePointRead(BaseModel):
    """Full change point detail for list views and detail endpoint."""

    id: uuid.UUID
    asset_id: uuid.UUID
    slo_name: str
    metric_name: str
    period_start: datetime
    direction: str
    change_relative_pct: float
    change_absolute: float
    t_statistic: float
    pre_segment_mean: float
    post_segment_mean: float
    status: str
    triage_author: str | None
    triage_note: str | None
    triage_at: datetime | None
    linked_ticket: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class TriageRequest(StrictInput):
    """Request body for triaging a change point."""

    status: str  # "acknowledged" | "hidden"
    triage_note: str | None = None
    linked_ticket: str | None = None
    triage_author: str | None = None


class BulkTriageRequest(StrictInput):
    """Request body for bulk-triaging change points."""

    ids: list[uuid.UUID]
    status: str
    triage_note: str | None = None
    triage_author: str | None = None


class ChangePointConfigRead(BaseModel):
    """Detection config for a single SLO+metric pair."""

    slo_name: str
    metric_name: str
    enabled: bool
    window_size: int
    min_sample_size: int

    model_config = {'from_attributes': True}


class ChangePointConfigUpsert(StrictInput):
    """Request body for creating/updating detection config."""

    enabled: bool
    window_size: int = 30
    min_sample_size: int = 10
```

- [ ] **Step 2: Add `change_point` field to `HeatmapCellGrouped`**

In `api/tropek/modules/quality_gate/schemas/heatmap.py`, add to `HeatmapCellGrouped`:

```python
    change_point: ChangePointMarker | None = None
```

Add the import at the top:

```python
from tropek.modules.change_points.schemas import ChangePointMarker
```

- [ ] **Step 3: Add `change_point` field to `TrendPoint` and `IndicatorResult`**

In `api/tropek/modules/quality_gate/schemas/evaluations.py`:

Add to `TrendPoint`:
```python
    change_point: ChangePointMarker | None = None
```

Add to `IndicatorResult`:
```python
    change_point: ChangePointMarker | None = None
```

Add the import at the top:
```python
from tropek.modules.change_points.schemas import ChangePointMarker
```

- [ ] **Step 4: Verify type check passes**

```bash
uv run --directory api mypy tropek/modules/change_points/ tropek/modules/quality_gate/schemas/
```

- [ ] **Step 5: Commit**

```bash
git add api/tropek/modules/change_points/schemas.py api/tropek/modules/quality_gate/schemas/heatmap.py api/tropek/modules/quality_gate/schemas/evaluations.py
git commit -m "feat(otava): add change point marker schemas to heatmap and trend responses"
```

---

## Task 9: Presenter Enrichment — Attach Change Points to Heatmap Cells

**Files:**
- Modify: `api/tropek/modules/quality_gate/workflows/presentation/presenter.py`

The presenter already has `slo_name`, `metric_name`, and `period_start` in scope when building `HeatmapCellGrouped` objects. The change point lookup is a dict keyed by `(metric_name, period_start)` loaded in one batch query.

- [ ] **Step 1: Write test for enrichment**

Add to an existing or new test file `api/tests/change_points/test_presenter_enrichment.py`:

```python
"""Unit tests for change point enrichment in the heatmap presenter."""

from __future__ import annotations

from tropek.modules.change_points.schemas import ChangePointMarker


def test_change_point_marker_serialization() -> None:
    """ChangePointMarker round-trips through JSON."""
    marker = ChangePointMarker(direction='regression', change_relative_pct=15.2)
    data = marker.model_dump()
    assert data == {'direction': 'regression', 'change_relative_pct': 15.2}
    restored = ChangePointMarker.model_validate(data)
    assert restored == marker
```

- [ ] **Step 2: Modify `_collect_slo_heatmap_data` to accept change point lookup**

In `presenter.py`, update `_collect_slo_heatmap_data` to accept an optional `change_point_lookup` parameter:

```python
def _collect_slo_heatmap_data(
    runs_asc: list[EvaluationRun],
    column_index_by_run_id: dict[uuid.UUID, int],
    change_point_lookup: dict[tuple[str, datetime], object] | None = None,
) -> dict[str, dict[str, Any]]:
```

Inside the loop where `HeatmapCellGrouped` is constructed (around line 144-173), add before the closing paren:

```python
                    change_point=_resolve_change_point_marker(
                        change_point_lookup, metric_name, run.period_start,
                    ),
```

Add the helper function:

```python
def _resolve_change_point_marker(
    lookup: dict[tuple[str, datetime], object] | None,
    metric_name: str,
    period_start: datetime,
) -> ChangePointMarker | None:
    """Look up a change point marker for a specific metric+timestamp."""
    if not lookup:
        return None
    cp = lookup.get((metric_name, period_start))
    if cp is None:
        return None
    return ChangePointMarker(
        direction=cp.direction,
        change_relative_pct=cp.change_relative_pct,
    )
```

Add the import:
```python
from tropek.modules.change_points.schemas import ChangePointMarker
```

- [ ] **Step 3: Update `build_grouped_heatmap_response` to pass the lookup through**

```python
def build_grouped_heatmap_response(
    asset_name: str,
    runs: list[EvaluationRun],
    noted_run_ids: set[uuid.UUID] | None = None,
    change_point_lookup: dict[tuple[str, datetime], object] | None = None,
) -> GroupedMetricHeatmapResponse:
```

Pass it to `_collect_slo_heatmap_data`:

```python
    slo_data = _collect_slo_heatmap_data(runs_asc, column_index_by_run_id, change_point_lookup)
```

- [ ] **Step 4: Run existing heatmap tests to verify no regressions**

```bash
./scripts/api-test.sh --tail 10 tests/quality_gate/db/test_grouped_heatmap.py -v -m integration
```

- [ ] **Step 5: Commit**

```bash
git add api/tropek/modules/quality_gate/workflows/presentation/presenter.py api/tests/change_points/test_presenter_enrichment.py
git commit -m "feat(otava): enrich heatmap cells with change point markers"
```

---

## Task 10: Trend Query Enrichment

**Files:**
- Modify: `api/tropek/modules/quality_gate/repositories/trend.py`

The trend query `get_trend_by_domain` returns dicts with `timestamp`, `value`, `eval_id`, etc. Add `change_point` to each dict by looking up against the `change_points` table.

- [ ] **Step 1: Add change point lookup to `get_trend_by_domain`**

The simplest approach: after the existing query runs, do a batch lookup of change points for the same `(asset_id, slo_name, metric_name)` and date range, then merge by `period_start`.

Add a new parameter to `get_trend_by_domain`:

```python
    async def get_trend_by_domain(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        metric_name: str,
        from_ts: datetime,
        to_ts: datetime | None = None,
        change_point_lookup: dict[tuple[str, datetime], object] | None = None,
    ) -> list[dict[str, Any]]:
```

In the return dict construction, add:

```python
                'change_point': _trend_change_point(change_point_lookup, metric_name, r.period_start),
```

Add helper at module level:

```python
def _trend_change_point(
    lookup: dict[tuple[str, Any], object] | None,
    metric_name: str,
    period_start: datetime,
) -> dict[str, Any] | None:
    if not lookup:
        return None
    cp = lookup.get((metric_name, period_start))
    if cp is None:
        return None
    return {'direction': cp.direction, 'change_relative_pct': cp.change_relative_pct}
```

- [ ] **Step 2: Run existing trend tests to verify no regressions**

```bash
./scripts/api-test.sh --tail 10 tests/quality_gate/db/test_trend_query.py -v -m integration
```

- [ ] **Step 3: Commit**

```bash
git add api/tropek/modules/quality_gate/repositories/trend.py
git commit -m "feat(otava): enrich trend points with change point markers"
```

---

## Task 11: API Router — Change Points CRUD + Config

**Files:**
- Create: `api/tropek/modules/change_points/router.py`
- Modify: `api/tropek/app.py`

- [ ] **Step 1: Implement the router**

```python
"""Change points API — list, triage, and config endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.session import get_session
from tropek.modules.change_points.repository import ChangePointRepository
from tropek.modules.change_points.schemas import (
    BulkTriageRequest,
    ChangePointConfigRead,
    ChangePointConfigUpsert,
    ChangePointRead,
    TriageRequest,
)

router = APIRouter(prefix='/change-points', tags=['change-points'])


@router.get('', response_model=list[ChangePointRead])
async def list_change_points(
    status: str | None = None,
    direction: str | None = None,
    asset_id: uuid.UUID | None = None,
    slo_name: str | None = None,
    metric: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[ChangePointRead]:
    """List change points with optional filters."""
    repo = ChangePointRepository(session)
    rows = await repo.list_change_points(
        status=status,
        direction=direction,
        asset_id=asset_id,
        slo_name=slo_name,
        metric_name=metric,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        offset=offset,
    )
    return [ChangePointRead.model_validate(row) for row in rows]


@router.get('/{change_point_id}', response_model=ChangePointRead)
async def get_change_point(
    change_point_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ChangePointRead:
    """Get a single change point by ID."""
    repo = ChangePointRepository(session)
    row = await repo.get_by_id(change_point_id)
    if row is None:
        raise HTTPException(status_code=404, detail='change point not found')
    return ChangePointRead.model_validate(row)


@router.patch('/{change_point_id}', response_model=ChangePointRead)
async def triage_change_point(
    change_point_id: uuid.UUID,
    body: TriageRequest,
    session: AsyncSession = Depends(get_session),
) -> ChangePointRead:
    """Update triage state of a change point."""
    repo = ChangePointRepository(session)
    row = await repo.triage(
        change_point_id,
        status=body.status,
        triage_note=body.triage_note,
        linked_ticket=body.linked_ticket,
        triage_author=body.triage_author,
    )
    if row is None:
        raise HTTPException(status_code=404, detail='change point not found')
    await session.commit()
    return ChangePointRead.model_validate(row)


@router.patch('/bulk', response_model=dict)
async def bulk_triage(
    body: BulkTriageRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Bulk-update triage state for multiple change points."""
    repo = ChangePointRepository(session)
    count = await repo.bulk_triage(
        body.ids,
        status=body.status,
        triage_note=body.triage_note,
        triage_author=body.triage_author,
    )
    await session.commit()
    return {'updated': count}


# --- Config endpoints ---

@router.get('/config/{slo_name}', response_model=list[ChangePointConfigRead])
async def list_configs(
    slo_name: str,
    session: AsyncSession = Depends(get_session),
) -> list[ChangePointConfigRead]:
    """List all detection configs for an SLO."""
    repo = ChangePointRepository(session)
    configs = await repo.get_configs_for_slo(slo_name)
    return [ChangePointConfigRead.model_validate(c) for c in configs.values()]


@router.put('/config/{slo_name}/{metric_name}', response_model=ChangePointConfigRead)
async def upsert_config(
    slo_name: str,
    metric_name: str,
    body: ChangePointConfigUpsert,
    session: AsyncSession = Depends(get_session),
) -> ChangePointConfigRead:
    """Create or update detection config for a specific SLO+metric."""
    repo = ChangePointRepository(session)
    config = await repo.upsert_config(
        slo_name=slo_name,
        metric_name=metric_name,
        enabled=body.enabled,
        window_size=body.window_size,
        min_sample_size=body.min_sample_size,
    )
    await session.commit()
    return ChangePointConfigRead.model_validate(config)
```

**Important:** The `/bulk` route must be registered BEFORE `/{change_point_id}` to avoid FastAPI interpreting `"bulk"` as a UUID path parameter. Reorder the routes so `bulk_triage` comes first, or use a different path like `/bulk-triage`.

- [ ] **Step 2: Register the router in `app.py`**

Find the existing `app.include_router(...)` calls in `api/tropek/app.py` and add:

```python
from tropek.modules.change_points.router import router as change_points_router

app.include_router(change_points_router, prefix='/api')
```

- [ ] **Step 3: Verify the app starts**

```bash
uv run --directory api uvicorn tropek.app:app --host 0.0.0.0 --port 8080 &
sleep 2
curl -s http://localhost:8080/api/change-points | head -c 100
kill %1
```

Expected: `[]` (empty list) or a valid JSON response.

- [ ] **Step 4: Commit**

```bash
git add api/tropek/modules/change_points/router.py api/tropek/app.py
git commit -m "feat(otava): add change points API router with triage and config endpoints"
```

---

## Task 12: Wire Change Point Lookup into Heatmap and Trend Callers

**Files:**
- Modify: the router/service layer that calls `build_grouped_heatmap_response` and `get_trend_by_domain`

This is the glue that loads change points from the DB and passes them to the presenters.

- [ ] **Step 1: Find the grouped heatmap caller**

Search for `build_grouped_heatmap_response` in the router to find where it's called. Add a `ChangePointRepository` query before the call to load change points for the displayed evaluations.

```python
# In the grouped heatmap endpoint, after fetching runs:
cp_repo = ChangePointRepository(session)
period_starts = [run.period_start for run in runs]
change_point_lookup = await cp_repo.get_change_points_for_evaluations(
    asset_id=asset_id,
    slo_name=slo_name,  # may need to iterate SLO groups
    period_starts=period_starts,
)

response = build_grouped_heatmap_response(
    asset_name=asset_name,
    runs=runs,
    noted_run_ids=noted,
    change_point_lookup=change_point_lookup,
)
```

Note: the grouped heatmap shows multiple SLOs. The `get_change_points_for_evaluations` query might need to run per-SLO, or be extended to accept multiple SLO names. Evaluate during implementation based on the actual caller structure.

- [ ] **Step 2: Find the trend endpoint caller**

In the trend endpoint, add the same pattern — load change points for the queried `(asset_id, slo_name)` and date range, then pass as `change_point_lookup`.

- [ ] **Step 3: Run the full test suite to verify no regressions**

```bash
./scripts/api-test.sh --tail 10
```

- [ ] **Step 4: Commit**

```bash
git add api/tropek/modules/quality_gate/router.py
git commit -m "feat(otava): wire change point lookup into heatmap and trend endpoints"
```

---

## Task 13: Frontend — Heatmap Diamond Markers

**Files:**
- Modify: `ui/src/features/navigator/components/AssetHeatmap.tsx`
- Modify: relevant heatmap chart component

The backend now sends `change_point: {direction, change_relative_pct} | null` on each `HeatmapCellGrouped`. The frontend renders a diamond overlay when this field is present.

- [ ] **Step 1: Update TypeScript types**

Add `change_point` to the heatmap cell type wherever `HeatmapCellGrouped` is defined in the frontend:

```typescript
change_point: { direction: 'regression' | 'improvement'; change_relative_pct: number } | null
```

- [ ] **Step 2: Render diamond markers in ECharts**

In the heatmap chart rendering, when building the data array, check each cell for `change_point`. If present, add a `markPoint` or overlay scatter series with diamond symbols:

- Red diamond (`◆`) for `direction === 'regression'`
- Green diamond (`◆`) for `direction === 'improvement'`
- Tooltip: `"Change point: {metric_name} {direction} {change_relative_pct}%"`

The exact ECharts integration depends on the chart type used (`HeatmapChart`). Options:
- Add a separate `scatter` series overlay with `symbol: 'diamond'`
- Use `markPoint` on the heatmap series
- Use `graphic` elements positioned at cell coordinates

- [ ] **Step 3: Test visually**

Start the dev server and verify diamonds appear on heatmap cells that have change points. Test with both regression (red) and improvement (green) cases.

- [ ] **Step 4: Write component test**

Verify that the component renders the diamond marker when `change_point` data is present, and does not render it when null.

- [ ] **Step 5: Commit**

```bash
git add ui/src/
git commit -m "feat(otava): render change point diamond markers on heatmap cells"
```

---

## Task 14: Frontend — Trend Chart Diamond Markers

**Files:**
- Modify: `ui/src/features/evaluations/hooks/useMetricTrendState.ts`
- Modify: `ui/src/features/evaluations/components/MetricTrendBlock.tsx`

The `TrendPoint` now includes `change_point: {direction, change_relative_pct} | null`.

- [ ] **Step 1: Update TypeScript types**

Add `change_point` to the `TrendPoint` type.

- [ ] **Step 2: Add diamond scatter series**

In `useMetricTrendState.ts`, when building the ECharts series, add a second scatter series for change points:

```typescript
// Filter trend points that have change_point data
const changePointData = trend
  .map((p, i) => p.change_point ? { value: p.value, index: i, ...p.change_point } : null)
  .filter(Boolean)

if (changePointData.length > 0) {
  series.push({
    type: 'scatter',
    data: changePointData.map(cp => [cp!.index, cp!.value]),
    symbol: 'diamond',
    symbolSize: 14,
    itemStyle: {
      color: (params) => params.data.direction === 'regression' ? '#f85149' : '#3fb950',
      borderColor: '#ffffff',
      borderWidth: 1,
    },
    tooltip: {
      formatter: (params) =>
        `Change point: ${params.data.direction} ${params.data.change_relative_pct}%`,
    },
    z: 10, // render above the line
  })
}
```

- [ ] **Step 3: Test visually**

Start the dev server, navigate to a metric trend chart that has change points, and verify the diamond markers appear at the correct positions.

- [ ] **Step 4: Write component test**

- [ ] **Step 5: Commit**

```bash
git add ui/src/
git commit -m "feat(otava): render change point diamond markers on trend charts"
```

---

## Task 15: Frontend — Change Points List Page

**Files:**
- Create: `ui/src/features/change-points/ChangePointsPage.tsx`
- Create: `ui/src/features/change-points/useChangePoints.ts`
- Modify: router config to add `/change-points` route

This is a filterable, sortable table showing all change points with triage actions. Follow the existing page patterns in the codebase.

- [ ] **Step 1: Create the data hook**

```typescript
// useChangePoints.ts
// React Query hook for GET /api/change-points with filter params
// Returns paginated list of ChangePointRead objects
```

- [ ] **Step 2: Create the page component**

Table columns: Status, Direction, Metric, Asset, SLO, Magnitude (% + absolute), Detected at, Linked ticket, Triage author.

Filters: status dropdown, direction dropdown, date range. Default: `status=unprocessed`, newest first.

Row click → navigate to evaluation detail (via `indicator_result_id` → `slo_evaluation_id` chain, or store `eval_id` on the change point).

- [ ] **Step 3: Add triage actions**

- Acknowledge (with optional note)
- Hide (mark as false positive)
- Link ticket (text input)
- Bulk select + bulk triage

- [ ] **Step 4: Register route**

Add `/change-points` to the router config.

- [ ] **Step 5: Test visually + write component test**

- [ ] **Step 6: Commit**

```bash
git add ui/src/
git commit -m "feat(otava): add change points list page with triage workflow"
```

---

## Task 16: Frontend — SLI Breakdown Table Change Point Column

**Files:**
- Modify: `ui/src/features/evaluations/components/SLIBreakdownTable.tsx`

The `IndicatorResult` now includes `change_point: ChangePointMarker | null`.

- [ ] **Step 1: Add change point indicator to the table**

When `indicator.change_point` is present, show a diamond icon (red/green) with the magnitude percentage next to the metric name or as a new column.

- [ ] **Step 2: Write component test**

- [ ] **Step 3: Commit**

```bash
git add ui/src/features/evaluations/components/SLIBreakdownTable.tsx
git commit -m "feat(otava): show change point indicators in SLI breakdown table"
```

---

## Verification Checklist

After all tasks are complete:

- [ ] `./scripts/api-test.sh --tail 5` — all unit tests pass
- [ ] `just test-env && ./scripts/api-test.sh --tail 5 -m integration -v` — all integration tests pass
- [ ] `./scripts/ui-test.sh --tail 10` — all UI tests pass
- [ ] `./scripts/ui-lint.sh --tail 10` — no lint errors
- [ ] `uv run --directory api mypy tropek/` — type check passes
- [ ] `just dev` — full stack starts, navigate to an asset with evaluations and verify:
  - Heatmap cells show diamond markers where change points exist
  - Trend charts show diamond markers at change point positions
  - `/change-points` page loads with filterable list
  - Triage actions (acknowledge, hide) work
  - Config endpoint (`PUT /api/change-points/config/{slo}/{metric}`) creates/updates config
- [ ] Pin a baseline → verify that subsequent change point detection only uses evaluations after the pin
- [ ] Create a new SLO version with `comparable_from_version` set → verify detection history respects version boundaries
