"""Tests for the three-phase worker functions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from app.modules.quality_gate.worker import (
    EvaluationSnapshot,
    FetchAndEvaluateResult,
    fetch_and_evaluate,
    load_evaluation_snapshot,
    write_results,
    write_sli_values_phase,
)

EVAL_ID = uuid.uuid4()
PARENT_RUN_ID = uuid.uuid4()
ASSET_ID = uuid.uuid4()
NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
LATER = datetime(2025, 6, 1, 13, 0, 0, tzinfo=UTC)


def _make_orm_evaluation(
    *,
    status: str = 'running',
    eval_id: uuid.UUID = EVAL_ID,
) -> MagicMock:
    ev = MagicMock()
    ev.id = eval_id
    ev.evaluation_id = PARENT_RUN_ID
    ev.slo_name = 'perf-slo'
    ev.slo_version = 1
    ev.sli_name = 'system-sli'
    ev.sli_version = 1
    ev.data_source_name = 'prometheus'
    ev.evaluation_name = 'daily-check'
    ev.period_start = NOW
    ev.period_end = LATER
    ev.asset_snapshot = {'name': 'my-service', 'variables': {}, 'tags': {}}
    ev.asset_id = ASSET_ID
    ev.variables = {}
    ev.status = status
    return ev


def _make_snapshot() -> EvaluationSnapshot:
    return EvaluationSnapshot(
        eval_id=EVAL_ID,
        parent_run_id=PARENT_RUN_ID,
        slo_name='perf-slo',
        slo_version=1,
        sli_name='system-sli',
        sli_version=1,
        data_source_name='prometheus',
        evaluation_name='daily-check',
        period_start=NOW,
        period_end=LATER,
        asset_snapshot={'name': 'my-service', 'variables': {}, 'tags': {}},
        asset_id=ASSET_ID,
        variables={},
    )


# --- load_evaluation_snapshot tests ---


async def test_load_snapshot_marks_running_and_returns_snapshot() -> None:
    """Phase 1 marks running and returns an EvaluationSnapshot with correct fields."""
    session = AsyncMock()
    repo = AsyncMock()
    repo.get_by_id.return_value = _make_orm_evaluation()

    with patch(
        'app.modules.quality_gate.worker.EvaluationRepository',
        return_value=repo,
    ):
        result = await load_evaluation_snapshot(session, EVAL_ID, worker_id='w-1')

    repo.mark_running.assert_awaited_once_with(EVAL_ID, 'w-1')
    assert result is not None
    assert isinstance(result, EvaluationSnapshot)
    assert result.eval_id == EVAL_ID
    assert result.parent_run_id == PARENT_RUN_ID
    assert result.slo_name == 'perf-slo'
    assert result.slo_version == 1
    assert result.asset_id == ASSET_ID
    assert result.evaluation_name == 'daily-check'
    assert result.period_start == NOW
    assert result.period_end == LATER


async def test_load_snapshot_returns_none_for_missing_eval() -> None:
    """Phase 1 returns None when eval not found in the database."""
    session = AsyncMock()
    repo = AsyncMock()
    repo.get_by_id.return_value = None

    with patch(
        'app.modules.quality_gate.worker.EvaluationRepository',
        return_value=repo,
    ):
        result = await load_evaluation_snapshot(session, EVAL_ID)

    assert result is None


async def test_load_snapshot_returns_none_for_already_completed() -> None:
    """Phase 1 returns None when eval is already completed."""
    session = AsyncMock()
    repo = AsyncMock()
    repo.get_by_id.return_value = _make_orm_evaluation(status='completed')

    with patch(
        'app.modules.quality_gate.worker.EvaluationRepository',
        return_value=repo,
    ):
        result = await load_evaluation_snapshot(session, EVAL_ID)

    assert result is None


# --- fetch_and_evaluate tests ---


async def test_fetch_and_evaluate_returns_result() -> None:
    """Phase 2 returns a FetchAndEvaluateResult on success."""
    snapshot = _make_snapshot()

    slo_def = MagicMock()
    slo_def.objectives = [
        MagicMock(sli='response_time', display_name='RT', pass_threshold=['<600'],
                  warning_threshold=[], weight=1, key_sli=False),
    ]
    slo_def.total_score_pass_threshold = 90.0
    slo_def.total_score_warning_threshold = 75.0
    slo_def.comparison = None
    slo_def.variables = {}

    sli_def = MagicMock()
    sli_def.mode = 'raw'
    sli_def.indicators = {'response_time': 'up{job="api"}'}
    sli_def.name = 'system-sli'

    datasource = MagicMock()
    datasource.adapter_url = 'http://adapter:8081'
    datasource.name = 'prometheus'

    adapter_client = AsyncMock()
    adapter_client.query.return_value = (
        {'response_time': 500.0},
        {},
        {},
    )

    baseline_repo = AsyncMock()
    baseline_repo.get_evaluation_baselines.return_value = []

    result = await fetch_and_evaluate(
        snapshot=snapshot,
        slo_def=slo_def,
        sli_def=sli_def,
        datasource=datasource,
        adapter_client=adapter_client,
        baseline_repo=baseline_repo,
    )

    assert result is not None
    assert isinstance(result, FetchAndEvaluateResult)
    assert result.metrics_fetched == {'response_time': 500.0}
    assert result.fetch_errors == {}
    adapter_client.query.assert_awaited_once()


async def test_fetch_and_evaluate_returns_none_on_adapter_failure() -> None:
    """Phase 2 returns None when adapter raises ConnectError."""
    snapshot = _make_snapshot()

    slo_def = MagicMock()
    slo_def.objectives = [
        MagicMock(sli='response_time', display_name='RT', pass_threshold=['<600'],
                  warning_threshold=[], weight=1, key_sli=False),
    ]
    slo_def.total_score_pass_threshold = 90.0
    slo_def.total_score_warning_threshold = 75.0
    slo_def.comparison = None
    slo_def.variables = {}

    sli_def = MagicMock()
    sli_def.mode = 'raw'
    sli_def.indicators = {'response_time': 'up{job="api"}'}
    sli_def.name = 'system-sli'

    datasource = MagicMock()
    datasource.adapter_url = 'http://adapter:8081'
    datasource.name = 'prometheus'

    adapter_client = AsyncMock()
    adapter_client.query.side_effect = httpx.ConnectError('connection refused')

    baseline_repo = AsyncMock()

    result = await fetch_and_evaluate(
        snapshot=snapshot,
        slo_def=slo_def,
        sli_def=sli_def,
        datasource=datasource,
        adapter_client=adapter_client,
        baseline_repo=baseline_repo,
    )

    assert result is None


# --- write_results tests ---


async def test_write_results_commits_eval_and_indicators() -> None:
    """Phase 3a calls mark_completed and bulk_insert (no sli_values)."""
    session = AsyncMock()
    snapshot = _make_snapshot()

    ir = MagicMock()
    ir.metric = 'response_time'
    ir.value = 500.0
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
        metrics_fetched={'response_time': 500.0},
        fetch_errors={},
        sli_metadata={},
        baselines={},
        compared_eval_ids=[],
    )

    slo_def = MagicMock()
    obj = MagicMock()
    obj.sli = 'response_time'
    obj.id = uuid.uuid4()
    obj.weight = 1
    slo_def.objectives = [obj]
    slo_def.total_score_pass_threshold = 90.0
    slo_def.total_score_warning_threshold = 75.0

    mock_repo = AsyncMock()
    mock_indicator_repo = AsyncMock()

    with (
        patch(
            'app.modules.quality_gate.worker.EvaluationRepository',
            return_value=mock_repo,
        ),
        patch(
            'app.modules.quality_gate.worker.IndicatorRepository',
            return_value=mock_indicator_repo,
        ),
    ):
        await write_results(
            session=session,
            snapshot=snapshot,
            slo_def=slo_def,
            fetch_result=fetch_result,
        )

    mock_repo.mark_completed.assert_awaited_once()
    mock_indicator_repo.bulk_insert.assert_awaited_once()


async def test_write_sli_values_phase_writes_to_hypertable() -> None:
    """Phase 3b writes SLI values via SLIValueRepository."""
    session = AsyncMock()
    snapshot = _make_snapshot()

    ir = MagicMock()
    ir.metric = 'response_time'
    ir.value = 500.0
    ir.compared_value = None
    ir.change_absolute = None
    ir.change_relative_pct = None
    ir.status = 'pass'
    ir.score = 1.0

    eval_result = MagicMock()
    eval_result.indicator_results = [ir]

    fetch_result = FetchAndEvaluateResult(
        eval_result=eval_result,
        metrics_fetched={'response_time': 500.0},
        fetch_errors={},
        sli_metadata={},
        baselines={},
        compared_eval_ids=[],
    )

    sli_def = MagicMock()
    sli_def.mode = 'raw'
    sli_def.indicators = {'response_time': 'up{job="api"}'}

    mock_sli_repo = AsyncMock()

    with patch(
        'app.modules.quality_gate.worker.SLIValueRepository',
        return_value=mock_sli_repo,
    ):
        await write_sli_values_phase(
            session=session,
            snapshot=snapshot,
            sli_def=sli_def,
            fetch_result=fetch_result,
        )

    mock_sli_repo.write_sli_values.assert_awaited_once()
