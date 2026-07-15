"""Integration tests for the batched trend repository queries (Task 4).

Covers ``TrendRepository.list_slo_evaluation_ids_for_trend`` and
``TrendRepository.get_trend_fragment_rows``, which back the per-SLO batched
trend endpoint. The filter set for both must match ``get_trend_by_domain`` so
downstream parity (Task 6) holds — see that method for the reference filters.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import Asset, AssetType, SLIDefinition, SLODefinition, SLOObjective
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.repositories.indicator import IndicatorRepository
from tropek.modules.quality_gate.repositories.sli_value import SLIValueRepository
from tropek.modules.quality_gate.repositories.trend import TrendRepository
from tropek.modules.quality_gate.shared.params import EvalCreateParams

_BASE = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
_SLO_NAME = 'perf-slo'
_METRIC_NAMES = ('cpu_time', 'memory_bytes')


@dataclass
class SeededTrendAsset:
    """Everything a trend-batch test needs: asset/SLO identity plus expected ids."""

    trend_repo: TrendRepository
    asset_id: uuid.UUID
    slo_name: str
    range_from: datetime
    expected_slo_evaluation_ids_oldest_first: list[uuid.UUID]


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
        name='trend-batch-sli',
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
        display_name='Perf SLO',
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
    """Factory-style fixture: seeds one asset/SLO with 3 completed runs + 1 invalidated run."""

    async def _seed() -> SeededTrendAsset:
        asset_name = f'trend-batch-{uuid.uuid4().hex[:8]}'
        asset_id = await _create_asset(db_session, asset_name)
        objectives_by_metric = await _seed_slo_objectives(db_session, _METRIC_NAMES)

        evaluation_repo = EvaluationRepository(db_session)
        sli_value_repo = SLIValueRepository(db_session)

        expected_ids: list[uuid.UUID] = []
        for index in range(3):
            period_start = _BASE + timedelta(hours=index)
            slo_evaluation_id = await _seed_completed_slo_evaluation(
                db_session,
                asset_id=asset_id,
                asset_name=asset_name,
                period_start=period_start,
                evaluation_name=f'perf-eval-{index}',
                objectives_by_metric=objectives_by_metric,
            )
            expected_ids.append(slo_evaluation_id)

        # An invalidated SLO-evaluation, positioned in the middle of the range, that
        # must be excluded from both the id listing and the fragment rows.
        invalidated_period_start = _BASE + timedelta(hours=1, minutes=30)
        invalidated_evaluation_name = 'perf-eval-invalidated'
        invalidated_slo_evaluation_id = await _seed_completed_slo_evaluation(
            db_session,
            asset_id=asset_id,
            asset_name=asset_name,
            period_start=invalidated_period_start,
            evaluation_name=invalidated_evaluation_name,
            objectives_by_metric=objectives_by_metric,
        )
        await evaluation_repo.invalidate(invalidated_slo_evaluation_id, note='excluded from trend batch test')
        # Keep the SLI values in place too — the filter must exclude via
        # SLOEvaluation.invalidated, not because there is no SLI data at all.
        assert await sli_value_repo.get_sli_values_for_eval(invalidated_slo_evaluation_id)

        return SeededTrendAsset(
            trend_repo=TrendRepository(db_session),
            asset_id=asset_id,
            slo_name=_SLO_NAME,
            range_from=_BASE - timedelta(hours=1),
            expected_slo_evaluation_ids_oldest_first=expected_ids,
        )

    return _seed


@pytest.mark.integration
async def test_list_slo_evaluation_ids_matches_ordered_periods_excluding_invalidated(
    seeded_trend_asset,
) -> None:
    fixture = await seeded_trend_asset()
    slo_evaluation_ids = await fixture.trend_repo.list_slo_evaluation_ids_for_trend(
        asset_id=fixture.asset_id,
        slo_name=fixture.slo_name,
        from_ts=fixture.range_from,
    )
    assert slo_evaluation_ids == fixture.expected_slo_evaluation_ids_oldest_first


@pytest.mark.integration
async def test_get_trend_fragment_rows_normalizes_score_and_groups_metrics(
    seeded_trend_asset,
) -> None:
    fixture = await seeded_trend_asset()
    fragments = await fixture.trend_repo.get_trend_fragment_rows(
        asset_id=fixture.asset_id,
        slo_name=fixture.slo_name,
        slo_evaluation_ids=fixture.expected_slo_evaluation_ids_oldest_first,
    )
    assert len(fragments) == 3
    metrics = {point.metric for fragment in fragments for point in fragment.points}
    assert metrics == set(_METRIC_NAMES)
    # every score is a normalized percentage in [0, 100]
    assert all(0 <= point.score <= 100 for fragment in fragments for point in fragment.points)
