"""FastAPI dependencies for the quality gate module."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.cache.redis_cache import RedisCache
from tropek.config import get_settings
from tropek.db.session import get_session
from tropek.modules.assets.repository import (
    AssetGroupRepository,
    AssetRepository,
)
from tropek.modules.assignments.repository import AssignmentRepository
from tropek.modules.datasource.repository import DataSourceRepository
from tropek.modules.quality_gate.repositories.annotation import AnnotationRepository
from tropek.modules.quality_gate.repositories.annotation_category import (
    AnnotationCategoryRepository,
)
from tropek.modules.quality_gate.repositories.baseline import BaselineRepository
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.repositories.evaluation_run import EvaluationRunRepository
from tropek.modules.quality_gate.repositories.heatmap import HeatmapRepository
from tropek.modules.quality_gate.repositories.sli_value import SLIValueRepository
from tropek.modules.quality_gate.repositories.trend import TrendRepository
from tropek.modules.quality_gate.workflows.presentation.heatmap_cache import HeatmapColumnCache
from tropek.modules.quality_gate.workflows.presentation.trend_cache import TrendColumnCache
from tropek.modules.sli_registry.repository import SLIRepository
from tropek.modules.slo_registry.repository import SLORepository


async def get_heatmap_column_cache(request: Request) -> HeatmapColumnCache | None:
    """Return a ``HeatmapColumnCache`` for the request, or ``None`` when Redis is unavailable.

    Reaches through the existing ``RedisCache`` on ``app.state.cache`` to reuse
    the same underlying ``redis.asyncio`` client. The handler treats ``None``
    as "cache disabled" and falls through to the DB build path.

    This is deliberately a thin reach-through rather than a second top-level
    provider: the lifespan in ``main.py`` owns exactly one redis client (via
    ``RedisCache``), and Task 10's worker warm path will want the same
    construction, so keeping a single wiring point avoids drift.
    """
    redis_cache: RedisCache | None = getattr(request.app.state, 'cache', None)
    if redis_cache is None:
        return None
    settings = get_settings()
    return HeatmapColumnCache(
        redis_cache.client,
        ttl_seconds=settings.cache.ttl.heatmap_column,
    )


async def get_trend_column_cache(request: Request) -> TrendColumnCache | None:
    """Return a ``TrendColumnCache`` for the request, or ``None`` when Redis is unavailable."""
    redis_cache: RedisCache | None = getattr(request.app.state, 'cache', None)
    if redis_cache is None:
        return None
    settings = get_settings()
    return TrendColumnCache(redis_cache.client, ttl_seconds=settings.cache.ttl.trend_column)


@dataclass
class QualityGateRepos:
    """Bundle of all repositories needed by quality gate endpoints."""

    eval_repo: EvaluationRepository
    eval_run_repo: EvaluationRunRepository
    annotation_repo: AnnotationRepository
    category_repo: AnnotationCategoryRepository
    sli_repo: SLIValueRepository
    trend_repo: TrendRepository
    heatmap_repo: HeatmapRepository
    baseline_repo: BaselineRepository
    asset_repo: AssetRepository
    asset_group_repo: AssetGroupRepository
    assignment_repo: AssignmentRepository
    sli_def_repo: SLIRepository
    slo_repo: SLORepository
    ds_repo: DataSourceRepository
    session: AsyncSession
    cache: RedisCache | None = None
    heatmap_cache: HeatmapColumnCache | None = None
    trend_cache: TrendColumnCache | None = None


async def get_qg_repos(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    heatmap_cache: HeatmapColumnCache | None = Depends(get_heatmap_column_cache),  # noqa: B008
    trend_cache: TrendColumnCache | None = Depends(get_trend_column_cache),  # noqa: B008
) -> QualityGateRepos:
    """Build the full repository bundle from a DB session."""
    cache: RedisCache | None = getattr(request.app.state, 'cache', None)
    return QualityGateRepos(
        eval_repo=EvaluationRepository(session, cache=cache, heatmap_cache=heatmap_cache),
        eval_run_repo=EvaluationRunRepository(session),
        annotation_repo=AnnotationRepository(session, cache=cache),
        category_repo=AnnotationCategoryRepository(session),
        sli_repo=SLIValueRepository(session),
        trend_repo=TrendRepository(session),
        heatmap_repo=HeatmapRepository(session),
        baseline_repo=BaselineRepository(session, cache=cache),
        asset_repo=AssetRepository(session, cache=cache),
        asset_group_repo=AssetGroupRepository(session),
        assignment_repo=AssignmentRepository(session),
        sli_def_repo=SLIRepository(session, cache=cache),
        slo_repo=SLORepository(session, cache=cache),
        ds_repo=DataSourceRepository(session),
        session=session,
        cache=cache,
        heatmap_cache=heatmap_cache,
        trend_cache=trend_cache,
    )
