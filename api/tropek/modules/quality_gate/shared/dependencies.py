"""FastAPI dependencies for the quality gate module."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.cache.redis_cache import RedisCache
from tropek.db.session import get_session
from tropek.modules.assets.repository import (
    AssetGroupRepository,
    AssetRepository,
)
from tropek.modules.assignments.repository import AssignmentRepository
from tropek.modules.datasource.repository import DataSourceRepository
from tropek.modules.quality_gate.repositories.annotation import AnnotationRepository
from tropek.modules.quality_gate.repositories.baseline import BaselineRepository
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.repositories.evaluation_run import EvaluationRunRepository
from tropek.modules.quality_gate.repositories.sli_value import SLIValueRepository
from tropek.modules.quality_gate.repositories.trend import TrendRepository
from tropek.modules.sli_registry.repository import SLIRepository
from tropek.modules.slo_registry.repository import SLORepository


@dataclass
class QualityGateRepos:
    """Bundle of all repositories needed by quality gate endpoints."""

    eval_repo: EvaluationRepository
    eval_run_repo: EvaluationRunRepository
    annotation_repo: AnnotationRepository
    sli_repo: SLIValueRepository
    trend_repo: TrendRepository
    baseline_repo: BaselineRepository
    asset_repo: AssetRepository
    asset_group_repo: AssetGroupRepository
    assignment_repo: AssignmentRepository
    sli_def_repo: SLIRepository
    slo_repo: SLORepository
    ds_repo: DataSourceRepository
    session: AsyncSession
    cache: RedisCache | None = None


async def get_qg_repos(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> QualityGateRepos:
    """Build the full repository bundle from a DB session."""
    cache: RedisCache | None = getattr(request.app.state, 'cache', None)
    return QualityGateRepos(
        eval_repo=EvaluationRepository(session, cache=cache),
        eval_run_repo=EvaluationRunRepository(session),
        annotation_repo=AnnotationRepository(session, cache=cache),
        sli_repo=SLIValueRepository(session),
        trend_repo=TrendRepository(session),
        baseline_repo=BaselineRepository(session, cache=cache),
        asset_repo=AssetRepository(session, cache=cache),
        asset_group_repo=AssetGroupRepository(session),
        assignment_repo=AssignmentRepository(session),
        sli_def_repo=SLIRepository(session, cache=cache),
        slo_repo=SLORepository(session, cache=cache),
        ds_repo=DataSourceRepository(session),
        session=session,
        cache=cache,
    )
