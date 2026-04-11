"""FastAPI dependencies for the quality gate module."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_cache import RedisCache
from app.db.session import get_session
from app.modules.assets.repository import (
    AssetGroupRepository,
    AssetRepository,
)
from app.modules.assignments.repository import AssignmentRepository
from app.modules.datasource.repository import DataSourceRepository
from app.modules.quality_gate.annotation_repository import AnnotationRepository
from app.modules.quality_gate.baseline_repository import BaselineRepository
from app.modules.quality_gate.evaluation_run_repository import EvaluationRunRepository
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.sli_repository import SLIValueRepository
from app.modules.quality_gate.trend_repository import TrendRepository
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_registry.repository import SLORepository


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


async def get_qg_repos(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> QualityGateRepos:
    """Build the full repository bundle from a DB session."""
    cache: RedisCache | None = getattr(request.app.state, 'cache', None)
    return QualityGateRepos(
        eval_repo=EvaluationRepository(session),
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
    )
