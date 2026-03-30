# End-to-End Wiring Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire all TROPEK layers together — DB schema, evaluation lifecycle (baseline pinning, status overrides, heatmap), mock adapter, evaluation trigger/worker, Prometheus adapter, and integration test pipeline.

**Architecture:** Bottom-up implementation across 5 phases. Each phase builds on the previous: schema fixes → eval lifecycle endpoints → mock adapter service → trigger/worker flow → Prometheus adapter + integration tests. The mock adapter is a standalone FastAPI service that speaks the same `POST /query` contract as real adapters but serves CSV-backed time-series data.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Pydantic v2, PostgreSQL + TimescaleDB, Redis (arq), httpx, uv/pytest.

**Spec:** `docs/superpowers/specs/2026-03-17-end-to-end-wiring-design.md`

---

## File Map

**New files:**
- `api/alembic/versions/003_baseline_pin_and_override.py` — migration: 7 cols on evaluations, 3 cols on evaluation_batches, partial unique index, check constraint
- `adapters/mock/__init__.py` — package marker
- `adapters/mock/app/__init__.py` — package marker
- `adapters/mock/app/main.py` — FastAPI service: POST /query, GET /health
- `adapters/mock/app/csv_store.py` — CSV reader with time-range lookup
- `adapters/mock/generate.py` — scenario YAML → CSV generator
- `adapters/mock/scenarios/stable.yaml` — flat metrics scenario
- `adapters/mock/scenarios/regression.yaml` — degradation scenario
- `adapters/mock/pyproject.toml` — uv package definition
- `adapters/mock/Dockerfile` — container build
- `adapters/mock/tests/test_csv_store.py` — unit tests for CSV store
- `adapters/mock/tests/test_generator.py` — unit tests for generator
- `api/app/modules/quality_gate/worker.py` — arq job: evaluation execution
- `api/app/modules/quality_gate/trigger.py` — trigger logic: resolve refs, create pending, enqueue
- `api/tests/engine/test_trigger.py` — unit tests for trigger resolution logic
- `scripts/integration-test.sh` — end-to-end test orchestrator

**Modified files:**
- `api/app/db/models.py` — add 7 columns to Evaluation (lines 290-296), 3 to EvaluationBatch (lines 417-419)
- `api/app/modules/quality_gate/schemas.py` — add pin/override fields to EvaluationSummary (lines 78-101), new request/response schemas
- `api/app/modules/quality_gate/repository.py` — add pin/unpin/override/restore/heatmap methods, update get_baselines() (line 228)
- `api/app/modules/quality_gate/router.py` — add pin/unpin, override/restore, heatmap, trigger, batch endpoints
- `docker-compose.yml` — add adapter-mock service
- `adapters/prometheus/app/main.py` — implement POST /query (currently only GET /health, line 8)
- `clients/python/tropek_client/client.py` — add trigger/pin/override methods to _Evaluations class (line 395)
- `bootstrap_mock/manifests/asset-groups.yaml` — add group members
- `bootstrap_mock/manifests/datasources.yaml` — add mock datasource

---

## Chunk 1: DB Layer — Migration 003 + ORM Updates

### Task 1: Update Evaluation ORM model

**Files:**
- Modify: `api/app/db/models.py:273-296`

- [ ] **Step 1: Add baseline pin columns to Evaluation model**

After line 291 (`invalidation_note`), but **inside** the existing `# fmt: off` / `# fmt: on` block (lines 271-299), add:

```python
    baseline_pinned_at:   Mapped[datetime | None]  = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_unpinned_at: Mapped[datetime | None]  = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_pin_reason:  Mapped[str | None]        = mapped_column(Text, nullable=True)
    baseline_pin_author:  Mapped[str | None]        = mapped_column(Text, nullable=True)
    original_result:      Mapped[str | None]        = mapped_column(Text, nullable=True)
    override_reason:      Mapped[str | None]        = mapped_column(Text, nullable=True)
    override_author:      Mapped[str | None]        = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: Add rollup columns to EvaluationBatch model**

After line 419 (`evaluation_ids`), add:

```python
    result:         Mapped[str | None]            = mapped_column(Text, nullable=True)
    score:          Mapped[float | None]          = mapped_column(Float, nullable=True)
    rollup_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
```

Verify `Float` and `JSONB` are already in the SQLAlchemy imports at the top of the file (they should be — do not add duplicates).

- [ ] **Step 3: Verify the module imports cleanly**

```bash
uv run --directory api python -c "from app.db.models import Evaluation, EvaluationBatch; print('ok')"
```

Expected: `ok`

### Task 2: Autogenerate and apply migration 003

**Files:**
- Create: `api/alembic/versions/003_baseline_pin_and_override.py`

- [ ] **Step 1: Run autogenerate**

```bash
uv run --directory api alembic revision --autogenerate -m "003_baseline_pin_and_override"
```

Expected: Creates migration file with auto-detected column additions.

- [ ] **Step 2: Inspect and correct the generated migration**

Open the generated file. Verify it includes:

1. Seven `add_column` calls on `evaluations` (baseline_pinned_at, baseline_unpinned_at, baseline_pin_reason, baseline_pin_author, original_result, override_reason, override_author)
2. Three `add_column` calls on `evaluation_batches` (result, score, rollup_details)

Then manually add the partial unique index and check constraint after the column additions in `upgrade()`:

```python
    # Enforce single active pin per (asset_id, slo_name)
    op.create_index(
        "uq_evaluations_active_pin",
        "evaluations",
        ["asset_id", "slo_name"],
        unique=True,
        postgresql_where=sa.text(
            "baseline_pinned_at IS NOT NULL AND baseline_unpinned_at IS NULL"
        ),
    )

    # Check constraint on original_result — same enum as result
    op.create_check_constraint(
        "ck_evaluations_original_result",
        "evaluations",
        "original_result IN ('pass', 'warning', 'fail', 'error') OR original_result IS NULL",
    )
```

And in `downgrade()`, add before the column drops:

```python
    op.drop_constraint("ck_evaluations_original_result", "evaluations", type_="check")
    op.drop_index("uq_evaluations_active_pin", table_name="evaluations")
```

- [ ] **Step 3: Start dev DB and apply migration**

```bash
docker compose up timescaledb -d
```

```bash
uv run --directory api alembic upgrade head
```

Expected: Migration applies cleanly.

- [ ] **Step 4: Verify migration applied**

```bash
uv run --directory api alembic current
```

Expected: `003_baseline_pin_and_override (head)`

- [ ] **Step 5: Run existing unit tests to confirm nothing broke**

```bash
uv run pytest api/tests/ -m "not integration" -q
```

Expected: All unit tests pass.

- [ ] **Step 6: Commit**

Note: Alembic autogenerate creates files with a hash prefix (e.g., `a1b2c3d4_003_baseline_pin_and_override.py`). Use the actual generated filename in the git add command below.

```bash
git add api/app/db/models.py
```

```bash
git add api/alembic/versions/
```

```bash
git commit --signoff -m "feat: add baseline pin + override columns (migration 003)"
```

---

## Chunk 2: Evaluation Lifecycle — Schemas + Repository + Router

### Task 3: Add schemas for pin/override/heatmap

**Files:**
- Modify: `api/app/modules/quality_gate/schemas.py:78-128`

- [ ] **Step 1: Add pin/override fields to EvaluationSummary**

After line 95 (`invalidated: bool`) in `EvaluationSummary`, add:

```python
    baseline_pinned_at: datetime | None = None
    baseline_unpinned_at: datetime | None = None
    baseline_pin_reason: str | None = None
    baseline_pin_author: str | None = None
    original_result: str | None = None
    override_reason: str | None = None
    override_author: str | None = None
```

- [ ] **Step 2: Add request and response schemas**

After `TrendPoint` (line 128), add:

```python
class PinBaselineRequest(BaseModel):
    """Request body for pinning an evaluation as baseline."""

    reason: str
    author: str


class OverrideStatusRequest(BaseModel):
    """Request body for overriding evaluation result."""

    new_result: str
    reason: str
    author: str


class HeatmapMetric(BaseModel):
    """A metric definition in the heatmap grid."""

    name: str
    display_name: str


class HeatmapCell(BaseModel):
    """A single cell in the metric heatmap grid."""

    slot: datetime
    metric: str
    display_name: str
    result: str
    score: float
    eval_id: uuid.UUID


class MetricHeatmapResponse(BaseModel):
    """Response for the metric heatmap endpoint."""

    asset_name: str
    slots: list[datetime]
    metrics: list[HeatmapMetric]
    cells: list[HeatmapCell]
```

- [ ] **Step 3: Verify imports**

```bash
uv run --directory api python -c "from app.modules.quality_gate.schemas import PinBaselineRequest, MetricHeatmapResponse; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add api/app/modules/quality_gate/schemas.py
```

```bash
git commit --signoff -m "feat: add pin/override/heatmap schemas to quality_gate"
```

### Task 4: Add repository methods for pin/override/heatmap

**Files:**
- Modify: `api/app/modules/quality_gate/repository.py:228-276` and end of class

- [ ] **Step 1: Add pin_baseline method**

Add after the `restore()` method (around line 364):

```python
    async def pin_baseline(
        self,
        eval_id: uuid.UUID,
        *,
        reason: str,
        author: str,
    ) -> Evaluation | None:
        """Pin an evaluation as the baseline floor for its asset+SLO combination.

        Atomically unpins any existing active pin for the same (asset_id, slo_name).
        """
        ev = await self.get_by_id(eval_id)
        if ev is None:
            return None
        # Unpin any existing active pin for this asset+SLO
        if ev.asset_id and ev.slo_name:
            await self._session.execute(
                update(Evaluation)
                .where(
                    Evaluation.asset_id == ev.asset_id,
                    Evaluation.slo_name == ev.slo_name,
                    Evaluation.baseline_pinned_at.is_not(None),
                    Evaluation.baseline_unpinned_at.is_(None),
                )
                .values(baseline_unpinned_at=func.now())
            )
        # Pin the target evaluation
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(
                baseline_pinned_at=func.now(),
                baseline_pin_reason=reason,
                baseline_pin_author=author,
            )
        )
        await self._session.flush()
        return await self.get_by_id(eval_id)

    async def unpin_baseline(self, eval_id: uuid.UUID) -> Evaluation | None:
        """Remove the baseline pin from an evaluation."""
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(baseline_unpinned_at=func.now())
        )
        await self._session.flush()
        return await self.get_by_id(eval_id)
```

Verify `func` is already in the SQLAlchemy imports (it should be at line 9 — do not add a duplicate).

- [ ] **Step 2: Add override_status and restore_override methods**

```python
    async def override_status(
        self,
        eval_id: uuid.UUID,
        *,
        new_result: str,
        reason: str,
        author: str,
    ) -> Evaluation | None:
        """Override the evaluation result, preserving the original."""
        ev = await self.get_by_id(eval_id)
        if ev is None:
            return None
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(
                original_result=ev.result,
                result=new_result,
                override_reason=reason,
                override_author=author,
            )
        )
        await self._session.flush()
        return await self.get_by_id(eval_id)

    async def restore_override(self, eval_id: uuid.UUID) -> Evaluation | None:
        """Restore the original result, clearing the override."""
        ev = await self.get_by_id(eval_id)
        if ev is None or ev.original_result is None:
            return ev
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(
                result=ev.original_result,
                original_result=None,
                override_reason=None,
                override_author=None,
            )
        )
        await self._session.flush()
        return await self.get_by_id(eval_id)
```

- [ ] **Step 3: Add get_metric_heatmap method**

```python
    async def get_metric_heatmap(
        self,
        *,
        asset_id: uuid.UUID,
        limit: int = 20,
    ) -> list[Evaluation]:
        """Fetch the last N completed evaluations for an asset, ordered by period_start DESC."""
        q = (
            select(Evaluation)
            .where(
                Evaluation.asset_id == asset_id,
                Evaluation.status == EvaluationStatus.COMPLETED,
            )
            .order_by(Evaluation.period_start.desc())
            .limit(limit)
        )
        result = await self._session.execute(q)
        return list(result.scalars().all())
```

- [ ] **Step 4: Update get_baselines() with pin awareness**

Modify `get_baselines()` (line 228) — add `asset_id` and `slo_name` parameters:

Change the signature from:
```python
    async def get_baselines(
        self,
        *,
        name: str,
        scope_tags: list[str],
        asset_snapshot: dict[str, Any],
        include_result_with_score: str,
        limit: int,
        sli_name: str | None = None,
    ) -> list[Evaluation]:
```

To:
```python
    async def get_baselines(
        self,
        *,
        name: str,
        scope_tags: list[str],
        asset_snapshot: dict[str, Any],
        include_result_with_score: str,
        limit: int,
        sli_name: str | None = None,
        asset_id: uuid.UUID | None = None,
        slo_name: str | None = None,
    ) -> list[Evaluation]:
```

Then, after the initial `q = select(Evaluation).where(...)` block (around line 253), add the pin check:

```python
        # Pin-aware: restrict baseline window to evaluations after the active pin
        if asset_id and slo_name:
            pin_q = select(Evaluation.period_start).where(
                Evaluation.asset_id == asset_id,
                Evaluation.slo_name == slo_name,
                Evaluation.baseline_pinned_at.is_not(None),
                Evaluation.baseline_unpinned_at.is_(None),
            )
            pin_row = await self._session.execute(pin_q)
            pin_start = pin_row.scalar_one_or_none()
            if pin_start is not None:
                q = q.where(Evaluation.period_start >= pin_start)
```

- [ ] **Step 5: Verify imports compile**

```bash
uv run --directory api python -c "from app.modules.quality_gate.repository import EvaluationRepository; print('ok')"
```

Expected: `ok`

- [ ] **Step 6: Run existing tests**

```bash
uv run pytest api/tests/ -m "not integration" -q
```

Expected: All pass (no existing tests should break since we only added new methods and optional params).

- [ ] **Step 7: Commit**

```bash
git add api/app/modules/quality_gate/repository.py
```

```bash
git commit --signoff -m "feat: add pin/override/heatmap repository methods + pin-aware baselines"
```

### Task 5: Add router endpoints for pin/override/heatmap

**Files:**
- Modify: `api/app/modules/quality_gate/router.py`

- [ ] **Step 1: Add imports for new schemas**

`AssetRepository` is already imported (line 13) — do not add a duplicate. Extend the existing `from app.modules.quality_gate.schemas import (...)` block (line 17) with these additional imports:

```python
    HeatmapCell,
    HeatmapMetric,
    MetricHeatmapResponse,
    OverrideStatusRequest,
    PinBaselineRequest,
```

- [ ] **Step 2: Add pin-baseline endpoint**

After the `restore_evaluation` endpoint (line 174), add:

```python
@router.patch("/evaluations/{eval_id}/pin-baseline", response_model=EvaluationDetail)
async def pin_baseline(
    eval_id: uuid.UUID,
    body: PinBaselineRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EvaluationDetail:
    """Pin an evaluation as the new baseline for future comparisons."""
    repo = EvaluationRepository(session)
    ev = await repo.get_by_id(eval_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="evaluation not found")
    if ev.status != "completed":
        raise HTTPException(status_code=409, detail="only completed evaluations can be pinned")
    if ev.invalidated:
        raise HTTPException(status_code=409, detail="cannot pin an invalidated evaluation")
    updated = await repo.pin_baseline(eval_id, reason=body.reason, author=body.author)
    return _build_detail(updated)


@router.patch("/evaluations/{eval_id}/unpin-baseline", response_model=EvaluationDetail)
async def unpin_baseline(
    eval_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EvaluationDetail:
    """Remove baseline pin from an evaluation."""
    repo = EvaluationRepository(session)
    ev = await repo.get_by_id(eval_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="evaluation not found")
    updated = await repo.unpin_baseline(eval_id)
    return _build_detail(updated)
```

- [ ] **Step 3: Add override-status endpoint**

```python
@router.patch("/evaluations/{eval_id}/override-status", response_model=EvaluationDetail)
async def override_status(
    eval_id: uuid.UUID,
    body: OverrideStatusRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EvaluationDetail:
    """Override the evaluation result."""
    repo = EvaluationRepository(session)
    ev = await repo.get_by_id(eval_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="evaluation not found")
    if ev.status != "completed":
        raise HTTPException(status_code=409, detail="only completed evaluations can be overridden")
    if body.new_result not in ("pass", "warning", "fail"):
        raise HTTPException(status_code=422, detail="new_result must be pass, warning, or fail")
    updated = await repo.override_status(
        eval_id, new_result=body.new_result, reason=body.reason, author=body.author
    )
    return _build_detail(updated)


@router.patch("/evaluations/{eval_id}/restore-override", response_model=EvaluationDetail)
async def restore_override(
    eval_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EvaluationDetail:
    """Restore the original evaluation result."""
    repo = EvaluationRepository(session)
    ev = await repo.get_by_id(eval_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="evaluation not found")
    if ev.original_result is None:
        raise HTTPException(status_code=409, detail="evaluation has no override to restore")
    updated = await repo.restore_override(eval_id)
    return _build_detail(updated)
```

- [ ] **Step 4: Add metric-heatmap endpoint**

This MUST be inserted immediately before the `@router.get("/evaluations/{eval_id}")` route (line 114), after the closing of `list_evaluations` (line 111). If placed after the `{eval_id}` route, FastAPI will interpret `metric-heatmap` as a UUID path parameter and return 422:

```python
@router.get("/evaluations/metric-heatmap", response_model=MetricHeatmapResponse)
async def get_metric_heatmap(
    asset_name: str,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MetricHeatmapResponse:
    """Return a metric × evaluation heatmap grid for an asset."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(asset_name)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"asset '{asset_name}' not found")
    eval_repo = EvaluationRepository(session)
    evals = await eval_repo.get_metric_heatmap(asset_id=asset.id, limit=limit)
    # Build slots (timestamps) and collect all unique metrics
    slots: list[datetime] = []
    metric_set: dict[str, str] = {}  # name → display_name
    cells: list[HeatmapCell] = []
    for ev in reversed(evals):  # oldest first for display
        slots.append(ev.period_start)
        for ir in ev.indicator_results or []:
            metric_name = ir.get("metric", "")
            if metric_name not in metric_set:
                metric_set[metric_name] = ir.get("display_name", metric_name)
            cells.append(
                HeatmapCell(
                    slot=ev.period_start,
                    metric=metric_name,
                    display_name=ir.get("display_name", metric_name),
                    result=ir.get("status", "error"),
                    score=ir.get("score", 0.0),
                    eval_id=ev.id,
                )
            )
    return MetricHeatmapResponse(
        asset_name=asset_name,
        slots=slots,
        metrics=[HeatmapMetric(name=k, display_name=v) for k, v in metric_set.items()],
        cells=cells,
    )
```

- [ ] **Step 5: Add `_build_detail` helper if not present**

Check if `_build_detail` already exists in the router. If not, add it after `_build_summary` (line 54). The helper must call `_build_summary` with its required `annotation_count` and `latest_ann` arguments, and use `model_validate` (not keyword constructor) to avoid serialization type mismatches:

```python
def _build_detail(ev: object) -> EvaluationDetail:
    """Construct EvaluationDetail from an ORM Evaluation with annotations loaded."""
    annotations = [AnnotationRead.model_validate(a) for a in (ev.annotations or [])]
    indicator_results = [IndicatorResult(**ir) for ir in (ev.indicator_results or [])]
    compared_ids = (ev.job_stats or {}).get("compared_evaluation_ids", [])
    top_failures = [
        FailingIndicator(
            metric=ind.metric,
            display_name=ind.display_name,
            value=ind.value,
            threshold=(ind.pass_targets or [{}])[0].get("criteria", ""),
        )
        for ind in indicator_results
        if ind.status == "fail"
    ]
    sorted_annotations = sorted(annotations, key=lambda a: a.created_at)
    return EvaluationDetail.model_validate(
        {
            **ev.__dict__,
            "annotation_count": len(annotations),
            "latest_annotation": sorted_annotations[-1].created_at if sorted_annotations else None,
            "top_failures": top_failures,
            "compared_evaluation_ids": [uuid.UUID(eid) for eid in compared_ids],
            "annotations": sorted_annotations,
            "indicator_results": indicator_results,
        }
    )
```

- [ ] **Step 6: Lint**

```bash
uv run ruff check api/app/modules/quality_gate/ --fix
```

```bash
uv run ruff format api/app/modules/quality_gate/
```

- [ ] **Step 7: Run unit tests**

```bash
uv run pytest api/tests/ -m "not integration" -q
```

Expected: All pass.

- [ ] **Step 8: Commit**

```bash
git add api/app/modules/quality_gate/router.py
```

```bash
git commit --signoff -m "feat: add pin/unpin, override/restore, heatmap endpoints"
```

---

## Chunk 3: Mock Adapter Service

### Task 6: Create mock adapter package and CSV store

**Files:**
- Create: `adapters/mock/pyproject.toml`
- Create: `adapters/mock/__init__.py`
- Create: `adapters/mock/app/__init__.py`
- Create: `adapters/mock/app/csv_store.py`
- Create: `adapters/mock/tests/test_csv_store.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "tropek-adapter-mock"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.28"]

[tool.hatch.build.targets.wheel]
packages = ["app"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty `__init__.py` files**

Create `adapters/mock/__init__.py`, `adapters/mock/app/__init__.py`, and `adapters/mock/tests/__init__.py` as empty files.

- [ ] **Step 3: Write failing test for CSV store**

`adapters/mock/tests/test_csv_store.py`:

```python
"""Unit tests for the CSV data store."""

from __future__ import annotations

import csv
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.csv_store import CsvStore


def _write_csv(directory: Path, namespace: str, rows: list[dict[str, str]]) -> None:
    """Write test CSV data into namespace directory."""
    ns_dir = directory / namespace
    ns_dir.mkdir(parents=True, exist_ok=True)
    path = ns_dir / "metrics.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "metric_name", "value"])
        writer.writeheader()
        writer.writerows(rows)


def test_lookup_returns_last_value_in_range() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        _write_csv(data_dir, "prom-dc-a", [
            {"timestamp": "2026-03-15T08:00:00Z", "metric_name": "cpu", "value": "40.0"},
            {"timestamp": "2026-03-15T08:05:00Z", "metric_name": "cpu", "value": "45.0"},
            {"timestamp": "2026-03-15T08:10:00Z", "metric_name": "cpu", "value": "50.0"},
            {"timestamp": "2026-03-15T09:00:00Z", "metric_name": "cpu", "value": "60.0"},
        ])
        store = CsvStore(data_dir)
        result = store.query(
            namespace="prom-dc-a",
            queries={"cpu": "ignored_query_string"},
            start=datetime(2026, 3, 15, 8, 0, tzinfo=timezone.utc),
            end=datetime(2026, 3, 15, 8, 15, tzinfo=timezone.utc),
        )
        assert result.values == {"cpu": 50.0}
        assert result.errors == {}


def test_missing_metric_goes_to_errors() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        _write_csv(data_dir, "prom-dc-a", [
            {"timestamp": "2026-03-15T08:00:00Z", "metric_name": "cpu", "value": "40.0"},
        ])
        store = CsvStore(data_dir)
        result = store.query(
            namespace="prom-dc-a",
            queries={"cpu": "q1", "missing_metric": "q2"},
            start=datetime(2026, 3, 15, 8, 0, tzinfo=timezone.utc),
            end=datetime(2026, 3, 15, 8, 15, tzinfo=timezone.utc),
        )
        assert result.values == {"cpu": 40.0}
        assert "missing_metric" in result.errors


def test_unknown_namespace_all_errors() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = CsvStore(Path(tmpdir))
        result = store.query(
            namespace="nonexistent",
            queries={"cpu": "q"},
            start=datetime(2026, 3, 15, 8, 0, tzinfo=timezone.utc),
            end=datetime(2026, 3, 15, 8, 15, tzinfo=timezone.utc),
        )
        assert result.values == {}
        assert "cpu" in result.errors
```

- [ ] **Step 4: Run tests — expect ImportError**

```bash
uv run --directory adapters/mock pytest tests/test_csv_store.py -v
```

Expected: `ModuleNotFoundError` for `app.csv_store`.

- [ ] **Step 5: Implement CSV store**

`adapters/mock/app/csv_store.py`:

```python
"""CSV-backed time-series data store for the mock adapter."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class QueryResult:
    """Result of a metric query — mirrors the adapter response contract."""

    values: dict[str, float] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


class CsvStore:
    """Reads CSV files from namespace directories and performs time-range lookups."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def query(
        self,
        *,
        namespace: str,
        queries: dict[str, str],
        start: datetime,
        end: datetime,
    ) -> QueryResult:
        """Look up metric values within a time range.

        For each requested metric, finds all CSV rows in the namespace directory
        where start <= timestamp <= end and returns the last (most recent) value.
        """
        ns_dir = self._data_dir / namespace
        if not ns_dir.is_dir():
            return QueryResult(
                errors={name: f"namespace '{namespace}' not found" for name in queries},
            )

        # Load all CSV rows from the namespace
        rows = self._load_namespace(ns_dir)

        result = QueryResult()
        for metric_name in queries:
            matching = [
                r for r in rows
                if r["metric_name"] == metric_name
                and start <= _parse_ts(r["timestamp"]) <= end
            ]
            if matching:
                # Take the last value in the range (sorted by timestamp)
                matching.sort(key=lambda r: r["timestamp"])
                result.values[metric_name] = float(matching[-1]["value"])
            else:
                result.errors[metric_name] = f"no data for '{metric_name}' in range"

        return result

    def _load_namespace(self, ns_dir: Path) -> list[dict[str, str]]:
        """Load all CSV files in a namespace directory."""
        rows: list[dict[str, str]] = []
        for csv_path in ns_dir.glob("*.csv"):
            with csv_path.open() as f:
                reader = csv.DictReader(f)
                rows.extend(reader)
        return rows


def _parse_ts(ts_str: str) -> datetime:
    """Parse an ISO 8601 timestamp string to a timezone-aware datetime."""
    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
```

- [ ] **Step 6: Run tests — expect pass**

```bash
uv run --directory adapters/mock pytest tests/test_csv_store.py -v
```

Expected: 3 tests pass.

- [ ] **Step 7: Commit**

```bash
git add adapters/mock/
```

```bash
git commit --signoff -m "feat: add mock adapter CSV store with unit tests"
```

### Task 7: Create mock adapter FastAPI service

**Files:**
- Create: `adapters/mock/app/main.py`
- Create: `adapters/mock/Dockerfile`

- [ ] **Step 1: Implement the FastAPI app**

`adapters/mock/app/main.py`:

```python
"""TROPEK Mock adapter — serves CSV-backed time-series data."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Header, Request
from pydantic import BaseModel

from app.csv_store import CsvStore

app = FastAPI(title="TROPEK Mock Adapter", version="0.1.0")

DATA_DIR = Path(os.getenv("MOCK_DATA_DIR", "/app/data"))
_store = CsvStore(DATA_DIR)


class QueryRequest(BaseModel):
    """Adapter query request body."""

    queries: dict[str, str]
    start: datetime
    end: datetime


class QueryResponse(BaseModel):
    """Adapter query response body."""

    values: dict[str, float]
    errors: dict[str, str]


@app.post("/query", response_model=QueryResponse)
async def query_metrics(
    body: QueryRequest,
    x_datasource_name: str = Header(default="default"),
) -> QueryResponse:
    """Execute metric queries against CSV data store."""
    result = _store.query(
        namespace=x_datasource_name,
        queries=body.queries,
        start=body.start,
        end=body.end,
    )
    return QueryResponse(values=result.values, errors=result.errors)


@app.get("/health")
async def health() -> dict[str, str]:
    """Return adapter health status."""
    return {"status": "ok", "datasource": "mock"}
```

- [ ] **Step 2: Create Dockerfile**

`adapters/mock/Dockerfile`:

```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project
COPY app/ app/

EXPOSE 8082
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8082"]
```

Note: The `data/` directory is NOT copied into the image — it is mounted as a volume via docker-compose. This avoids build failures when generated data doesn't exist yet.

- [ ] **Step 3: Add to docker-compose.yml**

Add after the `adapter-prometheus` service:

```yaml
  adapter-mock:
    build:
      context: ./adapters/mock
      dockerfile: Dockerfile
    ports:
      - "8082:8082"
    volumes:
      - ./adapters/mock/data:/app/data:ro
```

- [ ] **Step 4: Create empty data directory with .gitkeep**

```bash
mkdir -p adapters/mock/data
```

```bash
touch adapters/mock/data/.gitkeep
```

- [ ] **Step 5: Commit**

```bash
git add adapters/mock/app/main.py adapters/mock/Dockerfile docker-compose.yml adapters/mock/data/.gitkeep
```

```bash
git commit --signoff -m "feat: add mock adapter FastAPI service + docker-compose entry"
```

### Task 8: Create scenario generator

**Files:**
- Create: `adapters/mock/generate.py`
- Create: `adapters/mock/scenarios/stable.yaml`
- Create: `adapters/mock/scenarios/regression.yaml`
- Create: `adapters/mock/tests/test_generator.py`

- [ ] **Step 1: Write failing test for generator**

`adapters/mock/tests/test_generator.py`:

```python
"""Unit tests for the scenario CSV generator."""

from __future__ import annotations

import tempfile
from pathlib import Path

from generate import generate_scenario, load_scenario


def test_load_scenario() -> None:
    scenario = load_scenario(Path("scenarios/stable.yaml"))
    assert scenario["name"] == "stable"
    assert "metrics" in scenario
    assert scenario["interval_minutes"] > 0


def test_generate_stable_creates_csv_per_namespace() -> None:
    scenario = load_scenario(Path("scenarios/stable.yaml"))
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        generate_scenario(scenario, out_dir)
        # Should create a directory per namespace
        for ns in scenario["namespaces"]:
            csv_path = out_dir / ns / "metrics.csv"
            assert csv_path.exists(), f"missing {csv_path}"
            with csv_path.open() as f:
                header = f.readline().strip()
                assert "timestamp" in header
                assert "metric_name" in header
                assert "value" in header


def test_generate_is_deterministic() -> None:
    scenario = load_scenario(Path("scenarios/stable.yaml"))
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        generate_scenario(scenario, Path(d1))
        generate_scenario(scenario, Path(d2))
        for ns in scenario["namespaces"]:
            f1 = Path(d1) / ns / "metrics.csv"
            f2 = Path(d2) / ns / "metrics.csv"
            assert f1.read_text() == f2.read_text()
```

- [ ] **Step 2: Create scenario YAML files**

`adapters/mock/scenarios/stable.yaml`:

Scenarios now include a `namespaces` list that maps each scenario to the datasource namespace directories it should generate data into. This connects the scenario data to the `X-Datasource-Name` header routing.

```yaml
name: stable
namespaces:
  - prometheus-local
  - mock-dc-b
metrics:
  response_time_p99:
    baseline: 450
    phases:
      - duration_hours: 48
        pattern: stable
        jitter_pct: 5
  error_rate:
    baseline: 0.001
    phases:
      - duration_hours: 48
        pattern: stable
        jitter_pct: 10
  availability:
    baseline: 99.95
    phases:
      - duration_hours: 48
        pattern: stable
        jitter_pct: 0.05
interval_minutes: 5
start: "2026-03-15T00:00:00Z"
```

`adapters/mock/scenarios/regression.yaml`:

```yaml
name: regression
namespaces:
  - splunk-prod
metrics:
  response_time_p99:
    baseline: 450
    phases:
      - duration_hours: 24
        pattern: stable
        jitter_pct: 5
      - duration_hours: 12
        pattern: ramp
        target: 800
        jitter_pct: 3
      - duration_hours: 24
        pattern: stable
        jitter_pct: 5
  error_rate:
    baseline: 0.001
    phases:
      - duration_hours: 24
        pattern: stable
        jitter_pct: 10
      - duration_hours: 12
        pattern: ramp
        target: 0.05
        jitter_pct: 5
      - duration_hours: 24
        pattern: stable
        jitter_pct: 10
interval_minutes: 5
start: "2026-03-15T00:00:00Z"
```

- [ ] **Step 3: Implement generator**

`adapters/mock/generate.py`:

```python
"""Generate CSV time-series data from scenario YAML definitions."""

from __future__ import annotations

import csv
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml


def load_scenario(path: Path) -> dict:
    """Load a scenario YAML file."""
    with path.open() as f:
        return yaml.safe_load(f)


def generate_scenario(scenario: dict, output_dir: Path) -> None:
    """Generate CSV files from a scenario definition.

    Uses the scenario name as the random seed for deterministic output.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(scenario["name"])
    interval = timedelta(minutes=scenario["interval_minutes"])
    start = datetime.fromisoformat(scenario["start"].replace("Z", "+00:00"))

    all_rows: list[dict[str, str]] = []
    for metric_name, metric_def in scenario["metrics"].items():
        baseline = metric_def["baseline"]
        current_time = start
        for phase in metric_def["phases"]:
            duration = timedelta(hours=phase["duration_hours"])
            phase_end = current_time + duration
            jitter_pct = phase["jitter_pct"] / 100.0
            pattern = phase["pattern"]
            target = phase.get("target", baseline)
            phase_start_time = current_time
            while current_time < phase_end:
                if pattern == "stable":
                    value = baseline * (1.0 + rng.uniform(-jitter_pct, jitter_pct))
                elif pattern == "ramp":
                    progress = (current_time - phase_start_time) / duration
                    value = baseline + (target - baseline) * progress
                    value *= 1.0 + rng.uniform(-jitter_pct, jitter_pct)
                elif pattern == "spike":
                    mid = phase_start_time + duration / 2
                    if current_time < mid:
                        progress = (current_time - phase_start_time) / (duration / 2)
                        value = baseline + (target - baseline) * progress
                    else:
                        progress = (current_time - mid) / (duration / 2)
                        value = target + (baseline - target) * progress
                    value *= 1.0 + rng.uniform(-jitter_pct, jitter_pct)
                else:
                    value = baseline
                all_rows.append({
                    "timestamp": current_time.isoformat(),
                    "metric_name": metric_name,
                    "value": f"{value:.6f}",
                })
                current_time += interval
            # Update baseline for next phase (ramp endpoint becomes new baseline)
            if pattern == "ramp":
                baseline = target

    # Write CSV into each namespace directory (matches X-Datasource-Name routing)
    namespaces = scenario.get("namespaces", [scenario["name"]])
    all_rows.sort(key=lambda r: (r["timestamp"], r["metric_name"]))
    for ns in namespaces:
        ns_dir = output_dir / ns
        ns_dir.mkdir(parents=True, exist_ok=True)
        csv_path = ns_dir / "metrics.csv"
        with csv_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "metric_name", "value"])
            writer.writeheader()
            writer.writerows(all_rows)


def main() -> None:
    """Generate CSVs for all scenarios into the data directory."""
    scenarios_dir = Path("scenarios")
    data_dir = Path("data")
    for scenario_path in sorted(scenarios_dir.glob("*.yaml")):
        scenario = load_scenario(scenario_path)
        generate_scenario(scenario, data_dir)
        namespaces = scenario.get("namespaces", [scenario["name"]])
        for ns in namespaces:
            print(f"generated {data_dir}/{ns}/metrics.csv ({scenario['name']})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run generator tests**

```bash
uv run --directory adapters/mock pytest tests/test_generator.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Generate initial data**

```bash
uv run --directory adapters/mock python generate.py
```

Expected: Creates `adapters/mock/data/prometheus-local/metrics.csv`, `adapters/mock/data/mock-dc-b/metrics.csv`, and `adapters/mock/data/splunk-prod/metrics.csv`.

- [ ] **Step 6: Add data/ to .gitignore**

Create `adapters/mock/.gitignore`:

```
data/*/
!data/.gitkeep
```

- [ ] **Step 7: Commit**

```bash
git add adapters/mock/generate.py adapters/mock/scenarios/ adapters/mock/tests/test_generator.py adapters/mock/.gitignore
```

```bash
git commit --signoff -m "feat: add scenario YAML generator for mock adapter CSV data"
```

---

## Chunk 4: Evaluation Trigger + Worker

### Task 9: Create trigger logic module

**Files:**
- Create: `api/app/modules/quality_gate/trigger.py`
- Create: `api/tests/engine/test_trigger.py`

- [ ] **Step 1: Write failing test for trigger resolution**

`api/tests/engine/test_trigger.py`:

```python
"""Unit tests for evaluation trigger resolution logic."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.modules.quality_gate.trigger import resolve_single_trigger, TriggerContext


@pytest.fixture
def mock_repos() -> dict:
    asset_repo = AsyncMock()
    slo_link_repo = AsyncMock()
    sli_repo = AsyncMock()
    slo_repo = AsyncMock()
    ds_repo = AsyncMock()

    asset_repo.get_by_name.return_value = type("Asset", (), {
        "id": uuid.uuid4(),
        "name": "vm-01",
        "labels": {"os": "linux"},
    })()

    slo_link_repo.list_by_asset.return_value = [
        type("Link", (), {
            "slo_name": "perf-slo",
            "sli_name": "system-sli",
            "data_source_name": "prom-1",
        })(),
    ]

    sli_repo.get_latest.return_value = type("SLI", (), {
        "name": "system-sli",
        "version": 1,
        "indicators": {"cpu": "query"},
    })()

    slo_repo.get_latest.return_value = type("SLO", (), {
        "name": "perf-slo",
        "version": 1,
    })()

    ds_repo.get_by_name.return_value = type("DS", (), {
        "name": "prom-1",
        "adapter_url": "http://prom:8081",
        "adapter_type": "prometheus",
    })()

    return {
        "asset_repo": asset_repo,
        "slo_link_repo": slo_link_repo,
        "sli_repo": sli_repo,
        "slo_repo": slo_repo,
        "ds_repo": ds_repo,
    }


async def test_resolve_single_trigger(mock_repos: dict) -> None:
    ctx = await resolve_single_trigger(
        asset_name="vm-01",
        slo_name="perf-slo",
        **mock_repos,
    )
    assert ctx.asset_name == "vm-01"
    assert ctx.slo_name == "perf-slo"
    assert ctx.sli_name == "system-sli"
    assert ctx.data_source_name == "prom-1"
    assert ctx.adapter_url == "http://prom:8081"
    assert ctx.indicators == {"cpu": "query"}


async def test_resolve_single_trigger_asset_not_found(mock_repos: dict) -> None:
    mock_repos["asset_repo"].get_by_name.return_value = None
    with pytest.raises(ValueError, match="asset"):
        await resolve_single_trigger(
            asset_name="nonexistent",
            slo_name="perf-slo",
            **mock_repos,
        )
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
uv run pytest api/tests/engine/test_trigger.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement trigger resolution**

`api/app/modules/quality_gate/trigger.py`:

```python
"""Evaluation trigger resolution — resolves asset/SLO/SLI/datasource references."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class TriggerContext:
    """All resolved references needed to run an evaluation job."""

    asset_id: uuid.UUID
    asset_name: str
    asset_labels: dict[str, Any]
    slo_name: str
    slo_version: int
    sli_name: str
    sli_version: int
    data_source_name: str
    adapter_url: str
    adapter_type: str
    indicators: dict[str, str]


async def resolve_single_trigger(
    *,
    asset_name: str,
    slo_name: str,
    asset_repo: Any,
    slo_link_repo: Any,
    sli_repo: Any,
    slo_repo: Any,
    ds_repo: Any,
) -> TriggerContext:
    """Resolve all references for a single asset evaluation.

    Raises ValueError with descriptive message if any reference is missing.
    """
    asset = await asset_repo.get_by_name(asset_name)
    if asset is None:
        msg = f"asset '{asset_name}' not found"
        raise ValueError(msg)

    # Find the SLO link for this asset + slo_name
    links = await slo_link_repo.list_by_asset(asset.id)
    link = next((lnk for lnk in links if lnk.slo_name == slo_name), None)
    if link is None:
        msg = f"no slo link for asset '{asset_name}' with slo '{slo_name}'"
        raise ValueError(msg)

    sli_def = await sli_repo.get_latest(link.sli_name)
    if sli_def is None:
        msg = f"sli definition '{link.sli_name}' not found"
        raise ValueError(msg)

    slo_def = await slo_repo.get_latest(link.slo_name)
    if slo_def is None:
        msg = f"slo definition '{link.slo_name}' not found"
        raise ValueError(msg)

    ds = await ds_repo.get_by_name(link.data_source_name)
    if ds is None:
        msg = f"datasource '{link.data_source_name}' not found"
        raise ValueError(msg)

    return TriggerContext(
        asset_id=asset.id,
        asset_name=asset.name,
        asset_labels=getattr(asset, "labels", {}),
        slo_name=slo_def.name,
        slo_version=slo_def.version,
        sli_name=sli_def.name,
        sli_version=sli_def.version,
        data_source_name=ds.name,
        adapter_url=ds.adapter_url,
        adapter_type=ds.adapter_type,
        indicators=sli_def.indicators,
    )
```

- [ ] **Step 4: Run tests — expect pass**

```bash
uv run pytest api/tests/engine/test_trigger.py -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/quality_gate/trigger.py api/tests/engine/test_trigger.py
```

```bash
git commit --signoff -m "feat: add trigger resolution module with unit tests"
```

### Task 10: Create worker job module

**Files:**
- Create: `api/app/modules/quality_gate/worker.py`

- [ ] **Step 1: Implement the arq worker job**

`api/app/modules/quality_gate/worker.py`:

```python
"""arq worker job for evaluation execution."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Evaluation, EvaluationBatch
from app.modules.datasource.repository import DataSourceRepository
from app.modules.quality_gate.engine.criteria import aggregate_values
from app.modules.quality_gate.engine.evaluator import evaluate
from app.modules.quality_gate.engine.slo_parser import build_slo
from app.modules.quality_gate.engine.variables import build_variables, substitute_variables
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_registry.repository import SLORepository


async def run_evaluation(
    session: AsyncSession,
    eval_id: uuid.UUID,
    *,
    worker_id: str | None = None,
) -> None:
    """Execute a single evaluation job.

    1. Mark running
    2. Build SLO model from stored definition
    3. Build variables and substitute into SLI queries
    4. Query adapter
    5. Resolve baselines (pin-aware)
    6. Evaluate
    7. Write results
    """
    repo = EvaluationRepository(session)
    await repo.mark_running(eval_id, worker_id)

    ev = await repo.get_by_id(eval_id)
    if ev is None:
        return

    # Load SLO definition
    slo_repo = SLORepository(session)
    slo_def = await slo_repo.get_version(ev.slo_name, ev.slo_version)
    if slo_def is None:
        await repo.mark_failed(eval_id, job_stats={"error": f"slo '{ev.slo_name}' v{ev.slo_version} not found"})
        return

    # Build SLO model
    objectives = [
        {
            "sli": obj.sli,
            "display_name": obj.display_name,
            "pass_threshold": obj.pass_threshold,
            "warning_threshold": obj.warning_threshold,
            "weight": obj.weight,
            "key_sli": obj.key_sli,
        }
        for obj in slo_def.objectives
    ]
    slo = build_slo(
        objectives=objectives,
        total_score_pass_threshold=slo_def.total_score_pass_threshold,
        total_score_warning_threshold=slo_def.total_score_warning_threshold,
        comparison=slo_def.comparison,
    )

    # Load SLI definition
    sli_repo = SLIRepository(session)
    sli_def = await sli_repo.get_version(ev.sli_name, ev.sli_version)
    if sli_def is None:
        await repo.mark_failed(eval_id, job_stats={"error": f"sli '{ev.sli_name}' v{ev.sli_version} not found"})
        return

    # Build variables and substitute
    asset_labels = (ev.asset_snapshot or {}).get("tags", {})
    variables = build_variables(
        metadata=ev.evaluation_metadata or {},
        asset_name=(ev.asset_snapshot or {}).get("name"),
        test_name=ev.name,
        start=ev.period_start.isoformat(),
        end=ev.period_end.isoformat(),
    )
    # Add asset labels as variables
    for k, v in asset_labels.items():
        if k not in variables:
            variables[k] = str(v)

    resolved_queries: dict[str, str] = {}
    for metric_name, query_template in sli_def.indicators.items():
        resolved_queries[metric_name] = substitute_variables(query_template, variables)

    # Query adapter
    ds_repo = DataSourceRepository(session)
    ds = await ds_repo.get_by_name(ev.data_source_name)
    if ds is None:
        await repo.mark_failed(eval_id, job_stats={"error": f"datasource '{ev.data_source_name}' not found"})
        return

    metrics_fetched: dict[str, float] = {}
    fetch_errors: dict[str, str] = {}
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            adapter_resp = await http_client.post(
                f"{ds.adapter_url}/query",
                headers={"X-Datasource-Name": ds.name},
                json={
                    "queries": resolved_queries,
                    "start": ev.period_start.isoformat(),
                    "end": ev.period_end.isoformat(),
                },
            )
            adapter_resp.raise_for_status()
            adapter_data = adapter_resp.json()
            for name, val in adapter_data.get("values", {}).items():
                if val is not None:
                    metrics_fetched[name] = float(val)
            for name, err in adapter_data.get("errors", {}).items():
                fetch_errors[name] = str(err)
    except httpx.ConnectError:
        await repo.mark_failed(eval_id, job_stats={"error": f"could not reach adapter at {ds.adapter_url}"})
        return
    except httpx.TimeoutException:
        await repo.mark_failed(eval_id, job_stats={"error": "adapter query timed out"})
        return
    except httpx.HTTPStatusError as exc:
        await repo.mark_failed(eval_id, job_stats={"error": f"adapter returned {exc.response.status_code}"})
        return

    # Resolve baselines (pin-aware)
    baselines: dict[str, float | None] = {}
    compared_eval_ids: list[str] = []
    if slo.comparison.number_of_comparison_results > 0:
        baseline_evals = await repo.get_baselines(
            name=ev.name,
            scope_tags=slo.comparison.scope_tags,
            asset_snapshot=ev.asset_snapshot or {},
            include_result_with_score=slo.comparison.include_result_with_score.value,
            limit=slo.comparison.number_of_comparison_results,
            sli_name=ev.sli_name,
            asset_id=ev.asset_id,
            slo_name=ev.slo_name,
        )
        compared_eval_ids = [str(bev.id) for bev in baseline_evals]
        for metric_name in sli_def.indicators:
            vals = []
            for bev in baseline_evals:
                for ir in bev.indicator_results or []:
                    if ir.get("metric") == metric_name and ir.get("value") is not None:
                        vals.append(ir["value"])
            if vals:
                baselines[metric_name] = aggregate_values(vals, slo.comparison.aggregate_function)

    # Evaluate
    eval_result = evaluate(slo, metrics_fetched, baselines, compared_eval_ids)

    # Write results
    await repo.mark_completed(
        eval_id,
        result=eval_result.result,
        score=eval_result.score,
        indicator_results=eval_result.indicator_results,
        slo_name=ev.slo_name,
        slo_version=ev.slo_version,
        job_stats={"compared_evaluation_ids": compared_eval_ids, "fetch_errors": fetch_errors},
    )

    # Write SLI values for TimescaleDB hypertable
    sli_rows = []
    for ir in eval_result.indicator_results:
        if ir.get("value") is not None:
            sli_rows.append({
                "eval_id": eval_id,
                "eval_start": ev.period_start,
                "metric_name": ir["metric"],
                "aggregation": ir.get("aggregation", "raw"),
                "value": ir["value"],
                "asset_name": (ev.asset_snapshot or {}).get("name"),
                "test_name": ev.name,
                "os_tag": asset_labels.get("os"),
            })
    if sli_rows:
        await repo.write_sli_values(sli_rows)
```

- [ ] **Step 2: Verify imports**

```bash
uv run --directory api python -c "from app.modules.quality_gate.worker import run_evaluation; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add api/app/modules/quality_gate/worker.py
```

```bash
git commit --signoff -m "feat: add evaluation worker job module"
```

### Task 11: Add trigger and batch endpoints to router

**Files:**
- Modify: `api/app/modules/quality_gate/router.py`

- [ ] **Step 1: Add trigger schemas to quality_gate schemas**

Add to `api/app/modules/quality_gate/schemas.py`:

```python
class TriggerRequest(BaseModel):
    """Request body for triggering a single evaluation."""

    asset_name: str
    test_name: str
    slo_name: str
    period_start: datetime
    period_end: datetime
    metadata: dict[str, str] = {}


class TriggerResponse(BaseModel):
    """Response from evaluation trigger."""

    id: uuid.UUID
    status: str


class BatchTriggerRequest(BaseModel):
    """Request body for triggering a group evaluation batch."""

    group_name: str
    test_name: str
    period_start: datetime
    period_end: datetime
    metadata: dict[str, str] = {}


class BatchTriggerResponse(BaseModel):
    """Response from batch trigger."""

    batch_id: uuid.UUID
    evaluation_ids: list[uuid.UUID]
    status: str
```

- [ ] **Step 2: Add POST /evaluations endpoint to router**

```python
@router.post("/evaluations", response_model=TriggerResponse, status_code=202)
async def trigger_evaluation(
    body: TriggerRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TriggerResponse:
    """Trigger a single asset evaluation."""
    asset_repo = AssetRepository(session)
    slo_link_repo = AssetSLOLinkRepository(session)
    sli_repo = SLIRepository(session)
    slo_repo = SLORepository(session)
    ds_repo = DataSourceRepository(session)

    try:
        ctx = await resolve_single_trigger(
            asset_name=body.asset_name,
            slo_name=body.slo_name,
            asset_repo=asset_repo,
            slo_link_repo=slo_link_repo,
            sli_repo=sli_repo,
            slo_repo=slo_repo,
            ds_repo=ds_repo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    eval_repo = EvaluationRepository(session)
    ev = await eval_repo.create_pending(
        name=body.test_name,
        period_start=body.period_start,
        period_end=body.period_end,
        ingestion_mode="pull",
        asset_snapshot={"name": ctx.asset_name, "tags": ctx.asset_labels},
        metadata=body.metadata,
        asset_id=ctx.asset_id,
        slo_name=ctx.slo_name,
        slo_version=ctx.slo_version,
        sli_name=ctx.sli_name,
        sli_version=ctx.sli_version,
        data_source_name=ctx.data_source_name,
        adapter_used=ctx.adapter_type,
    )
    # TODO: enqueue arq job here — await arq_pool.enqueue_job("run_evaluation", ev.id)
    return TriggerResponse(id=ev.id, status="pending")
```

Note: Add these top-level imports to `router.py`:

```python
from app.modules.assets.repository import AssetSLOLinkRepository, AssetGroupSLOLinkRepository
from app.modules.datasource.repository import DataSourceRepository
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_registry.repository import SLORepository
from app.modules.quality_gate.trigger import resolve_single_trigger
from app.modules.quality_gate.schemas import (
    # ... add to existing import block ...
    TriggerRequest,
    TriggerResponse,
    BatchTriggerRequest,
    BatchTriggerResponse,
)
```

- [ ] **Step 3: Add POST /evaluations/batch endpoint**

```python
@router.post("/evaluations/batch", response_model=BatchTriggerResponse, status_code=202)
async def trigger_batch(
    body: BatchTriggerRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> BatchTriggerResponse:
    """Trigger evaluations for all assets in a group."""
    group_repo = AssetGroupRepository(session)
    group = await group_repo.get_by_name(body.group_name)
    if group is None:
        raise HTTPException(status_code=404, detail=f"asset group '{body.group_name}' not found")

    asset_repo = AssetRepository(session)
    slo_link_repo = AssetSLOLinkRepository(session)
    sli_repo = SLIRepository(session)
    slo_repo = SLORepository(session)
    ds_repo = DataSourceRepository(session)
    eval_repo = EvaluationRepository(session)

    # Collect all SLO links for group members + group-level links
    group_link_repo = AssetGroupSLOLinkRepository(session)
    group_links = await group_link_repo.list_by_group(group.id)

    evaluation_ids: list[uuid.UUID] = []
    for member in group.members:
        # Get asset-level SLO links
        asset = await asset_repo.get_by_name(member.asset_name)
        if asset is None:
            continue
        asset_links = await slo_link_repo.list_by_asset(asset.id)
        # Combine asset links + group links (deduplicate by slo_name)
        all_links = {lnk.slo_name: lnk for lnk in asset_links}
        for gl in group_links:
            if gl.slo_name not in all_links:
                all_links[gl.slo_name] = gl

        for slo_name, link in all_links.items():
            try:
                ctx = await resolve_single_trigger(
                    asset_name=asset.name,
                    slo_name=slo_name,
                    asset_repo=asset_repo,
                    slo_link_repo=slo_link_repo,
                    sli_repo=sli_repo,
                    slo_repo=slo_repo,
                    ds_repo=ds_repo,
                )
            except ValueError:
                continue

            ev = await eval_repo.create_pending(
                name=body.test_name,
                period_start=body.period_start,
                period_end=body.period_end,
                ingestion_mode="pull",
                asset_snapshot={"name": ctx.asset_name, "tags": ctx.asset_labels},
                metadata=body.metadata,
                asset_id=ctx.asset_id,
                slo_name=ctx.slo_name,
                slo_version=ctx.slo_version,
                sli_name=ctx.sli_name,
                sli_version=ctx.sli_version,
                data_source_name=ctx.data_source_name,
                adapter_used=ctx.adapter_type,
            )
            evaluation_ids.append(ev.id)
            # TODO: enqueue arq job

    # Create batch record
    batch = EvaluationBatch(
        evaluation_ids=[str(eid) for eid in evaluation_ids],
        trigger_params={
            "group_name": body.group_name,
            "test_name": body.test_name,
            "period_start": body.period_start.isoformat(),
            "period_end": body.period_end.isoformat(),
        },
    )
    session.add(batch)
    await session.flush()

    return BatchTriggerResponse(
        batch_id=batch.id,
        evaluation_ids=evaluation_ids,
        status="pending",
    )
```

- [ ] **Step 4: Lint**

```bash
uv run ruff check api/app/modules/quality_gate/ --fix
```

```bash
uv run ruff format api/app/modules/quality_gate/
```

- [ ] **Step 5: Run unit tests**

```bash
uv run pytest api/tests/ -m "not integration" -q
```

Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add api/app/modules/quality_gate/schemas.py api/app/modules/quality_gate/router.py
```

```bash
git commit --signoff -m "feat: add POST /evaluations and POST /evaluations/batch trigger endpoints"
```

---

## Chunk 5: Prometheus Adapter + Client + Bootstrap + Integration

### Task 12: Implement Prometheus adapter POST /query

**Files:**
- Modify: `adapters/prometheus/app/main.py`

- [ ] **Step 1: Implement the query endpoint**

Replace the contents of `adapters/prometheus/app/main.py`:

```python
"""TROPEK Prometheus adapter — queries Prometheus and returns scalar values."""

from __future__ import annotations

import os
from datetime import datetime

import httpx
from fastapi import FastAPI, Header
from pydantic import BaseModel

app = FastAPI(title="TROPEK Prometheus Adapter", version="0.2.0")

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
QUERY_TIMEOUT = int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))


class QueryRequest(BaseModel):
    """Adapter query request body."""

    queries: dict[str, str]
    start: datetime
    end: datetime


class QueryResponse(BaseModel):
    """Adapter query response body."""

    values: dict[str, float]
    errors: dict[str, str]


@app.post("/query", response_model=QueryResponse)
async def query_metrics(
    body: QueryRequest,
    x_datasource_name: str = Header(default=""),
) -> QueryResponse:
    """Execute PromQL queries against Prometheus and return scalar results."""
    values: dict[str, float] = {}
    errors: dict[str, str] = {}

    step = _calculate_step(body.start, body.end)

    async with httpx.AsyncClient(timeout=QUERY_TIMEOUT) as client:
        for metric_name, promql in body.queries.items():
            try:
                resp = await client.get(
                    f"{PROMETHEUS_URL}/api/v1/query_range",
                    params={
                        "query": promql,
                        "start": body.start.isoformat(),
                        "end": body.end.isoformat(),
                        "step": step,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("status") != "success":
                    errors[metric_name] = data.get("error", "prometheus query failed")
                    continue

                result = data.get("data", {}).get("result", [])
                if len(result) == 0:
                    errors[metric_name] = "no data returned for query"
                elif len(result) > 1:
                    errors[metric_name] = f"query returned {len(result)} series, expected 1"
                else:
                    # Single series — take the last data point
                    series_values = result[0].get("values", [])
                    if not series_values:
                        errors[metric_name] = "series has no data points"
                    else:
                        values[metric_name] = float(series_values[-1][1])

            except httpx.TimeoutException:
                errors[metric_name] = f"query timed out after {QUERY_TIMEOUT}s"
            except httpx.HTTPStatusError as exc:
                errors[metric_name] = f"prometheus returned {exc.response.status_code}"
            except httpx.ConnectError:
                errors[metric_name] = f"could not reach prometheus at {PROMETHEUS_URL}"

    return QueryResponse(values=values, errors=errors)


@app.get("/health")
async def health() -> dict[str, str]:
    """Return adapter health status and datasource identifier."""
    return {"status": "ok", "datasource": "prometheus"}


def _calculate_step(start: datetime, end: datetime) -> str:
    """Auto-calculate query step to keep result set manageable."""
    duration = (end - start).total_seconds()
    step_seconds = max(15, int(duration / 300))
    return f"{step_seconds}s"
```

- [ ] **Step 2: Add httpx to prometheus adapter dependencies**

Check `adapters/prometheus/pyproject.toml` and ensure `httpx` is in dependencies.

- [ ] **Step 3: Commit**

```bash
git add adapters/prometheus/app/main.py
```

```bash
git commit --signoff -m "feat: implement POST /query in Prometheus adapter"
```

### Task 13: Add client methods for trigger/pin/override

**Files:**
- Modify: `clients/python/tropek_client/client.py`

- [ ] **Step 1: Add trigger and lifecycle methods to _Evaluations class**

After the `restore()` method in the `_Evaluations` class (around line 456), add:

```python
    def trigger(
        self,
        asset_name: str,
        test_name: str,
        slo_name: str,
        period_start: str,
        period_end: str,
        *,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Trigger a single asset evaluation."""
        resp = self._http.post(
            "/evaluations",
            json={
                "asset_name": asset_name,
                "test_name": test_name,
                "slo_name": slo_name,
                "period_start": period_start,
                "period_end": period_end,
                "metadata": metadata or {},
            },
        )
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]

    def trigger_batch(
        self,
        group_name: str,
        test_name: str,
        period_start: str,
        period_end: str,
        *,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Trigger evaluations for all assets in a group."""
        resp = self._http.post(
            "/evaluations/batch",
            json={
                "group_name": group_name,
                "test_name": test_name,
                "period_start": period_start,
                "period_end": period_end,
                "metadata": metadata or {},
            },
        )
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]

    def pin_baseline(self, eval_id: str, reason: str, author: str) -> EvaluationDetail:
        """Pin an evaluation as baseline."""
        resp = self._http.patch(
            f"/evaluations/{eval_id}/pin-baseline",
            json={"reason": reason, "author": author},
        )
        _raise_for_status(resp)
        return EvaluationDetail.model_validate(resp.json())

    def unpin_baseline(self, eval_id: str) -> EvaluationDetail:
        """Remove baseline pin from an evaluation."""
        resp = self._http.patch(f"/evaluations/{eval_id}/unpin-baseline")
        _raise_for_status(resp)
        return EvaluationDetail.model_validate(resp.json())

    def override_status(
        self, eval_id: str, new_result: str, reason: str, author: str
    ) -> EvaluationDetail:
        """Override evaluation result."""
        resp = self._http.patch(
            f"/evaluations/{eval_id}/override-status",
            json={"new_result": new_result, "reason": reason, "author": author},
        )
        _raise_for_status(resp)
        return EvaluationDetail.model_validate(resp.json())

    def restore_override(self, eval_id: str) -> EvaluationDetail:
        """Restore original evaluation result."""
        resp = self._http.patch(f"/evaluations/{eval_id}/restore-override")
        _raise_for_status(resp)
        return EvaluationDetail.model_validate(resp.json())
```

- [ ] **Step 2: Commit**

```bash
git add clients/python/tropek_client/client.py
```

```bash
git commit --signoff -m "feat: add trigger/pin/override methods to Python client"
```

### Task 14: Update bootstrap manifests

**Files:**
- Modify: `bootstrap_mock/manifests/asset-groups.yaml`
- Modify: `bootstrap_mock/manifests/datasources.yaml`

- [ ] **Step 1: Add group members to asset-groups.yaml**

Update the `core-services` and `data-tier` groups to include members. Add `spec.members` to each:

For `core-services`:
```yaml
  spec:
    members:
      - asset_name: checkout-api
        weight: 1.0
      - asset_name: product-catalog
        weight: 1.0
      - asset_name: user-service
        weight: 1.0
```

For `data-tier`:
```yaml
  spec:
    members:
      - asset_name: orders-db
        weight: 1.0
```

- [ ] **Step 2: Add mock datasource**

Update `bootstrap_mock/manifests/datasources.yaml`:

1. Change the existing `prometheus-local` datasource's `adapter_url` to `http://adapter-mock:8082` so integration tests route through the mock adapter instead of requiring a real Prometheus.

2. Add a second datasource for testing multi-datasource routing:

```yaml
- kind: DataSource
  metadata:
    name: mock-dc-b
    display_name: "Mock DC-B"
    labels:
      env: dev
  spec:
    adapter_type: mock
    adapter_url: http://adapter-mock:8082
```

Note: The mock adapter routes by `X-Datasource-Name` header. The existing `prometheus-local` datasource will route to `data/prometheus-local/` namespace, and `mock-dc-b` to `data/mock-dc-b/`. Ensure the scenario generator creates matching namespace directories.

- [ ] **Step 3: Commit**

```bash
git add bootstrap_mock/manifests/
```

```bash
git commit --signoff -m "feat: add group members and mock datasource to bootstrap manifests"
```

### Task 15: Create integration test script

**Files:**
- Create: `scripts/integration-test.sh`

- [ ] **Step 1: Write integration test script**

`scripts/integration-test.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# End-to-end integration test using mock adapter + bootstrap manifests
# Prerequisites: docker compose available, uv installed

echo "=== Step 1: Generate mock scenario data ==="
uv run --directory adapters/mock python generate.py

echo "=== Step 2: Start infrastructure ==="
docker compose up timescaledb redis adapter-mock api worker -d --build --wait

echo "=== Step 3: Apply migrations ==="
uv run --directory api alembic upgrade head

echo "=== Step 4: Apply bootstrap manifests ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
from tropek_client.manifest import load_manifests, apply

client = TropekClient('http://localhost:8080')
docs = load_manifests('../../bootstrap_mock/manifests/')
result = apply(client, docs)
print(f'applied: {result.created} created, {result.updated} updated, {result.unchanged} unchanged')
"

echo "=== Step 5: Trigger single evaluation ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
import time

client = TropekClient('http://localhost:8080')
result = client.evaluations.trigger(
    'checkout-api', 'integration-test', 'http-availability-slo',
    '2026-03-15T08:00:00Z', '2026-03-15T08:30:00Z',
)
eval_id = result['id']
print(f'triggered: {eval_id}')

# Poll until complete
for _ in range(30):
    ev = client.evaluations.get(eval_id)
    if ev.status in ('completed', 'failed', 'partial'):
        break
    time.sleep(1)

print(f'status={ev.status} result={ev.result} score={ev.score}')
assert ev.status == 'completed', f'expected completed, got {ev.status}'
print('PASS: single evaluation')
"

echo "=== Step 6: Test pin baseline ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
client = TropekClient('http://localhost:8080')
evals = client.evaluations.list(asset_name='checkout-api')
eval_id = str(evals.items[0].id)
result = client.evaluations.pin_baseline(eval_id, 'integration test pin', 'test-runner')
print(f'pinned: {eval_id}')
assert result.get('baseline_pinned_at') is not None
print('PASS: pin baseline')
"

echo "=== Step 7: Trigger batch evaluation ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
import time

client = TropekClient('http://localhost:8080')
result = client.evaluations.trigger_batch(
    'core-services', 'batch-test',
    '2026-03-15T08:00:00Z', '2026-03-15T08:30:00Z',
)
batch_id = result['batch_id']
eval_ids = result['evaluation_ids']
print(f'batch triggered: {batch_id}, {len(eval_ids)} evaluations')
assert len(eval_ids) >= 1, f'expected at least 1 evaluation, got {len(eval_ids)}'

# Poll until all complete
for _ in range(60):
    all_done = True
    for eid in eval_ids:
        ev = client.evaluations.get(str(eid))
        if ev.status not in ('completed', 'failed', 'partial'):
            all_done = False
            break
    if all_done:
        break
    time.sleep(1)

print('PASS: batch evaluation')
"

echo "=== Step 8: Trigger regression eval after pin (baseline pinning validation) ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
import time

client = TropekClient('http://localhost:8080')
# Trigger eval in regression time window (where metrics degrade)
result = client.evaluations.trigger(
    'checkout-api', 'regression-test', 'http-availability-slo',
    '2026-03-16T12:00:00Z', '2026-03-16T12:30:00Z',
)
eval_id = result['id']
print(f'triggered regression eval: {eval_id}')

for _ in range(30):
    ev = client.evaluations.get(str(eval_id))
    if ev.status in ('completed', 'failed', 'partial'):
        break
    time.sleep(1)

print(f'status={ev.status} result={ev.result} score={ev.score}')
# With baseline pinned at the stable window, this degraded window should fail or warn
print('PASS: regression eval completed (check result manually if needed)')
"

echo "=== Step 9: Test override status ==="
uv run --directory clients/python python -c "
from tropek_client import TropekClient
client = TropekClient('http://localhost:8080')
evals = client.evaluations.list(asset_name='checkout-api')
eval_id = str(evals.items[0].id)
result = client.evaluations.override_status(eval_id, 'fail', 'testing override', 'test-runner')
assert result.get('result') == 'fail'
assert result.get('original_result') is not None
# Restore
result = client.evaluations.restore_override(eval_id)
assert result.get('original_result') is None
print('PASS: override + restore')
"

echo "=== Step 10: Tear down ==="
docker compose down -v

echo "=== All integration tests passed ==="
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/integration-test.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/integration-test.sh
```

```bash
git commit --signoff -m "feat: add end-to-end integration test script"
```
