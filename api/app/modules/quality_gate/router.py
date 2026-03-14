"""FastAPI router for evaluations, annotations, and trend."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.assets.repository import AssetGroupRepository, AssetRepository
from app.modules.common.errors import raise_not_found
from app.modules.common.schemas import PagedResponse
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.schemas import (
    AnnotationCreate,
    AnnotationRead,
    AnnotationUpdate,
    EvaluationDetail,
    EvaluationSummary,
    FailingIndicator,
    IndicatorResult,
    InvalidateRequest,
    TrendPoint,
)

router = APIRouter()


def _build_summary(
    ev: object, annotation_count: int, latest_ann: object | None
) -> EvaluationSummary:
    """Construct EvaluationSummary with computed fields from a bare Evaluation ORM object."""
    indicator_results: list[dict[str, Any]] = getattr(ev, "indicator_results", []) or []
    top_failures = [
        FailingIndicator(
            metric=ind["metric"],
            display_name=ind.get("display_name", ind["metric"]),
            value=ind["value"],
            threshold=(ind.get("pass_targets") or [{}])[0].get("criteria", ""),
        )
        for ind in indicator_results
        if ind.get("status") == "fail"
    ]
    return EvaluationSummary.model_validate(
        {
            **ev.__dict__,
            "annotation_count": annotation_count,
            "latest_annotation": latest_ann,
            "top_failures": top_failures,
        }
    )


# ---- Evaluations ----


@router.get("/evaluations", response_model=PagedResponse[EvaluationSummary])
async def list_evaluations(
    asset_name: str | None = None,
    slo_name: str | None = None,
    result: str | None = None,
    date: str | None = None,
    group_name: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> PagedResponse[EvaluationSummary]:
    """List evaluations with optional filters."""
    eval_repo = EvaluationRepository(session)
    resolved_asset_id: uuid.UUID | None = None
    asset_ids: list[uuid.UUID] | None = None

    if asset_name:
        asset_repo = AssetRepository(session)
        asset = await asset_repo.get_by_name(asset_name)
        if asset is None:
            raise_not_found("asset", asset_name)
        resolved_asset_id = asset.id

    if group_name:
        group_repo = AssetGroupRepository(session)
        group = await group_repo.get_by_name(group_name)
        if group:
            asset_ids = [m.asset_id for m in group.members]

    evals, total, count_map = await eval_repo.list_with_counts(
        asset_id=resolved_asset_id,
        slo_name=slo_name,
        result=result,
        date_prefix=date,
        asset_ids=asset_ids,
        limit=limit,
        offset=offset,
    )
    items = [
        _build_summary(ev, annotation_count=count_map.get(ev.id, 0), latest_ann=None)
        for ev in evals
    ]
    return PagedResponse(items=items, total=total)


@router.get("/evaluations/{eval_id}", response_model=EvaluationDetail)
async def get_evaluation(
    eval_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EvaluationDetail:
    """Get full evaluation detail including annotations and indicator results."""
    repo = EvaluationRepository(session)
    ev = await repo.get_by_id(eval_id)
    if ev is None:
        raise_not_found("evaluation", str(eval_id))
    annotations = [AnnotationRead.model_validate(a) for a in ev.annotations]
    indicator_results = [IndicatorResult(**ind) for ind in (ev.indicator_results or [])]
    top_failures = [
        FailingIndicator(
            metric=ind.metric,
            display_name=ind.display_name,
            value=ind.value,
            threshold=(ind.pass_targets or [{}])[0].get("criteria", ""),
        )
        for ind in indicator_results
        if ind.status == "fail"
    ]
    sorted_annotations = sorted(annotations, key=lambda a: a.created_at)
    return EvaluationDetail.model_validate(
        {
            **ev.__dict__,
            "annotation_count": len(annotations),
            "latest_annotation": sorted_annotations[-1] if sorted_annotations else None,
            "top_failures": top_failures,
            "annotations": annotations,
            "indicator_results": indicator_results,
            "compared_evaluation_ids": [],
        }
    )


@router.patch("/evaluations/{eval_id}/invalidate", response_model=EvaluationSummary)
async def invalidate_evaluation(
    eval_id: uuid.UUID,
    body: InvalidateRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EvaluationSummary:
    """Mark an evaluation as invalidated."""
    repo = EvaluationRepository(session)
    ev = await repo.invalidate(eval_id, note=body.invalidation_note)
    if ev is None:
        raise_not_found("evaluation", str(eval_id))
    return _build_summary(ev, annotation_count=0, latest_ann=None)


@router.patch("/evaluations/{eval_id}/restore", response_model=EvaluationSummary)
async def restore_evaluation(
    eval_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EvaluationSummary:
    """Clear invalidation flag on an evaluation."""
    repo = EvaluationRepository(session)
    ev = await repo.restore(eval_id)
    if ev is None:
        raise_not_found("evaluation", str(eval_id))
    return _build_summary(ev, annotation_count=0, latest_ann=None)


# ---- Annotations ----


@router.get("/evaluations/{eval_id}/annotations", response_model=list[AnnotationRead])
async def list_annotations(
    eval_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[AnnotationRead]:
    """List all annotations for an evaluation."""
    repo = EvaluationRepository(session)
    ev = await repo.get_by_id(eval_id)
    if ev is None:
        raise_not_found("evaluation", str(eval_id))
    return [AnnotationRead.model_validate(a) for a in ev.annotations]


@router.post("/evaluations/{eval_id}/annotations", response_model=AnnotationRead, status_code=201)
async def create_annotation(
    eval_id: uuid.UUID,
    body: AnnotationCreate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> AnnotationRead:
    """Add an annotation to an evaluation."""
    repo = EvaluationRepository(session)
    ev = await repo.get_by_id(eval_id)
    if ev is None:
        raise_not_found("evaluation", str(eval_id))
    ann = await repo.add_annotation(
        eval_id,
        content=body.content,
        author=body.author,
        category=body.category,
        meta=body.meta,
    )
    return AnnotationRead.model_validate(ann)


@router.patch("/evaluations/{eval_id}/annotations/{ann_id}", response_model=AnnotationRead)
async def update_annotation(
    eval_id: uuid.UUID,
    ann_id: uuid.UUID,
    body: AnnotationUpdate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> AnnotationRead:
    """Update an annotation."""
    repo = EvaluationRepository(session)
    ann = await repo.update_annotation(ann_id, **body.model_dump(exclude_unset=True))
    if ann is None:
        raise_not_found("annotation", str(ann_id))
    return AnnotationRead.model_validate(ann)


@router.delete("/evaluations/{eval_id}/annotations/{ann_id}", status_code=204)
async def delete_annotation(
    eval_id: uuid.UUID,
    ann_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    """Delete an annotation."""
    repo = EvaluationRepository(session)
    await repo.delete_annotation(ann_id)


# ---- Trend ----


@router.get("/trend", response_model=list[TrendPoint])
async def get_trend(
    asset_name: str,
    slo_name: str,
    metric: str,
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[TrendPoint]:
    """Return time-series trend data for a specific asset+SLO+metric combination."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(asset_name)
    if asset is None:
        raise_not_found("asset", asset_name)
    eval_repo = EvaluationRepository(session)
    points = await eval_repo.get_trend_by_domain(
        asset_id=asset.id,
        slo_name=slo_name,
        metric_name=metric,
        limit=limit,
    )
    return [TrendPoint(**p) for p in points]
