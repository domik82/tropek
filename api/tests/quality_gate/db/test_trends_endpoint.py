"""Integration tests for the batched per-SLO ``/trends`` endpoint (Task 6).

Seeds real trend data (objectives + IndicatorResultRow + SLIValue rows for two
metrics across two completed SLO-evaluations, plus one invalidated
SLO-evaluation) so the parity assertions against the single-metric ``/trend``
endpoint are non-vacuous, and so the cache warm/cached/bypass comparison
exercises a real fragment rebuild + cache round-trip via fakeredis.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import Asset, AssetType, SLIDefinition, SLODefinition, SLOObjective
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.repositories.indicator import IndicatorRepository
from tropek.modules.quality_gate.repositories.sli_value import SLIValueRepository
from tropek.modules.quality_gate.shared.params import EvalCreateParams

pytestmark = pytest.mark.integration

_BASE = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
_SLO_NAME = 'trend-endpoint-slo'
_METRIC_NAMES = ('cpu_time', 'memory_bytes')


@dataclass
class SeededTrendAsset:
    """Everything the endpoint parity tests need: asset/SLO identity plus the range."""

    asset_name: str
    slo_name: str
    range_from: datetime


async def _create_asset(session: AsyncSession, name: str) -> uuid.UUID:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=name, type_name=type_name))
    await session.flush()
    return asset_id


async def _seed_slo_objectives(session: AsyncSession, metric_names: tuple[str, ...]) -> dict[str, SLOObjective]:
    """Create one SLO definition with one objective per metric name."""
    sli_definition = SLIDefinition(
        id=uuid.uuid4(),
        name='trend-endpoint-sli',
        version=1,
        adapter_type='prometheus',
        indicators={},
        tags={},
    )
    session.add(sli_definition)

    slo_definition_id = uuid.uuid4()
    slo_definition = SLODefinition(
        id=slo_definition_id,
        name=_SLO_NAME,
        version=1,
        display_name='Trend Endpoint SLO',
        comparison={},
        total_score_pass_threshold=90.0,
        total_score_warning_threshold=75.0,
        tags={},
        variables={},
    )
    session.add(slo_definition)

    objectives_by_metric: dict[str, SLOObjective] = {}
    for sort_order, metric_name in enumerate(metric_names):
        objective = SLOObjective(
            id=uuid.uuid4(),
            slo_definition_id=slo_definition_id,
            sli=metric_name,
            display_name=metric_name,
            weight=1,
            key_sli=False,
            sort_order=sort_order,
            pass_threshold=['<600'],
            warning_threshold=[],
        )
        session.add(objective)
        objectives_by_metric[metric_name] = objective
    await session.flush()
    return objectives_by_metric


async def _seed_completed_slo_evaluation(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    asset_name: str,
    period_start: datetime,
    evaluation_name: str,
    objectives_by_metric: dict[str, SLOObjective],
) -> uuid.UUID:
    """Seed one completed SLO-evaluation with indicator rows + SLI values for both metrics."""
    evaluation_repo = EvaluationRepository(session)
    indicator_repo = IndicatorRepository(session)
    sli_value_repo = SLIValueRepository(session)

    slo_evaluation = await evaluation_repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name=evaluation_name,
            period_start=period_start,
            period_end=period_start + timedelta(minutes=30),
            ingestion_mode='push',
            asset_snapshot={'name': asset_name, 'tags': {}},
            variables={},
            asset_id=asset_id,
            slo_name=_SLO_NAME,
        )
    )
    await evaluation_repo.mark_completed(slo_evaluation.id, result='pass', score=100.0, slo_name=_SLO_NAME)

    await indicator_repo.bulk_insert(
        slo_evaluation.id,
        [
            {
                'evaluation_id': slo_evaluation.id,
                'slo_objective_id': objectives_by_metric[metric_name].id,
                'value': 100.0 + index,
                'compared_value': 90.0 + index,
                'change_absolute': 10.0,
                'change_relative_pct': 10.0,
                'status': 'pass',
                'score': 1.0,
            }
            for index, metric_name in enumerate(_METRIC_NAMES)
        ],
    )
    await sli_value_repo.write_sli_values(
        [
            {
                'slo_evaluation_id': slo_evaluation.id,
                'eval_start': period_start,
                'metric_name': metric_name,
                'aggregation': 'avg',
                'value': 100.0 + index,
                'asset_name': asset_name,
                'evaluation_name': evaluation_name,
                'os_tag': None,
            }
            for index, metric_name in enumerate(_METRIC_NAMES)
        ]
    )
    return slo_evaluation.id


@pytest.fixture
def seeded_trend_asset(db_session: AsyncSession):
    """Factory-style fixture: seeds one asset/SLO with 2 completed runs + 1 invalidated run.

    Two metrics per run guarantee the parity test's per-metric comparison is
    exercised for more than one indicator, and the invalidated run proves
    exclusion holds for the batched endpoint the same way it does for the
    single-metric endpoint.
    """

    async def _seed() -> SeededTrendAsset:
        asset_name = f'trend-endpoint-{uuid.uuid4().hex[:8]}'
        asset_id = await _create_asset(db_session, asset_name)
        objectives_by_metric = await _seed_slo_objectives(db_session, _METRIC_NAMES)

        evaluation_repo = EvaluationRepository(db_session)

        for index in range(2):
            period_start = _BASE + timedelta(hours=index)
            await _seed_completed_slo_evaluation(
                db_session,
                asset_id=asset_id,
                asset_name=asset_name,
                period_start=period_start,
                evaluation_name=f'trend-endpoint-eval-{index}',
                objectives_by_metric=objectives_by_metric,
            )

        # An invalidated SLO-evaluation, positioned in the middle of the range,
        # that must be excluded from both endpoints' trend series.
        invalidated_period_start = _BASE + timedelta(hours=0, minutes=30)
        invalidated_slo_evaluation_id = await _seed_completed_slo_evaluation(
            db_session,
            asset_id=asset_id,
            asset_name=asset_name,
            period_start=invalidated_period_start,
            evaluation_name='trend-endpoint-eval-invalidated',
            objectives_by_metric=objectives_by_metric,
        )
        await evaluation_repo.invalidate(invalidated_slo_evaluation_id, note='excluded from trends endpoint test')

        return SeededTrendAsset(
            asset_name=asset_name,
            slo_name=_SLO_NAME,
            range_from=_BASE - timedelta(hours=1),
        )

    return _seed


async def test_batch_trends_matches_single_metric_endpoint(
    api_client: AsyncClient,
    redis_client,
    seeded_trend_asset,
) -> None:
    """Every metric's point list from ``/trends`` must be non-empty and equal
    to the same metric's point list from the single-metric ``/trend`` endpoint.

    Non-emptiness is asserted explicitly: an empty seed would make batch == single
    trivially true without proving the projection logic is correct.
    """
    fixture = await seeded_trend_asset()
    from_ts = fixture.range_from.isoformat()

    batch = await api_client.get(
        f'/assets/{fixture.asset_name}/slos/{fixture.slo_name}/trends',
        params={'from': from_ts},
    )
    assert batch.status_code == 200
    batch_body = batch.json()

    for metric in _METRIC_NAMES:
        single = await api_client.get(
            f'/assets/{fixture.asset_name}/slos/{fixture.slo_name}/trend',
            params={'metric': metric, 'from': from_ts},
        )
        assert single.status_code == 200
        single_body = single.json()
        assert len(single_body) == 2, f'expected 2 completed points for {metric}, got {len(single_body)}'
        assert metric in batch_body, f'batch response missing metric {metric}'
        assert len(batch_body[metric]) == 2, f'expected 2 completed points for {metric} in batch, got vacuous result'
        assert batch_body[metric] == single_body


async def test_batch_trends_identical_with_cache_on_and_off(
    api_client: AsyncClient,
    redis_client,
    seeded_trend_asset,
) -> None:
    fixture = await seeded_trend_asset()
    from_ts = fixture.range_from.isoformat()
    url = f'/assets/{fixture.asset_name}/slos/{fixture.slo_name}/trends'

    warm = await api_client.get(url, params={'from': from_ts})  # populates cache
    cached = await api_client.get(url, params={'from': from_ts})  # reads cache
    bypass = await api_client.get(url, params={'from': from_ts, 'cache': 'false'})

    assert warm.status_code == 200
    assert cached.status_code == 200
    assert bypass.status_code == 200
    warm_body = warm.json()
    assert any(len(points) > 0 for points in warm_body.values()), 'seed produced no trend points — test is vacuous'
    assert warm_body == cached.json() == bypass.json()


async def test_unknown_asset_returns_404(api_client: AsyncClient) -> None:
    response = await api_client.get(
        '/assets/does-not-exist/slos/whatever/trends',
        params={'from': '2026-01-01T00:00:00'},
    )
    assert response.status_code == 404
