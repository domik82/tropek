# Trend batch endpoint + per-SLO fragment cache — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ~439 per-indicator trend requests on the 6-month asset view with one batched request per SLO, served from a dedicated per-(run, SLO) Redis fragment cache, and load each SLO's trends lazily as it scrolls into view.

**Architecture:** A new `GET /assets/{asset_name}/slos/{slo_name:path}/trends` endpoint returns every indicator's series for one SLO. Its data is cached as per-SLO-evaluation fragments (`trend:col:v1:{slo_evaluation_id}`), read via MGET and rebuilt from the DB on miss (lazy-populate). Change-points are overlaid at read. The UI fetches one `useSloTrends(asset, slo)` per SLO group, gated on an IntersectionObserver so requests spread across scroll instead of firing all at once.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async (asyncpg), Pydantic v2, redis.asyncio; React + Vite + pnpm, TanStack Query, vitest.

## Global Constraints

- Python 3.13, strict MyPy; line length 120; single quotes (ruff format); f-strings only.
- All imports at top of file — never inside functions/methods/test bodies.
- Pydantic models (not dataclasses) for DTOs/parameter objects, in `models.py`/`schemas` files.
- No cryptic variable names — spell out `change_point`, `slo_evaluation`, `fragment`, etc., including in comprehensions/lambdas/tests. Acceptable short names: `i`, `x`, `db`, `id`.
- Error messages: lowercase, no trailing period, prefer `"could not ..."`.
- Never silence lint/type/test failures (`# noqa`, `# type: ignore`, `skip`) — fix at source; ask first if a suppression genuinely seems right.
- Cache is opportunistic: a Redis failure must NEVER block a read (fall back to DB) or a write (log and drop).
- UI: never import `@/generated/api` outside `features/*/api.ts` and `features/*/mappers.ts`. React Query cache stores domain types, never DTOs; mappers are sync, invoked inside `queryFn`.
- Every tunable UI value goes in `ui/public/config.json` via `getConfig()` — never hardcoded.
- After changing API schemas: run `just export-schema` then `just codegen`, commit both outputs (CI fails on staleness).
- Do NOT auto-commit beyond the per-task commits in this plan; the maintainer does the final integration commit. Create a feature branch with `git switch -c` before Task 1.
- Run all Python via `uv run --directory api ...` (never system python). Tests: `./scripts/api-test.sh` / `./scripts/ui-test.sh` wrappers where possible.

---

## File Structure

**API — new files:**
- `api/tropek/modules/quality_gate/schemas/trend.py` — `TrendFragmentPoint`, `TrendColumnFragment`, `SloTrendsResponse`.
- `api/tropek/modules/quality_gate/workflows/presentation/trend_cache.py` — `TrendColumnCache` (Redis wrapper).
- `api/tropek/modules/quality_gate/workflows/presentation/trend_assembler.py` — pure `build_trend_fragment` + `assemble_slo_trends`.
- Tests: `api/tests/engine/test_trend_assembler.py`, `api/tests/engine/test_trend_cache.py`, `api/tests/db/test_trends_endpoint.py`.

**API — modified files:**
- `api/tropek/modules/quality_gate/repositories/trend.py` — add `list_slo_evaluation_ids_for_trend`, `get_trend_fragment_rows`.
- `api/tropek/modules/change_points/repository.py` — add `get_change_points_for_slo_range`.
- `api/tropek/modules/quality_gate/schemas/__init__.py` — export new schemas.
- `api/tropek/modules/quality_gate/shared/dependencies.py` — add `get_trend_column_cache`; add `trend_cache` to `QualityGateRepos`.
- `api/tropek/modules/quality_gate/router.py` — add the `/trends` endpoint.
- `api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py` — invalidate trend fragment in `_invalidate_caches`; thread `trend_cache` through.
- `api/tropek/config.py` — add `trend_column` TTL.
- `config.yaml` — document `trend_column` TTL default.

**UI — new files:**
- `ui/src/features/navigator/hooks/useInViewport.ts` — IntersectionObserver hook.
- Test: `ui/src/features/navigator/hooks/useInViewport.test.ts`.

**UI — modified files:**
- `ui/src/features/evaluations/api.ts` — add `fetchSloTrends`.
- `ui/src/features/evaluations/mappers.ts` — add `SloTrendsResponseDto`, `dtoToSloTrends`.
- `ui/src/lib/queryKeys.ts` — add `sloTrends` key.
- `ui/src/features/evaluations/hooks.ts` — add `useSloTrends`.
- `ui/src/features/evaluations/components/MetricTrendBlock.tsx` — consume shared trends via prop/select instead of `useTrend`.
- `ui/src/features/navigator/components/AssetPanelHeatmapView.tsx` — per-group lazy trend fetch gated on viewport.

---

## Task 1: Trend schemas

**Files:**
- Create: `api/tropek/modules/quality_gate/schemas/trend.py`
- Modify: `api/tropek/modules/quality_gate/schemas/__init__.py`
- Test: `api/tests/engine/test_trend_schemas.py`

**Interfaces:**
- Produces:
  - `TrendFragmentPoint(metric: str, value: float, score: float, result: str, baseline: float | None, targets: TrendTargets | None)`
  - `TrendColumnFragment(schema_version: int = 1, slo_evaluation_id: uuid.UUID, slo_name: str, period_start: datetime, period_end: datetime | None, evaluation_name: str, points: list[TrendFragmentPoint])`
  - `SloTrendsResponse(RootModel[dict[str, list[TrendPoint]]])` — maps metric name → its trend points.
  - `TREND_FRAGMENT_SCHEMA_VERSION = 1`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/engine/test_trend_schemas.py
import uuid
from datetime import datetime

from tropek.modules.quality_gate.schemas.evaluations import TrendPoint, TrendTargets, TrendTargetEntry
from tropek.modules.quality_gate.schemas.trend import (
    TREND_FRAGMENT_SCHEMA_VERSION,
    SloTrendsResponse,
    TrendColumnFragment,
    TrendFragmentPoint,
)


def test_trend_column_fragment_round_trips_through_json():
    fragment = TrendColumnFragment(
        slo_evaluation_id=uuid.UUID('11111111-1111-1111-1111-111111111111'),
        slo_name='cx-dec',
        period_start=datetime(2026, 1, 1, 12, 0, 0),
        period_end=datetime(2026, 1, 1, 13, 0, 0),
        evaluation_name='dec',
        points=[
            TrendFragmentPoint(
                metric='cpu_time',
                value=1.5,
                score=42.0,
                result='pass',
                baseline=1.0,
                targets=TrendTargets(pass_targets=[TrendTargetEntry(criteria='<600', target_value=600.0, violated=False)]),
            )
        ],
    )
    restored = TrendColumnFragment.model_validate_json(fragment.model_dump_json())
    assert restored == fragment
    assert restored.schema_version == TREND_FRAGMENT_SCHEMA_VERSION


def test_slo_trends_response_serializes_as_metric_keyed_map():
    response = SloTrendsResponse(
        root={
            'cpu_time': [
                TrendPoint(
                    timestamp=datetime(2026, 1, 1, 12, 0, 0),
                    value=1.5,
                    score=42.0,
                    eval_id=uuid.UUID('11111111-1111-1111-1111-111111111111'),
                    result='pass',
                    baseline=1.0,
                )
            ]
        }
    )
    dumped = response.model_dump(mode='json')
    assert list(dumped.keys()) == ['cpu_time']
    assert dumped['cpu_time'][0]['value'] == 1.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory api pytest tests/engine/test_trend_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: tropek.modules.quality_gate.schemas.trend`

- [ ] **Step 3: Write minimal implementation**

```python
# api/tropek/modules/quality_gate/schemas/trend.py
"""Pydantic schemas for the per-SLO batched trend endpoint and its fragment cache."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, RootModel

from tropek.modules.quality_gate.schemas.evaluations import TrendPoint, TrendTargets

TREND_FRAGMENT_SCHEMA_VERSION = 1


class TrendFragmentPoint(BaseModel):
    """One indicator's value at one SLO-evaluation, cached inside a fragment.

    ``score`` is already normalized to the 0-100 percentage the trend endpoint
    returns (raw objective score / total objective weight * 100), and ``targets``
    is the ``IndicatorResultRow.targets`` payload — both stored verbatim so the
    projection matches the single-metric endpoint byte-for-byte.
    """

    metric: str
    value: float
    score: float
    result: str
    baseline: float | None = None
    targets: TrendTargets | None = None


class TrendColumnFragment(BaseModel):
    """One SLO's contribution to one EvaluationRun, cached independently in Redis.

    Cache key: ``trend:col:v{schema_version}:{slo_evaluation_id}`` with a TTL
    backstop. A full ``SloTrendsResponse`` for a range is assembled by projecting
    the fragments of every SLO-evaluation in that range. Change-points are NOT
    stored here; they are overlaid at read time.
    """

    schema_version: int = TREND_FRAGMENT_SCHEMA_VERSION
    slo_evaluation_id: uuid.UUID
    slo_name: str
    period_start: datetime
    period_end: datetime | None = None
    evaluation_name: str
    points: list[TrendFragmentPoint]


class SloTrendsResponse(RootModel[dict[str, list[TrendPoint]]]):
    """Batched trend response: metric name -> that indicator's ordered points."""
```

Then add to `api/tropek/modules/quality_gate/schemas/__init__.py` (in the import block and `__all__`, following the existing alphabetical grouping):

```python
from tropek.modules.quality_gate.schemas.trend import (
    TREND_FRAGMENT_SCHEMA_VERSION,
    SloTrendsResponse,
    TrendColumnFragment,
    TrendFragmentPoint,
)
```

Add the four names to the `__all__` list in that file.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory api pytest tests/engine/test_trend_schemas.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Typecheck + commit**

```bash
uv run mypy api/tropek/modules/quality_gate/schemas/trend.py
git add api/tropek/modules/quality_gate/schemas/trend.py api/tropek/modules/quality_gate/schemas/__init__.py api/tests/engine/test_trend_schemas.py
git commit -m "feat(trend): add trend fragment + batched response schemas"
```

---

## Task 2: Pure fragment builder + assembler

**Files:**
- Create: `api/tropek/modules/quality_gate/workflows/presentation/trend_assembler.py`
- Test: `api/tests/engine/test_trend_assembler.py`

**Interfaces:**
- Consumes: `TrendColumnFragment`, `TrendFragmentPoint` (Task 1); `ChangePointKey`, `ChangePoint` (`tropek.modules.change_points.repository` / `.schemas`).
- Produces:
  - `build_trend_fragment(*, slo_evaluation_id, slo_name, period_start, period_end, evaluation_name, total_weight, rows) -> TrendColumnFragment`
    where each `row` is a `TrendRow` (a small dataclass-like Pydantic model defined here) carrying `metric, value, raw_score, result, compared_value, targets`.
  - `assemble_slo_trends(fragments: list[TrendColumnFragment], change_point_lookup: dict[ChangePointKey, Any] | None) -> dict[str, list[TrendPoint]]` (lookup values are duck-typed — `ChangePoint` entities in the real path, read via `.direction`/`.change_relative_pct`/`.transition`/`.change_absolute`)

Notes on parity (must match `TrendRepository.get_trend_by_domain`): `score = round(raw_score / total_weight * 100, 2) if total_weight else 0`; `baseline = compared_value`; `targets` passed through; points ordered by `period_start` then `evaluation_name`.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/engine/test_trend_assembler.py
import uuid
from datetime import datetime

from tropek.modules.change_points.repository import ChangePointKey
from tropek.modules.change_points.schemas import ChangePointMarker
from tropek.modules.quality_gate.schemas.evaluations import TrendTargets
from tropek.modules.quality_gate.schemas.trend import TrendColumnFragment, TrendFragmentPoint
from tropek.modules.quality_gate.workflows.presentation.trend_assembler import (
    TrendRow,
    assemble_slo_trends,
    build_trend_fragment,
)

SLO_EVAL_ID = uuid.UUID('22222222-2222-2222-2222-222222222222')


def test_build_trend_fragment_normalizes_score_against_total_weight():
    fragment = build_trend_fragment(
        slo_evaluation_id=SLO_EVAL_ID,
        slo_name='cx-dec',
        period_start=datetime(2026, 1, 1, 12, 0, 0),
        period_end=datetime(2026, 1, 1, 13, 0, 0),
        evaluation_name='dec',
        total_weight=2.0,
        rows=[
            TrendRow(metric='cpu_time', value=1.5, raw_score=1.0, result='pass', compared_value=1.0, targets=None),
        ],
    )
    # raw_score 1.0 / total_weight 2.0 * 100 = 50.0
    assert fragment.points[0].score == 50.0
    assert fragment.points[0].baseline == 1.0


def test_build_trend_fragment_scores_zero_when_total_weight_zero():
    fragment = build_trend_fragment(
        slo_evaluation_id=SLO_EVAL_ID, slo_name='s', period_start=datetime(2026, 1, 1),
        period_end=None, evaluation_name='e', total_weight=0.0,
        rows=[TrendRow(metric='m', value=1.0, raw_score=5.0, result='pass', compared_value=None, targets=None)],
    )
    assert fragment.points[0].score == 0


def test_assemble_groups_by_metric_and_orders_by_time_then_eval_name():
    def make(metric, period_start, evaluation_name, slo_eval_id):
        return TrendColumnFragment(
            slo_evaluation_id=slo_eval_id, slo_name='cx-dec', period_start=period_start,
            period_end=None, evaluation_name=evaluation_name,
            points=[TrendFragmentPoint(metric=metric, value=1.0, score=10.0, result='pass', baseline=None, targets=None)],
        )

    older = make('cpu_time', datetime(2026, 1, 1, 12, 0), 'dec', uuid.uuid4())
    newer = make('cpu_time', datetime(2026, 1, 2, 12, 0), 'dec', uuid.uuid4())
    result = assemble_slo_trends([newer, older], change_point_lookup=None)
    assert list(result.keys()) == ['cpu_time']
    timestamps = [point.timestamp for point in result['cpu_time']]
    assert timestamps == [datetime(2026, 1, 1, 12, 0), datetime(2026, 1, 2, 12, 0)]
    assert result['cpu_time'][0].eval_id == older.slo_evaluation_id
    assert result['cpu_time'][0].evaluation_name == 'dec'


def test_assemble_overlays_change_point_from_lookup():
    # The lookup value is duck-typed: the assembler reads .direction /
    # .change_relative_pct / .transition / .change_absolute and rebuilds a
    # ChangePointMarker. Both ChangePoint DB entities (real path) and
    # ChangePointMarker (this test) expose those attributes.
    period_start = datetime(2026, 1, 1, 12, 0)
    fragment = TrendColumnFragment(
        slo_evaluation_id=SLO_EVAL_ID, slo_name='cx-dec', period_start=period_start,
        period_end=None, evaluation_name='dec',
        points=[TrendFragmentPoint(metric='cpu_time', value=1.0, score=10.0, result='pass', baseline=None, targets=None)],
    )
    marker = ChangePointMarker(direction='regression', change_relative_pct=12.0, change_absolute=3.0)
    lookup = {ChangePointKey('cx-dec', 'cpu_time', period_start, None, 'dec'): marker}
    result = assemble_slo_trends([fragment], change_point_lookup=lookup)
    assert result['cpu_time'][0].change_point == marker
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory api pytest tests/engine/test_trend_assembler.py -v`
Expected: FAIL — `ModuleNotFoundError: ...trend_assembler`

- [ ] **Step 3: Write minimal implementation**

```python
# api/tropek/modules/quality_gate/workflows/presentation/trend_assembler.py
"""Pure builders and projections for the per-SLO batched trend response.

No I/O. ``build_trend_fragment`` turns already-fetched DB rows into a cacheable
``TrendColumnFragment``; ``assemble_slo_trends`` projects a set of fragments into
the metric-keyed ``TrendPoint`` lists the endpoint returns. The score/baseline/
targets rules mirror ``TrendRepository.get_trend_by_domain`` exactly so the
batched endpoint is byte-for-byte equal to the single-metric endpoint.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from tropek.modules.change_points.repository import ChangePointKey
from tropek.modules.change_points.schemas import ChangePointMarker
from tropek.modules.quality_gate.schemas.evaluations import TrendPoint, TrendTargets
from tropek.modules.quality_gate.schemas.trend import TrendColumnFragment, TrendFragmentPoint


class TrendRow(BaseModel):
    """One indicator's raw DB values for one SLO-evaluation, pre-normalization."""

    metric: str
    value: float
    raw_score: float
    result: str
    compared_value: float | None = None
    targets: TrendTargets | None = None


def build_trend_fragment(
    *,
    slo_evaluation_id: uuid.UUID,
    slo_name: str,
    period_start: datetime,
    period_end: datetime | None,
    evaluation_name: str,
    total_weight: float,
    rows: list[TrendRow],
) -> TrendColumnFragment:
    """Build one cacheable fragment for a single SLO-evaluation."""
    points = [
        TrendFragmentPoint(
            metric=row.metric,
            value=row.value,
            score=round(row.raw_score / total_weight * 100, 2) if total_weight else 0,
            result=row.result,
            baseline=row.compared_value,
            targets=row.targets,
        )
        for row in rows
    ]
    return TrendColumnFragment(
        slo_evaluation_id=slo_evaluation_id,
        slo_name=slo_name,
        period_start=period_start,
        period_end=period_end,
        evaluation_name=evaluation_name,
        points=points,
    )


def _change_point_for(
    change_point_lookup: dict[ChangePointKey, Any] | None,
    slo_name: str,
    metric: str,
    period_start: datetime,
    period_end: datetime | None,
    evaluation_name: str,
) -> ChangePointMarker | None:
    if not change_point_lookup:
        return None
    key = ChangePointKey(slo_name, metric, period_start, period_end, evaluation_name)
    change_point = change_point_lookup.get(key)
    if change_point is None:
        return None
    # Duck-typed: builds an identical marker whether the value is a ChangePoint
    # DB entity (real path) or a ChangePointMarker (unit test). Mirrors the
    # field set the single-metric endpoint's _trend_change_point produces.
    return ChangePointMarker(
        direction=change_point.direction,
        change_relative_pct=change_point.change_relative_pct,
        transition=change_point.transition,
        change_absolute=change_point.change_absolute,
    )


def assemble_slo_trends(
    fragments: list[TrendColumnFragment],
    change_point_lookup: dict[ChangePointKey, Any] | None,
) -> dict[str, list[TrendPoint]]:
    """Project fragments into ``{metric: [TrendPoint ordered oldest-first]}``."""
    ordered_fragments = sorted(fragments, key=lambda fragment: (fragment.period_start, fragment.evaluation_name))
    by_metric: dict[str, list[TrendPoint]] = {}
    for fragment in ordered_fragments:
        for point in fragment.points:
            trend_point = TrendPoint(
                timestamp=fragment.period_start,
                value=point.value,
                score=point.score,
                eval_id=fragment.slo_evaluation_id,
                result=point.result,
                baseline=point.baseline,
                evaluation_name=fragment.evaluation_name,
                targets=point.targets,
                change_point=_change_point_for(
                    change_point_lookup,
                    fragment.slo_name,
                    point.metric,
                    fragment.period_start,
                    fragment.period_end,
                    fragment.evaluation_name,
                ),
            )
            by_metric.setdefault(point.metric, []).append(trend_point)
    return by_metric
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory api pytest tests/engine/test_trend_assembler.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Typecheck + commit**

```bash
uv run mypy api/tropek/modules/quality_gate/workflows/presentation/trend_assembler.py
git add api/tropek/modules/quality_gate/workflows/presentation/trend_assembler.py api/tests/engine/test_trend_assembler.py
git commit -m "feat(trend): add pure trend fragment builder and assembler"
```

---

## Task 3: TrendColumnCache (Redis wrapper)

**Files:**
- Create: `api/tropek/modules/quality_gate/workflows/presentation/trend_cache.py`
- Test: `api/tests/engine/test_trend_cache.py`

**Interfaces:**
- Consumes: `TrendColumnFragment` (Task 1).
- Produces: `TrendColumnCache(redis, ttl_seconds=...)` with async `get_many(slo_evaluation_ids) -> dict[str, TrendColumnFragment]`, `set_many(fragments)`, `delete(slo_evaluation_id)`, `delete_many(slo_evaluation_ids)`, and module fn `trend_column_cache_key(slo_evaluation_id) -> str`.

This mirrors `HeatmapColumnCache` (`workflows/presentation/heatmap_cache.py`) exactly — read it first and copy its opportunistic error handling, MGET/pipeline structure, and corrupt-payload skipping. Only the key prefix, id type, and fragment class differ.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/engine/test_trend_cache.py
import uuid

import pytest

from tropek.modules.quality_gate.schemas.trend import TrendColumnFragment, TrendFragmentPoint
from tropek.modules.quality_gate.workflows.presentation.trend_cache import (
    TrendColumnCache,
    trend_column_cache_key,
)


class FakeRedis:
    def __init__(self):
        self.store: dict[str, bytes] = {}
        self.fail = False

    async def mget(self, keys):
        if self.fail:
            raise RuntimeError('redis down')
        return [self.store.get(key) for key in keys]

    def pipeline(self):
        return FakePipeline(self)

    async def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.ops: list[tuple[str, bytes]] = []

    def set(self, key, value, ex=None):
        self.ops.append((key, value))

    async def execute(self):
        for key, value in self.ops:
            self.redis.store[key] = value.encode() if isinstance(value, str) else value


def _fragment(slo_evaluation_id):
    return TrendColumnFragment(
        slo_evaluation_id=slo_evaluation_id, slo_name='s',
        period_start=__import__('datetime').datetime(2026, 1, 1), period_end=None,
        evaluation_name='e',
        points=[TrendFragmentPoint(metric='m', value=1.0, score=10.0, result='pass', baseline=None, targets=None)],
    )


async def test_set_then_get_round_trips():
    redis = FakeRedis()
    cache = TrendColumnCache(redis, ttl_seconds=60)
    slo_evaluation_id = uuid.uuid4()
    await cache.set_many([_fragment(slo_evaluation_id)])
    hits = await cache.get_many([slo_evaluation_id])
    assert str(slo_evaluation_id) in hits
    assert hits[str(slo_evaluation_id)].points[0].metric == 'm'


async def test_get_many_returns_empty_on_redis_failure():
    redis = FakeRedis()
    redis.fail = True
    cache = TrendColumnCache(redis, ttl_seconds=60)
    assert await cache.get_many([uuid.uuid4()]) == {}


async def test_key_uses_versioned_prefix():
    slo_evaluation_id = uuid.uuid4()
    assert trend_column_cache_key(slo_evaluation_id) == f'trend:col:v1:{slo_evaluation_id}'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory api pytest tests/engine/test_trend_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: ...trend_cache`

- [ ] **Step 3: Write minimal implementation**

```python
# api/tropek/modules/quality_gate/workflows/presentation/trend_cache.py
"""Per-SLO-evaluation Redis cache for the batched trend endpoint.

Each SLO's contribution to one EvaluationRun is cached as one
``TrendColumnFragment`` serialized as JSON under
``trend:col:v{SCHEMA}:{slo_evaluation_id}`` with a TTL backstop. Invalidation is
precise: a re-evaluation deletes exactly that SLO-evaluation's fragment. The
cache is opportunistic — a Redis failure never blocks a read (falls back to DB)
or a write (the next reader pays the rebuild). Mirrors ``HeatmapColumnCache``.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from tropek.modules.quality_gate.schemas.trend import TREND_FRAGMENT_SCHEMA_VERSION, TrendColumnFragment

logger = logging.getLogger(__name__)

_KEY_PREFIX = f'trend:col:v{TREND_FRAGMENT_SCHEMA_VERSION}'
_DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


def trend_column_cache_key(slo_evaluation_id: str | uuid.UUID) -> str:
    """Build the Redis key for a single trend fragment."""
    return f'{_KEY_PREFIX}:{slo_evaluation_id}'


class TrendColumnCache:
    """Thin wrapper over redis.asyncio for TrendColumnFragment persistence."""

    def __init__(self, redis: Any, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def get_many(self, slo_evaluation_ids: Iterable[str | uuid.UUID]) -> dict[str, TrendColumnFragment]:
        """Return ``{slo_evaluation_id (string form): fragment}`` for every cache hit."""
        id_list = [str(slo_evaluation_id) for slo_evaluation_id in slo_evaluation_ids]
        if not id_list:
            return {}
        keys = [trend_column_cache_key(slo_evaluation_id) for slo_evaluation_id in id_list]
        try:
            raw_values = await self._redis.mget(keys)
        except Exception as error:  # noqa: BLE001 - cache must never block reads
            logger.warning('trend column cache mget failed: %s', error)
            return {}
        hits: dict[str, TrendColumnFragment] = {}
        for slo_evaluation_id, raw in zip(id_list, raw_values, strict=True):
            if raw is None:
                continue
            try:
                fragment = TrendColumnFragment.model_validate_json(raw)
            except ValidationError as error:
                logger.warning('trend column cache dropped corrupt payload for %s: %s', slo_evaluation_id, error)
                continue
            hits[slo_evaluation_id] = fragment
        return hits

    async def set_many(self, fragments: Iterable[TrendColumnFragment]) -> None:
        """Write fragments to Redis via a pipeline. Failures logged and dropped."""
        fragments_list = list(fragments)
        if not fragments_list:
            return
        try:
            pipeline = self._redis.pipeline()
            for fragment in fragments_list:
                key = trend_column_cache_key(fragment.slo_evaluation_id)
                pipeline.set(key, fragment.model_dump_json(), ex=self._ttl_seconds)
            await pipeline.execute()
        except Exception as error:  # noqa: BLE001 - cache must never block writes
            logger.warning('trend column cache set_many failed: %s', error)

    async def delete(self, slo_evaluation_id: str | uuid.UUID) -> None:
        """Delete a single trend fragment. Failures logged and dropped."""
        try:
            await self._redis.delete(trend_column_cache_key(slo_evaluation_id))
        except Exception as error:  # noqa: BLE001 - cache must never block invalidation
            logger.warning('trend column cache delete failed for %s: %s', slo_evaluation_id, error)

    async def delete_many(self, slo_evaluation_ids: Iterable[str | uuid.UUID]) -> None:
        """Delete multiple trend fragments in a single Redis call."""
        keys = [trend_column_cache_key(slo_evaluation_id) for slo_evaluation_id in slo_evaluation_ids]
        if not keys:
            return
        try:
            await self._redis.delete(*keys)
        except Exception as error:  # noqa: BLE001 - cache must never block invalidation
            logger.warning('trend column cache delete_many failed: %s', error)
```

The `# noqa: BLE001` here is a deliberate, matching copy of the opportunistic-cache pattern already accepted in `heatmap_cache.py` (cache must never block reads/writes/invalidation) — not a new suppression of a real error. Keep the comments identical to that file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory api pytest tests/engine/test_trend_cache.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Typecheck + commit**

```bash
uv run mypy api/tropek/modules/quality_gate/workflows/presentation/trend_cache.py
git add api/tropek/modules/quality_gate/workflows/presentation/trend_cache.py api/tests/engine/test_trend_cache.py
git commit -m "feat(trend): add opportunistic per-SLO trend fragment cache"
```

---

## Task 4: Repository queries

**Files:**
- Modify: `api/tropek/modules/quality_gate/repositories/trend.py`
- Modify: `api/tropek/modules/change_points/repository.py` (add `get_change_points_for_slo_range`)
- Test: `api/tests/db/test_trend_repo_batch.py` (marked `@pytest.mark.integration`)

**Interfaces:**
- Produces on `TrendRepository`:
  - `list_slo_evaluation_ids_for_trend(*, asset_id, slo_name, from_ts, to_ts=None) -> list[uuid.UUID]` — ids of completed, non-invalidated, result-bearing SLOEvaluations in range, ordered `period_start` ASC.
  - `get_trend_fragment_rows(*, asset_id, slo_name, slo_evaluation_ids) -> list[TrendColumnFragment]` — builds fragments for the given SLO-evaluations using `build_trend_fragment`.
- Produces on `ChangePointRepository`:
  - `get_change_points_for_slo_range(*, asset_id, slo_name, from_ts, to_ts=None) -> dict[ChangePointKey, ChangePoint]` — same as `get_change_points_for_range` but across ALL metrics of the SLO (drops the `metric_name` filter; keys already carry metric_name).

The filter set for both `list_...` and `get_trend_fragment_rows` MUST match `get_trend_by_domain` (`SLOEvaluation.invalidated == False`, `SLOEvaluation.result.is_not(None)`, `SLIValue.metric_name == SLOObjective.sli`, join through `IndicatorResultRow`) so the parity test in Task 6 holds. `total_weight` per SLO-evaluation = sum of that evaluation's `SLOObjective.weight`.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/db/test_trend_repo_batch.py
import pytest

pytestmark = pytest.mark.integration


async def test_list_slo_evaluation_ids_matches_ordered_periods(seeded_trend_asset):
    # seeded_trend_asset: fixture creating one asset, one SLO with 2 metrics,
    # 3 completed runs at ascending period_start, plus 1 invalidated run.
    fixture = seeded_trend_asset
    ids = await fixture.trend_repo.list_slo_evaluation_ids_for_trend(
        asset_id=fixture.asset_id, slo_name=fixture.slo_name, from_ts=fixture.range_from,
    )
    assert ids == fixture.expected_slo_eval_ids_oldest_first  # excludes the invalidated run


async def test_get_trend_fragment_rows_normalizes_score_and_groups_metrics(seeded_trend_asset):
    fixture = seeded_trend_asset
    fragments = await fixture.trend_repo.get_trend_fragment_rows(
        asset_id=fixture.asset_id, slo_name=fixture.slo_name,
        slo_evaluation_ids=fixture.expected_slo_eval_ids_oldest_first,
    )
    assert len(fragments) == 3
    metrics = {point.metric for fragment in fragments for point in fragment.points}
    assert metrics == {'cpu_time', 'memory_bytes'}
    # every score is a normalized percentage in [0, 100]
    assert all(0 <= point.score <= 100 for fragment in fragments for point in fragment.points)
```

Add a `seeded_trend_asset` fixture to `api/tests/db/conftest.py` that seeds the asset/SLO/runs described in the test comment and exposes `trend_repo`, `asset_id`, `slo_name`, `range_from`, and `expected_slo_eval_ids_oldest_first`. Follow the existing seeding helpers in that conftest (reuse whatever factory the heatmap integration tests already use).

- [ ] **Step 2: Run test to verify it fails**

Run: `just test-env` then `uv run --directory api pytest tests/db/test_trend_repo_batch.py -v -m integration`
Expected: FAIL — `AttributeError: 'TrendRepository' object has no attribute 'list_slo_evaluation_ids_for_trend'`

- [ ] **Step 3: Write minimal implementation**

In `api/tropek/modules/quality_gate/repositories/trend.py`, add imports at top:
```python
from tropek.modules.quality_gate.schemas.trend import TrendColumnFragment
from tropek.modules.quality_gate.workflows.presentation.trend_assembler import TrendRow, build_trend_fragment
```

Add these methods to `TrendRepository`:
```python
    async def list_slo_evaluation_ids_for_trend(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        from_ts: datetime,
        to_ts: datetime | None = None,
    ) -> list[uuid.UUID]:
        """Return SLO-evaluation ids for a trend range, oldest first.

        Same filter set as ``get_trend_by_domain`` so the batched endpoint covers
        exactly the same evaluations as the single-metric endpoint.
        """
        query = (
            select(SLOEvaluation.id)
            .where(
                SLOEvaluation.asset_id == asset_id,
                SLOEvaluation.slo_name == slo_name,
                SLOEvaluation.invalidated == False,  # noqa: E712
                SLOEvaluation.result.is_not(None),
                SLOEvaluation.period_start >= from_ts,
            )
            .order_by(SLOEvaluation.period_start)
        )
        if to_ts:
            query = query.where(SLOEvaluation.period_start <= to_ts)
        result = await self._session.execute(query)
        return [row[0] for row in result.all()]

    async def get_trend_fragment_rows(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        slo_evaluation_ids: list[uuid.UUID],
    ) -> list[TrendColumnFragment]:
        """Build trend fragments for the given SLO-evaluations from the DB."""
        if not slo_evaluation_ids:
            return []
        total_weight_subquery = (
            select(func.coalesce(func.sum(SLOObjective.weight), 1))
            .join(IndicatorResultRow, IndicatorResultRow.slo_objective_id == SLOObjective.id)
            .where(IndicatorResultRow.slo_evaluation_id == SLOEvaluation.id)
            .correlate(SLOEvaluation)
            .scalar_subquery()
            .label('total_weight')
        )
        query = (
            select(
                SLOEvaluation.id.label('slo_evaluation_id'),
                SLOEvaluation.period_start,
                SLOEvaluation.period_end,
                SLOEvaluation.evaluation_name,
                SLIValue.value,
                SLIValue.metric_name,
                IndicatorResultRow.status.label('result'),
                IndicatorResultRow.compared_value,
                IndicatorResultRow.score,
                IndicatorResultRow.targets.label('targets'),
                total_weight_subquery,
            )
            .join(SLOEvaluation, SLIValue.slo_evaluation_id == SLOEvaluation.id)
            .join(IndicatorResultRow, IndicatorResultRow.slo_evaluation_id == SLOEvaluation.id)
            .join(SLOObjective, IndicatorResultRow.slo_objective_id == SLOObjective.id)
            .where(
                SLOEvaluation.id.in_(slo_evaluation_ids),
                SLOObjective.sli == SLIValue.metric_name,
            )
            .order_by(SLOEvaluation.period_start, SLIValue.metric_name)
        )
        result = await self._session.execute(query)
        grouped: dict[uuid.UUID, dict[str, Any]] = {}
        for row in result.all():
            entry = grouped.setdefault(
                row.slo_evaluation_id,
                {
                    'slo_name': slo_name,
                    'period_start': row.period_start,
                    'period_end': row.period_end,
                    'evaluation_name': row.evaluation_name,
                    'total_weight': row.total_weight,
                    'rows': [],
                },
            )
            entry['rows'].append(
                TrendRow(
                    metric=row.metric_name,
                    value=row.value,
                    raw_score=row.score,
                    result=row.result,
                    compared_value=row.compared_value,
                    targets=row.targets,
                )
            )
        return [
            build_trend_fragment(
                slo_evaluation_id=slo_evaluation_id,
                slo_name=entry['slo_name'],
                period_start=entry['period_start'],
                period_end=entry['period_end'],
                evaluation_name=entry['evaluation_name'],
                total_weight=entry['total_weight'],
                rows=entry['rows'],
            )
            for slo_evaluation_id, entry in grouped.items()
        ]
```

In `api/tropek/modules/change_points/repository.py`, add a sibling method to `get_change_points_for_range` that omits `metric_name`:
```python
    async def get_change_points_for_slo_range(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        from_ts: datetime,
        to_ts: datetime | None = None,
    ) -> dict[ChangePointKey, ChangePoint]:
        """Load change points for every metric of an SLO within a time range."""
        query = (
            select(ChangePoint, EvaluationRun.eval_name)
            .join(EvaluationRun, ChangePoint.evaluation_run_id == EvaluationRun.id)
            .where(
                ChangePoint.asset_id == asset_id,
                ChangePoint.slo_name == slo_name,
                ChangePoint.period_start >= from_ts,
                ChangePoint.status != 'hidden',
            )
        )
        if to_ts is not None:
            query = query.where(ChangePoint.period_start <= to_ts)
        result = await self._session.execute(query)
        return {
            ChangePointKey(
                row.ChangePoint.slo_name,
                row.ChangePoint.metric_name,
                row.ChangePoint.period_start,
                row.ChangePoint.period_end,
                row.eval_name,
            ): row.ChangePoint
            for row in result.all()
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory api pytest tests/db/test_trend_repo_batch.py -v -m integration`
Expected: PASS (2 passed)

- [ ] **Step 5: Typecheck + commit**

```bash
uv run mypy api/tropek/modules/quality_gate/repositories/trend.py api/tropek/modules/change_points/repository.py
git add api/tropek/modules/quality_gate/repositories/trend.py api/tropek/modules/change_points/repository.py api/tests/db/test_trend_repo_batch.py api/tests/db/conftest.py
git commit -m "feat(trend): add batch trend repo queries and per-SLO change-point lookup"
```

---

## Task 5: Config TTL + cache dependency

**Files:**
- Modify: `api/tropek/config.py:70-78` (`CacheTTLSettings`)
- Modify: `config.yaml` (document default)
- Modify: `api/tropek/modules/quality_gate/shared/dependencies.py`
- Test: `api/tests/engine/test_trend_cache_dependency.py`

**Interfaces:**
- Produces: `settings.cache.ttl.trend_column: int` (default `7*24*60*60`); `get_trend_column_cache(request) -> TrendColumnCache | None`; `QualityGateRepos.trend_cache: TrendColumnCache | None`.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/engine/test_trend_cache_dependency.py
from tropek.config import CacheTTLSettings


def test_trend_column_ttl_defaults_to_seven_days():
    settings = CacheTTLSettings({})
    assert settings.trend_column == 7 * 24 * 60 * 60


def test_trend_column_ttl_reads_override():
    settings = CacheTTLSettings({'trend_column': 3600})
    assert settings.trend_column == 3600
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory api pytest tests/engine/test_trend_cache_dependency.py -v`
Expected: FAIL — `AttributeError: 'CacheTTLSettings' object has no attribute 'trend_column'`

- [ ] **Step 3: Write minimal implementation**

In `api/tropek/config.py`, inside `CacheTTLSettings.__init__` (next to the `heatmap_column` line):
```python
        self.trend_column: int = data.get('trend_column', 7 * 24 * 60 * 60)
```

In `config.yaml`, under `cache: ttl_seconds:` (next to `heatmap_column`), add:
```yaml
    trend_column: 604800  # 7 days — per-SLO trend fragment cache backstop
```

In `api/tropek/modules/quality_gate/shared/dependencies.py`:
- Add import: `from tropek.modules.quality_gate.workflows.presentation.trend_cache import TrendColumnCache`
- Add the provider (mirror `get_heatmap_column_cache`):
```python
async def get_trend_column_cache(request: Request) -> TrendColumnCache | None:
    """Return a ``TrendColumnCache`` for the request, or ``None`` when Redis is unavailable."""
    redis_cache: RedisCache | None = getattr(request.app.state, 'cache', None)
    if redis_cache is None:
        return None
    settings = get_settings()
    return TrendColumnCache(redis_cache._redis, ttl_seconds=settings.cache.ttl.trend_column)
```
- Add `trend_cache: TrendColumnCache | None = None` to the `QualityGateRepos` dataclass.
- In `get_qg_repos`, add the dependency param `trend_cache: TrendColumnCache | None = Depends(get_trend_column_cache)  # noqa: B008` and pass `trend_cache=trend_cache` into the `QualityGateRepos(...)` construction.

- [ ] **Step 4: Run test + typecheck**

Run: `uv run --directory api pytest tests/engine/test_trend_cache_dependency.py -v`
Expected: PASS (2 passed)
Run: `uv run mypy api/tropek/config.py api/tropek/modules/quality_gate/shared/dependencies.py`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add api/tropek/config.py config.yaml api/tropek/modules/quality_gate/shared/dependencies.py api/tests/engine/test_trend_cache_dependency.py
git commit -m "feat(trend): wire trend cache TTL config and request dependency"
```

---

## Task 6: The `/trends` endpoint (read path + parity)

**Files:**
- Modify: `api/tropek/modules/quality_gate/router.py` (add endpoint after the single-metric route at line 624)
- Test: `api/tests/db/test_trends_endpoint.py` (marked `@pytest.mark.integration`)

**Interfaces:**
- Consumes: `QualityGateRepos.trend_cache` (Task 5); `TrendRepository.list_slo_evaluation_ids_for_trend`, `get_trend_fragment_rows` (Task 4); `ChangePointRepository.get_change_points_for_slo_range` (Task 4); `assemble_slo_trends` (Task 2); `SloTrendsResponse` (Task 1).
- Produces: `GET /assets/{asset_name}/slos/{slo_name:path}/trends?from=&to=` → `SloTrendsResponse`.

Read path: resolve asset → list slo_evaluation_ids in range → `trend_cache.get_many` → rebuild misses via `get_trend_fragment_rows` and `trend_cache.set_many` → overlay change-points via `get_change_points_for_slo_range` → `assemble_slo_trends`. A `cache: bool = Query(True)` param bypasses Redis (copy the heatmap endpoint's `cache` param semantics at router.py:217) so the parity test can run both paths.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/db/test_trends_endpoint.py
import pytest

pytestmark = pytest.mark.integration


async def test_batch_trends_matches_single_metric_endpoint(client, seeded_trend_asset):
    fixture = seeded_trend_asset
    from_ts = fixture.range_from.isoformat()

    batch = await client.get(
        f'/assets/{fixture.asset_name}/slos/{fixture.slo_name}/trends',
        params={'from': from_ts},
    )
    assert batch.status_code == 200
    batch_body = batch.json()

    for metric in ('cpu_time', 'memory_bytes'):
        single = await client.get(
            f'/assets/{fixture.asset_name}/slos/{fixture.slo_name}/trend',
            params={'metric': metric, 'from': from_ts},
        )
        assert single.status_code == 200
        assert batch_body[metric] == single.json()


async def test_batch_trends_identical_with_cache_on_and_off(client, seeded_trend_asset):
    fixture = seeded_trend_asset
    from_ts = fixture.range_from.isoformat()
    url = f'/assets/{fixture.asset_name}/slos/{fixture.slo_name}/trends'
    warm = await client.get(url, params={'from': from_ts})            # populates cache
    cached = await client.get(url, params={'from': from_ts})          # reads cache
    bypass = await client.get(url, params={'from': from_ts, 'cache': 'false'})
    assert warm.json() == cached.json() == bypass.json()


async def test_unknown_asset_returns_404(client):
    response = await client.get('/assets/does-not-exist/slos/whatever/trends', params={'from': '2026-01-01T00:00:00'})
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory api pytest tests/db/test_trends_endpoint.py -v -m integration`
Expected: FAIL — 404/405 (route not registered) on the batch URL

- [ ] **Step 3: Write minimal implementation**

Add to `api/tropek/modules/quality_gate/router.py` (import `SloTrendsResponse`, `assemble_slo_trends`, and `ChangePointRepository` if not already imported; `ChangePointRepository` is already used at line 608):
```python
@router.get('/assets/{asset_name}/slos/{slo_name:path}/trends', response_model=SloTrendsResponse)
async def get_slo_trends(
    asset_name: str,
    slo_name: str,
    from_ts: datetime = Query(alias='from'),
    to_ts: datetime | None = Query(
        default=None,
        alias='to',
        json_schema_extra={'anyOf': [{'format': 'date-time', 'type': 'string'}]},
    ),
    cache: bool = Query(
        default=True,
        description='When false, bypass the Redis trend fragment cache entirely (debugging / parity test).',
    ),
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> SloTrendsResponse:
    """Return every indicator's trend series for one asset+SLO in a single response."""
    asset = await repos.asset_repo.get_by_name(asset_name)
    if asset is None:
        raise NotFoundError('asset', asset_name)

    slo_evaluation_ids = await repos.trend_repo.list_slo_evaluation_ids_for_trend(
        asset_id=asset.id, slo_name=slo_name, from_ts=from_ts, to_ts=to_ts,
    )

    active_cache = repos.trend_cache if cache else None
    fragments_by_id: dict[str, TrendColumnFragment] = {}
    if active_cache is not None:
        fragments_by_id = await active_cache.get_many(slo_evaluation_ids)

    missing_ids = [
        slo_evaluation_id
        for slo_evaluation_id in slo_evaluation_ids
        if str(slo_evaluation_id) not in fragments_by_id
    ]
    if missing_ids:
        rebuilt = await repos.trend_repo.get_trend_fragment_rows(
            asset_id=asset.id, slo_name=slo_name, slo_evaluation_ids=missing_ids,
        )
        if active_cache is not None:
            await active_cache.set_many(rebuilt)
        for fragment in rebuilt:
            fragments_by_id[str(fragment.slo_evaluation_id)] = fragment

    change_point_repo = ChangePointRepository(repos.session)
    change_point_lookup = await change_point_repo.get_change_points_for_slo_range(
        asset_id=asset.id, slo_name=slo_name, from_ts=from_ts, to_ts=to_ts,
    )
    by_metric = assemble_slo_trends(list(fragments_by_id.values()), change_point_lookup)
    return SloTrendsResponse(by_metric)
```

Add the imports near the other schema/workflow imports at the top of `router.py`:
```python
from tropek.modules.quality_gate.schemas import SloTrendsResponse
from tropek.modules.quality_gate.schemas.trend import TrendColumnFragment
from tropek.modules.quality_gate.workflows.presentation.trend_assembler import assemble_slo_trends
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory api pytest tests/db/test_trends_endpoint.py -v -m integration`
Expected: PASS (3 passed)

- [ ] **Step 5: Regenerate schema, typecheck, commit**

```bash
just export-schema
uv run mypy api/tropek/modules/quality_gate/router.py
git add api/tropek/modules/quality_gate/router.py api/tests/db/test_trends_endpoint.py api/openapi.json
git commit -m "feat(trend): add batched per-SLO /trends endpoint with fragment cache"
```

---

## Task 7: Re-evaluation invalidation

**Files:**
- Modify: `api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py`
- Test: `api/tests/db/test_trend_invalidation.py` (marked `@pytest.mark.integration`)

**Interfaces:**
- Consumes: `TrendColumnCache.delete` (Task 3); the existing re-eval call chain that already threads `heatmap_cache`.
- Produces: `_invalidate_caches(fresh_ev, cache, heatmap_cache, trend_cache)` deletes `trend_cache.delete(fresh_ev.id)` (the SLO-evaluation id — the trend fragment key).

Thread a `trend_cache: TrendColumnCache | None = None` parameter through the same functions that already carry `heatmap_cache` (lines 246, 304, 345, 443, 451, 557, 578 pass `heatmap_cache`; add `trend_cache` beside each). The public re-eval entry points are called from `router.py` re-evaluate endpoints — pass `repos.trend_cache` there alongside `repos.heatmap_cache`.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/db/test_trend_invalidation.py
import pytest

pytestmark = pytest.mark.integration


async def test_reevaluation_drops_trend_fragment_for_affected_slo_eval(client, seeded_trend_asset, redis_client):
    from tropek.modules.quality_gate.workflows.presentation.trend_cache import trend_column_cache_key

    fixture = seeded_trend_asset
    from_ts = fixture.range_from.isoformat()
    # Warm the cache
    await client.get(f'/assets/{fixture.asset_name}/slos/{fixture.slo_name}/trends', params={'from': from_ts})
    target_id = fixture.expected_slo_eval_ids_oldest_first[0]
    assert await redis_client.get(trend_column_cache_key(target_id)) is not None

    # Re-evaluate the column owning that SLO-evaluation
    await client.post(
        '/evaluations/re-evaluate/from-date',
        json=fixture.reeval_from_date_payload,  # fixture builds a payload covering target_id's run
    )
    assert await redis_client.get(trend_column_cache_key(target_id)) is None
```

Extend the `seeded_trend_asset` fixture (Task 4) with `reeval_from_date_payload` and expose the integration `redis_client` fixture (reuse whatever the heatmap invalidation integration test uses; if none exists, add one to `api/tests/db/conftest.py` connecting to the test Redis).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory api pytest tests/db/test_trend_invalidation.py -v -m integration`
Expected: FAIL — the fragment key still returns a value after re-evaluation

- [ ] **Step 3: Write minimal implementation**

In `re_evaluation_service.py`:
- Add import: `from tropek.modules.quality_gate.workflows.presentation.trend_cache import TrendColumnCache`
- Change `_invalidate_caches` signature and body:
```python
async def _invalidate_caches(
    fresh_ev: SLOEvaluation,
    cache: RedisCache | None,
    heatmap_cache: HeatmapColumnCache | None,
    trend_cache: TrendColumnCache | None,
) -> None:
    """Drop stale baseline, heatmap, and trend caches tied to the re-scored evaluation."""
    if cache:
        await cache.invalidate(f'baseline:{fresh_ev.asset_id}:{fresh_ev.slo_name}')
    if heatmap_cache is not None:
        await heatmap_cache.delete(fresh_ev.evaluation_id)
    if trend_cache is not None:
        await trend_cache.delete(fresh_ev.id)
```
- Add `trend_cache: TrendColumnCache | None = None` to every function that currently declares `heatmap_cache: HeatmapColumnCache | None = None` (the re-eval functions at lines 246, 304, 451, 557, 578) and forward `trend_cache=trend_cache` at every internal call that currently forwards `heatmap_cache=heatmap_cache` (lines 345, 443, and the `_invalidate_caches(...)` call at 262).
- In `router.py`, the re-evaluate endpoints (`re_evaluate_from_date_endpoint`, `re_evaluate_from_baseline_endpoint`, `re_evaluate_from_evaluation_endpoint`, lines 362-412) that call these services: pass `trend_cache=repos.trend_cache` alongside the existing `heatmap_cache=repos.heatmap_cache`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory api pytest tests/db/test_trend_invalidation.py -v -m integration`
Expected: PASS (1 passed)
Then run the full re-eval suite to confirm no regression:
Run: `uv run --directory api pytest tests/db -k reeval -v -m integration`
Expected: PASS

- [ ] **Step 5: Typecheck + commit**

```bash
uv run mypy api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py api/tropek/modules/quality_gate/router.py
git add api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py api/tropek/modules/quality_gate/router.py api/tests/db/test_trend_invalidation.py api/tests/db/conftest.py
git commit -m "feat(trend): invalidate per-SLO trend fragment on re-evaluation"
```

---

## Task 8: UI — codegen, fetch, mapper, hook, query key

**Files:**
- Modify: `ui/src/generated/api.ts` (via `just codegen`)
- Modify: `ui/src/features/evaluations/mappers.ts`
- Modify: `ui/src/features/evaluations/api.ts`
- Modify: `ui/src/lib/queryKeys.ts`
- Modify: `ui/src/features/evaluations/hooks.ts`
- Test: `ui/src/features/evaluations/mappers.test.ts` (add cases)

**Interfaces:**
- Produces:
  - `queryKeys` addition: `sloTrends(assetName, sloName, dateRange?) => ['slo-trends', assetName, sloName, dateRange]`
  - `fetchSloTrends(assetName, sloName, dateRange?) => Promise<Record<string, TrendPoint[]>>`
  - `dtoToSloTrends(dto: SloTrendsResponseDto) => Record<string, TrendPoint[]>`
  - `useSloTrends(assetName, sloName, options?: { enabled?: boolean }) => UseQueryResult<Record<string, TrendPoint[]>>`

- [ ] **Step 1: Regenerate the client and write the failing mapper test**

Run first (Task 6 already updated `openapi.json`):
```bash
just codegen
```
Then add to `ui/src/features/evaluations/mappers.test.ts`:
```typescript
import { dtoToSloTrends } from './mappers'

test('dtoToSloTrends maps each metric to domain TrendPoints', () => {
  const dto = {
    cpu_time: [
      { timestamp: '2026-01-01T12:00:00Z', value: 1.5, score: 42, eval_id: '11111111-1111-1111-1111-111111111111', result: 'pass', baseline: 1 },
    ],
  }
  const domain = dtoToSloTrends(dto)
  expect(Object.keys(domain)).toEqual(['cpu_time'])
  expect(domain.cpu_time[0].value).toBe(1.5)
  expect(domain.cpu_time[0].evalId).toBe('11111111-1111-1111-1111-111111111111')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/mappers.test.ts`
Expected: FAIL — `dtoToSloTrends is not exported`

- [ ] **Step 3: Write minimal implementation**

In `ui/src/features/evaluations/mappers.ts` (reuse the existing `dtoToTrendPoint` at line 542):
```typescript
export type SloTrendsResponseDto = components['schemas']['SloTrendsResponse']

export function dtoToSloTrends(dto: SloTrendsResponseDto): Record<string, TrendPoint[]> {
  const byMetric: Record<string, TrendPoint[]> = {}
  for (const [metric, points] of Object.entries(dto)) {
    byMetric[metric] = points.map(dtoToTrendPoint)
  }
  return byMetric
}
```

In `ui/src/features/evaluations/api.ts` (next to `fetchTrend`):
```typescript
import { dtoToSloTrends, type SloTrendsResponseDto } from './mappers'

export async function fetchSloTrends(
  assetName: string,
  sloName: string,
  dateRange?: { from?: string; to?: string },
): Promise<Record<string, TrendPoint[]>> {
  const params = new URLSearchParams()
  if (dateRange?.from) params.set('from', dateRange.from)
  if (dateRange?.to) params.set('to', dateRange.to)
  const res = await fetch(
    `${BASE}/assets/${encodeURIComponent(assetName)}/slos/${encodeURIComponent(sloName)}/trends?${params}`,
  )
  if (!res.ok) throw new Error(`fetchSloTrends: ${res.status}`)
  const body: SloTrendsResponseDto = await res.json()
  return dtoToSloTrends(body)
}
```

In `ui/src/lib/queryKeys.ts` (next to `trend`):
```typescript
  sloTrends: (assetName: string, sloName: string, dateRange?: Record<string, string | undefined>) =>
    ['slo-trends', assetName, sloName, dateRange] as const,
```

In `ui/src/features/evaluations/hooks.ts` (next to `useTrend`):
```typescript
import { fetchSloTrends } from './api'

export function useSloTrends(
  assetName: string,
  sloName: string,
  options?: { enabled?: boolean },
) {
  const { from, to } = useTimeRange()
  const dateRange = { from, ...(to ? { to } : {}) }
  return useQuery({
    queryKey: evaluationKeys.sloTrends(assetName, sloName, dateRange),
    queryFn: () => fetchSloTrends(assetName, sloName, dateRange),
    enabled: (options?.enabled ?? true) && !!assetName && !!sloName,
    staleTime: Infinity,
  })
}
```

- [ ] **Step 4: Run test + lint**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/mappers.test.ts`
Expected: PASS
Run: `./scripts/ui-lint.sh --tail 20`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add ui/src/generated/api.ts ui/src/features/evaluations/mappers.ts ui/src/features/evaluations/api.ts ui/src/lib/queryKeys.ts ui/src/features/evaluations/hooks.ts ui/src/features/evaluations/mappers.test.ts
git commit -m "feat(ui): add useSloTrends batched trend hook + client"
```

---

## Task 9: UI — viewport hook

**Files:**
- Create: `ui/src/features/navigator/hooks/useInViewport.ts`
- Test: `ui/src/features/navigator/hooks/useInViewport.test.ts`

**Interfaces:**
- Produces: `useInViewport<T extends Element>(options?: { once?: boolean }) => { ref: (node: T | null) => void; inView: boolean }`. Once `inView` becomes true with `once: true` (default), it stays true (so a fetched group doesn't unload when scrolled away).

- [ ] **Step 1: Write the failing test**

```typescript
// ui/src/features/navigator/hooks/useInViewport.test.ts
import { renderHook, act } from '@testing-library/react'
import { useInViewport } from './useInViewport'

class MockObserver {
  static instances: MockObserver[] = []
  callback: IntersectionObserverCallback
  constructor(cb: IntersectionObserverCallback) { this.callback = cb; MockObserver.instances.push(this) }
  observe() {}
  disconnect() {}
  trigger(isIntersecting: boolean) {
    this.callback([{ isIntersecting } as IntersectionObserverEntry], this as unknown as IntersectionObserver)
  }
}

beforeEach(() => {
  MockObserver.instances = []
  vi.stubGlobal('IntersectionObserver', MockObserver)
})

test('inView flips to true once the element intersects and stays true', () => {
  const { result } = renderHook(() => useInViewport<HTMLDivElement>())
  act(() => { result.current.ref(document.createElement('div')) })
  expect(result.current.inView).toBe(false)
  act(() => { MockObserver.instances[0].trigger(true) })
  expect(result.current.inView).toBe(true)
  act(() => { MockObserver.instances[0].trigger(false) })
  expect(result.current.inView).toBe(true) // once: true keeps it latched
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/ui-test.sh --tail 20 src/features/navigator/hooks/useInViewport.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

```typescript
// ui/src/features/navigator/hooks/useInViewport.ts
import { useCallback, useRef, useState } from 'react'

/**
 * Track whether an element has entered the viewport. With `once` (default) the
 * flag latches true on first intersection so a lazily-loaded section does not
 * unload when scrolled away. Used to defer per-SLO trend fetches until visible.
 */
export function useInViewport<T extends Element>(options?: { once?: boolean }) {
  const once = options?.once ?? true
  const [inView, setInView] = useState(false)
  const observerRef = useRef<IntersectionObserver | null>(null)

  const ref = useCallback((node: T | null) => {
    observerRef.current?.disconnect()
    observerRef.current = null
    if (!node) return
    const observer = new IntersectionObserver(entries => {
      const isIntersecting = entries.some(entry => entry.isIntersecting)
      if (isIntersecting) {
        setInView(true)
        if (once) { observer.disconnect(); observerRef.current = null }
      } else if (!once) {
        setInView(false)
      }
    })
    observer.observe(node)
    observerRef.current = observer
  }, [once])

  return { ref, inView }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./scripts/ui-test.sh --tail 20 src/features/navigator/hooks/useInViewport.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/src/features/navigator/hooks/useInViewport.ts ui/src/features/navigator/hooks/useInViewport.test.ts
git commit -m "feat(ui): add useInViewport hook for lazy section loading"
```

---

## Task 10: UI — wire MetricTrendBlock + per-group lazy fetch

**Files:**
- Modify: `ui/src/features/evaluations/components/MetricTrendBlock.tsx`
- Modify: `ui/src/features/navigator/components/AssetPanelHeatmapView.tsx`
- Test: `ui/src/features/navigator/components/AssetPanelHeatmapView.test.tsx` (add a case) or a focused `MetricTrendBlock` test.

**Interfaces:**
- Consumes: `useSloTrends` (Task 8), `useInViewport` (Task 9).
- Change: `MetricTrendBlock` stops calling `useTrend` and instead receives its series via a new prop `trend?: TrendPoint[]` and `isLoading: boolean`. The parent (per SLO group) calls `useSloTrends` once, gated on viewport visibility, and passes each block its metric slice.

- [ ] **Step 1: Write the failing test**

```typescript
// add to ui/src/features/navigator/components/AssetPanelHeatmapView.test.tsx
test('does not fetch a group\'s trends until the group scrolls into view', async () => {
  // Render AssetPanelHeatmapView with one expanded SLO group and a mocked
  // fetchSloTrends spy. Assert the spy is NOT called on mount (group starts
  // out of view), then simulate the IntersectionObserver firing and assert the
  // spy IS called exactly once for that (asset, slo).
  // Use the MockObserver pattern from useInViewport.test.ts.
})
```

Flesh this out using the existing test's render harness and MSW handlers in `ui/src/mocks/handlers/evaluations.ts` (add a `/trends` handler there mirroring the existing `/trend` handler). Assert on the MSW request count for the `/trends` URL rather than spying internals where practical.

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/ui-test.sh --tail 20 src/features/navigator/components/AssetPanelHeatmapView.test.tsx`
Expected: FAIL — trends fetched on mount (or prop not supported yet)

- [ ] **Step 3: Write minimal implementation**

In `MetricTrendBlock.tsx`:
- Remove `useTrend` usage (keep `useTrendAnnotations`). Change `Props` to add `trend?: TrendPoint[]` and `isLoading?: boolean`; delete the `const { data: trend, isLoading } = useTrend(...)` line and read from props: `const trend = props.trend; const isLoading = props.isLoading ?? false`.
- Import `TrendPoint` type from `@/features/evaluations`.

In `AssetPanelHeatmapView.tsx`, replace the inner `g.indicators.map(...)` rendering (lines 319-333) with a per-group child component that owns the lazy fetch. Add above the `return`:
```typescript
function SloTrendGroup(props: {
  assetName: string
  group: SloBreakdownGroup
  expanded: boolean
  selectedEvalId: string | undefined
  selectedColumnSloEvalIds: ReadonlySet<string>
  selectedPeriodStart: string | undefined
  columns: number
  onEvalSelect: (evalId: string) => void
  trendIdFor: (sloName: string, metric: string) => string
  scrollToRow: (sloName: string, metric: string) => void
}) {
  const { ref, inView } = useInViewport<HTMLDivElement>()
  const { data: trendsByMetric, isLoading } = useSloTrends(
    props.assetName, props.group.slo_name, { enabled: props.expanded && inView },
  )
  return (
    <div ref={ref} className="border border-t-0 border-border rounded-b p-4">
      <div className={props.columns === 1 ? 'grid grid-cols-1 gap-4' : 'grid grid-cols-1 xl:grid-cols-2 gap-4'}>
        {props.group.indicators.map(indicator => (
          <MetricTrendBlock
            key={indicator.metric}
            assetName={props.assetName}
            sloName={props.group.slo_name}
            sloDisplayName={props.group.slo_display_name}
            selectedEvalId={props.selectedEvalId}
            selectedEvalIds={props.selectedColumnSloEvalIds}
            selectedPeriodStart={props.selectedPeriodStart}
            indicator={indicator}
            trend={trendsByMetric?.[indicator.metric]}
            isLoading={isLoading}
            onEvalSelect={props.onEvalSelect}
            blockId={props.trendIdFor(props.group.slo_name, indicator.metric)}
            onScrollToTable={() => props.scrollToRow(props.group.slo_name, indicator.metric)}
          />
        ))}
      </div>
    </div>
  )
}
```
Then in the `trendGroups.map` body, replace the expanded block with:
```typescript
{indicatorGroup.indicators.length > 0 && expanded && (
  <SloTrendGroup
    assetName={assetName}
    group={indicatorGroup}
    expanded={expanded}
    selectedEvalId={effectiveEvalId}
    selectedColumnSloEvalIds={selectedColumnSloEvalIds}
    selectedPeriodStart={selectedPeriodStart}
    columns={columns}
    onEvalSelect={handleTrendClick}
    trendIdFor={trendIdFor}
    scrollToRow={scrollToRow}
  />
)}
```
Add imports at top of `AssetPanelHeatmapView.tsx`: `import { useSloTrends } from '@/features/evaluations/hooks'` and `import { useInViewport } from '../hooks/useInViewport'`. Rename the loop variable `g` to `indicatorGroup` in that `.map` to satisfy the no-cryptic-names rule (touch only the lines you are editing).

- [ ] **Step 4: Run tests + lint**

Run: `./scripts/ui-test.sh --tail 20 src/features/navigator/components/AssetPanelHeatmapView.test.tsx`
Expected: PASS
Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/components/MetricTrendBlock.test.tsx` (if present) and the full suite `./scripts/ui-test.sh --tail 20`
Expected: PASS
Run: `./scripts/ui-lint.sh --tail 20`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add ui/src/features/evaluations/components/MetricTrendBlock.tsx ui/src/features/navigator/components/AssetPanelHeatmapView.tsx ui/src/features/navigator/components/AssetPanelHeatmapView.test.tsx ui/src/mocks/handlers/evaluations.ts
git commit -m "feat(ui): batch per-SLO trends and lazy-load them on viewport entry"
```

---

## Task 11: Full verification pass

**Files:** none (verification only).

- [ ] **Step 1: API unit + lint + type**

Run: `just check`
Expected: lint, lint-ui, fmt-check, typecheck all pass

- [ ] **Step 2: API unit tests**

Run: `./scripts/api-test.sh --tail 30`
Expected: PASS (no integration)

- [ ] **Step 3: API integration tests**

Run: `just test-env` then `just test-int`
Expected: PASS — including the parity, cache-on/off, and invalidation tests
Then: `just test-env-down`

- [ ] **Step 4: UI tests**

Run: `./scripts/ui-test.sh --tail 30`
Expected: PASS

- [ ] **Step 5: Manual smoke (optional, recommended)**

Run: `just dev`, open the navigator on a 6-month asset with many SLOs, open DevTools Network. Confirm: (a) collapsed/off-screen SLO groups do NOT fetch `/trends` until scrolled into view; (b) each visible SLO fires exactly one `/trends` call, not one per indicator; (c) a second load of the same asset serves those `/trends` fast (fragment cache warm). No commit — this is observation only. Report findings back for the final review.

---

## Notes for the implementer

- **Parity is the safety net.** Task 6's `test_batch_trends_matches_single_metric_endpoint` is the contract: the batched endpoint must equal the single-metric endpoint metric-by-metric. If it diverges, the bug is almost always in `get_trend_fragment_rows` (filter set or `total_weight`) or `build_trend_fragment` (score rounding) — fix there, not by mutating the assembler to paper over a difference.
- **Cache is opportunistic everywhere.** Never let a Redis error escape `TrendColumnCache`. If a test needs a "Redis down" path, the endpoint must still return correct data from the DB.
- **Follow-up (Option 2), explicitly out of scope here:** splitting the grouped `/evaluations/heatmap` (the ~40 MB response) into per-SLO fetches sharing a per-(run, SLO) grain plus a composite endpoint. Documented in `docs/superpowers/specs/2026-07-11-trend-batch-fragment-cache-design.md`; it gets its own spec → plan cycle after this lands and is measured.
```
