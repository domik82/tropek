# Worker Pipeline Redesign — Multi-Phase Evaluation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate deadlocks and increase parallelism by splitting the monolithic `run_evaluation` transaction into three micro-transactions with HTTP I/O outside any open transaction.

**Architecture:** The current worker runs the entire evaluation (mark_running → HTTP adapter query → write results) in a single long-lived DB transaction that holds locks for 1-10 seconds. This causes FK-induced deadlocks when multiple workers process children of the same `EvaluationRun` concurrently. The fix splits `run_evaluation` into three phases: (1) mark_running + snapshot in its own committed transaction, (2) HTTP query + pure evaluation with NO open transaction, (3) write results in a short-lived transaction. Finalization moves to a separate deduped arq job.

**Tech Stack:** Python 3.13, SQLAlchemy async, arq, httpx, PostgreSQL/TimescaleDB

**Design doc:** `docs/backend-evaluation-flow.md` — full analysis with diagrams

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `api/app/queue.py` | **Major rewrite** | Split `run_evaluation_job` into phased flow, add `finalize_run_job`, register both in `WorkerSettings`, add shared httpx client to worker startup, remove deadlock retry loop |
| `api/app/modules/quality_gate/worker.py` | **Major rewrite** | Split `run_evaluation()` into 3 functions: `load_evaluation_snapshot()`, `fetch_and_evaluate()`, `write_results()` |
| `api/app/modules/quality_gate/adapter_client.py` | **Modify** | Accept external `httpx.AsyncClient` instead of creating one per call |
| `config.yaml` | **Modify** | Add `queue.max_jobs` setting |
| `api/app/config.py` | **Modify** | Read `queue.max_jobs` |
| `api/tests/test_queue.py` | **Rewrite** | Tests for new phased flow + finalize_run_job |
| `api/tests/engine/test_worker_finalize.py` | **Delete** | Merged into `test_queue.py` |
| `api/tests/engine/test_worker_phases.py` | **Create** | Unit tests for the 3 worker phase functions |

---

### Task 1: Make `HttpAdapterClient` accept an external httpx client

**Files:**
- Modify: `api/app/modules/quality_gate/adapter_client.py:13-57`
- Test: `api/tests/engine/test_adapter_client.py` (create)

The adapter client currently creates and closes a fresh `httpx.AsyncClient` per call. For connection reuse across concurrent jobs, it needs to accept an external client.

- [ ] **Step 1: Write test for external client injection**

Create `api/tests/engine/test_adapter_client.py`:

```python
"""Tests for HttpAdapterClient with injected httpx client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.modules.quality_gate.adapter_client import HttpAdapterClient


@pytest.fixture
def mock_response() -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.is_success = True
    resp.json.return_value = {
        'values': {'cpu_usage': 42.5},
        'errors': {},
        'metadata': {},
    }
    resp.raise_for_status = MagicMock()
    return resp


async def test_uses_injected_client(mock_response: MagicMock) -> None:
    """When an external httpx client is provided, it is used instead of creating a new one."""
    external_client = AsyncMock(spec=httpx.AsyncClient)
    external_client.post.return_value = mock_response

    client = HttpAdapterClient(timeout=10, http_client=external_client)
    values, errors, metadata = await client.query(
        adapter_url='http://adapter:8081',
        datasource_name='prom',
        queries={'cpu_usage': {'mode': 'raw', 'query': 'up'}},
        variables={},
        start='2026-01-01T00:00:00Z',
        end='2026-01-01T01:00:00Z',
    )

    external_client.post.assert_awaited_once()
    assert values == {'cpu_usage': 42.5}


async def test_creates_own_client_when_none_injected(mock_response: MagicMock) -> None:
    """When no external client is provided, creates and closes its own."""
    client = HttpAdapterClient(timeout=10)
    # We can't easily test this without hitting the network, so just verify construction
    assert client._http_client is None
    assert client._timeout == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/api-test.sh --tail 10 tests/engine/test_adapter_client.py -v`

Expected: FAIL — `HttpAdapterClient` does not accept `http_client` parameter.

- [ ] **Step 3: Implement external client injection**

Edit `api/app/modules/quality_gate/adapter_client.py`. Replace the `__init__` and `query` methods:

```python
class HttpAdapterClient:
    """Concrete adapter client that queries adapters over HTTP."""

    def __init__(
        self,
        timeout: float,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._timeout = timeout
        self._http_client = http_client

    async def query(
        self,
        *,
        adapter_url: str,
        datasource_name: str,
        queries: dict[str, dict[str, Any]],
        variables: dict[str, str],
        start: str,
        end: str,
    ) -> tuple[dict[str, float | None], dict[str, str], dict[str, Any]]:
        """Send metric queries to the adapter and return (values, errors, metadata)."""
        url = f'{adapter_url}/query'
        logger.info(
            'adapter request',
            url=url,
            datasource=datasource_name,
            query_count=len(queries),
            start=start,
            end=end,
            timeout=self._timeout,
        )
        payload = {
            'queries': queries,
            'variables': variables,
            'start': start,
            'end': end,
        }
        headers = {'X-Datasource-Name': datasource_name}

        if self._http_client is not None:
            resp = await self._http_client.post(url, headers=headers, json=payload)
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as http_client:
                resp = await http_client.post(url, headers=headers, json=payload)

        resp.raise_for_status()
        data = resp.json()

        metrics_fetched: dict[str, float | None] = {
            name: float(val) if val is not None else None
            for name, val in data.get('values', {}).items()
        }
        fetch_errors: dict[str, str] = {
            name: str(err) for name, err in data.get('errors', {}).items()
        }
        metadata: dict[str, Any] = data.get('metadata', {})
        logger.info(
            'adapter response',
            url=url,
            values_count=len(metrics_fetched),
            errors_count=len(fetch_errors),
            values=metrics_fetched,
            errors=fetch_errors,
            metadata=metadata,
        )
        return metrics_fetched, fetch_errors, metadata
```

The `health` method stays unchanged (it's called rarely, ephemeral client is fine).

- [ ] **Step 4: Run test to verify it passes**

Run: `./scripts/api-test.sh --tail 10 tests/engine/test_adapter_client.py -v`

Expected: PASS

- [ ] **Step 5: Run full unit test suite to check nothing broke**

Run: `./scripts/api-test.sh --tail 5`

Expected: All pass (no other code uses `HttpAdapterClient` constructor positionally).

- [ ] **Step 6: Commit**

```
feat: allow HttpAdapterClient to accept external httpx client
```

---

### Task 2: Split `run_evaluation` into three phase functions

This is the core refactor. The monolithic `run_evaluation()` (which does everything in one session) gets split into three independent functions that each receive plain data and return plain data.

**Files:**
- Modify: `api/app/modules/quality_gate/worker.py` (major rewrite)
- Test: `api/tests/engine/test_worker_phases.py` (create)

- [ ] **Step 1: Write tests for `load_evaluation_snapshot`**

Create `api/tests/engine/test_worker_phases.py`:

```python
"""Tests for the three worker phase functions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.quality_gate.worker import (
    EvaluationSnapshot,
    load_evaluation_snapshot,
)


def _make_ev(
    *,
    status: str = 'pending',
    slo_name: str = 'perf-slo',
    slo_version: int = 1,
    sli_name: str = 'system-sli',
    sli_version: int = 1,
) -> MagicMock:
    ev = MagicMock()
    ev.id = uuid.uuid4()
    ev.evaluation_id = uuid.uuid4()
    ev.status = status
    ev.slo_name = slo_name
    ev.slo_version = slo_version
    ev.sli_name = sli_name
    ev.sli_version = sli_version
    ev.data_source_name = 'prom-1'
    ev.evaluation_name = 'nightly'
    ev.period_start = datetime(2026, 1, 1, tzinfo=UTC)
    ev.period_end = datetime(2026, 1, 1, 1, tzinfo=UTC)
    ev.asset_snapshot = {'name': 'vm-01', 'tags': {}, 'variables': {}}
    ev.asset_id = uuid.uuid4()
    ev.variables = {}
    return ev


async def test_load_snapshot_marks_running_and_returns_snapshot() -> None:
    """Phase 1 marks the eval as running and returns a detached snapshot."""
    session = AsyncMock()
    ev = _make_ev()

    repo = AsyncMock()
    repo.get_by_id.return_value = ev

    with patch('app.modules.quality_gate.worker.EvaluationRepository', return_value=repo):
        snapshot = await load_evaluation_snapshot(session, ev.id, worker_id='w-1')

    repo.mark_running.assert_awaited_once_with(ev.id, 'w-1')
    assert isinstance(snapshot, EvaluationSnapshot)
    assert snapshot.eval_id == ev.id
    assert snapshot.parent_run_id == ev.evaluation_id
    assert snapshot.slo_name == 'perf-slo'


async def test_load_snapshot_returns_none_for_missing_eval() -> None:
    """Phase 1 returns None when the evaluation row doesn't exist."""
    session = AsyncMock()
    repo = AsyncMock()
    repo.get_by_id.return_value = None

    with patch('app.modules.quality_gate.worker.EvaluationRepository', return_value=repo):
        result = await load_evaluation_snapshot(session, uuid.uuid4(), worker_id='w-1')

    assert result is None


async def test_load_snapshot_returns_none_for_already_completed() -> None:
    """Phase 1 returns None when the evaluation is already completed (dedup guard)."""
    session = AsyncMock()
    ev = _make_ev(status='completed')
    repo = AsyncMock()
    repo.get_by_id.return_value = ev

    with patch('app.modules.quality_gate.worker.EvaluationRepository', return_value=repo):
        result = await load_evaluation_snapshot(session, ev.id, worker_id='w-1')

    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/api-test.sh --tail 10 tests/engine/test_worker_phases.py -v`

Expected: FAIL — `EvaluationSnapshot` and `load_evaluation_snapshot` don't exist.

- [ ] **Step 3: Write tests for `fetch_and_evaluate`**

Append to `api/tests/engine/test_worker_phases.py`:

```python
from app.modules.quality_gate.worker import (
    EvaluationSnapshot,
    FetchAndEvaluateResult,
    fetch_and_evaluate,
    load_evaluation_snapshot,
)


def _make_snapshot() -> EvaluationSnapshot:
    return EvaluationSnapshot(
        eval_id=uuid.uuid4(),
        parent_run_id=uuid.uuid4(),
        slo_name='perf-slo',
        slo_version=1,
        sli_name='system-sli',
        sli_version=1,
        data_source_name='prom-1',
        evaluation_name='nightly',
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=datetime(2026, 1, 1, 1, tzinfo=UTC),
        asset_snapshot={'name': 'vm-01', 'tags': {}, 'variables': {}},
        asset_id=uuid.uuid4(),
        variables={},
    )


def _make_slo_def() -> MagicMock:
    obj = MagicMock()
    obj.sli = 'cpu_usage'
    obj.display_name = 'CPU'
    obj.pass_threshold = ['<90']
    obj.warning_threshold = None
    obj.weight = 1
    obj.key_sli = False
    obj.id = uuid.uuid4()

    slo_def = MagicMock()
    slo_def.objectives = [obj]
    slo_def.total_score_pass_threshold = '90%'
    slo_def.total_score_warning_threshold = '75%'
    slo_def.comparison = None
    slo_def.variables = {}
    return slo_def


def _make_sli_def() -> MagicMock:
    sli_def = MagicMock()
    sli_def.name = 'system-sli'
    sli_def.mode = 'raw'
    sli_def.indicators = {'cpu_usage': 'rate(cpu_seconds_total[5m])'}
    return sli_def


async def test_fetch_and_evaluate_returns_result() -> None:
    """Phase 2 queries the adapter, evaluates, and returns the result without DB writes."""
    snapshot = _make_snapshot()
    slo_def = _make_slo_def()
    sli_def = _make_sli_def()

    mock_adapter = AsyncMock()
    mock_adapter.query.return_value = (
        {'cpu_usage': 42.5},  # values
        {},                    # errors
        {},                    # metadata
    )

    mock_ds = MagicMock()
    mock_ds.adapter_url = 'http://adapter:8081'

    mock_baseline_repo = AsyncMock()
    mock_baseline_repo.get_evaluation_baselines.return_value = []

    result = await fetch_and_evaluate(
        snapshot=snapshot,
        slo_def=slo_def,
        sli_def=sli_def,
        datasource=mock_ds,
        adapter_client=mock_adapter,
        baseline_repo=mock_baseline_repo,
    )

    assert isinstance(result, FetchAndEvaluateResult)
    assert result.eval_result is not None
    assert result.metrics_fetched == {'cpu_usage': 42.5}
    mock_adapter.query.assert_awaited_once()


async def test_fetch_and_evaluate_returns_none_on_adapter_failure() -> None:
    """Phase 2 returns None when the adapter is unreachable."""
    import httpx

    snapshot = _make_snapshot()
    slo_def = _make_slo_def()
    sli_def = _make_sli_def()

    mock_adapter = AsyncMock()
    mock_adapter.query.side_effect = httpx.ConnectError('connection refused')

    mock_ds = MagicMock()
    mock_ds.adapter_url = 'http://adapter:8081'

    result = await fetch_and_evaluate(
        snapshot=snapshot,
        slo_def=slo_def,
        sli_def=sli_def,
        datasource=mock_ds,
        adapter_client=mock_adapter,
        baseline_repo=AsyncMock(),
    )

    assert result is None
```

- [ ] **Step 4: Write tests for `write_results`**

Append to `api/tests/engine/test_worker_phases.py`:

```python
from app.modules.quality_gate.worker import write_results


async def test_write_results_commits_all_data() -> None:
    """Phase 3 writes mark_completed + indicator_rows + sli_values."""
    session = AsyncMock()
    snapshot = _make_snapshot()
    slo_def = _make_slo_def()
    sli_def = _make_sli_def()

    ir = MagicMock()
    ir.metric = 'cpu_usage'
    ir.value = 42.5
    ir.compared_value = None
    ir.change_absolute = None
    ir.change_relative_pct = None
    ir.status = 'pass'
    ir.score = 1.0

    eval_result = MagicMock()
    eval_result.result = 'pass'
    eval_result.score = 100.0
    eval_result.indicator_results = [ir]

    fetch_result = FetchAndEvaluateResult(
        eval_result=eval_result,
        metrics_fetched={'cpu_usage': 42.5},
        fetch_errors={},
        sli_metadata={},
        baselines={},
        compared_eval_ids=[],
    )

    mock_eval_repo = AsyncMock()
    mock_indicator_repo = AsyncMock()
    mock_sli_repo = AsyncMock()

    with (
        patch('app.modules.quality_gate.worker.EvaluationRepository', return_value=mock_eval_repo),
        patch('app.modules.quality_gate.worker.IndicatorRepository', return_value=mock_indicator_repo),
        patch('app.modules.quality_gate.worker.SLIValueRepository', return_value=mock_sli_repo),
    ):
        await write_results(
            session=session,
            snapshot=snapshot,
            slo_def=slo_def,
            sli_def=sli_def,
            fetch_result=fetch_result,
        )

    mock_eval_repo.mark_completed.assert_awaited_once()
    mock_indicator_repo.bulk_insert.assert_awaited_once()
    mock_sli_repo.write_sli_values.assert_awaited_once()
```

- [ ] **Step 5: Run all phase tests to verify they fail**

Run: `./scripts/api-test.sh --tail 20 tests/engine/test_worker_phases.py -v`

Expected: FAIL — imports don't exist yet.

- [ ] **Step 6: Implement the three phase functions**

Rewrite `api/app/modules/quality_gate/worker.py`. The file keeps all existing helper functions (`_load_definitions`, `_resolve_baselines`, `_build_eval_variables`, `_build_query_specs`, `_build_sli_rows`, `_log_adapter_response`, `_log_eval_result`) but replaces the monolithic `run_evaluation` with three functions and two dataclasses.

Add at the top of the file (after existing imports):

```python
from pydantic import BaseModel


class EvaluationSnapshot(BaseModel):
    """Detached snapshot of everything needed to run an evaluation without a DB session."""

    model_config = {'arbitrary_types_allowed': True}

    eval_id: uuid.UUID
    parent_run_id: uuid.UUID
    slo_name: str
    slo_version: int
    sli_name: str | None
    sli_version: int | None
    data_source_name: str | None
    evaluation_name: str
    period_start: datetime
    period_end: datetime
    asset_snapshot: dict[str, Any]
    asset_id: uuid.UUID
    variables: dict[str, Any]


class FetchAndEvaluateResult(BaseModel):
    """Output of fetch_and_evaluate — everything needed to write results."""

    model_config = {'arbitrary_types_allowed': True}

    eval_result: Any  # engine EvaluationResult
    metrics_fetched: dict[str, float | None]
    fetch_errors: dict[str, str]
    sli_metadata: dict[str, Any]
    baselines: dict[str, float | None]
    compared_eval_ids: list[str]
```

Add `datetime` to the imports from `datetime` module (it's used in the snapshot).

Then add the three phase functions:

```python
async def load_evaluation_snapshot(
    session: AsyncSession,
    eval_id: uuid.UUID,
    *,
    worker_id: str | None = None,
) -> EvaluationSnapshot | None:
    """Phase 1: Mark running and return a detached snapshot.

    Caller should COMMIT after this returns. The snapshot contains all data
    needed to run the evaluation without holding a DB session open.
    """
    log = logger.bind(evaluation_id=str(eval_id), worker_id=worker_id)
    repo = EvaluationRepository(session)
    await repo.mark_running(eval_id, worker_id)

    ev = await repo.get_by_id(eval_id)
    if ev is None:
        log.error('evaluation not found, cannot proceed')
        return None

    if ev.status not in ('pending', 'running'):
        log.warning('evaluation already processed, skipping', status=ev.status)
        return None

    log.info('evaluation snapshot loaded', slo_name=ev.slo_name, asset=ev.asset_snapshot.get('name'))

    return EvaluationSnapshot(
        eval_id=ev.id,
        parent_run_id=ev.evaluation_id,
        slo_name=ev.slo_name,
        slo_version=ev.slo_version,
        sli_name=ev.sli_name,
        sli_version=ev.sli_version,
        data_source_name=ev.data_source_name,
        evaluation_name=ev.evaluation_name,
        period_start=ev.period_start,
        period_end=ev.period_end,
        asset_snapshot=ev.asset_snapshot or {},
        asset_id=ev.asset_id,
        variables=ev.variables or {},
    )


async def fetch_and_evaluate(
    *,
    snapshot: EvaluationSnapshot,
    slo_def: SLODefinition,
    sli_def: SLIDefinition,
    datasource: DataSource,
    adapter_client: HttpAdapterClient,
    baseline_repo: BaselineRepository,
) -> FetchAndEvaluateResult | None:
    """Phase 2: Query adapter, resolve baselines, evaluate. No DB writes.

    Returns None if the adapter query fails. Caller handles marking failed.
    """
    log = logger.bind(evaluation_id=str(snapshot.eval_id))

    slo = build_slo(
        objectives=[
            {
                'sli': obj.sli,
                'display_name': obj.display_name,
                'pass_threshold': obj.pass_threshold,
                'warning_threshold': obj.warning_threshold,
                'weight': obj.weight,
                'key_sli': obj.key_sli,
            }
            for obj in slo_def.objectives
        ],
        total_score_pass_threshold=slo_def.total_score_pass_threshold,
        total_score_warning_threshold=slo_def.total_score_warning_threshold,
        comparison=slo_def.comparison,
    )

    variables = _build_eval_variables(snapshot, snapshot.asset_snapshot, slo_def)

    resolved_queries: dict[str, str] = {}
    if sli_def.mode == 'raw':
        resolved_queries = {
            name: substitute_variables(tmpl, variables)
            for name, tmpl in sli_def.indicators.items()
        }

    query_specs = _build_query_specs(sli_def, resolved_queries)

    log.info(
        'querying adapter',
        adapter_url=datasource.adapter_url,
        metric_count=len(query_specs),
        sli_mode=sli_def.mode,
    )

    try:
        metrics_fetched, fetch_errors, sli_metadata = await adapter_client.query(
            adapter_url=datasource.adapter_url,
            datasource_name=datasource.name,
            queries=query_specs,
            variables=variables,
            start=snapshot.period_start.isoformat(),
            end=snapshot.period_end.isoformat(),
        )
    except Exception:
        log.exception('adapter query failed', adapter_url=datasource.adapter_url)
        return None

    _log_adapter_response(log, metrics_fetched, fetch_errors, sli_metadata)

    indicator_names = (
        list(sli_def.indicators)
        if sli_def.mode == 'raw'
        else [obj.sli for obj in slo.objectives]
    )
    baselines, compared_eval_ids = await _resolve_baselines(
        baseline_repo=baseline_repo, slo=slo, ev=snapshot, indicator_names=indicator_names,
    )
    eval_result = evaluate(slo, metrics_fetched, baselines, compared_eval_ids)

    _log_eval_result(log, eval_result, metrics_fetched, baselines)

    return FetchAndEvaluateResult(
        eval_result=eval_result,
        metrics_fetched=metrics_fetched,
        fetch_errors=fetch_errors,
        sli_metadata=sli_metadata,
        baselines=baselines,
        compared_eval_ids=compared_eval_ids,
    )


async def write_results(
    *,
    session: AsyncSession,
    snapshot: EvaluationSnapshot,
    slo_def: SLODefinition,
    sli_def: SLIDefinition,
    fetch_result: FetchAndEvaluateResult,
) -> None:
    """Phase 3: Write evaluation results to the database.

    Caller should COMMIT after this returns.
    """
    log = logger.bind(evaluation_id=str(snapshot.eval_id))
    er = fetch_result.eval_result
    repo = EvaluationRepository(session)

    achieved_points = sum(round(ir.score) for ir in er.indicator_results)
    total_points = sum(int(obj.weight) for obj in slo_def.objectives)

    await repo.mark_completed(
        snapshot.eval_id,
        result=er.result,
        score=er.score,
        slo_name=snapshot.slo_name,
        slo_version=snapshot.slo_version,
        job_stats={
            'fetch_errors': fetch_result.fetch_errors,
            'total_score_pass_threshold': slo_def.total_score_pass_threshold,
            'total_score_warning_threshold': slo_def.total_score_warning_threshold,
            **({'sli_metadata': fetch_result.sli_metadata} if fetch_result.sli_metadata else {}),
        },
        compared_evaluation_ids=fetch_result.compared_eval_ids,
        achieved_points=achieved_points,
        total_points=total_points,
    )

    await _write_indicator_rows(log, session, snapshot.eval_id, slo_def, er.indicator_results)

    sli_rows = _build_sli_rows(
        eval_id=snapshot.eval_id,
        ev=snapshot,
        sli_def=sli_def,
        indicator_results=er.indicator_results,
        asset_snapshot=snapshot.asset_snapshot,
    )
    if sli_rows:
        sli_repo = SLIValueRepository(session)
        await sli_repo.write_sli_values(sli_rows)

    log.info('results written', result=er.result, score=er.score)
```

**Important compatibility changes needed in helper functions:**

The helpers `_build_eval_variables` and `_build_sli_rows` currently accept an `SLOEvaluation` ORM object (parameter named `ev`). They access `ev.period_start`, `ev.evaluation_name`, `ev.asset_snapshot`, etc. The `EvaluationSnapshot` Pydantic model has the same field names, so these helpers work without changes — Python duck typing handles it.

The `_resolve_baselines` helper also takes `ev` and accesses `ev.asset_id`, `ev.slo_name`, `ev.period_start` — all present on `EvaluationSnapshot`. No changes needed.

**Remove the old `run_evaluation` function** entirely. It is replaced by the three phase functions orchestrated from `queue.py`.

- [ ] **Step 7: Run all phase tests**

Run: `./scripts/api-test.sh --tail 20 tests/engine/test_worker_phases.py -v`

Expected: All PASS.

- [ ] **Step 8: Commit**

```
refactor: split run_evaluation into three phase functions

load_evaluation_snapshot (Phase 1): mark running + snapshot
fetch_and_evaluate (Phase 2): HTTP query + evaluate, no DB writes
write_results (Phase 3): commit results to DB
```

---

### Task 3: Add `max_jobs` to config

**Files:**
- Modify: `config.yaml`
- Modify: `api/app/config.py:104-111`

- [ ] **Step 1: Add `max_jobs` to config.yaml**

```yaml
queue:
  backend: "redis"
  db_index: 1
  max_jobs: 10
  max_retries: 3
  retry_delay_seconds: 10
  job_timeout_seconds: 120
  keep_result_seconds: 3600
```

- [ ] **Step 2: Add `max_jobs` to QueueSettings**

In `api/app/config.py`, add to the `QueueSettings` class:

```python
class QueueSettings(BaseSettings):
    """arq job queue configuration (uses Redis db_index separate from cache)."""

    db_index: int = _yaml.get('queue', {}).get('db_index', 1)
    max_jobs: int = _yaml.get('queue', {}).get('max_jobs', 10)
    max_retries: int = _yaml.get('queue', {}).get('max_retries', 3)
    retry_delay_seconds: int = _yaml.get('queue', {}).get('retry_delay_seconds', 10)
    job_timeout_seconds: int = _yaml.get('queue', {}).get('job_timeout_seconds', 120)
    keep_result_seconds: int = _yaml.get('queue', {}).get('keep_result_seconds', 3600)
```

- [ ] **Step 3: Commit**

```
feat: add queue.max_jobs config setting (default 10)
```

---

### Task 4: Rewrite `queue.py` — phased job + finalize job

This is the orchestrator rewrite. The monolithic `run_evaluation_job` with deadlock retry becomes a clean phased pipeline. The `_finalize_parent_run` becomes its own arq job.

**Files:**
- Modify: `api/app/queue.py` (major rewrite)
- Test: `api/tests/test_queue.py` (rewrite)

- [ ] **Step 1: Write tests for the new `run_evaluation_job`**

Rewrite `api/tests/test_queue.py`:

```python
"""Tests for phased run_evaluation_job and finalize_run_job."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.queue import finalize_run_job, run_evaluation_job


def _fake_snapshot(
    eval_id: uuid.UUID | None = None,
    parent_run_id: uuid.UUID | None = None,
) -> MagicMock:
    from app.modules.quality_gate.worker import EvaluationSnapshot

    s = MagicMock(spec=EvaluationSnapshot)
    s.eval_id = eval_id or uuid.uuid4()
    s.parent_run_id = parent_run_id or uuid.uuid4()
    s.slo_name = 'perf-slo'
    s.slo_version = 1
    s.sli_name = 'system-sli'
    s.sli_version = 1
    s.data_source_name = 'prom-1'
    return s


def _fake_fetch_result() -> MagicMock:
    from app.modules.quality_gate.worker import FetchAndEvaluateResult

    r = MagicMock(spec=FetchAndEvaluateResult)
    r.eval_result = MagicMock()
    r.eval_result.result = 'pass'
    return r


@pytest.fixture
def session_factory():
    """Mock session factory returning async context manager sessions."""
    sessions: list[AsyncMock] = []

    def factory():
        s = AsyncMock()
        sessions.append(s)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=s)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    return factory, sessions


def _base_patches():
    """Common patches for all tests — disables predecessor check."""
    return patch(
        'app.queue._has_pending_predecessor',
        new_callable=AsyncMock,
        return_value=False,
    )


# --- Happy path ---


async def test_happy_path_three_phases(session_factory: tuple) -> None:
    """Job runs 3 phases in 3 separate sessions and enqueues finalize."""
    factory, sessions = session_factory
    parent_run_id = uuid.uuid4()
    snapshot = _fake_snapshot(parent_run_id=parent_run_id)
    fetch_result = _fake_fetch_result()
    mock_pool = AsyncMock()

    slo_def = MagicMock()
    sli_def = MagicMock()
    ds = MagicMock()

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue.load_evaluation_snapshot', new_callable=AsyncMock, return_value=snapshot),
        patch('app.queue._load_definitions_cached', new_callable=AsyncMock, return_value=(slo_def, sli_def)),
        patch('app.queue._load_datasource', new_callable=AsyncMock, return_value=ds),
        patch('app.queue.fetch_and_evaluate', new_callable=AsyncMock, return_value=fetch_result),
        patch('app.queue.write_results', new_callable=AsyncMock),
        _base_patches(),
    ):
        ctx = {'cache': None, 'redis': mock_pool, 'job_id': 'w-1', 'http_client': AsyncMock()}
        await run_evaluation_job(ctx, str(uuid.uuid4()))

    # 3 sessions: phase 1 (snapshot), phase 2 (baselines), phase 3 (write)
    assert len(sessions) == 3
    # Each session committed
    for s in sessions:
        s.commit.assert_awaited_once()
    # Finalize job enqueued
    mock_pool.enqueue_job.assert_awaited_once()
    call_args = mock_pool.enqueue_job.call_args
    assert call_args[0][0] == 'finalize_run_job'
    assert call_args[1]['_job_id'] == f'finalize:{parent_run_id}'


# --- Phase 1 early exits ---


async def test_snapshot_none_skips_remaining_phases(session_factory: tuple) -> None:
    """When load_evaluation_snapshot returns None, no further phases run."""
    factory, sessions = session_factory

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue.load_evaluation_snapshot', new_callable=AsyncMock, return_value=None),
        patch('app.queue.fetch_and_evaluate', new_callable=AsyncMock) as mock_fetch,
        _base_patches(),
    ):
        await run_evaluation_job({}, str(uuid.uuid4()))

    mock_fetch.assert_not_awaited()
    assert len(sessions) == 1  # only phase 1 session


# --- Phase 2 adapter failure ---


async def test_adapter_failure_marks_failed(session_factory: tuple) -> None:
    """When fetch_and_evaluate returns None, evaluation is marked failed."""
    factory, sessions = session_factory
    snapshot = _fake_snapshot()

    mock_eval_repo = AsyncMock()

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue.load_evaluation_snapshot', new_callable=AsyncMock, return_value=snapshot),
        patch('app.queue._load_definitions_cached', new_callable=AsyncMock, return_value=(MagicMock(), MagicMock())),
        patch('app.queue._load_datasource', new_callable=AsyncMock, return_value=MagicMock()),
        patch('app.queue.fetch_and_evaluate', new_callable=AsyncMock, return_value=None),
        patch('app.queue.EvaluationRepository', return_value=mock_eval_repo),
        patch('app.queue.write_results', new_callable=AsyncMock) as mock_write,
        _base_patches(),
    ):
        ctx = {'cache': None, 'redis': AsyncMock(), 'job_id': 'w-1', 'http_client': AsyncMock()}
        await run_evaluation_job(ctx, str(uuid.uuid4()))

    mock_eval_repo.mark_failed.assert_awaited_once()
    mock_write.assert_not_awaited()


# --- Finalize job ---


async def test_finalize_run_job_completes_parent(session_factory: tuple) -> None:
    """finalize_run_job calls finalize_if_all_done and commits."""
    factory, sessions = session_factory
    run_id = uuid.uuid4()
    mock_run_repo = AsyncMock()
    mock_run_repo.finalize_if_all_done.return_value = MagicMock(result='pass')

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue.EvaluationRunRepository', return_value=mock_run_repo),
    ):
        await finalize_run_job({}, str(run_id))

    mock_run_repo.finalize_if_all_done.assert_awaited_once_with(run_id)
    sessions[0].commit.assert_awaited_once()


async def test_finalize_run_job_noop_when_children_pending(session_factory: tuple) -> None:
    """finalize_run_job does nothing when children are still pending."""
    factory, sessions = session_factory
    mock_run_repo = AsyncMock()
    mock_run_repo.finalize_if_all_done.return_value = None

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue.EvaluationRunRepository', return_value=mock_run_repo),
    ):
        await finalize_run_job({}, str(uuid.uuid4()))

    sessions[0].commit.assert_awaited_once()


# --- Predecessor deferral (unchanged behavior) ---


async def test_predecessor_defers_job(session_factory: tuple) -> None:
    """Job is deferred when a predecessor evaluation is still pending."""
    factory, _sessions = session_factory
    mock_pool = AsyncMock()

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue._has_pending_predecessor', new_callable=AsyncMock, return_value=True),
        patch('app.queue.load_evaluation_snapshot', new_callable=AsyncMock) as mock_load,
    ):
        await run_evaluation_job(
            {'redis': mock_pool},
            '00000000-0000-0000-0000-000000000001',
        )

    mock_load.assert_not_awaited()
    mock_pool.enqueue_job.assert_awaited_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/api-test.sh --tail 10 tests/test_queue.py -v`

Expected: FAIL — `finalize_run_job`, `load_evaluation_snapshot` etc. not importable from new `queue.py` yet.

- [ ] **Step 3: Implement the new `queue.py`**

Rewrite `api/app/queue.py`:

```python
"""arq job queue — worker settings, phased evaluation pipeline, and pool dependency."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, ClassVar, cast

import httpx
import redis.asyncio as aioredis
import structlog
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_cache import RedisCache
from app.config import get_settings
from app.db.session import get_session_factory
from app.logging_config import configure_logging
from app.modules.datasource.repository import DataSourceRepository
from app.modules.quality_gate.adapter_client import HttpAdapterClient
from app.modules.quality_gate.baseline_repository import BaselineRepository
from app.modules.quality_gate.evaluation_run_repository import EvaluationRunRepository
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.worker import (
    DefinitionLoadError,
    EvaluationSnapshot,
    fetch_and_evaluate,
    load_evaluation_snapshot,
    write_results,
)
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_registry.repository import SLORepository

logger = structlog.get_logger()

_MAX_PREDECESSOR_DEFERS = 60


async def _has_pending_predecessor(session_factory: Any, eval_id: uuid.UUID) -> bool:
    """Check if an earlier eval for the same asset+SLO is still pending/running."""
    try:
        async with session_factory() as session:
            repo = EvaluationRepository(session)
            ev = await repo.get_by_id(eval_id)
            if ev is None or ev.status not in ('pending', 'running'):
                return False
            return await repo.has_pending_predecessor(
                asset_id=ev.asset_id,
                slo_name=ev.slo_name,
                period_start=ev.period_start,
            )
    except (OSError, ValueError, AttributeError):
        logger.warning('predecessor check failed, proceeding', evaluation_id=str(eval_id))
        return False


def _redis_settings() -> RedisSettings:
    """Build arq RedisSettings from application config."""
    settings = get_settings()
    pw = settings.cache.password.get_secret_value()
    return RedisSettings(
        host=settings.cache.host,
        port=settings.cache.port,
        password=pw or None,
        database=settings.queue.db_index,
    )


def get_arq_pool(request: Request) -> ArqRedis:
    """FastAPI dependency — returns the arq pool stored on app.state at startup."""
    pool = getattr(request.app.state, 'arq_pool', None)
    if pool is None:
        raise RuntimeError('arq pool not initialised — lifespan did not run')
    return cast('ArqRedis', pool)


async def create_arq_pool() -> ArqRedis:
    """Create and return an arq connection pool using application config."""
    return await create_pool(_redis_settings())


async def _worker_startup(ctx: dict[str, Any]) -> None:
    """Initialize shared resources for worker processes."""
    configure_logging(service_name='worker')
    settings = get_settings()
    redis_client = aioredis.from_url(settings.cache.url)
    ctx['cache'] = RedisCache(redis_client)
    ctx['http_client'] = httpx.AsyncClient(
        timeout=settings.reliability.adapter_timeout_seconds,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )


async def _worker_shutdown(ctx: dict[str, Any]) -> None:
    """Close shared connections."""
    cache: RedisCache | None = ctx.get('cache')
    if cache and cache._redis:
        await cache._redis.close()
    http_client: httpx.AsyncClient | None = ctx.get('http_client')
    if http_client:
        await http_client.aclose()


async def _load_definitions_cached(
    session: AsyncSession,
    snapshot: EvaluationSnapshot,
    cache: RedisCache | None,
) -> tuple[Any, Any]:
    """Load SLO + SLI definitions (cache-backed, short-lived session read)."""
    from app.modules.quality_gate.worker import _load_definitions

    # Build a minimal object that _load_definitions can read slo_name/version from
    return await _load_definitions(session, snapshot, cache=cache)


async def _load_datasource(session: AsyncSession, name: str) -> Any:
    """Load datasource by name."""
    ds = await DataSourceRepository(session).get_by_name(name)
    if ds is None:
        msg = f"datasource '{name}' not found"
        raise DefinitionLoadError(msg)
    return ds


async def run_evaluation_job(ctx: dict[str, Any], eval_id_str: str, defer_count: int = 0) -> None:
    """Arq job — phased evaluation pipeline.

    Phase 1: mark_running + snapshot (own transaction, ~5ms)
    Phase 2: load definitions + HTTP adapter query + evaluate (no locks during HTTP)
    Phase 3: write results (own transaction, ~15ms)
    Then: enqueue deduped finalize job for the parent run.
    """
    session_factory = get_session_factory()
    eval_id = uuid.UUID(eval_id_str)
    cache: RedisCache | None = ctx.get('cache')
    log = logger.bind(evaluation_id=eval_id_str)

    # Predecessor deferral (unchanged)
    if defer_count < _MAX_PREDECESSOR_DEFERS and await _has_pending_predecessor(
        session_factory, eval_id
    ):
        log.info(
            'deferring evaluation — predecessor still pending',
            defer_count=defer_count + 1,
        )
        pool: ArqRedis = ctx['redis']
        await pool.enqueue_job(
            'run_evaluation_job',
            eval_id_str,
            defer_count + 1,
            _defer_by=timedelta(seconds=2),
        )
        return

    # === Phase 1: Mark running + snapshot (COMMIT immediately) ===
    async with session_factory() as session:
        snapshot = await load_evaluation_snapshot(session, eval_id, worker_id=ctx.get('job_id'))
        await session.commit()

    if snapshot is None:
        return

    # === Phase 2a: Load definitions (short read session) ===
    try:
        async with session_factory() as session:
            slo_def, sli_def = await _load_definitions_cached(session, snapshot, cache)
            datasource = await _load_datasource(session, snapshot.data_source_name)
            # Read-only — commit just closes the transaction cleanly
            await session.commit()
    except DefinitionLoadError as exc:
        log.warning('definitions not found', reason=str(exc))
        async with session_factory() as session:
            await EvaluationRepository(session).mark_failed(
                eval_id, job_stats={'error': str(exc)},
            )
            await session.commit()
        return

    # === Phase 2b: HTTP query + evaluate (NO open transaction) ===
    http_client: httpx.AsyncClient | None = ctx.get('http_client')
    adapter_client = HttpAdapterClient(
        timeout=get_settings().reliability.adapter_timeout_seconds,
        http_client=http_client,
    )

    # Baselines need a short read session
    async with session_factory() as session:
        baseline_repo = BaselineRepository(session, cache=cache)
        fetch_result = await fetch_and_evaluate(
            snapshot=snapshot,
            slo_def=slo_def,
            sli_def=sli_def,
            datasource=datasource,
            adapter_client=adapter_client,
            baseline_repo=baseline_repo,
        )
        await session.commit()

    if fetch_result is None:
        async with session_factory() as session:
            await EvaluationRepository(session).mark_failed(
                eval_id, job_stats={'error': 'adapter query failed'},
            )
            await session.commit()
        return

    # === Phase 3: Write results (COMMIT immediately) ===
    async with session_factory() as session:
        await write_results(
            session=session,
            snapshot=snapshot,
            slo_def=slo_def,
            sli_def=sli_def,
            fetch_result=fetch_result,
        )
        await session.commit()

    log.info('evaluation completed', result=fetch_result.eval_result.result)

    # === Enqueue deduped finalize for parent run ===
    pool = ctx['redis']
    await pool.enqueue_job(
        'finalize_run_job',
        str(snapshot.parent_run_id),
        _job_id=f'finalize:{snapshot.parent_run_id}',
    )


async def finalize_run_job(ctx: dict[str, Any], run_id_str: str) -> None:
    """Arq job — finalize parent EvaluationRun when all children are done.

    Deduped via _job_id so only one runs per parent, regardless of how many
    children enqueue it. Idempotent — safe to run multiple times.
    """
    session_factory = get_session_factory()
    run_id = uuid.UUID(run_id_str)

    async with session_factory() as session:
        run_repo = EvaluationRunRepository(session)
        finalized = await run_repo.finalize_if_all_done(run_id)
        await session.commit()

    if finalized is not None:
        logger.info(
            'parent evaluation run completed',
            evaluation_id=run_id_str,
            result=finalized.result,
        )


class WorkerSettings:
    """arq worker configuration — discovered by `arq app.queue.WorkerSettings`."""

    functions: ClassVar[list[Any]] = [run_evaluation_job, finalize_run_job]
    on_startup = _worker_startup
    on_shutdown = _worker_shutdown
    max_jobs = get_settings().queue.max_jobs
    redis_settings = _redis_settings()
```

**Key differences from old code:**
- No deadlock retry loop (transactions are <50ms now)
- No `_finalize_parent_run` inline function — it's `finalize_run_job`
- `_worker_startup` creates shared `httpx.AsyncClient` in `ctx['http_client']`
- `_worker_shutdown` closes it
- `WorkerSettings.functions` includes both job types
- `WorkerSettings.max_jobs` set from config

- [ ] **Step 4: Run the new queue tests**

Run: `./scripts/api-test.sh --tail 20 tests/test_queue.py -v`

Expected: All PASS.

- [ ] **Step 5: Commit**

```
refactor: rewrite queue.py with phased evaluation pipeline

- Split monolithic run_evaluation_job into 3 micro-transactions
- HTTP adapter query runs outside any DB transaction
- Finalization is a separate deduped arq job (finalize_run_job)
- Shared httpx.AsyncClient per worker process
- max_jobs configurable (default 10 concurrent jobs per worker)
- Deadlock retry loop removed (transactions now <50ms)
```

---

### Task 5: Fix `_load_definitions` to accept `EvaluationSnapshot`

The `_load_definitions` helper in `worker.py` currently type-hints its second parameter as `SLOEvaluation`. It needs to accept `EvaluationSnapshot` too (duck typing works, but the type hint should be accurate).

**Files:**
- Modify: `api/app/modules/quality_gate/worker.py:37-67`

- [ ] **Step 1: Update `_load_definitions` signature**

Change the `ev` parameter type from `SLOEvaluation` to accept either:

```python
async def _load_definitions(
    session: AsyncSession,
    ev: SLOEvaluation | EvaluationSnapshot,
    cache: RedisCache | None = None,
) -> tuple[SLODefinition, SLIDefinition]:
```

The function body only accesses `ev.slo_name`, `ev.slo_version`, `ev.sli_name`, `ev.sli_version` — all present on both types.

- [ ] **Step 2: Run mypy**

Run: `uv run mypy api/app/modules/quality_gate/worker.py --no-error-summary`

Expected: No new errors.

- [ ] **Step 3: Commit**

```
fix: widen _load_definitions signature to accept EvaluationSnapshot
```

---

### Task 6: Delete old `test_worker_finalize.py` and clean up old `run_evaluation` references

**Files:**
- Delete: `api/tests/engine/test_worker_finalize.py`
- Modify: `api/tests/test_queue.py` (already done in Task 4)

- [ ] **Step 1: Delete the old finalize test file**

```bash
git rm api/tests/engine/test_worker_finalize.py
```

- [ ] **Step 2: Grep for any remaining references to old `run_evaluation` import**

Search for `from app.modules.quality_gate.worker import run_evaluation` or `from app.queue import run_evaluation` in the codebase (outside of worker.py and queue.py themselves). The `run_evaluation` function no longer exists — it's been replaced by the three phase functions.

Check these files and fix any remaining imports:
- `api/app/queue.py` — should import `load_evaluation_snapshot`, `fetch_and_evaluate`, `write_results` (done in Task 4)
- Any integration tests referencing `run_evaluation` directly

- [ ] **Step 3: Run full unit test suite**

Run: `./scripts/api-test.sh --tail 5`

Expected: All pass with no import errors.

- [ ] **Step 4: Commit**

```
chore: remove old test_worker_finalize and clean up run_evaluation references
```

---

### Task 7: Run integration tests to verify end-to-end

This task doesn't write new code — it validates that the refactored worker pipeline works with a real database.

**Files:**
- None (verification only)

- [ ] **Step 1: Start test infrastructure**

```bash
just test-env
```

- [ ] **Step 2: Run integration tests**

```bash
./scripts/api-test.sh --tail 20 -m integration -v
```

Expected: All integration tests pass. The trigger_evaluate tests create pending evaluations and verify they're created correctly — they don't actually run the worker, so they should be unaffected.

- [ ] **Step 3: Run the full test suite (unit + integration)**

```bash
./scripts/api-test.sh --tail 10
```

Expected: All pass.

- [ ] **Step 4: Run linter and type checker**

```bash
uv run ruff check api/app/queue.py api/app/modules/quality_gate/worker.py api/app/modules/quality_gate/adapter_client.py
```

```bash
uv run mypy api/app/modules/quality_gate/worker.py api/app/queue.py
```

Expected: No errors.

- [ ] **Step 5: Tear down test infrastructure**

```bash
just test-env-down
```

---

### Task 8: Update the deadlock bug doc

**Files:**
- Modify: `docs/bug-evaluation-run-rollup-deadlock.md`

- [ ] **Step 1: Add resolution section to the bug doc**

Append to `docs/bug-evaluation-run-rollup-deadlock.md`:

```markdown
## Resolution (2026-04-04)

The root cause — long transactions holding FK locks across HTTP I/O — was eliminated
by splitting `run_evaluation` into three micro-transactions:

1. **Phase 1** (mark_running + snapshot) — 5ms transaction, COMMIT immediately
2. **Phase 2** (HTTP adapter query + evaluate) — NO open DB transaction
3. **Phase 3** (write results) — 15ms transaction, COMMIT immediately

Finalization moved to a separate deduped arq job (`finalize_run_job`), eliminating
both the in-transaction deadlock and the 20× redundant finalize attempts.

The deadlock retry loop in `queue.py` was removed entirely as transactions are now
too short (<50ms) to deadlock. arq `max_jobs=10` was enabled for 40× parallelism
(4 workers × 10 concurrent async jobs).

See `docs/backend-evaluation-flow.md` for the full architecture analysis.
```

- [ ] **Step 2: Commit**

```
docs: mark deadlock bug as resolved with pipeline redesign
```
