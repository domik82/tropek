# Evaluation Runs — Part B: Grouped Heatmap API + Frontend

> **Prerequisite:** `docs/superpowers/plans/2026-03-31-evaluation-runs-heatmap-a-db-trigger.md` must be fully merged before starting this plan. This plan assumes `evaluations` (parent), `slo_evaluations` (child), `EvaluationRun` ORM model, and `SLOEvaluation` ORM model are all in place.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat metric heatmap API with a grouped response (`EvaluationRun` → SLO groups → indicators), and rebuild the frontend heatmap, SLI breakdown table, and trend charts to show SLO-grouped accordion sections.

**Architecture:** New endpoint `GET /evaluate/metric-heatmap` returns `GroupedMetricHeatmapResponse` keyed by `evaluation_id` (parent run UUID). Frontend types are updated, `buildAssetHeatmapData` is rewritten to produce ECharts-ready flat rows from the grouped response + per-SLO expand state. A shared `Map<slo_name, boolean>` in `AssetPanel` drives accordion expand/collapse across the heatmap, SLI breakdown table, and trend charts simultaneously. `SLIBreakdownGrouped` replaces `EvaluationTabs` + `SLIBreakdownTable`. Trend charts gain SLO section headers. A new `heatmap_slo_groups_expanded_by_default` config flag sets the initial expand state.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, pytest; React 19, TypeScript, ECharts-for-React, Tailwind CSS v4, React Query, Vitest + React Testing Library.

---

## File Map

| File | Change |
|---|---|
| `api/app/modules/quality_gate/schemas.py` | Add `HeatmapSummaryCell`, `HeatmapCellGrouped`, `SloGroup`, `EvaluationColumn`, `GroupedMetricHeatmapResponse` |
| `api/app/modules/quality_gate/trend_repository.py` | Add `get_grouped_metric_heatmap()` |
| `api/app/modules/quality_gate/router.py` | Add helper `_build_grouped_heatmap_response()` + `GET /evaluate/metric-heatmap` |
| `api/tests/db/test_grouped_heatmap.py` | New: integration tests for grouped heatmap query and endpoint |
| `config.yaml` | Add `heatmap_slo_groups_expanded_by_default: true` under `ui:` |
| `api/app/config.py` | Add `heatmap_slo_groups_expanded_by_default: bool` to `UISettings` |
| `api/app/main.py` | Add field to `ui_config()` response |
| `ui/src/lib/config.ts` | Add `heatmapSloGroupsExpandedByDefault: boolean` |
| `ui/src/features/navigator/types.ts` | Add `EvaluationColumn`, `HeatmapSloGroup`, update `MetricHeatmapResponse`, `MetricHeatmapCell`; extend `HeatmapCell` with `columnKey?`, `isSloHeader?`, `sloName?`; update `AssetHeatmapData` with `headerRowIndices` |
| `ui/src/features/navigator/utils.ts` | Rewrite `buildAssetHeatmapData(resp, expandState)` |
| `ui/src/features/evaluations/api.ts` | Add `fetchGroupedMetricHeatmap()` |
| `ui/src/features/navigator/hooks.ts` | Update `useMetricHeatmap` to call new endpoint |
| `ui/src/mocks/handlers/evaluations.ts` | Add handler for `GET /api/evaluate/metric-heatmap` |
| `ui/src/mocks/generate.ts` | Add `getGroupedMetricHeatmap()` |
| `ui/src/components/charts/HeatmapChart.tsx` | Add `headerRowIndices?: Set<number>` prop; style SLO header labels blue |
| `ui/src/features/navigator/components/AssetHeatmap.tsx` | Add `expandState`, `onSloToggle` props; route clicks |
| `ui/src/features/navigator/components/AssetPanel.tsx` | Add `sloExpandState: Map<string, boolean>`, init from config, pass to children |
| Create: `ui/src/features/evaluations/components/SLIBreakdownGrouped.tsx` | New: SLO-grouped SLI breakdown replacing EvaluationTabs + SLIBreakdownTable |
| `ui/src/features/navigator/components/AssetPanelHeatmapView.tsx` | Replace EvaluationTabs + SLIBreakdownTable with SLIBreakdownGrouped; add SLO-grouped trend sections |

---

## Task 1: Backend — Grouped Heatmap Schemas

**Files:**
- Modify: `api/app/modules/quality_gate/schemas.py`

- [ ] **Step 1: Add schemas after the existing `HeatmapCell` class**

Append to the end of `api/app/modules/quality_gate/schemas.py`:

```python
class HeatmapSummaryCell(BaseModel):
    """Per-column aggregate for an SLO group or the Overall composite row."""

    evaluation_id: uuid.UUID
    period_start: datetime
    result: str
    score: float  # 0–100, achieved_points / total_points × 100


class HeatmapCellGrouped(BaseModel):
    """A single indicator × column cell in the grouped heatmap."""

    evaluation_id: uuid.UUID       # parent eval (column key)
    slo_evaluation_id: uuid.UUID   # FK to slo_evaluations (for trend navigation)
    period_start: datetime         # display label only
    metric: str
    display_name: str
    result: str
    score: float


class SloGroup(BaseModel):
    """One SLO's contribution to the grouped heatmap."""

    slo_name: str
    slo_display_name: str | None = None
    metrics: list[HeatmapMetric]
    cells: list[HeatmapCellGrouped]
    summary: list[HeatmapSummaryCell]  # per-column worst-case aggregate


class EvaluationColumn(BaseModel):
    """One heatmap column — corresponds to one parent EvaluationRun."""

    evaluation_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    eval_name: str


class GroupedMetricHeatmapResponse(BaseModel):
    """Grouped metric heatmap response. Columns are parent EvaluationRun rows."""

    asset_name: str
    columns: list[EvaluationColumn]      # ordered oldest → newest
    groups: list[SloGroup]               # SLO groups in appearance order
    composite: list[HeatmapSummaryCell]  # Overall row (worst-case across all groups)
```

- [ ] **Step 2: Run the type-checker to confirm no import issues**

Run: `./scripts/api-test.sh --tail 5 -k "not True"`
Expected: ruff + mypy clean (no new errors)

- [ ] **Step 3: Commit**

```bash
git add api/app/modules/quality_gate/schemas.py
git commit -m "feat(api): add grouped heatmap schemas — GroupedMetricHeatmapResponse"
```

---

## Task 2: Backend — Grouped Heatmap Query

**Files:**
- Modify: `api/app/modules/quality_gate/trend_repository.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/db/test_grouped_heatmap.py`:

```python
"""Integration tests for the grouped metric heatmap query."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.db.models import Asset, AssetType, EvaluationRun, SLOEvaluation
from app.modules.quality_gate.evaluation_run_repository import EvaluationRunRepository
from app.modules.quality_gate.params import EvalCreateParams
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.trend_repository import TrendRepository
from sqlalchemy.ext.asyncio import AsyncSession

_BASE = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)


async def _create_asset(session: AsyncSession, name: str) -> uuid.UUID:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=name, type_name=type_name))
    await session.flush()
    return asset_id


@pytest.mark.integration
async def test_grouped_heatmap_returns_completed_runs(db_session: AsyncSession) -> None:
    """Each completed EvaluationRun becomes one column in the grouped response."""
    asset_id = await _create_asset(db_session, 'grouped-hm-asset')
    run_repo = EvaluationRunRepository(db_session)
    eval_repo = EvaluationRepository(db_session)
    trend_repo = TrendRepository(db_session)

    # Create 3 parent EvaluationRuns
    for i in range(3):
        start = _BASE + timedelta(hours=i)
        run = await run_repo.create(
            asset_id=asset_id,
            eval_name='daily',
            period_start=start,
            period_end=start + timedelta(hours=1),
        )
        # Create a child SLO evaluation
        await eval_repo.create_pending(
            EvalCreateParams(
                evaluation_name='daily',
                period_start=start,
                period_end=start + timedelta(hours=1),
                ingestion_mode='push',
                asset_snapshot={'name': 'grouped-hm-asset', 'tags': {}},
                variables={},
                asset_id=asset_id,
                slo_name='my-slo',
                evaluation_id=run.id,
            )
        )
        await run_repo.mark_completed(
            run.id,
            result='pass',
            achieved_points=10,
            total_points=10,
        )

    runs = await trend_repo.get_grouped_metric_heatmap(asset_id=asset_id, limit=10)
    assert len(runs) == 3


@pytest.mark.integration
async def test_grouped_heatmap_excludes_pending_runs(db_session: AsyncSession) -> None:
    """Pending EvaluationRun rows do not appear in the heatmap."""
    asset_id = await _create_asset(db_session, 'grouped-hm-pending-asset')
    run_repo = EvaluationRunRepository(db_session)
    trend_repo = TrendRepository(db_session)

    await run_repo.create(
        asset_id=asset_id,
        eval_name='daily',
        period_start=_BASE,
        period_end=_BASE + timedelta(hours=1),
    )

    runs = await trend_repo.get_grouped_metric_heatmap(asset_id=asset_id, limit=10)
    assert len(runs) == 0


@pytest.mark.integration
async def test_grouped_heatmap_eval_name_filter(db_session: AsyncSession) -> None:
    """eval_name filter restricts which EvaluationRuns are returned."""
    asset_id = await _create_asset(db_session, 'grouped-hm-filter-asset')
    run_repo = EvaluationRunRepository(db_session)
    trend_repo = TrendRepository(db_session)

    for name in ('daily', 'weekly'):
        run = await run_repo.create(
            asset_id=asset_id,
            eval_name=name,
            period_start=_BASE,
            period_end=_BASE + timedelta(hours=1),
        )
        await run_repo.mark_completed(
            run.id, result='pass', achieved_points=10, total_points=10
        )

    runs = await trend_repo.get_grouped_metric_heatmap(
        asset_id=asset_id, eval_name=['daily']
    )
    assert len(runs) == 1
    assert runs[0].eval_name == 'daily'
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `./scripts/api-test.sh --tail 5 -m integration tests/db/test_grouped_heatmap.py -v`
Expected: FAIL — `AttributeError: 'TrendRepository' object has no attribute 'get_grouped_metric_heatmap'`

- [ ] **Step 3: Add `get_grouped_metric_heatmap` to `TrendRepository`**

In `api/app/modules/quality_gate/trend_repository.py`, add these imports at the top:

```python
from app.db.models import Evaluation, EvaluationRun, IndicatorResultRow, SLIValue, SLOEvaluation, SLOObjective
```

Then add the method after `get_metric_heatmap`:

```python
async def get_grouped_metric_heatmap(
    self,
    *,
    asset_id: uuid.UUID,
    limit: int = 30,
    eval_name: list[str] | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> list[EvaluationRun]:
    """Fetch completed EvaluationRun rows with all child SLO evaluations and indicator results.

    Returns rows ordered period_start DESC (caller reverses to oldest-first for display).
    """
    from sqlalchemy.orm import selectinload  # already imported at top of file

    q = (
        select(EvaluationRun)
        .options(
            selectinload(EvaluationRun.slo_evaluations)
            .selectinload(SLOEvaluation.indicator_rows)
            .joinedload(IndicatorResultRow.objective),
        )
        .where(
            EvaluationRun.asset_id == asset_id,
            EvaluationRun.status == EvaluationStatus.COMPLETED,
        )
        .order_by(EvaluationRun.period_start.desc())
        .limit(limit)
    )
    if eval_name:
        q = q.where(EvaluationRun.eval_name.in_(eval_name))
    if from_ts:
        q = q.where(EvaluationRun.period_start >= from_ts)
    if to_ts:
        q = q.where(EvaluationRun.period_start <= to_ts)
    result = await self._session.execute(q)
    return list(result.scalars().all())
```

Also move the `from sqlalchemy.orm import selectinload` to the top-level imports (it's already there via the existing `get_metric_heatmap` method). Verify the import is already at the top of the file. If `EvaluationRun` and `SLOEvaluation` are not yet in the imports, add them.

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `./scripts/api-test.sh --tail 5 -m integration tests/db/test_grouped_heatmap.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/quality_gate/trend_repository.py api/tests/db/test_grouped_heatmap.py
git commit -m "feat(api): add get_grouped_metric_heatmap query — EvaluationRun with eager-loaded children"
```

---

## Task 3: Backend — New Endpoint `GET /evaluate/metric-heatmap`

**Files:**
- Modify: `api/app/modules/quality_gate/router.py`

- [ ] **Step 1: Add imports for new schemas**

In `router.py`, extend the import from `schemas`:

```python
from app.modules.quality_gate.schemas import (
    # ... existing imports ...
    EvaluationColumn,
    GroupedMetricHeatmapResponse,
    HeatmapCellGrouped,
    HeatmapSummaryCell,
    SloGroup,
)
```

Also add to the ORM model imports:
```python
from app.db.models import EvaluationRun, SLOEvaluation
```

- [ ] **Step 2: Add the response builder helper function**

Add this function before the router endpoints (after the existing imports):

```python
_RESULT_RANK: dict[str, int] = {'pass': 0, 'warning': 1, 'fail': 2, 'error': 3, 'invalidated': 4}


def _worst_result(results: list[str]) -> str:
    """Return the worst result in `results`, defaulting to 'none' if empty."""
    if not results:
        return 'none'
    return max(results, key=lambda r: _RESULT_RANK.get(r, -1))


def _build_grouped_heatmap_response(
    asset_name: str,
    runs: list[EvaluationRun],
) -> GroupedMetricHeatmapResponse:
    """Build GroupedMetricHeatmapResponse from a list of EvaluationRun rows.

    Assumes each run already has slo_evaluations + indicator_rows eager-loaded.
    Runs must arrive in DESC order (newest first) — this function reverses to ASC.
    """
    runs_asc = sorted(runs, key=lambda r: r.period_start)
    n = len(runs_asc)

    columns = [
        EvaluationColumn(
            evaluation_id=run.id,
            period_start=run.period_start,
            period_end=run.period_end,
            eval_name=run.eval_name,
        )
        for run in runs_asc
    ]
    col_idx: dict[uuid.UUID, int] = {run.id: i for i, run in enumerate(runs_asc)}

    # slo_name → {metrics, cells, per_col_results, per_col: xi → slo_eval}
    slo_data: dict[str, dict] = {}

    for run in runs_asc:
        xi = col_idx[run.id]
        for slo_eval in run.slo_evaluations or []:
            sn = slo_eval.slo_name
            if sn not in slo_data:
                slo_data[sn] = {
                    'metrics': {},
                    'cells': [],
                    'per_col': {},
                }
            sd = slo_data[sn]
            sd['per_col'][xi] = slo_eval
            for row in slo_eval.indicator_rows or []:
                obj = row.objective
                mn = obj.sli
                dn = obj.display_name or mn
                if mn not in sd['metrics']:
                    sd['metrics'][mn] = dn
                sd['cells'].append(
                    HeatmapCellGrouped(
                        evaluation_id=run.id,
                        slo_evaluation_id=slo_eval.id,
                        period_start=run.period_start,
                        metric=mn,
                        display_name=dn,
                        result=row.status,
                        score=row.score,
                    )
                )

    groups = []
    for sn, sd in slo_data.items():
        summary = []
        for xi in range(n):
            slo_ev = sd['per_col'].get(xi)
            result = slo_ev.result if slo_ev and slo_ev.result else 'none'
            score = (
                slo_ev.achieved_points / slo_ev.total_points * 100
                if slo_ev and slo_ev.total_points
                else 0.0
            )
            summary.append(
                HeatmapSummaryCell(
                    evaluation_id=runs_asc[xi].id,
                    period_start=runs_asc[xi].period_start,
                    result=result,
                    score=round(score, 2),
                )
            )
        groups.append(
            SloGroup(
                slo_name=sn,
                metrics=[HeatmapMetric(name=mn, display_name=dn) for mn, dn in sd['metrics'].items()],
                cells=sd['cells'],
                summary=summary,
            )
        )

    composite = [
        HeatmapSummaryCell(
            evaluation_id=runs_asc[xi].id,
            period_start=runs_asc[xi].period_start,
            result=runs_asc[xi].result or 'none',
            score=(
                round(runs_asc[xi].achieved_points / runs_asc[xi].total_points * 100, 2)
                if runs_asc[xi].total_points
                else 0.0
            ),
        )
        for xi in range(n)
    ]

    return GroupedMetricHeatmapResponse(
        asset_name=asset_name,
        columns=columns,
        groups=groups,
        composite=composite,
    )
```

- [ ] **Step 3: Add the new endpoint**

Add this endpoint after the existing `get_metric_heatmap` endpoint in `router.py`:

```python
@router.get('/evaluate/metric-heatmap', response_model=GroupedMetricHeatmapResponse)
async def get_grouped_metric_heatmap(
    asset_name: str,
    evaluation_name: list[str] | None = Query(default=None),
    from_ts: datetime | None = Query(default=None, alias='from'),
    to_ts: datetime | None = Query(default=None, alias='to'),
    limit: int = Query(default=30, le=100),
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> GroupedMetricHeatmapResponse:
    """Return a grouped metric heatmap — one column per parent EvaluationRun."""
    asset = await repos.asset_repo.get_by_name(asset_name)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"asset '{asset_name}' not found")
    runs = await repos.trend_repo.get_grouped_metric_heatmap(
        asset_id=asset.id,
        limit=limit,
        eval_name=evaluation_name,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    return _build_grouped_heatmap_response(asset_name, runs)
```

- [ ] **Step 4: Run unit tests + type check**

Run: `./scripts/api-test.sh --tail 10`
Expected: PASS with no mypy errors

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/quality_gate/router.py
git commit -m "feat(api): add GET /evaluate/metric-heatmap — grouped response by EvaluationRun"
```

---

## Task 4: Config Flag End-to-End

**Files:**
- Modify: `config.yaml`
- Modify: `api/app/config.py`
- Modify: `api/app/main.py`
- Modify: `ui/src/lib/config.ts`

- [ ] **Step 1: Add flag to `config.yaml`**

In `config.yaml` under the `ui:` section:
```yaml
ui:
  max_evaluations: 1000
  page_size: 200
  heatmap_slo_groups_expanded_by_default: true
```

- [ ] **Step 2: Add field to `UISettings` in `api/app/config.py`**

```python
class UISettings(BaseSettings):
    """UI-facing limits served via GET /config/ui."""

    max_evaluations: int = _yaml.get('ui', {}).get('max_evaluations', 1000)
    page_size: int = _yaml.get('ui', {}).get('page_size', 200)
    heatmap_slo_groups_expanded_by_default: bool = _yaml.get('ui', {}).get(
        'heatmap_slo_groups_expanded_by_default', True
    )
```

- [ ] **Step 3: Expose field in `api/app/main.py`**

Update `ui_config()`:
```python
@app.get('/config/ui')
async def ui_config() -> dict[str, int | bool]:
    """Return UI-facing configuration limits."""
    settings = get_settings()
    return {
        'maxEvaluations': settings.ui.max_evaluations,
        'pageSize': settings.ui.page_size,
        'heatmapSloGroupsExpandedByDefault': settings.ui.heatmap_slo_groups_expanded_by_default,
    }
```

- [ ] **Step 4: Update `ui/src/lib/config.ts` to consume the new field**

```typescript
interface UIConfig {
  maxEvaluations: number
  pageSize: number
  heatmapSloGroupsExpandedByDefault: boolean
}

const DEFAULTS: UIConfig = {
  maxEvaluations: 1000,
  pageSize: 200,
  heatmapSloGroupsExpandedByDefault: true,
}

let config: UIConfig = DEFAULTS

export async function loadConfig(): Promise<void> {
  try {
    const res = await fetch('/api/config/ui')
    if (res.ok) {
      const json = await res.json()
      config = { ...DEFAULTS, ...json }
    }
  } catch {
    // Use defaults if API is unreachable
  }
}

export function getConfig(): UIConfig {
  return config
}
```

- [ ] **Step 5: Run all tests**

Run: `./scripts/api-test.sh --tail 5`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add config.yaml api/app/config.py api/app/main.py ui/src/lib/config.ts
git commit -m "feat: add heatmap_slo_groups_expanded_by_default config flag"
```

---

## Task 5: Frontend Types + Data Layer

**Files:**
- Modify: `ui/src/features/navigator/types.ts`
- Modify: `ui/src/features/navigator/utils.ts`
- Modify: `ui/src/features/evaluations/api.ts`
- Modify: `ui/src/features/navigator/hooks.ts`

- [ ] **Step 1: Write failing tests for `buildAssetHeatmapData`**

Create `ui/src/features/navigator/utils.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { buildAssetHeatmapData } from './utils'
import type { MetricHeatmapResponse } from './types'

const EVAL_ID_1 = 'aaaaaaaa-0000-0000-0000-000000000001'
const EVAL_ID_2 = 'aaaaaaaa-0000-0000-0000-000000000002'
const SLO_EVAL_ID_1 = 'bbbbbbbb-0000-0000-0000-000000000001'
const SLO_EVAL_ID_2 = 'bbbbbbbb-0000-0000-0000-000000000002'

const RESP: MetricHeatmapResponse = {
  asset_name: 'test-asset',
  columns: [
    { evaluation_id: EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', period_end: '2026-01-15T23:59:59Z', eval_name: 'daily' },
    { evaluation_id: EVAL_ID_2, period_start: '2026-01-16T00:00:00Z', period_end: '2026-01-16T23:59:59Z', eval_name: 'daily' },
  ],
  groups: [
    {
      slo_name: 'nginx',
      metrics: [
        { name: 'error_rate', display_name: 'Error Rate' },
        { name: 'p99_latency', display_name: 'P99 Latency' },
      ],
      cells: [
        { evaluation_id: EVAL_ID_1, slo_evaluation_id: SLO_EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', metric: 'error_rate', display_name: 'Error Rate', result: 'pass', score: 100 },
        { evaluation_id: EVAL_ID_1, slo_evaluation_id: SLO_EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', metric: 'p99_latency', display_name: 'P99 Latency', result: 'warning', score: 50 },
        { evaluation_id: EVAL_ID_2, slo_evaluation_id: SLO_EVAL_ID_2, period_start: '2026-01-16T00:00:00Z', metric: 'error_rate', display_name: 'Error Rate', result: 'pass', score: 100 },
        { evaluation_id: EVAL_ID_2, slo_evaluation_id: SLO_EVAL_ID_2, period_start: '2026-01-16T00:00:00Z', metric: 'p99_latency', display_name: 'P99 Latency', result: 'pass', score: 90 },
      ],
      summary: [
        { evaluation_id: EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', result: 'warning', score: 75 },
        { evaluation_id: EVAL_ID_2, period_start: '2026-01-16T00:00:00Z', result: 'pass', score: 95 },
      ],
    },
  ],
  composite: [
    { evaluation_id: EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', result: 'warning', score: 75 },
    { evaluation_id: EVAL_ID_2, period_start: '2026-01-16T00:00:00Z', result: 'pass', score: 95 },
  ],
}

describe('buildAssetHeatmapData', () => {
  it('returns 2 columns', () => {
    const d = buildAssetHeatmapData(RESP, new Map())
    expect(d.slots).toHaveLength(2)
  })

  it('with all groups collapsed: rows = Overall + 1 header = 2 rows', () => {
    const d = buildAssetHeatmapData(RESP, new Map([['nginx', false]]))
    // Overall + nginx header
    expect(d.rows).toHaveLength(2)
  })

  it('with nginx expanded: rows = Overall + 1 header + 2 indicators = 4 rows', () => {
    const d = buildAssetHeatmapData(RESP, new Map([['nginx', true]]))
    expect(d.rows).toHaveLength(4)
  })

  it('Overall row cells carry composite result', () => {
    const d = buildAssetHeatmapData(RESP, new Map())
    const overallCells = d.cells.filter(c => c.rowLabel === 'Overall Score')
    expect(overallCells).toHaveLength(2)
    expect(overallCells[0].result).toBe('warning')
    expect(overallCells[1].result).toBe('pass')
  })

  it('SLO header cells carry summary result', () => {
    const d = buildAssetHeatmapData(RESP, new Map([['nginx', false]]))
    const headerCells = d.cells.filter(c => c.isSloHeader)
    expect(headerCells).toHaveLength(2)
    expect(headerCells[0].result).toBe('warning')
  })

  it('expanded indicator cells carry slo_evaluation_id in evalId', () => {
    const d = buildAssetHeatmapData(RESP, new Map([['nginx', true]]))
    const indCells = d.cells.filter(c => c.evalId)
    expect(indCells[0].evalId).toBe(SLO_EVAL_ID_1)
  })

  it('headerRowIndices marks SLO header rows', () => {
    const d = buildAssetHeatmapData(RESP, new Map([['nginx', true]]))
    // With 4 display rows (Overall at i=0, nginx header at i=1), ECharts
    // reverses so Overall is at yi=3, nginx header at yi=2.
    // headerRowIndices should contain the ECharts y-index of nginx header.
    expect(d.headerRowIndices.size).toBe(1)
  })
})
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `./scripts/ui-test.sh --tail 10 src/features/navigator/utils.test.ts`
Expected: FAIL — `buildAssetHeatmapData` wrong signature

- [ ] **Step 3: Update `ui/src/features/navigator/types.ts`**

Replace the file contents with:

```typescript
// ui/src/features/navigator/types.ts

// Grid cell for both group and asset heatmaps
export interface HeatmapCell {
  value: [number, number]       // [xIndex (col), yIndex (row)]
  result: string                // pass | warning | fail | error | invalidated | none
  score: number
  slot: string                  // ISO timestamp for column label (period_start)
  rowLabel: string              // asset name (group view) or metric display name / SLO name (asset view)
  evalId?: string               // slo_evaluation_id — defined for indicator cells
  columnKey?: string            // evaluation_id (parent run UUID) — for column identity
  evaluation_name?: string      // kept for backward compat / tooltip
  hasNote?: boolean             // triggers annotation triangle
  noteContent?: string          // shown in tooltip
  isSloHeader?: boolean         // true for SLO group header rows
  sloName?: string              // for isSloHeader rows — used for toggle callback
}

// Pre-computed group heatmap: rows=assets, cols=slots
export interface GroupHeatmapData {
  slots: string[]
  rows: string[]
  cells: HeatmapCell[]
}

// One data point in the stacked bar chart
export interface AssetScorePoint {
  slot: string
  assetName: string
  score: number
  result: string
  maxScore: number
}

// Grouped by slot for stacked bar rendering
export interface SlotScoreData {
  slot: string
  assets: AssetScorePoint[]
  totalAchieved: number
  totalMax: number
}

// One column in the grouped heatmap — corresponds to one EvaluationRun
export interface EvaluationColumn {
  evaluation_id: string
  period_start: string
  period_end: string
  eval_name: string
}

// Summary cell for an SLO group header row or the Overall composite row
export interface HeatmapSummaryCell {
  evaluation_id: string
  period_start: string
  result: string
  score: number
}

// One SLO group in the grouped heatmap response
export interface HeatmapSloGroup {
  slo_name: string
  slo_display_name?: string
  metrics: Array<{ name: string; display_name: string }>
  cells: MetricHeatmapCell[]
  summary: HeatmapSummaryCell[]
}

// An individual indicator cell in the grouped heatmap
export interface MetricHeatmapCell {
  evaluation_id: string         // parent eval (column key)
  slo_evaluation_id: string     // FK to slo_evaluations (for trend nav)
  period_start: string          // display only
  metric: string
  display_name: string
  result: string
  score: number
}

// API response for GET /api/evaluate/metric-heatmap?asset_name=X
export interface MetricHeatmapResponse {
  asset_name: string
  columns: EvaluationColumn[]
  groups: HeatmapSloGroup[]
  composite: HeatmapSummaryCell[]
}

// Pre-computed asset heatmap: rows=metrics/headers, cols=evaluations
export interface AssetHeatmapData {
  slots: string[]           // ISO period_start per column (display labels)
  rows: string[]            // ECharts bottom-to-top row labels
  cells: HeatmapCell[]
  headerRowIndices: Set<number>  // ECharts y-indices of SLO header rows
}
```

- [ ] **Step 4: Rewrite `buildAssetHeatmapData` in `ui/src/features/navigator/utils.ts`**

Replace the `buildAssetHeatmapData` function:

```typescript
export function buildAssetHeatmapData(
  resp: MetricHeatmapResponse,
  expandState: Map<string, boolean>,
): AssetHeatmapData {
  const columns = resp.columns
  const n = columns.length

  // Build column index map: evaluation_id → xi
  const colIdx = new Map<string, number>()
  for (let i = 0; i < columns.length; i++) colIdx.set(columns[i].evaluation_id, i)

  // Build display rows in visual top-to-bottom order:
  //   displayRows[0] = "Overall Score" (top)
  //   displayRows[1] = SLO header (nginx)
  //   displayRows[2..] = nginx indicators if expanded
  //   ... etc.
  const displayRows: Array<{
    label: string
    type: 'overall' | 'slo-header' | 'indicator'
    sloName?: string
    metricName?: string
  }> = [{ label: 'Overall Score', type: 'overall' }]

  for (const group of resp.groups) {
    const label = group.slo_display_name ?? group.slo_name
    const isExpanded = expandState.get(group.slo_name) ?? false
    displayRows.push({ label, type: 'slo-header', sloName: group.slo_name })
    if (isExpanded) {
      for (const m of group.metrics) {
        displayRows.push({ label: m.display_name, type: 'indicator', sloName: group.slo_name, metricName: m.name })
      }
    }
  }

  const N = displayRows.length
  // ECharts renders category axis bottom-to-top, so reverse for correct visual order
  const rows = [...displayRows].reverse().map(r => r.label)

  // ECharts y-index for displayRows[i] = N - 1 - i
  function yi(displayRowIndex: number): number {
    return N - 1 - displayRowIndex
  }

  // Build indicator cell lookup: `${sloName}\0${evaluationId}\0${metricName}` → MetricHeatmapCell
  const indicatorMap = new Map<string, MetricHeatmapCell>()
  for (const group of resp.groups) {
    for (const cell of group.cells) {
      indicatorMap.set(`${group.slo_name}\0${cell.evaluation_id}\0${cell.metric}`, cell)
    }
  }

  // Build summary cell lookups
  const compositeByCol = new Map<string, HeatmapSummaryCell>()
  for (const s of resp.composite) compositeByCol.set(s.evaluation_id, s)

  const summaryByGroupCol = new Map<string, HeatmapSummaryCell>()
  for (const group of resp.groups) {
    for (const s of group.summary) {
      summaryByGroupCol.set(`${group.slo_name}\0${s.evaluation_id}`, s)
    }
  }

  const gridCells: HeatmapCell[] = []
  const headerRowIndices = new Set<number>()

  for (let di = 0; di < displayRows.length; di++) {
    const row = displayRows[di]
    const rowYi = yi(di)

    if (row.type === 'overall') {
      for (let xi = 0; xi < n; xi++) {
        const col = columns[xi]
        const s = compositeByCol.get(col.evaluation_id)
        gridCells.push({
          value: [xi, rowYi],
          result: s?.result ?? 'none',
          score: s ? Math.round(s.score) : 0,
          slot: col.period_start,
          rowLabel: row.label,
          columnKey: col.evaluation_id,
        })
      }
    } else if (row.type === 'slo-header') {
      headerRowIndices.add(rowYi)
      for (let xi = 0; xi < n; xi++) {
        const col = columns[xi]
        const s = summaryByGroupCol.get(`${row.sloName}\0${col.evaluation_id}`)
        gridCells.push({
          value: [xi, rowYi],
          result: s?.result ?? 'none',
          score: s ? Math.round(s.score) : 0,
          slot: col.period_start,
          rowLabel: row.label,
          columnKey: col.evaluation_id,
          isSloHeader: true,
          sloName: row.sloName,
        })
      }
    } else {
      // indicator row
      for (let xi = 0; xi < n; xi++) {
        const col = columns[xi]
        const key = `${row.sloName}\0${col.evaluation_id}\0${row.metricName}`
        const cell = indicatorMap.get(key)
        gridCells.push({
          value: [xi, rowYi],
          result: cell?.result ?? 'none',
          score: cell ? Math.round(cell.score) : 0,
          slot: col.period_start,
          rowLabel: row.label,
          columnKey: col.evaluation_id,
          evalId: cell?.slo_evaluation_id,
        })
      }
    }
  }

  const slots = columns.map(c => c.period_start)
  return { slots, rows, cells: gridCells, headerRowIndices }
}
```

- [ ] **Step 5: Update `ui/src/features/evaluations/api.ts` — add fetch function**

Add after the `fetchMetricHeatmap` function:

```typescript
export async function fetchGroupedMetricHeatmap(
  assetName: string,
  filters: { evaluation_name?: string[]; from?: string; to?: string } = {}
): Promise<MetricHeatmapResponse> {
  const p = new URLSearchParams({ asset_name: assetName })
  if (filters.evaluation_name?.length) {
    for (const n of filters.evaluation_name) p.append('evaluation_name', n)
  }
  if (filters.from) p.set('from', filters.from)
  if (filters.to) p.set('to', filters.to)
  const res = await fetch(`${BASE}/evaluate/metric-heatmap?${p}`)
  if (!res.ok) throw new Error(`fetchGroupedMetricHeatmap: ${res.status}`)
  return res.json()
}
```

Also add the import of `MetricHeatmapResponse` from the navigator types at the top:
```typescript
import type { MetricHeatmapResponse } from '@/features/navigator/types'
```
(The old import from `navigator/types` of the old `MetricHeatmapResponse` may already exist — replace it with the updated one from the updated `types.ts`.)

- [ ] **Step 6: Update `useMetricHeatmap` in `ui/src/features/navigator/hooks.ts`**

```typescript
import { fetchGroupedMetricHeatmap, fetchEvaluations, fetchEvaluationNames } from '@/features/evaluations/api'

export function useMetricHeatmap(assetName: string | undefined, evaluationNames?: string[]) {
  const { from, to } = useTimeRange()
  const timeFilters = { from, ...(to ? { to } : {}) }
  const fetchFilters = { ...timeFilters, evaluation_name: evaluationNames }
  return useQuery({
    queryKey: evaluationKeys.heatmap(assetName!, timeFilters, evaluationNames),
    queryFn: () => fetchGroupedMetricHeatmap(assetName!, fetchFilters),
    enabled: !!assetName,
  })
}
```

- [ ] **Step 7: Run the tests**

Run: `./scripts/ui-test.sh --tail 10 src/features/navigator/utils.test.ts`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add ui/src/features/navigator/types.ts ui/src/features/navigator/utils.ts ui/src/features/navigator/utils.test.ts ui/src/features/evaluations/api.ts ui/src/features/navigator/hooks.ts
git commit -m "feat(ui): update heatmap types + rewrite buildAssetHeatmapData for grouped response"
```

---

## Task 6: Frontend Mocks

**Files:**
- Modify: `ui/src/mocks/handlers/evaluations.ts`
- Modify: `ui/src/mocks/generate.ts`

- [ ] **Step 1: Add `getGroupedMetricHeatmap` to `generate.ts`**

After the existing `getMetricHeatmap` function, add:

```typescript
export function getGroupedMetricHeatmap(assetName: string): MetricHeatmapResponse {
  import type { MetricHeatmapResponse, EvaluationColumn, HeatmapSloGroup, HeatmapSummaryCell } from '../features/navigator/types'
  // NOTE: add MetricHeatmapResponse to the import at the top of generate.ts
  const prng = makePrng(assetName.charCodeAt(0) + 42)
  const RESULTS = ['pass', 'pass', 'pass', 'warning', 'fail'] as const

  const N_COLS = 7
  const columns: EvaluationColumn[] = Array.from({ length: N_COLS }, (_, i) => {
    const d = new Date('2026-01-15T00:00:00Z')
    d.setDate(d.getDate() + i)
    return {
      evaluation_id: crypto.randomUUID(),
      period_start: d.toISOString(),
      period_end: new Date(d.getTime() + 86_400_000).toISOString(),
      eval_name: 'daily',
    }
  })

  const SLO_GROUPS = ['nginx', 'redis', 'postgres']
  const SLO_METRICS: Record<string, Array<{ name: string; display_name: string }>> = {
    nginx: [
      { name: 'error_rate', display_name: 'Error Rate' },
      { name: 'p99_latency', display_name: 'P99 Latency' },
      { name: 'throughput_rps', display_name: 'Throughput' },
    ],
    redis: [
      { name: 'cache_hit_rate', display_name: 'Cache Hit Rate' },
      { name: 'latency_p99', display_name: 'Latency P99' },
    ],
    postgres: [
      { name: 'query_p95', display_name: 'Query P95' },
      { name: 'connection_pool', display_name: 'Connection Pool' },
      { name: 'deadlocks', display_name: 'Deadlocks' },
    ],
  }

  const SLO_EVAL_IDS: Record<string, string[]> = {}
  for (const slo of SLO_GROUPS) {
    SLO_EVAL_IDS[slo] = columns.map(() => crypto.randomUUID())
  }

  const groups: HeatmapSloGroup[] = SLO_GROUPS.map(sloName => {
    const metrics = SLO_METRICS[sloName]
    const cells = columns.flatMap((col, xi) =>
      metrics.map(m => ({
        evaluation_id: col.evaluation_id,
        slo_evaluation_id: SLO_EVAL_IDS[sloName][xi],
        period_start: col.period_start,
        metric: m.name,
        display_name: m.display_name,
        result: RESULTS[Math.floor(prng() * RESULTS.length)],
        score: Math.round(prng() * 100),
      }))
    )
    const summary: HeatmapSummaryCell[] = columns.map((col, xi) => ({
      evaluation_id: col.evaluation_id,
      period_start: col.period_start,
      result: RESULTS[Math.floor(prng() * RESULTS.length)],
      score: Math.round(prng() * 100),
    }))
    return { slo_name: sloName, metrics, cells, summary }
  })

  const composite: HeatmapSummaryCell[] = columns.map(col => ({
    evaluation_id: col.evaluation_id,
    period_start: col.period_start,
    result: RESULTS[Math.floor(prng() * RESULTS.length)],
    score: Math.round(prng() * 100),
  }))

  return { asset_name: assetName, columns, groups, composite }
}
```

Also add `MetricHeatmapResponse` to the top-level import in `generate.ts`:
```typescript
import type { ... MetricHeatmapResponse } from '../features/navigator/types'
```

- [ ] **Step 2: Add mock handler to `evaluations.ts`**

In `ui/src/mocks/handlers/evaluations.ts`, add a new handler:

```typescript
http.get('/api/evaluate/metric-heatmap', async ({ request }) => {
  const url = new URL(request.url)
  const assetName = url.searchParams.get('asset_name') ?? ''
  const { getGroupedMetricHeatmap } = await gen()
  return HttpResponse.json(getGroupedMetricHeatmap(assetName))
}),
```

- [ ] **Step 3: Type-check the UI**

Run: `./scripts/ui-test.sh --tail 10`
Expected: PASS (no type errors)

- [ ] **Step 4: Commit**

```bash
git add ui/src/mocks/handlers/evaluations.ts ui/src/mocks/generate.ts
git commit -m "feat(ui/mocks): add mock for GET /api/evaluate/metric-heatmap grouped response"
```

---

## Task 7: HeatmapChart — SLO Header Row Styling

**Files:**
- Modify: `ui/src/components/charts/HeatmapChart.tsx`

- [ ] **Step 1: Add `headerRowIndices` prop and Y-axis formatter**

In `HeatmapChart.tsx`, extend `HeatmapChartProps`:

```typescript
export interface HeatmapChartProps {
  // ... existing props ...
  /**
   * ECharts y-indices (positions in the `rows` array) that should be styled
   * as SLO header rows — blue label, bold.
   */
  headerRowIndices?: Set<number>
}
```

Add `headerRowIndices = new Set<number>()` to the destructured props.

Update `useMemo` for `option` to pass it, and update the `yAxis` config:

```typescript
yAxis: {
  type: 'category' as const,
  data: rows,
  axisLabel: {
    fontSize: 14,
    color: ct.axisLabel,
    width: 210,
    overflow: 'truncate' as const,
    ...(headerRowIndices && headerRowIndices.size > 0
      ? {
          formatter: (value: string, index: number) =>
            headerRowIndices.has(index) ? `{sloHeader|${value}}` : value,
          rich: {
            sloHeader: {
              color: '#58a6ff',
              fontSize: 14,
              fontWeight: 'bold',
              width: 210,
              overflow: 'truncate',
            },
          },
        }
      : {}),
  },
  axisLine: { lineStyle: { color: ct.grid } },
  splitLine: { lineStyle: { color: ct.bg } },
},
```

Add `headerRowIndices` to the `useMemo` dependency array.

- [ ] **Step 2: Run type-check**

Run: `./scripts/ui-test.sh --tail 10`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/charts/HeatmapChart.tsx
git commit -m "feat(ui): add headerRowIndices prop to HeatmapChart — blue label for SLO group rows"
```

---

## Task 8: AssetHeatmap — Expand State + Click Routing

**Files:**
- Modify: `ui/src/features/navigator/components/AssetHeatmap.tsx`

- [ ] **Step 1: Write a failing test**

Create `ui/src/features/navigator/components/AssetHeatmap.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AssetHeatmap } from './AssetHeatmap'
import type { MetricHeatmapResponse } from '../types'

const EVAL_ID_1 = 'aaaaaaaa-0000-0000-0000-000000000001'
const SLO_EVAL_ID_1 = 'bbbbbbbb-0000-0000-0000-000000000001'

const RESP: MetricHeatmapResponse = {
  asset_name: 'test-asset',
  columns: [
    { evaluation_id: EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', period_end: '2026-01-15T23:59:59Z', eval_name: 'daily' },
  ],
  groups: [
    {
      slo_name: 'nginx',
      metrics: [{ name: 'error_rate', display_name: 'Error Rate' }],
      cells: [{ evaluation_id: EVAL_ID_1, slo_evaluation_id: SLO_EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', metric: 'error_rate', display_name: 'Error Rate', result: 'pass', score: 100 }],
      summary: [{ evaluation_id: EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', result: 'pass', score: 100 }],
    },
  ],
  composite: [{ evaluation_id: EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', result: 'pass', score: 100 }],
}

let queryClient: QueryClient
beforeEach(() => {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})
afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('AssetHeatmap', () => {
  it('renders without crashing', () => {
    render(
      <Wrapper>
        <AssetHeatmap
          data={RESP}
          expandState={new Map([['nginx', false]])}
          onSloToggle={vi.fn()}
        />
      </Wrapper>
    )
    // If it renders, the SVG chart is present (ECharts renders an svg/canvas)
    expect(document.body).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run to confirm it fails**

Run: `./scripts/ui-test.sh --tail 10 src/features/navigator/components/AssetHeatmap.test.tsx`
Expected: FAIL — `AssetHeatmap` missing `expandState` and `onSloToggle` props

- [ ] **Step 3: Rewrite `AssetHeatmap.tsx`**

```typescript
// ui/src/features/navigator/components/AssetHeatmap.tsx
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR } from '@/lib/theme'
import { fmtDateTime } from '@/lib/format'
import { HeatmapChart } from '@/components/charts/HeatmapChart'
import { NoteIndicatorRow, type SlotNote } from '@/components/charts/NoteIndicatorRow'
import { buildAssetHeatmapData } from '../utils'
import type { MetricHeatmapResponse, HeatmapCell } from '../types'

export interface TimeSlotSelection {
  periodStart: string
  evalIds: string[]
}

interface Props {
  data: MetricHeatmapResponse
  selectedEvalId?: string
  onEvalSelect?: (evalId: string) => void
  onSlotSelect?: (slot: TimeSlotSelection) => void
  notedSlots?: Map<string, SlotNote>
  expandState: Map<string, boolean>
  onSloToggle: (sloName: string) => void
}

export function AssetHeatmap({
  data,
  selectedEvalId,
  onEvalSelect,
  onSlotSelect,
  notedSlots,
  expandState,
  onSloToggle,
}: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]

  const { slots, rows, cells, headerRowIndices } = buildAssetHeatmapData(data, expandState)

  const selectedColumn = selectedEvalId
    ? (() => {
        const cell = cells.find(c => c.evalId === selectedEvalId)
        return cell ? cell.value[0] : undefined
      })()
    : undefined

  function formatTooltip(cell: HeatmapCell): string {
    if (cell.result === 'none') {
      return `${cell.rowLabel}<br/>${fmtDateTime(cell.slot)}<br/><em>no data</em>`
    }
    const rc = colours[cell.result as keyof typeof colours] ?? '#ccc'
    if (cell.isSloHeader) {
      return [
        `<b style="color:#58a6ff">${cell.rowLabel}</b>`,
        fmtDateTime(cell.slot),
        `Score: <b style="color:${rc}">${cell.score}</b> · <b style="color:${rc}">${cell.result.toUpperCase()}</b>`,
        `<span style="color:#888;font-size:10px">Click to expand/collapse</span>`,
      ].join('<br/>')
    }
    return [
      `<b>${cell.rowLabel}</b>`,
      fmtDateTime(cell.slot),
      `Score: <b style="color:${rc}">${cell.score}</b> · <b style="color:${rc}">${cell.result.toUpperCase()}</b>`,
      cell.evalId
        ? `<span style="color:#888;font-size:10px">Click to select this evaluation</span>`
        : '',
    ].filter(Boolean).join('<br/>')
  }

  function onCellClick(cell: HeatmapCell): void {
    // SLO header row click → toggle expand/collapse
    if (cell.isSloHeader && cell.sloName) {
      onSloToggle(cell.sloName)
      return
    }
    if (onSlotSelect) {
      // Collect all slo_evaluation_ids in the same column
      const colIdx = cell.value[0]
      const colCells = cells.filter(c => c.value[0] === colIdx && c.evalId)
      const evalIds = [...new Set(colCells.map(c => c.evalId!))]
      if (evalIds.length > 0) {
        onSlotSelect({ periodStart: cell.slot, evalIds })
      }
    } else if (cell.evalId && onEvalSelect) {
      onEvalSelect(cell.evalId)
    }
  }

  return (
    <HeatmapChart
      rows={rows}
      columns={slots}
      cells={cells}
      selectedColumn={selectedColumn}
      onCellClick={onCellClick}
      formatTooltip={formatTooltip}
      headerRowIndices={headerRowIndices}
      instructionText="Click an indicator cell to select that evaluation. Click an SLO row to expand/collapse."
      aboveChart={
        notedSlots && notedSlots.size > 0 ? (
          <NoteIndicatorRow columns={slots} notedColumns={notedSlots} />
        ) : undefined
      }
    />
  )
}
```

- [ ] **Step 4: Run the test**

Run: `./scripts/ui-test.sh --tail 10 src/features/navigator/components/AssetHeatmap.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/src/features/navigator/components/AssetHeatmap.tsx ui/src/features/navigator/components/AssetHeatmap.test.tsx
git commit -m "feat(ui): AssetHeatmap — accordion expand/collapse via expandState + onSloToggle"
```

---

## Task 9: AssetPanel — Expand State + Config Integration

**Files:**
- Modify: `ui/src/features/navigator/components/AssetPanel.tsx`

- [ ] **Step 1: Add `sloExpandState` to `AssetPanel`**

In `AssetPanel.tsx`:

1. Import `getConfig` at the top:
   ```typescript
   import { getConfig } from '@/lib/config'
   ```

2. Add expand state after existing `useState` declarations:
   ```typescript
   const [sloExpandState, setSloExpandState] = useState<Map<string, boolean>>(() => new Map())
   ```

3. Initialise expand state from config when heatmap data arrives (add a `useEffect`):
   ```typescript
   useEffect(() => {
     if (!heatmapData || sloExpandState.size > 0) return
     const defaultExpanded = getConfig().heatmapSloGroupsExpandedByDefault
     const m = new Map<string, boolean>()
     for (const g of heatmapData.groups) m.set(g.slo_name, defaultExpanded)
     setSloExpandState(m)
   }, [heatmapData])
   ```

4. Add `handleSloToggle` callback after the other handlers:
   ```typescript
   function handleSloToggle(sloName: string) {
     setSloExpandState(prev => {
       const next = new Map(prev)
       next.set(sloName, !prev.get(sloName))
       return next
     })
   }
   ```

5. Also reset expand state when asset changes (add to the existing `useEffect` that resets on `assetName`):
   ```typescript
   useEffect(() => {
     setSelectedEvalId(undefined)
     setSelectedSlot(undefined)
     setActiveAction(null)
     setSelectedNames(undefined)
     setSloExpandState(new Map())
   }, [assetName])
   ```

6. Pass `sloExpandState` and `handleSloToggle` to `AssetPanelHeatmapView` (update Props pass-through — see Task 10).

- [ ] **Step 2: Run type-check**

Run: `./scripts/ui-test.sh --tail 10`
Expected: PASS (may have prop-type errors until Task 10 updates `AssetPanelHeatmapView`)

- [ ] **Step 3: Commit**

```bash
git add ui/src/features/navigator/components/AssetPanel.tsx
git commit -m "feat(ui): AssetPanel — add sloExpandState Map initialised from config"
```

---

## Task 10: `SLIBreakdownGrouped` Component

**Files:**
- Create: `ui/src/features/evaluations/components/SLIBreakdownGrouped.tsx`

The `SLIBreakdownGrouped` component replaces `EvaluationTabs` + `SLIBreakdownTable` in `AssetPanelHeatmapView`. It renders SLO-level section headers (collapsible) with the existing `SLIBreakdownTable` content per section.

- [ ] **Step 1: Write a failing test**

Create `ui/src/features/evaluations/components/SLIBreakdownGrouped.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SLIBreakdownGrouped } from './SLIBreakdownGrouped'
import type { IndicatorResult } from '../types'

const IND: IndicatorResult = {
  metric: 'error_rate',
  display_name: 'Error Rate',
  tab_group: null,
  value: 0.02,
  compared_value: 0.03,
  change_absolute: -0.01,
  change_relative_pct: -33,
  aggregation: 'avg',
  status: 'pass',
  score: 100,
  weight: 1,
  key_sli: false,
  pass_targets: null,
  warning_targets: null,
}

const GROUPS = [
  {
    slo_name: 'nginx',
    slo_display_name: 'NGINX',
    indicators: [IND],
    score: 100,
    result: 'pass',
    achieved_points: 100,
    total_points: 100,
  },
  {
    slo_name: 'redis',
    indicators: [],
    score: 0,
    result: 'none',
    achieved_points: 0,
    total_points: 0,
  },
]

let queryClient: QueryClient
beforeEach(() => {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})
afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('SLIBreakdownGrouped', () => {
  it('renders SLO section headers', () => {
    render(
      <Wrapper>
        <SLIBreakdownGrouped
          groups={GROUPS}
          expandState={new Map([['nginx', true], ['redis', false]])}
          onToggle={vi.fn()}
        />
      </Wrapper>
    )
    expect(screen.getByText('NGINX')).toBeInTheDocument()
    expect(screen.getByText('redis')).toBeInTheDocument()
  })

  it('shows indicators when SLO is expanded', () => {
    render(
      <Wrapper>
        <SLIBreakdownGrouped
          groups={GROUPS}
          expandState={new Map([['nginx', true], ['redis', false]])}
          onToggle={vi.fn()}
        />
      </Wrapper>
    )
    expect(screen.getByText('Error Rate')).toBeInTheDocument()
  })

  it('hides indicators when SLO is collapsed', () => {
    render(
      <Wrapper>
        <SLIBreakdownGrouped
          groups={GROUPS}
          expandState={new Map([['nginx', false], ['redis', false]])}
          onToggle={vi.fn()}
        />
      </Wrapper>
    )
    expect(screen.queryByText('Error Rate')).not.toBeInTheDocument()
  })

  it('calls onToggle when section header is clicked', () => {
    const onToggle = vi.fn()
    render(
      <Wrapper>
        <SLIBreakdownGrouped
          groups={GROUPS}
          expandState={new Map([['nginx', false]])}
          onToggle={onToggle}
        />
      </Wrapper>
    )
    fireEvent.click(screen.getByText('NGINX'))
    expect(onToggle).toHaveBeenCalledWith('nginx')
  })
})
```

- [ ] **Step 2: Run to confirm it fails**

Run: `./scripts/ui-test.sh --tail 10 src/features/evaluations/components/SLIBreakdownGrouped.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Create `SLIBreakdownGrouped.tsx`**

```typescript
// ui/src/features/evaluations/components/SLIBreakdownGrouped.tsx
import { ChevronDown, ChevronRight } from 'lucide-react'
import { SLIBreakdownTable } from './SLIBreakdownTable'
import { resultBadge } from '@/lib/status'
import type { IndicatorResult, SliMetadata } from '../types'

export interface SloBreakdownGroup {
  slo_name: string
  slo_display_name?: string
  indicators: IndicatorResult[]
  score: number           // 0–100
  result: string
  achieved_points: number
  total_points: number
}

interface Props {
  groups: SloBreakdownGroup[]
  expandState: Map<string, boolean>
  onToggle: (sloName: string) => void
  sliMetadata?: Record<string, SliMetadata>
  onIndicatorClick?: (metric: string, sloName: string) => void
}

export function SLIBreakdownGrouped({
  groups,
  expandState,
  onToggle,
  sliMetadata,
  onIndicatorClick,
}: Props) {
  return (
    <div className="space-y-1">
      {groups.map(g => {
        const expanded = expandState.get(g.slo_name) ?? false
        const label = g.slo_display_name ?? g.slo_name
        const resultColour =
          g.result === 'pass' ? 'text-pass' :
          g.result === 'warning' ? 'text-warning' :
          g.result === 'fail' ? 'text-fail' :
          'text-muted-foreground'

        return (
          <div key={g.slo_name}>
            {/* SLO section header */}
            <button
              type="button"
              onClick={() => onToggle(g.slo_name)}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-t border border-border bg-surface-sunken hover:bg-state-hover-bg transition-colors text-left"
            >
              {expanded ? (
                <ChevronDown size={14} className="shrink-0 text-muted-foreground" />
              ) : (
                <ChevronRight size={14} className="shrink-0 text-muted-foreground" />
              )}
              <span
                className="text-sm font-semibold flex-1 truncate"
                style={{ color: '#58a6ff' }}
              >
                {label}
              </span>
              {g.total_points > 0 && (
                <span className="text-xs text-muted-foreground tabular-nums">
                  {g.achieved_points}/{g.total_points}pts
                </span>
              )}
              {g.result !== 'none' && (
                <span className={`text-xs font-bold uppercase ${resultColour}`}>
                  {g.result}
                </span>
              )}
            </button>

            {/* Indicator rows — only when expanded and there are indicators */}
            {expanded && g.indicators.length > 0 && (
              <div className="border border-t-0 border-border rounded-b mb-2">
                <SLIBreakdownTable
                  indicators={g.indicators}
                  sliMetadata={sliMetadata}
                  onIndicatorClick={
                    onIndicatorClick
                      ? (metric) => onIndicatorClick(metric, g.slo_name)
                      : undefined
                  }
                />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
```

Note: `resultBadge` import is not needed if we inline the logic. Remove the unused import.

- [ ] **Step 4: Run the test**

Run: `./scripts/ui-test.sh --tail 10 src/features/evaluations/components/SLIBreakdownGrouped.test.tsx`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add ui/src/features/evaluations/components/SLIBreakdownGrouped.tsx ui/src/features/evaluations/components/SLIBreakdownGrouped.test.tsx
git commit -m "feat(ui): SLIBreakdownGrouped — SLO section headers replacing EvaluationTabs + flat table"
```

---

## Task 11: `AssetPanelHeatmapView` — Wire Everything Together

**Files:**
- Modify: `ui/src/features/navigator/components/AssetPanelHeatmapView.tsx`
- Modify: `ui/src/features/navigator/components/AssetPanel.tsx`

This task updates `AssetPanelHeatmapView` to:
1. Use `SLIBreakdownGrouped` instead of `EvaluationTabs` + `SLIBreakdownTable`
2. Render SLO-grouped trend chart sections
3. Accept `heatmapData`, `allSlotEvals`, `sloExpandState`, `onSloToggle` in Props

- [ ] **Step 1: Update `AssetPanelHeatmapView` Props and implementation**

Replace `ui/src/features/navigator/components/AssetPanelHeatmapView.tsx`:

```typescript
// ui/src/features/navigator/components/AssetPanelHeatmapView.tsx
import { useRef, useCallback, useMemo } from 'react'
import { AssetHeatmap } from './AssetHeatmap'
import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
import { SLIBreakdownGrouped } from '@/features/evaluations/components/SLIBreakdownGrouped'
import type { SloBreakdownGroup } from '@/features/evaluations/components/SLIBreakdownGrouped'
import { ViewToggle } from '@/components/charts/ViewToggle'
import type { ViewMode } from '@/components/charts/ViewToggle'
import type { TimeSlotSelection } from './AssetHeatmap'
import type { MetricHeatmapResponse } from '../types'
import type { EvaluationDetail, SliMetadata } from '@/features/evaluations/types'
import { ChevronDown, ChevronRight } from 'lucide-react'

interface Props {
  assetName: string
  heatmapData: MetricHeatmapResponse | undefined
  allSlotEvals: EvaluationDetail[]
  effectiveEvalId: string | undefined
  notedSlots: Map<string, { evalId: string; count: number }>
  onEvalSelect: (evalId: string) => void
  onSlotSelect?: (slot: TimeSlotSelection) => void
  sliMetadata?: Record<string, SliMetadata>
  mode: ViewMode
  setMode: (m: ViewMode) => void
  explorerButton: React.ReactNode
  // Shared SLO expand state
  sloExpandState: Map<string, boolean>
  onSloToggle: (sloName: string) => void
  metricEvalMap?: Map<string, string>
}

export function AssetPanelHeatmapView({
  assetName, heatmapData, allSlotEvals, effectiveEvalId, notedSlots,
  onEvalSelect, onSlotSelect, mode, setMode, explorerButton,
  sloExpandState, onSloToggle, sliMetadata, metricEvalMap,
}: Props) {
  const sliTableRef = useRef<HTMLDivElement>(null)

  const handleScrollToTable = useCallback(() => {
    sliTableRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  // Build SLO breakdown groups from heatmap SLO group definitions + selected evals
  const breakdownGroups = useMemo((): SloBreakdownGroup[] => {
    if (!heatmapData || allSlotEvals.length === 0) return []
    return heatmapData.groups.map(g => {
      const sloEval = allSlotEvals.find(e => e.slo_name === g.slo_name)
      return {
        slo_name: g.slo_name,
        slo_display_name: g.slo_display_name,
        indicators: sloEval?.indicator_results ?? [],
        score: sloEval ? Math.round(sloEval.score ?? 0) : 0,
        result: sloEval ? (sloEval.invalidated ? 'invalidated' : sloEval.result ?? 'none') : 'none',
        achieved_points: Math.round((sloEval?.score ?? 0) * (sloEval?.indicator_results?.length ?? 1)),
        total_points: sloEval?.indicator_results?.length ?? 0,
      }
    }).filter(g => g.indicators.length > 0)
  }, [heatmapData, allSlotEvals])

  // Build SLO metric groups for trend charts
  const trendGroups = useMemo(() => {
    if (!heatmapData || allSlotEvals.length === 0) return []
    return heatmapData.groups.map(g => {
      const sloEval = allSlotEvals.find(e => e.slo_name === g.slo_name)
      const label = g.slo_display_name ?? g.slo_name
      const score = sloEval ? Math.round(sloEval.score ?? 0) : 0
      const result = sloEval ? (sloEval.invalidated ? 'invalidated' : sloEval.result ?? 'none') : 'none'
      return {
        slo_name: g.slo_name,
        label,
        score,
        result,
        indicators: sloEval?.indicator_results ?? [],
      }
    }).filter(g => g.indicators.length > 0)
  }, [heatmapData, allSlotEvals])

  const resultColour = (result: string) =>
    result === 'pass' ? 'text-pass' :
    result === 'warning' ? 'text-warning' :
    result === 'fail' ? 'text-fail' : 'text-muted-foreground'

  return (
    <>
      {/* Metric Heatmap with view toggle */}
      {heatmapData && (
        <div className="rounded-lg border border-border bg-surface-sunken p-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Metric Heatmap</h2>
            <div className="flex items-center gap-3">
              <ViewToggle mode={mode} setMode={setMode} />
              {explorerButton}
            </div>
          </div>
          <AssetHeatmap
            data={heatmapData}
            selectedEvalId={effectiveEvalId}
            onEvalSelect={onEvalSelect}
            onSlotSelect={onSlotSelect}
            notedSlots={notedSlots}
            expandState={sloExpandState}
            onSloToggle={onSloToggle}
          />
        </div>
      )}

      {/* SLI Breakdown — SLO-grouped sections */}
      {breakdownGroups.length > 0 && (
        <div ref={sliTableRef} className="space-y-0 scroll-mt-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">SLI Breakdown</h2>
          </div>
          <SLIBreakdownGrouped
            groups={breakdownGroups}
            expandState={sloExpandState}
            onToggle={onSloToggle}
            sliMetadata={sliMetadata}
            onIndicatorClick={(metric, sloName) => {
              const el = document.getElementById(`trend-${metric}`)
              if (el) setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
            }}
          />
        </div>
      )}

      {/* Metric Trend Charts — SLO-grouped collapsible sections */}
      {trendGroups.length > 0 && (
        <div className="space-y-4">
          <p className="text-xs text-muted-foreground">
            30-day trend for <strong className="text-foreground">{assetName}</strong>.
          </p>
          {trendGroups.map(g => {
            const expanded = sloExpandState.get(g.slo_name) ?? false
            return (
              <div key={g.slo_name}>
                {/* SLO section header for trend */}
                <button
                  type="button"
                  onClick={() => onSloToggle(g.slo_name)}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded border border-border bg-surface-sunken hover:bg-state-hover-bg transition-colors text-left mb-2"
                >
                  {expanded ? (
                    <ChevronDown size={14} className="shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronRight size={14} className="shrink-0 text-muted-foreground" />
                  )}
                  <span className="text-sm font-semibold flex-1" style={{ color: '#58a6ff' }}>
                    {g.label}
                  </span>
                  {g.result !== 'none' && (
                    <span className={`text-xs font-bold uppercase ${resultColour(g.result)}`}>
                      {g.result}
                    </span>
                  )}
                </button>

                {expanded && g.indicators.length > 0 && (
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    {g.indicators.map(ind => (
                      <MetricTrendBlock
                        key={ind.metric}
                        evalId={metricEvalMap?.get(ind.metric) ?? effectiveEvalId ?? ''}
                        indicator={ind}
                        onEvalSelect={onEvalSelect}
                        onScrollToTable={handleScrollToTable}
                      />
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </>
  )
}
```

- [ ] **Step 2: Update `AssetPanel.tsx` to pass new props to `AssetPanelHeatmapView`**

In `AssetPanel.tsx`, find the `<AssetPanelHeatmapView ...>` usage and update props:

Replace:
```typescript
<AssetPanelHeatmapView
  assetName={assetName}
  heatmapData={heatmapData}
  ev={ev}
  effectiveEvalId={effectiveEvalId}
  notedSlots={notedSlots}
  onEvalSelect={setSelectedEvalId}
  onSlotSelect={handleSlotSelect}
  sliMetadata={mergedSliMetadata}
  mode={mode}
  setMode={setMode}
  explorerButton={explorerButton}
  availableGroups={availableGroups}
  counts={counts}
  activeTab={activeTab}
  setActiveTab={setActiveTab}
  tabIndicators={tabIndicators}
  metricEvalMap={metricEvalMap}
/>
```

With:
```typescript
<AssetPanelHeatmapView
  assetName={assetName}
  heatmapData={heatmapData}
  allSlotEvals={allSlotEvals.length > 0 ? allSlotEvals : (ev ? [ev] : [])}
  effectiveEvalId={effectiveEvalId}
  notedSlots={notedSlots}
  onEvalSelect={setSelectedEvalId}
  onSlotSelect={handleSlotSelect}
  sliMetadata={mergedSliMetadata}
  mode={mode}
  setMode={setMode}
  explorerButton={explorerButton}
  sloExpandState={sloExpandState}
  onSloToggle={handleSloToggle}
  metricEvalMap={metricEvalMap}
/>
```

Also remove the `useTabState` hook usage and the `{ availableGroups, counts, activeTab, setActiveTab, tabIndicators }` destructuring from `AssetPanel.tsx` since they are no longer needed (unless they're used elsewhere in `AssetPanel.tsx` — if so, keep them).

Check if `useTabState` / `EvaluationTabs`-related imports are still used elsewhere in the file. If not, remove the import:
```typescript
// Remove if unused:
import { useTabState } from '@/features/evaluations/hooks/useTabState'
```

- [ ] **Step 3: Run all UI tests**

Run: `./scripts/ui-test.sh --tail 15`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add ui/src/features/navigator/components/AssetPanelHeatmapView.tsx ui/src/features/navigator/components/AssetPanel.tsx
git commit -m "feat(ui): wire SLO accordion — SLIBreakdownGrouped + grouped trend charts in AssetPanel"
```

---

## Task 12: Final Verification

- [ ] **Step 1: Run all backend tests**

Run: `./scripts/api-test.sh --tail 10`
Expected: All tests PASS (including integration tests from Task 2)

- [ ] **Step 2: Run all frontend tests**

Run: `./scripts/ui-test.sh --tail 15`
Expected: All tests PASS

- [ ] **Step 3: Typecheck the API**

Run: `just typecheck`
Expected: No mypy errors

- [ ] **Step 4: Typecheck the UI**

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: No TypeScript errors

- [ ] **Step 5: Verify the mock data flow manually** (optional — only if dev env is running)

If `just dev` is running:
1. Open http://localhost:5173
2. Navigate to any asset in the Navigator
3. Confirm the heatmap shows an "Overall Score" row and SLO group header rows
4. Click a SLO header row — confirm the group expands/collapses in the heatmap, SLI table, and trend charts simultaneously
5. Confirm the config endpoint: `curl http://localhost:8080/config/ui` includes `heatmapSloGroupsExpandedByDefault`
6. Confirm the new heatmap endpoint: `curl http://localhost:8080/evaluate/metric-heatmap?asset_name=X` returns grouped JSON

- [ ] **Step 6: Final commit if any cleanup was needed**

```bash
git add -u
git commit -m "chore: final cleanup after evaluation runs heatmap Plan B"
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec requirement | Task covering it |
|---|---|
| `GET /evaluate/metric-heatmap` grouped endpoint | Task 3 |
| `GroupedMetricHeatmapResponse` with `columns`, `groups`, `composite` | Task 1 |
| `HeatmapCell.slo_evaluation_id` (was `eval_id`) | Task 5 — `MetricHeatmapCell.slo_evaluation_id` |
| `EvaluationColumn.evaluation_id` as column key | Task 1, Task 5 |
| `heatmap_slo_groups_expanded_by_default` config flag | Task 4 |
| `Map<slo_name, boolean>` expand state in `AssetPanel` | Task 9 |
| Expand state initialised from config | Task 9 |
| SLO header rows in heatmap (blue label, chevron) | Task 7 + Task 8 |
| Overall Score row pinned at top | Task 5 (`buildAssetHeatmapData`) |
| Click SLO header → toggle expand/collapse | Task 8 |
| `SLIBreakdownGrouped` with SLO section headers | Task 10 |
| SLO breakdown + trend charts share expand state | Task 11 |
| Trend charts SLO-grouped with collapsible sections | Task 11 |
| `EvaluationTabs` removed from `AssetPanelHeatmapView` | Task 11 |
| Mock handler for new endpoint | Task 6 |
| Frontend types updated | Task 5 |
| Integration tests for new endpoint | Task 2 |

**Notes for implementors:**
- `EvaluationTabs.tsx` itself is NOT deleted — it is still used by `EvaluationIndicatorSection.tsx`. Only its use in `AssetPanelHeatmapView.tsx` is removed.
- `SLIBreakdownTable.tsx` is NOT deleted — it is re-used inside `SLIBreakdownGrouped` per SLO section.
- The old `GET /evaluations/metric-heatmap` endpoint is intentionally kept in place — it can be removed in a follow-on cleanup once all callers have migrated to the new endpoint.
- The `notedSlots` map in `AssetPanel` is still keyed by `period_start` ISO string (not `evaluation_id`) to maintain compatibility with `NoteIndicatorRow`. This works because `period_start` is used as the column display label (`slots` array) in `AssetHeatmapData`.
