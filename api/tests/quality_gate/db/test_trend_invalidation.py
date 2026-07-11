"""Integration test: re-evaluation invalidates the per-SLO trend fragment cache."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import Asset, AssetType, SLODefinition, SLOObjective
from tropek.modules.assets.repository import AssetGroupRepository, AssetRepository
from tropek.modules.assignments.repository import AssignmentRepository
from tropek.modules.datasource.repository import DataSourceRepository
from tropek.modules.quality_gate.repositories.annotation import AnnotationRepository
from tropek.modules.quality_gate.repositories.annotation_category import (
    AnnotationCategoryRepository,
)
from tropek.modules.quality_gate.repositories.baseline import BaselineRepository
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.repositories.evaluation_run import EvaluationRunRepository
from tropek.modules.quality_gate.repositories.indicator import IndicatorRepository
from tropek.modules.quality_gate.repositories.sli_value import SLIValueRepository
from tropek.modules.quality_gate.repositories.trend import TrendRepository
from tropek.modules.quality_gate.schemas.re_evaluation import ReEvaluateRequest
from tropek.modules.quality_gate.shared.dependencies import QualityGateRepos
from tropek.modules.quality_gate.shared.params import EvalCreateParams
from tropek.modules.quality_gate.workflows.presentation.trend_cache import (
    TrendColumnCache,
    trend_column_cache_key,
)
from tropek.modules.quality_gate.workflows.re_evaluation.re_evaluation_service import re_evaluate
from tropek.modules.sli_registry.repository import SLIRepository
from tropek.modules.slo_registry.params import SLOCreateParams, SLOObjectiveParams
from tropek.modules.slo_registry.repository import SLORepository

pytestmark = pytest.mark.integration

_START = datetime(2026, 3, 10, 10, 0, 0, tzinfo=UTC)


def _build_repos(session: AsyncSession, *, trend_cache: TrendColumnCache | None) -> QualityGateRepos:
    """Build a QualityGateRepos bundle wired with the given trend cache."""
    return QualityGateRepos(
        eval_repo=EvaluationRepository(session),
        eval_run_repo=EvaluationRunRepository(session),
        annotation_repo=AnnotationRepository(session),
        category_repo=AnnotationCategoryRepository(session),
        sli_repo=SLIValueRepository(session),
        trend_repo=TrendRepository(session),
        baseline_repo=BaselineRepository(session),
        asset_repo=AssetRepository(session),
        asset_group_repo=AssetGroupRepository(session),
        assignment_repo=AssignmentRepository(session),
        sli_def_repo=SLIRepository(session),
        slo_repo=SLORepository(session),
        ds_repo=DataSourceRepository(session),
        session=session,
        trend_cache=trend_cache,
    )


async def _create_asset(session: AsyncSession, name: str) -> uuid.UUID:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=name, type_name=type_name))
    await session.flush()
    return asset_id


async def test_reevaluation_drops_trend_fragment_for_affected_slo_eval(
    db_session: AsyncSession,
    redis_client,
) -> None:
    """Re-evaluating an SLO must delete the cached trend fragment for the re-scored evaluation."""
    slo_name = f'trend-invalidation-slo-{uuid.uuid4().hex[:6]}'
    asset_name = f'trend-invalidation-asset-{uuid.uuid4().hex[:6]}'
    asset_id = await _create_asset(db_session, asset_name)

    slo_repo = SLORepository(db_session)
    await slo_repo.create(
        SLOCreateParams(
            name=slo_name,
            objectives=[SLOObjectiveParams(sli='cpu', pass_threshold=['<90'], weight=1)],
        )
    )

    eval_repo = EvaluationRepository(db_session)
    evaluation = await eval_repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='daily',
            period_start=_START,
            period_end=_START,
            ingestion_mode='push',
            asset_snapshot={'name': asset_name},
            variables={},
            asset_id=asset_id,
            slo_name=slo_name,
        )
    )
    await eval_repo.mark_completed(evaluation.id, result='fail', score=0.0, slo_name=slo_name)

    obj_result = await db_session.execute(
        select(SLOObjective)
        .join(SLODefinition, SLOObjective.slo_definition_id == SLODefinition.id)
        .where(SLODefinition.name == slo_name, SLOObjective.sli == 'cpu')
    )
    slo_objective = obj_result.scalars().one()

    indicator_repo = IndicatorRepository(db_session)
    await indicator_repo.bulk_insert(
        evaluation.id,
        [
            {
                'evaluation_id': evaluation.id,
                'slo_objective_id': slo_objective.id,
                'value': 95.0,
                'compared_value': None,
                'change_absolute': None,
                'change_relative_pct': None,
                'status': 'fail',
                'score': 0.0,
            }
        ],
    )

    sli_repo = SLIValueRepository(db_session)
    await sli_repo.write_sli_values(
        [
            {
                'slo_evaluation_id': evaluation.id,
                'eval_start': _START,
                'metric_name': 'cpu',
                'aggregation': 'avg',
                'value': 95.0,
                'asset_name': asset_name,
                'evaluation_name': 'daily',
                'os_tag': None,
            }
        ]
    )

    # Warm the trend fragment cache for this SLO-evaluation.
    trend_cache = TrendColumnCache(redis_client)
    trend_repo = TrendRepository(db_session)
    fragments = await trend_repo.get_trend_fragment_rows(
        asset_id=asset_id,
        slo_name=slo_name,
        slo_evaluation_ids=[evaluation.id],
    )
    await trend_cache.set_many(fragments)

    assert await redis_client.get(trend_column_cache_key(evaluation.id)) is not None

    # Re-evaluate with a relaxed threshold so the row is re-scored.
    await slo_repo.create(
        SLOCreateParams(
            name=slo_name,
            objectives=[SLOObjectiveParams(sli='cpu', pass_threshold=['<100'], weight=1)],
        )
    )
    asset_row = await db_session.get(Asset, asset_id)
    assert asset_row is not None

    await re_evaluate(
        ReEvaluateRequest(
            asset_name=asset_row.name,
            slo_name=slo_name,
            from_date=_START,
        ),
        _build_repos(db_session, trend_cache=trend_cache),
    )

    assert await redis_client.get(trend_column_cache_key(evaluation.id)) is None
