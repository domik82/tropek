"""FastAPI dependencies for the quality gate module."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.assets.repository import (
    AssetGroupRepository,
    AssetGroupSLOLinkRepository,
    AssetRepository,
    AssetSLOLinkRepository,
)
from app.modules.datasource.repository import DataSourceRepository
from app.modules.quality_gate.annotation_repository import AnnotationRepository
from app.modules.quality_gate.baseline_repository import BaselineRepository
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.sli_repository import SLIValueRepository
from app.modules.quality_gate.trend_repository import TrendRepository
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_registry.repository import SLORepository


@dataclass
class QualityGateRepos:
    """Bundle of all repositories needed by quality gate endpoints."""

    eval_repo: EvaluationRepository
    annotation_repo: AnnotationRepository
    sli_repo: SLIValueRepository
    trend_repo: TrendRepository
    baseline_repo: BaselineRepository
    asset_repo: AssetRepository
    asset_group_repo: AssetGroupRepository
    slo_link_repo: AssetSLOLinkRepository
    group_link_repo: AssetGroupSLOLinkRepository
    sli_def_repo: SLIRepository
    slo_repo: SLORepository
    ds_repo: DataSourceRepository
    session: AsyncSession


async def get_qg_repos(
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> QualityGateRepos:
    """Build the full repository bundle from a DB session."""
    return QualityGateRepos(
        eval_repo=EvaluationRepository(session),
        annotation_repo=AnnotationRepository(session),
        sli_repo=SLIValueRepository(session),
        trend_repo=TrendRepository(session),
        baseline_repo=BaselineRepository(session),
        asset_repo=AssetRepository(session),
        asset_group_repo=AssetGroupRepository(session),
        slo_link_repo=AssetSLOLinkRepository(session),
        group_link_repo=AssetGroupSLOLinkRepository(session),
        sli_def_repo=SLIRepository(session),
        slo_repo=SLORepository(session),
        ds_repo=DataSourceRepository(session),
        session=session,
    )
