# Trend Chart Baselines & Multi-Target Thresholds — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store resolved SLO targets per indicator row at eval time, include them in the trend API, and render all threshold lines + baseline on the metric trend chart with a dropdown toggle.

**Architecture:** Add a `targets` JSONB column to `indicator_results`, populate it from the engine's already-computed `CriteriaTarget` lists during eval. The trend API includes targets per point. The UI scans the union of criteria across all points, renders each as an ECharts line series (solid for static, dashed for relative), and provides a `Tags` dropdown with checkboxes to toggle individual lines. A blue baseline line is also available.

**Tech Stack:** Python 3.13, SQLAlchemy, Alembic, FastAPI, Pydantic; React 19, TypeScript 5.9, ECharts, Vitest

**Spec:** `docs/superpowers/specs/2026-04-10-trend-chart-baselines-design.md`

---

## Task 1: Add `targets` JSONB column to `IndicatorResultRow`

**Files:**
- Modify: `api/app/db/models.py:225-235`

- [ ] **Step 1: Add the column**

In `api/app/db/models.py`, inside the `# fmt: off` / `# fmt: on` block of `IndicatorResultRow`, add after line 234 (`score`):

```python
    targets:            Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
```

Also ensure `JSONB` is already imported from `sqlalchemy.dialects.postgresql` (it is — verify at top of file).

- [ ] **Step 2: Regenerate migrations**

Run: `./scripts/db-regen-migrations.sh`

This squashes all migrations into a fresh `001_initial_schema.py` that includes the new column.

- [ ] **Step 3: Run integration tests to verify schema**

Run: `./scripts/api-test.sh --tail 5 -m integration -v`

Expected: All integration tests PASS (the column is nullable, so existing test data doesn't need updating).

- [ ] **Step 4: Commit**

```
git add api/app/db/models.py api/alembic/versions/001_initial_schema.py
git commit -m "schema: add targets JSONB column to indicator_results"
```

---

## Task 2: Persist targets in the worker write path

**Files:**
- Modify: `api/app/modules/quality_gate/worker.py:227-256`
- Modify: `api/app/modules/quality_gate/indicator_repository.py:26-38`

- [ ] **Step 1: Update `_write_indicator_rows` to build targets dict**

In `api/app/modules/quality_gate/worker.py`, replace lines 243-253 (the `rows.append(...)` block inside the for loop) with:

```python
        targets_dict = {
            'pass': [t.model_dump() for t in ir.pass_targets],
        }
        if ir.warning_targets is not None:
            targets_dict['warn'] = [t.model_dump() for t in ir.warning_targets]
        rows.append(
            {
                'evaluation_id': slo_evaluation_id,
                'slo_objective_id': obj_id,
                'value': ir.value,
                'compared_value': ir.compared_value,
                'change_absolute': ir.change_absolute,
                'change_relative_pct': ir.change_relative_pct,
                'status': ir.status,
                'score': ir.score,
                'targets': targets_dict,
            }
        )
```

- [ ] **Step 2: Update `bulk_insert` to write the targets column**

In `api/app/modules/quality_gate/indicator_repository.py`, add `targets` to the `IndicatorResultRow(...)` constructor inside `bulk_insert`. Replace lines 27-38 with:

```python
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
                    targets=row.get('targets'),
                )
            )
        await self._session.flush()
```

- [ ] **Step 3: Run unit tests**

Run: `./scripts/api-test.sh --tail 5`

Expected: All unit tests PASS.

- [ ] **Step 4: Run integration tests**

Run: `./scripts/api-test.sh --tail 5 -m integration -v`

Expected: All integration tests PASS.

- [ ] **Step 5: Commit**

```
git add api/app/modules/quality_gate/worker.py api/app/modules/quality_gate/indicator_repository.py
git commit -m "feat: persist resolved targets in indicator_results.targets JSONB"
```

---

## Task 3: Add integration test for targets round-trip

**Files:**
- Modify: `api/tests/db/test_indicator_repository.py`

- [ ] **Step 1: Add test for targets persistence**

Append this test at the end of `api/tests/db/test_indicator_repository.py`:

```python
@pytest.mark.integration
async def test_bulk_insert_persists_targets_jsonb(db_session: AsyncSession) -> None:
    """Targets JSONB is stored and readable."""
    _slo_name, _slo_version, objectives = await _seed_slo_with_objectives(db_session)
    asset_id = await _create_asset(db_session)
    eval_id = await _create_eval(db_session, asset_id)

    repo = IndicatorRepository(db_session)

    targets = {
        'pass': [
            {'criteria': '>0', 'target_value': 0.0, 'violated': False},
            {'criteria': '<=600', 'target_value': 600.0, 'violated': False},
            {'criteria': '<=+10%', 'target_value': 550.0, 'violated': False},
        ],
        'warn': [
            {'criteria': '>0', 'target_value': 0.0, 'violated': False},
            {'criteria': '<=+15%', 'target_value': 575.0, 'violated': True},
        ],
    }
    await repo.bulk_insert(
        eval_id,
        [
            {
                'evaluation_id': eval_id,
                'slo_objective_id': objectives[0].id,
                'value': 580.0,
                'compared_value': 500.0,
                'change_absolute': 80.0,
                'change_relative_pct': 16.0,
                'status': 'pass',
                'score': 1.0,
                'targets': targets,
            },
        ],
    )

    result = await db_session.execute(
        select(IndicatorResultRow).where(IndicatorResultRow.slo_evaluation_id == eval_id)
    )
    row = result.scalars().first()
    assert row is not None
    assert row.targets is not None
    assert len(row.targets['pass']) == 3
    assert row.targets['pass'][1]['criteria'] == '<=600'
    assert row.targets['pass'][1]['target_value'] == 600.0
    assert row.targets['warn'][1]['violated'] is True
```

- [ ] **Step 2: Run the new test**

Run: `./scripts/api-test.sh --tail 10 tests/db/test_indicator_repository.py -v`

Expected: All tests including `test_bulk_insert_persists_targets_jsonb` PASS.

- [ ] **Step 3: Commit**

```
git add api/tests/db/test_indicator_repository.py
git commit -m "test: integration test for targets JSONB round-trip"
```

---

## Task 4: Update presenter to read stored targets

**Files:**
- Modify: `api/app/modules/quality_gate/presenter.py:18-49`
- Modify: `api/tests/services/test_presenter.py`

- [ ] **Step 1: Update `_indicators_from_orm_rows` to use stored targets**

In `api/app/modules/quality_gate/presenter.py`, replace lines 37-46 (the `pass_targets=resolve_targets(...)` and `warning_targets=resolve_targets(...)` block) with:

```python
                pass_targets=_read_stored_targets(row, obj, is_pass=True),
                warning_targets=_read_stored_targets(row, obj, is_pass=False),
```

Add this helper function before `_indicators_from_orm_rows` (after the imports):

```python
def _read_stored_targets(
    row: Any,
    obj: Any,
    *,
    is_pass: bool,
) -> list[dict[str, Any]] | None:
    """Read targets from stored JSONB, falling back to resolve_targets for old rows."""
    stored = getattr(row, 'targets', None)
    if stored is not None:
        key = 'pass' if is_pass else 'warn'
        return stored.get(key)
    criteria = list(obj.pass_threshold) if is_pass else list(obj.warning_threshold)
    if not criteria:
        return None if not is_pass else []
    return resolve_targets(
        criteria,
        value=row.value,
        compared_value=row.compared_value,
    )
```

- [ ] **Step 2: Update presenter test helper to include `targets` attribute**

In `api/tests/services/test_presenter.py`, update the `_make_indicator_row` function (line 265-299). Add a `targets` parameter and set it on the returned `SimpleNamespace`:

```python
def _make_indicator_row(  # noqa: PLR0913
    *,
    sli: str = 'response_time',
    display_name: str = 'Response Time',
    tab_group: str | None = None,
    value: float | None = 580.0,
    compared_value: float | None = 500.0,
    change_absolute: float | None = 80.0,
    change_relative_pct: float | None = 16.0,
    status: str = 'pass',
    score: float = 1.0,
    weight: int = 1,
    key_sli: bool = False,
    pass_threshold: list[str] | None = None,
    warning_threshold: list[str] | None = None,
    targets: dict | None = None,
) -> SimpleNamespace:
    """Build a fake ORM IndicatorResultRow with joined objective."""
    objective = SimpleNamespace(
        sli=sli,
        display_name=display_name,
        tab_group=tab_group,
        weight=weight,
        key_sli=key_sli,
        pass_threshold=['<600'] if pass_threshold is None else pass_threshold,
        warning_threshold=[] if warning_threshold is None else warning_threshold,
    )
    return SimpleNamespace(
        value=value,
        compared_value=compared_value,
        change_absolute=change_absolute,
        change_relative_pct=change_relative_pct,
        status=status,
        score=score,
        objective=objective,
        targets=targets,
    )
```

- [ ] **Step 3: Add test for stored targets path**

Append this test at the end of `api/tests/services/test_presenter.py`:

```python
def test_build_detail_uses_stored_targets() -> None:
    """When row has stored targets JSONB, presenter uses them instead of resolve_targets."""
    stored = {
        'pass': [
            {'criteria': '>0', 'target_value': 0.0, 'violated': False},
            {'criteria': '<=600', 'target_value': 600.0, 'violated': False},
        ],
        'warn': [
            {'criteria': '<=+15%', 'target_value': 575.0, 'violated': True},
        ],
    }
    row = _make_indicator_row(
        status='pass',
        value=580.0,
        targets=stored,
    )
    ev = _make_evaluation(indicator_rows=[row])
    detail = build_detail(ev)
    ind = detail.indicator_results[0]
    assert ind.pass_targets == stored['pass']
    assert ind.warning_targets == stored['warn']
```

- [ ] **Step 4: Run presenter tests**

Run: `./scripts/api-test.sh --tail 10 tests/services/test_presenter.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```
git add api/app/modules/quality_gate/presenter.py api/tests/services/test_presenter.py
git commit -m "feat: presenter reads stored targets, falls back to resolve_targets"
```

---

## Task 5: Include targets in trend API response

**Files:**
- Modify: `api/app/modules/quality_gate/schemas/evaluations.py:105-114`
- Modify: `api/app/modules/quality_gate/trend_repository.py:157-210`

- [ ] **Step 1: Add targets to `TrendPoint` schema**

In `api/app/modules/quality_gate/schemas/evaluations.py`, replace lines 105-114 with:

```python
class TrendTargetEntry(BaseModel):
    """A single resolved criteria target within a trend point."""

    criteria: str
    target_value: float
    violated: bool


class TrendTargets(BaseModel):
    """Pass and warn target lists for a trend point."""

    pass_targets: list[TrendTargetEntry] | None = Field(default=None, alias='pass')
    warn: list[TrendTargetEntry] | None = None

    model_config = {'populate_by_name': True}


class TrendPoint(BaseModel):
    """A single point in a metric trend time series."""

    timestamp: datetime
    value: float
    score: float
    eval_id: uuid.UUID
    result: str
    baseline: float | None
    evaluation_name: str | None = None
    targets: TrendTargets | None = None
```

- [ ] **Step 2: Add `targets` to the trend query**

In `api/app/modules/quality_gate/trend_repository.py`, add `IndicatorResultRow.targets` to the `select()` on line 158. Replace lines 157-167 with:

```python
        inner = (
            select(
                SLOEvaluation.period_start,
                SLOEvaluation.evaluation_name,
                SLIValue.value,
                SLIValue.slo_evaluation_id,
                IndicatorResultRow.status.label('result'),
                IndicatorResultRow.compared_value,
                IndicatorResultRow.score,
                IndicatorResultRow.targets.label('targets'),
                total_weight_sq,
            )
```

- [ ] **Step 3: Include targets in the returned dict**

In the same file, update the return dict (lines 199-209). Replace with:

```python
        return [
            {
                'timestamp': r.period_start.isoformat(),
                'value': r.value,
                # Percentage contribution: stacks to 100% when all indicators pass
                'score': round(r.score / r.total_weight * 100, 2) if r.total_weight else 0,
                'eval_id': str(r.slo_evaluation_id),
                'result': r.result,
                'baseline': r.compared_value,
                'evaluation_name': r.evaluation_name,
                'targets': r.targets,
            }
            for r in rows
        ]
```

- [ ] **Step 4: Run unit tests**

Run: `./scripts/api-test.sh --tail 5`

Expected: All unit tests PASS.

- [ ] **Step 5: Commit**

```
git add api/app/modules/quality_gate/schemas/evaluations.py api/app/modules/quality_gate/trend_repository.py
git commit -m "feat: include resolved targets in trend API response"
```

---

## Task 6: Add integration test for targets in trend response

**Files:**
- Modify: `api/tests/db/test_trend_query.py`

- [ ] **Step 1: Add test**

Append this test at the end of `api/tests/db/test_trend_query.py`:

```python
@pytest.mark.integration
async def test_trend_returns_targets_from_indicator_row(db_session: AsyncSession) -> None:
    """Trend points include the stored targets JSONB from indicator_results."""
    asset_id = await _create_asset(db_session, 'trend-targets-asset')
    obj = await _seed_slo_objective(db_session)
    repo = EvaluationRepository(db_session)
    sli_repo = SLIValueRepository(db_session)
    indicator_repo = IndicatorRepository(db_session)
    trend_repo = TrendRepository(db_session)

    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='trend-targets',
            period_start=_BASE,
            period_end=_BASE + timedelta(minutes=30),
            ingestion_mode='push',
            asset_snapshot={'name': 'trend-targets-asset', 'tags': {}},
            variables={},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    await repo.mark_completed(ev.id, result='pass', score=90.0, slo_name='test-slo')

    targets = {
        'pass': [
            {'criteria': '>0', 'target_value': 0.0, 'violated': False},
            {'criteria': '<=600', 'target_value': 600.0, 'violated': False},
        ],
        'warn': [
            {'criteria': '<=+15%', 'target_value': 230.0, 'violated': False},
        ],
    }
    await indicator_repo.bulk_insert(
        ev.id,
        [
            {
                'evaluation_id': ev.id,
                'slo_objective_id': obj.id,
                'value': 250.0,
                'compared_value': 200.0,
                'change_absolute': 50.0,
                'change_relative_pct': 25.0,
                'status': 'pass',
                'score': 1.0,
                'targets': targets,
            },
        ],
    )

    await sli_repo.write_sli_values(
        [
            {
                'slo_evaluation_id': ev.id,
                'eval_start': _BASE,
                'metric_name': 'response_time',
                'aggregation': 'avg',
                'value': 250.0,
                'asset_name': 'trend-targets-asset',
                'evaluation_name': 'trend-targets',
                'os_tag': None,
            }
        ]
    )

    points = await trend_repo.get_trend_by_domain(
        asset_id=asset_id,
        slo_name='test-slo',
        metric_name='response_time',
        from_ts=_BASE - timedelta(hours=1),
    )
    assert len(points) == 1
    assert points[0]['targets'] is not None
    assert len(points[0]['targets']['pass']) == 2
    assert points[0]['targets']['pass'][1]['criteria'] == '<=600'
    assert points[0]['targets']['warn'][0]['violated'] is False
```

- [ ] **Step 2: Run test**

Run: `./scripts/api-test.sh --tail 10 tests/db/test_trend_query.py -v`

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```
git add api/tests/db/test_trend_query.py
git commit -m "test: integration test for targets in trend response"
```

---

## Task 7: Add baseline color to chart theme

**Files:**
- Modify: `ui/src/lib/theme.ts:16-81`

- [ ] **Step 1: Add `baseline` to `ChartTheme` interface and all theme values**

In `ui/src/lib/theme.ts`, add `baseline` to the `ChartTheme` interface (after `selectionRing`):

```typescript
export interface ChartTheme {
  bg:           string
  border:       string
  line:         string
  axisLabel:    string
  grid:         string
  selectionRing: string
  baseline:     string
}
```

Then add the value to each theme in `CHART_THEME`:

```typescript
  current: {
    bg:           '#1a2030',
    border:       '#374151',
    line:         '#374151',
    axisLabel:    '#c0c8d0',
    grid:         '#2a3040',
    selectionRing: '#ffffff',
    baseline:     '#58a6ff',
  },
  dark: {
    bg:           '#18191b',   // Radix slate-2
    border:       '#363a3f',   // Radix slate-6
    line:         '#363a3f',   // Radix slate-6
    axisLabel:    '#b0b4ba',   // Radix slate-11
    grid:         '#212225',   // Radix slate-3
    selectionRing: '#ffffff',
    baseline:     '#70b8ff',   // Radix sky-9
  },
  light: {
    bg:           '#ffffff',   // TODO: Radix light scales
    border:       '#e0e0e0',
    line:         '#e0e0e0',
    axisLabel:    '#595959',
    grid:         '#f5f5f5',
    selectionRing: '#ffffff',
    baseline:     '#3b82f6',
  },
```

- [ ] **Step 2: Run UI type check**

Run: `cd /home/domik/projects/tropek/ui && pnpm exec tsc --noEmit -p tsconfig.app.json`

Expected: No type errors.

- [ ] **Step 3: Commit**

```
git add ui/src/lib/theme.ts
git commit -m "feat: add baseline color to chart theme"
```

---

## Task 8: Update `TrendPoint` type and add target helpers

**Files:**
- Modify: `ui/src/features/evaluations/types.ts:61-111`

- [ ] **Step 1: Add `TrendTargetEntry` and update `TrendPoint`**

In `ui/src/features/evaluations/types.ts`, replace the `PassTarget` interface and `TrendPoint` interface (lines 61-111) with:

```typescript
export interface PassTarget {
  criteria: string
  target_value: number
  violated: boolean
}

export interface TrendTargetEntry {
  criteria: string
  target_value: number
  violated: boolean
}

export interface TrendTargets {
  pass?: TrendTargetEntry[]
  warn?: TrendTargetEntry[]
}

export interface IndicatorResult {
  metric: string
  display_name: string
  tab_group?: string
  value: number
  compared_value: number | null
  change_absolute: number | null
  change_relative_pct: number | null
  aggregation: string
  status: 'pass' | 'warning' | 'fail'
  score: number
  weight: number
  key_sli: boolean
  pass_targets: PassTarget[] | null
  warning_targets: PassTarget[] | null
}

export interface SliMetadata {
  mode: 'aggregated'
  expected_samples: number
  actual_samples: number
  missing_pct: number
  chunks_failed: number
}

export interface EvaluationDetail extends EvaluationSummary {
  invalidation_note: string | null
  evaluation_metadata: Record<string, string>
  compared_evaluation_ids: string[]
  annotations: Annotation[]
  indicator_results: IndicatorResult[]
  total_score_pass_threshold: number | null
  total_score_warning_threshold: number | null
  sli_metadata?: Record<string, SliMetadata>
}

export interface TrendPoint {
  timestamp: string
  value: number
  score: number
  eval_id: string
  result: 'pass' | 'warning' | 'fail'
  baseline?: number | null
  evaluation_name?: string | null
  targets?: TrendTargets | null
}
```

- [ ] **Step 2: Run UI type check**

Run: `cd /home/domik/projects/tropek/ui && pnpm exec tsc --noEmit -p tsconfig.app.json`

Expected: No type errors (existing code doesn't reference `targets` yet).

- [ ] **Step 3: Commit**

```
git add ui/src/features/evaluations/types.ts
git commit -m "feat: add TrendTargetEntry and targets to TrendPoint type"
```

---

## Task 9: Write tests for the new `buildChartOption` and hook

**Files:**
- Modify: `ui/src/features/evaluations/hooks/useMetricTrendState.test.ts`

- [ ] **Step 1: Rewrite the test file**

Replace the entire contents of `ui/src/features/evaluations/hooks/useMetricTrendState.test.ts` with:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { buildChartOption, useMetricTrendState } from './useMetricTrendState'
import type { ChartTarget } from './useMetricTrendState'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import type { TrendPoint, IndicatorResult } from '../types'

// ── Helpers ───────────────────────────────────────────────────────────────────

const colours = RESULT_COLOUR.current
const ct = CHART_THEME.current

function baseInput(overrides: Record<string, unknown> = {}) {
  return {
    trend: [] as TrendPoint[],
    evalId: 'eval-1',
    colours,
    ct,
    fontSize: 14,
    yMin: '',
    yMax: '',
    targets: [] as ChartTarget[],
    ...overrides,
  }
}

function makeTrendPoint(overrides: Partial<TrendPoint> = {}): TrendPoint {
  return {
    timestamp: '2026-03-15T10:30:00Z',
    value: 100,
    score: 1,
    eval_id: 'eval-1',
    result: 'pass',
    ...overrides,
  }
}

function makeIndicator(overrides: Partial<IndicatorResult> = {}): IndicatorResult {
  return {
    metric: 'response_time',
    display_name: 'Response Time',
    value: 100,
    compared_value: null,
    change_absolute: null,
    change_relative_pct: null,
    aggregation: 'avg',
    status: 'pass',
    score: 1,
    weight: 1,
    key_sli: false,
    pass_targets: null,
    warning_targets: null,
    ...overrides,
  }
}

// ── buildChartOption ──────────────────────────────────────────────────────────

describe('buildChartOption', () => {
  it('creates series for metric values', () => {
    const trend = [
      makeTrendPoint({ value: 100, result: 'pass' }),
      makeTrendPoint({ value: 200, result: 'warning', timestamp: '2026-03-16T10:30:00Z' }),
    ]
    const option = buildChartOption(baseInput({ trend })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series).toHaveLength(1)
    const data = series[0].data as Array<{ value: number }>
    expect(data).toHaveLength(2)
    expect(data[0].value).toBe(100)
    expect(data[1].value).toBe(200)
  })

  it('adds static pass target as solid line series', () => {
    const trend = [makeTrendPoint({ value: 100 })]
    const option = buildChartOption(baseInput({
      trend,
      targets: [
        { key: 'pass:<=600', level: 'pass', criteria: '<=600', visible: true },
      ],
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    // Main series + 1 target series
    expect(series).toHaveLength(2)
    expect((series[1].lineStyle as { type: string }).type).toBe('solid')
  })

  it('adds relative warn target as dashed line series', () => {
    const trend = [
      makeTrendPoint({ value: 100, targets: { warn: [{ criteria: '<=+15%', target_value: 230, violated: false }] } }),
    ]
    const option = buildChartOption(baseInput({
      trend,
      targets: [
        { key: 'warn:<=+15%', level: 'warn', criteria: '<=+15%', visible: true },
      ],
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series).toHaveLength(2)
    expect((series[1].lineStyle as { type: string }).type).toBe('dashed')
  })

  it('does not add series for hidden targets', () => {
    const trend = [makeTrendPoint({ value: 100 })]
    const option = buildChartOption(baseInput({
      trend,
      targets: [
        { key: 'pass:<=600', level: 'pass', criteria: '<=600', visible: false },
      ],
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series).toHaveLength(1) // Only main series
  })

  it('adds baseline series when visible', () => {
    const trend = [
      makeTrendPoint({ value: 100, baseline: 90 }),
      makeTrendPoint({ value: 110, baseline: 100, timestamp: '2026-03-16T10:30:00Z' }),
    ]
    const option = buildChartOption(baseInput({
      trend,
      targets: [
        { key: 'baseline', level: 'baseline', criteria: 'baseline', visible: true },
      ],
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series).toHaveLength(2)
    expect((series[1].lineStyle as { type: string }).type).toBe('dotted')
    const data = series[1].data as Array<number | null>
    expect(data).toEqual([90, 100])
  })

  it('renders static and relative targets simultaneously', () => {
    const trend = [
      makeTrendPoint({
        value: 100,
        baseline: 90,
        targets: {
          pass: [
            { criteria: '<=600', target_value: 600, violated: false },
            { criteria: '<=+10%', target_value: 99, violated: false },
          ],
        },
      }),
    ]
    const option = buildChartOption(baseInput({
      trend,
      targets: [
        { key: 'pass:<=600', level: 'pass', criteria: '<=600', visible: true },
        { key: 'pass:<=+10%', level: 'pass', criteria: '<=+10%', visible: true },
      ],
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    // Main + static + relative
    expect(series).toHaveLength(3)
  })

  it('renders all four targets when all visible', () => {
    const trend = [
      makeTrendPoint({
        value: 100,
        baseline: 90,
        targets: {
          pass: [
            { criteria: '<=600', target_value: 600, violated: false },
            { criteria: '<=+10%', target_value: 99, violated: false },
          ],
          warn: [
            { criteria: '<=800', target_value: 800, violated: false },
            { criteria: '<=+15%', target_value: 103, violated: false },
          ],
        },
      }),
    ]
    const option = buildChartOption(baseInput({
      trend,
      targets: [
        { key: 'pass:<=600', level: 'pass', criteria: '<=600', visible: true },
        { key: 'pass:<=+10%', level: 'pass', criteria: '<=+10%', visible: true },
        { key: 'warn:<=800', level: 'warn', criteria: '<=800', visible: true },
        { key: 'warn:<=+15%', level: 'warn', criteria: '<=+15%', visible: true },
      ],
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    // Main + 4 targets
    expect(series).toHaveLength(5)
  })

  it('sets yAxis min/max from state', () => {
    const option = buildChartOption(baseInput({ yMin: '10', yMax: '500' })) as Record<string, unknown>
    const yAxis = option.yAxis as { min: number; max: number }
    expect(yAxis.min).toBe(10)
    expect(yAxis.max).toBe(500)
  })

  it('leaves yAxis min/max undefined when empty', () => {
    const option = buildChartOption(baseInput()) as Record<string, unknown>
    const yAxis = option.yAxis as { min: unknown; max: unknown }
    expect(yAxis.min).toBeUndefined()
    expect(yAxis.max).toBeUndefined()
  })

  it('handles empty data points', () => {
    const option = buildChartOption(baseInput({ trend: [] })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series[0].data).toEqual([])
  })

  it('highlights current evaluation point with white border', () => {
    const trend = [
      makeTrendPoint({ eval_id: 'eval-1' }),
      makeTrendPoint({ eval_id: 'eval-2' }),
    ]
    const option = buildChartOption(baseInput({ trend, evalId: 'eval-1' })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    const data = series[0].data as Array<{ itemStyle: { borderColor: string } }>
    expect(data[0].itemStyle.borderColor).toBe('#ffffff')
    expect(data[1].itemStyle.borderColor).toBe('transparent')
  })

  it('sets cursor to pointer when onEvalSelect is provided', () => {
    const option = buildChartOption(baseInput({ onEvalSelect: () => {} })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series[0].cursor).toBe('pointer')
  })

  it('sets cursor to default when no onEvalSelect', () => {
    const option = buildChartOption(baseInput()) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series[0].cursor).toBe('default')
  })
})

// ── useMetricTrendState ───────────────────────────────────────────────────────

vi.mock('@/lib/theme-context', () => ({
  useTheme: () => ({ theme: 'current' as const, fontSize: 14 }),
}))

describe('useMetricTrendState', () => {
  it('initializes with empty yMin/yMax', () => {
    const { result } = renderHook(() =>
      useMetricTrendState([], 'eval-1', makeIndicator()),
    )
    expect(result.current.yMin).toBe('')
    expect(result.current.yMax).toBe('')
  })

  it('builds targets from trend data', () => {
    const trend: TrendPoint[] = [
      makeTrendPoint({
        targets: {
          pass: [
            { criteria: '<=600', target_value: 600, violated: false },
            { criteria: '<=+10%', target_value: 99, violated: false },
          ],
          warn: [
            { criteria: '<=+15%', target_value: 103, violated: false },
          ],
        },
      }),
    ]
    const { result } = renderHook(() =>
      useMetricTrendState(trend, 'eval-1', makeIndicator()),
    )
    // 3 criteria targets + baseline = 4 toggles
    expect(result.current.targets).toHaveLength(4)
    expect(result.current.targets[0]).toMatchObject({ key: 'pass:<=600', level: 'pass' })
    expect(result.current.targets[1]).toMatchObject({ key: 'pass:<=+10%', level: 'pass' })
    expect(result.current.targets[2]).toMatchObject({ key: 'warn:<=+15%', level: 'warn' })
    expect(result.current.targets[3]).toMatchObject({ key: 'baseline', level: 'baseline' })
  })

  it('filters out >0 targets where target_value is always 0', () => {
    const trend: TrendPoint[] = [
      makeTrendPoint({
        targets: {
          pass: [
            { criteria: '>0', target_value: 0, violated: false },
            { criteria: '<=600', target_value: 600, violated: false },
          ],
        },
      }),
    ]
    const { result } = renderHook(() =>
      useMetricTrendState(trend, 'eval-1', makeIndicator()),
    )
    // Only <=600 + baseline
    expect(result.current.targets).toHaveLength(2)
    expect(result.current.targets[0].key).toBe('pass:<=600')
    expect(result.current.targets[1].key).toBe('baseline')
  })

  it('toggling a target flips its visibility', () => {
    const trend: TrendPoint[] = [
      makeTrendPoint({
        targets: { pass: [{ criteria: '<=600', target_value: 600, violated: false }] },
      }),
    ]
    const { result } = renderHook(() =>
      useMetricTrendState(trend, 'eval-1', makeIndicator()),
    )
    expect(result.current.targets[0].visible).toBe(true)
    act(() => result.current.targets[0].toggle())
    expect(result.current.targets[0].visible).toBe(false)
    act(() => result.current.targets[0].toggle())
    expect(result.current.targets[0].visible).toBe(true)
  })

  it('baseline defaults to hidden', () => {
    const trend: TrendPoint[] = [
      makeTrendPoint({ baseline: 90, targets: {} }),
    ]
    const { result } = renderHook(() =>
      useMetricTrendState(trend, 'eval-1', makeIndicator()),
    )
    const baseline = result.current.targets.find(t => t.key === 'baseline')
    expect(baseline).toBeDefined()
    expect(baseline!.visible).toBe(false)
  })

  it('returns chartOption object', () => {
    const { result } = renderHook(() =>
      useMetricTrendState([], 'eval-1', makeIndicator()),
    )
    expect(result.current.chartOption).toBeDefined()
    expect(typeof result.current.chartOption).toBe('object')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/hooks/useMetricTrendState.test.ts`

Expected: Multiple failures — the hook and `buildChartOption` still use the old interface.

- [ ] **Step 3: Commit**

```
git add ui/src/features/evaluations/hooks/useMetricTrendState.test.ts
git commit -m "test: rewrite useMetricTrendState tests for multi-target baseline support"
```

---

## Task 10: Rewrite `useMetricTrendState` hook and `buildChartOption`

**Files:**
- Modify: `ui/src/features/evaluations/hooks/useMetricTrendState.ts`

- [ ] **Step 1: Replace the entire file**

Replace the entire contents of `ui/src/features/evaluations/hooks/useMetricTrendState.ts` with:

```typescript
// ui/src/features/evaluations/hooks/useMetricTrendState.ts
import { useState, useMemo } from 'react'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import type { TrendPoint, IndicatorResult, TrendTargetEntry } from '../types'

// ── Types ────────────────────────────────────────────────────────────────────

export interface TargetToggle {
  key: string
  level: 'pass' | 'warn' | 'baseline'
  criteria: string
  visible: boolean
  toggle: () => void
}

export interface ChartTarget {
  key: string
  level: 'pass' | 'warn' | 'baseline'
  criteria: string
  visible: boolean
}

export interface MetricTrendState {
  yMin: string
  yMax: string
  setYMin: (v: string) => void
  setYMax: (v: string) => void
  targets: TargetToggle[]
  chartOption: object
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Returns true if a criteria string is relative (contains % or explicit +/- sign). */
function isRelative(criteria: string): boolean {
  return /[%]/.test(criteria) || /^[<>=]+=?\s*[+-]/.test(criteria)
}

interface DiscoveredTarget {
  key: string
  level: 'pass' | 'warn'
  criteria: string
  alwaysZero: boolean
}

/**
 * Scan all trend points and collect the union of distinct {level, criteria} pairs.
 * A target is "always zero" if target_value === 0 on every point where it appears.
 */
function discoverTargets(trend: TrendPoint[]): DiscoveredTarget[] {
  const map = new Map<string, { level: 'pass' | 'warn'; criteria: string; hasNonZero: boolean }>()
  for (const p of trend) {
    if (!p.targets) continue
    for (const level of ['pass', 'warn'] as const) {
      const entries = p.targets[level]
      if (!entries) continue
      for (const e of entries) {
        const key = `${level}:${e.criteria}`
        const existing = map.get(key)
        if (existing) {
          if (e.target_value !== 0) existing.hasNonZero = true
        } else {
          map.set(key, { level, criteria: e.criteria, hasNonZero: e.target_value !== 0 })
        }
      }
    }
  }
  const result: DiscoveredTarget[] = []
  for (const [key, info] of map) {
    result.push({ key, level: info.level, criteria: info.criteria, alwaysZero: !info.hasNonZero })
  }
  // Stable order: pass first, then warn, alphabetical within level
  result.sort((a, b) => {
    if (a.level !== b.level) return a.level === 'pass' ? -1 : 1
    return a.criteria.localeCompare(b.criteria)
  })
  return result
}

/**
 * For a given criteria key and level, extract the target_value from a trend point.
 * Returns null if the point doesn't have that criteria.
 */
function getTargetValue(
  point: TrendPoint,
  level: 'pass' | 'warn',
  criteria: string,
): number | null {
  const entries: TrendTargetEntry[] | undefined = point.targets?.[level]
  if (!entries) return null
  const entry = entries.find(e => e.criteria === criteria)
  return entry?.target_value ?? null
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useMetricTrendState(
  trend: TrendPoint[] | undefined,
  evalId: string,
  _indicator: IndicatorResult,
  onEvalSelect?: (evalId: string) => void,
  selectedEvalIds?: ReadonlySet<string>,
  selectedPeriodStart?: string,
): MetricTrendState {
  const [yMin, setYMin] = useState('')
  const [yMax, setYMax] = useState('')
  const [visibility, setVisibility] = useState<Record<string, boolean>>({})

  const { theme, fontSize } = useTheme()
  const colours = RESULT_COLOUR[theme]
  const ct = CHART_THEME[theme]

  const trendData = trend ?? []

  const discovered = useMemo(() => discoverTargets(trendData), [trendData])

  const hasBaseline = trendData.some(p => p.baseline != null)

  const targets: TargetToggle[] = useMemo(() => {
    const result: TargetToggle[] = []

    // Criteria targets (filter out always-zero)
    for (const d of discovered) {
      if (d.alwaysZero) continue
      const visible = visibility[d.key] ?? true // default ON
      result.push({
        key: d.key,
        level: d.level,
        criteria: d.criteria,
        visible,
        toggle: () => setVisibility(v => ({ ...v, [d.key]: !(v[d.key] ?? true) })),
      })
    }

    // Baseline toggle (always last)
    if (hasBaseline) {
      const visible = visibility['baseline'] ?? false // default OFF
      result.push({
        key: 'baseline',
        level: 'baseline',
        criteria: 'baseline',
        visible,
        toggle: () => setVisibility(v => ({ ...v, baseline: !(v['baseline'] ?? false) })),
      })
    }

    return result
  }, [discovered, hasBaseline, visibility])

  const chartTargets: ChartTarget[] = useMemo(
    () => targets.map(t => ({ key: t.key, level: t.level, criteria: t.criteria, visible: t.visible })),
    [targets],
  )

  const chartOption = useMemo(
    () => buildChartOption({
      trend: trendData,
      evalId,
      selectedEvalIds,
      selectedPeriodStart,
      colours,
      ct,
      fontSize,
      yMin,
      yMax,
      targets: chartTargets,
      onEvalSelect,
    }),
    [trendData, evalId, selectedEvalIds, selectedPeriodStart, colours, ct, fontSize, yMin, yMax, chartTargets, onEvalSelect],
  )

  return { yMin, yMax, setYMin, setYMax, targets, chartOption }
}

// ── Pure chart option builder (testable without React) ─────────────────────

interface ChartOptionInput {
  trend: TrendPoint[]
  evalId: string
  selectedEvalIds?: ReadonlySet<string>
  selectedPeriodStart?: string
  colours: { pass: string; warning: string; fail: string; error: string; invalidated: string }
  ct: { bg: string; border: string; line: string; axisLabel: string; grid: string; baseline: string }
  fontSize: number
  yMin: string
  yMax: string
  targets: ChartTarget[]
  onEvalSelect?: (evalId: string) => void
}

export function buildChartOption(input: ChartOptionInput): object {
  const {
    trend, evalId, selectedEvalIds, selectedPeriodStart, colours, ct, fontSize,
    yMin, yMax, targets,
    onEvalSelect,
  } = input

  const fontScale = fontSize / 14

  const hasIdMatch = trend.some(
    p => (!!selectedEvalIds && selectedEvalIds.has(p.eval_id)) || p.eval_id === evalId,
  )

  const isSelected = (p: TrendPoint): boolean => {
    if ((!!selectedEvalIds && selectedEvalIds.has(p.eval_id)) || p.eval_id === evalId) return true
    if (!hasIdMatch && selectedPeriodStart && p.timestamp === selectedPeriodStart) return true
    return false
  }

  const times = trend.map(p => p.timestamp.slice(0, 16).replace('T', ' '))

  const chartData = trend.map(p => ({
    value: p.value,
    itemStyle: {
      color: colours[p.result as keyof typeof colours] ?? '#6b7280',
      borderColor: isSelected(p) ? '#ffffff' : 'transparent',
      borderWidth: 2,
    },
  }))

  // ── Target line series ──────────────────────────────────────────────────
  const targetSeries: object[] = []
  for (const t of targets) {
    if (!t.visible) continue

    // Baseline series
    if (t.level === 'baseline') {
      const data = trend.map(p => p.baseline ?? null)
      targetSeries.push({
        type: 'line',
        data,
        symbol: 'none',
        silent: true,
        lineStyle: { color: ct.baseline, type: 'dotted' as const, width: 1, opacity: 0.6 },
        tooltip: { show: false },
      })
      continue
    }

    // Criteria target series
    const color = t.level === 'pass' ? colours.pass : colours.warning
    const lineType = isRelative(t.criteria) ? 'dashed' as const : 'solid' as const
    const data = trend.map(p => getTargetValue(p, t.level, t.criteria))

    targetSeries.push({
      type: 'line',
      data,
      symbol: 'none',
      silent: true,
      lineStyle: { color, type: lineType, width: 1.5 },
      tooltip: { show: false },
    })
  }

  return {
    animation: false,
    backgroundColor: 'transparent',
    grid: { top: 16, bottom: 52, left: 56, right: 16 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: ct.bg,
      borderColor: ct.border,
      textStyle: { color: ct.axisLabel, fontSize: Math.round(12 * fontScale) },
      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : [params]
        const first = arr[0] as { dataIndex?: number } | undefined
        const idx = first?.dataIndex
        const p = idx != null ? trend[idx] : undefined
        if (!p) return ''
        const lines = [
          `<b style="color:#58a6ff">${p.evaluation_name ?? '(no evaluation_name)'}</b>`,
          `<b>${times[idx as number]}</b>`,
          `value: <b>${p.value}</b>`,
          `result: <b style="color:${colours[p.result as keyof typeof colours] ?? '#6b7280'}">${p.result.toUpperCase()}</b>`,
        ]
        return lines.join('<br/>')
      },
    },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { color: ct.axisLabel, fontSize: Math.round(9 * fontScale), rotate: 35 },
      axisLine: { lineStyle: { color: ct.grid } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      min: yMin !== '' ? parseFloat(yMin) : undefined,
      max: yMax !== '' ? parseFloat(yMax) : undefined,
      axisLabel: { color: ct.axisLabel, fontSize: Math.round(10 * fontScale) },
      splitLine: { lineStyle: { color: ct.grid } },
    },
    series: [
      {
        type: 'line',
        data: chartData,
        cursor: onEvalSelect ? 'pointer' : 'default',
        symbol: 'circle',
        symbolSize: (_val: unknown, params: { dataIndex: number }) => {
          const p = trend[params.dataIndex]
          return p && isSelected(p) ? 10 : 6
        },
        lineStyle: { color: ct.line, width: 1.5 },
      },
      ...targetSeries,
    ],
  }
}
```

- [ ] **Step 2: Run tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/hooks/useMetricTrendState.test.ts`

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```
git add ui/src/features/evaluations/hooks/useMetricTrendState.ts
git commit -m "feat: rewrite useMetricTrendState for multi-target baselines from trend data"
```

---

## Task 11: Update `MetricTrendBlock` with dropdown toggle

**Files:**
- Modify: `ui/src/features/evaluations/components/MetricTrendBlock.tsx`

- [ ] **Step 1: Replace the component**

Replace the entire contents of `ui/src/features/evaluations/components/MetricTrendBlock.tsx` with:

```tsx
// src/features/evaluations/components/MetricTrendBlock.tsx
import ReactECharts from 'echarts-for-react'
import { useCallback, useState, useRef, useEffect } from 'react'
import { Sheet, Tags } from 'lucide-react'
import { useTrend } from '../hooks'
import { STATUS_TEXT } from '@/lib/status'
import { useChartAreaClick } from '@/lib/useChartAreaClick'
import { useMetricTrendState } from '../hooks/useMetricTrendState'
import type { IndicatorResult } from '../types'

interface Props {
  assetName: string
  sloName: string
  sloDisplayName?: string
  selectedEvalId?: string
  selectedEvalIds?: ReadonlySet<string>
  selectedPeriodStart?: string
  indicator: IndicatorResult
  onEvalSelect?: (evalId: string) => void
  onScrollToTable?: () => void
  blockId?: string
}

function defaultScrollToTable() {
  document.getElementById('sli-table')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function TargetDropdown({ targets }: { targets: ReturnType<typeof useMetricTrendState>['targets'] }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  if (targets.length === 0) return null

  const activeCount = targets.filter(t => t.visible).length

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        className={`p-1 rounded border transition-colors ${
          activeCount > 0
            ? 'border-primary/40 text-primary'
            : 'border-border text-muted-foreground/60'
        }`}
        title="Toggle threshold lines"
      >
        <Tags className="size-3.5" />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 bg-popover border border-border rounded-lg shadow-lg py-1 min-w-[180px]">
          {targets.map(t => {
            const dotColor = t.level === 'pass'
              ? 'bg-pass'
              : t.level === 'warn'
                ? 'bg-warning'
                : 'bg-[#58a6ff]'
            return (
              <label
                key={t.key}
                className="flex items-center gap-2 px-3 py-1.5 hover:bg-muted/50 cursor-pointer text-xs"
              >
                <input
                  type="checkbox"
                  checked={t.visible}
                  onChange={t.toggle}
                  className="rounded border-border"
                />
                <span className={`size-2 rounded-full ${dotColor} shrink-0`} />
                <span className="text-foreground font-mono">{t.criteria}</span>
              </label>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function MetricTrendBlock({ assetName, sloName, sloDisplayName, selectedEvalId, selectedEvalIds, selectedPeriodStart, indicator, onEvalSelect, onScrollToTable, blockId }: Props) {
  const sloLabel = sloDisplayName ?? (sloName || null)
  const { data: trend, isLoading } = useTrend(assetName, sloName, indicator.metric)

  const handleClickIndex = useCallback(
    (idx: number) => {
      const pt = (trend ?? [])[idx]
      if (pt && onEvalSelect) onEvalSelect(pt.eval_id)
    },
    [trend, onEvalSelect],
  )

  const { chartRef, onContainerClick } = useChartAreaClick(
    onEvalSelect ? handleClickIndex : undefined,
    (trend ?? []).length,
  )

  const {
    yMin, yMax, setYMin, setYMax,
    targets,
    chartOption,
  } = useMetricTrendState(trend, selectedEvalId ?? '', indicator, onEvalSelect, selectedEvalIds, selectedPeriodStart)

  return (
    <div id={blockId ?? `trend-${indicator.metric}`} className="bg-card border border-border rounded-xl p-4 scroll-mt-4">
      <div className="relative flex items-center justify-between mb-1 gap-2">
        <span className={`text-xs font-semibold uppercase ${STATUS_TEXT[indicator.status] ?? 'text-muted-foreground'}`}>
          {indicator.status}
        </span>
        {sloLabel && (
          <span
            className="absolute left-1/2 -translate-x-1/2 text-xs font-semibold uppercase tracking-wide truncate max-w-[60%] text-center"
            style={{ color: '#58a6ff' }}
            title={sloName ? `SLO: ${sloName}` : undefined}
          >
            {sloLabel}
          </span>
        )}
        <button
          onClick={onScrollToTable ?? defaultScrollToTable}
          className="text-[#58a6ff]/60 hover:text-[#58a6ff] transition-colors"
          title="Go to SLI table"
          aria-label="Go to SLI table"
        >
          <Sheet className="size-5" />
        </button>
      </div>

      {isLoading ? (
        <div>
          <div className="text-xs text-muted-foreground mb-2">{indicator.display_name}</div>
          <div className="h-[200px] flex items-center justify-center text-muted-foreground/60 text-xs">loading…</div>
        </div>
      ) : (
        <div>
          <div className="flex items-center gap-3 mb-1">
            <span className="text-xs font-semibold text-foreground truncate" title={indicator.metric}>
              {indicator.display_name || indicator.metric}
            </span>
            <div className="flex items-center gap-1 ml-auto text-xs">
              <TargetDropdown targets={targets} />
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <label className="flex items-center gap-1">
                Y <input
                  type="number" value={yMin} onChange={e => setYMin(e.target.value)}
                  placeholder="min" className="w-14 px-1 py-0.5 bg-surface-sunken border border-border rounded text-foreground"
                />
              </label>
              <label className="flex items-center gap-1">
                – <input
                  type="number" value={yMax} onChange={e => setYMax(e.target.value)}
                  placeholder="max" className="w-14 px-1 py-0.5 bg-surface-sunken border border-border rounded text-foreground"
                />
              </label>
            </div>
          </div>
          <div onClick={onContainerClick} style={{ cursor: onEvalSelect ? 'crosshair' : undefined }}>
            <ReactECharts
              ref={chartRef}
              option={chartOption}
              style={{ height: 200 }}
              opts={{ renderer: 'svg' }}
              notMerge
            />
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Run lint**

Run: `./scripts/ui-lint.sh --tail 10 src/features/evaluations/components/MetricTrendBlock.tsx`

Expected: No lint errors.

- [ ] **Step 3: Run type check**

Run: `cd /home/domik/projects/tropek/ui && pnpm exec tsc --noEmit -p tsconfig.app.json`

Expected: No type errors.

- [ ] **Step 4: Commit**

```
git add ui/src/features/evaluations/components/MetricTrendBlock.tsx
git commit -m "feat: replace threshold pill buttons with Tags dropdown toggle"
```

---

## Task 12: Remove obsolete client-side threshold utils

**Files:**
- Modify: `ui/src/utils/metrics.ts`
- Modify: `ui/src/utils/metrics.test.ts`

- [ ] **Step 1: Remove `computeRelativeThresholdSeries` from `metrics.ts`**

In `ui/src/utils/metrics.ts`, remove the `computeRelativeThresholdSeries` function (lines 24-32) and its JSDoc comment (lines 15-23). Keep only `computeChangePct`.

The file should become:

```typescript
/**
 * Compute the relative percentage change between a current value and a baseline.
 *
 * When baseline is non-zero: standard (value - baseline) / |baseline| * 100
 * When baseline is zero:     treat denominator as 1, so the change equals value * 100
 *                            (0 → 2 = +200%, 0 → 0 = 0%)
 * When baseline is null:     no comparison available, returns null
 */
export function computeChangePct(value: number, baseline: number | null): number | null {
  if (baseline === null) return null
  const denominator = baseline === 0 ? 1 : Math.abs(baseline)
  return +((value - baseline) / denominator * 100).toFixed(2)
}
```

- [ ] **Step 2: Remove `computeRelativeThresholdSeries` tests from `metrics.test.ts`**

In `ui/src/utils/metrics.test.ts`, remove the import of `computeRelativeThresholdSeries` and the entire `describe('computeRelativeThresholdSeries', ...)` block (lines 47-72). Also update the import line:

```typescript
import { computeChangePct } from './metrics'
```

Keep only the `describe('computeChangePct', ...)` block.

- [ ] **Step 3: Check for remaining imports**

Verify no other file imports the removed functions:

Run: `grep -r "computeRelativeThresholdSeries\|isRelativeCriteria" ui/src/ --include="*.ts" --include="*.tsx"`

Expected: No results (all references were in the files we've already rewritten).

- [ ] **Step 4: Run all UI tests**

Run: `./scripts/ui-test.sh --tail 20`

Expected: All tests PASS.

- [ ] **Step 5: Run UI lint**

Run: `./scripts/ui-lint.sh --tail 10`

Expected: No lint errors.

- [ ] **Step 6: Commit**

```
git add ui/src/utils/metrics.ts ui/src/utils/metrics.test.ts
git commit -m "cleanup: remove computeRelativeThresholdSeries, now server-side"
```

---

## Task 13: Final verification

- [ ] **Step 1: Run full API unit tests**

Run: `./scripts/api-test.sh --tail 5`

Expected: All PASS.

- [ ] **Step 2: Run full API integration tests**

Run: `./scripts/api-test.sh --tail 5 -m integration -v`

Expected: All PASS.

- [ ] **Step 3: Run full UI test suite**

Run: `./scripts/ui-test.sh --tail 20`

Expected: All PASS.

- [ ] **Step 4: Run TypeScript type check**

Run: `cd /home/domik/projects/tropek/ui && pnpm exec tsc --noEmit -p tsconfig.app.json`

Expected: No type errors.

- [ ] **Step 5: Run Python lint + typecheck**

Run: `uv run ruff check api/ adapters/`

Run: `uv run mypy api/app adapters/prometheus/app`

Expected: No errors.

---

## File map summary

| File | Task | Action |
|------|------|--------|
| `api/app/db/models.py` | 1 | Add `targets` JSONB column |
| `api/alembic/versions/001_initial_schema.py` | 1 | Regenerated |
| `api/app/modules/quality_gate/worker.py` | 2 | Build targets dict from engine result |
| `api/app/modules/quality_gate/indicator_repository.py` | 2 | Persist `targets` in bulk_insert |
| `api/tests/db/test_indicator_repository.py` | 3 | Integration test for targets round-trip |
| `api/app/modules/quality_gate/presenter.py` | 4 | Read stored targets |
| `api/tests/services/test_presenter.py` | 4 | Test stored targets path |
| `api/app/modules/quality_gate/schemas/evaluations.py` | 5 | Add `TrendTargets`, `TrendTargetEntry` to `TrendPoint` |
| `api/app/modules/quality_gate/trend_repository.py` | 5 | Include targets in query + response |
| `api/tests/db/test_trend_query.py` | 6 | Integration test for targets in trend |
| `ui/src/lib/theme.ts` | 7 | Add `baseline` to `ChartTheme` |
| `ui/src/features/evaluations/types.ts` | 8 | Add `TrendTargetEntry`, `TrendTargets`, update `TrendPoint` |
| `ui/src/features/evaluations/hooks/useMetricTrendState.test.ts` | 9 | Rewrite tests |
| `ui/src/features/evaluations/hooks/useMetricTrendState.ts` | 10 | Rewrite hook + buildChartOption |
| `ui/src/features/evaluations/components/MetricTrendBlock.tsx` | 11 | Replace pills with Tags dropdown |
| `ui/src/utils/metrics.ts` | 12 | Remove `computeRelativeThresholdSeries` |
| `ui/src/utils/metrics.test.ts` | 12 | Remove related tests |
