"""FastAPI router for evaluations, annotations, and trend."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AssetGroupSLOLink, AssetSLOLink, EvaluationBatch
from app.db.session import get_session
from app.modules.assets.repository import (
    AssetGroupRepository,
    AssetGroupSLOLinkRepository,
    AssetRepository,
    AssetSLOLinkRepository,
)
from app.modules.common.errors import raise_not_found
from app.modules.common.schemas import PagedResponse
from app.modules.datasource.repository import DataSourceRepository
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.schemas import (
    AnnotationCreate,
    AnnotationRead,
    AnnotationUpdate,
    BatchTriggerRequest,
    BatchTriggerResponse,
    EvaluationDetail,
    EvaluationSummary,
    FailingIndicator,
    HeatmapCell,
    HeatmapMetric,
    IndicatorResult,
    InvalidateRequest,
    MetricHeatmapResponse,
    OverrideStatusRequest,
    PinBaselineRequest,
    TrendPoint,
    TriggerRequest,
    TriggerResponse,
)
from app.modules.quality_gate.trigger import resolve_single_trigger
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_registry.repository import SLORepository
from app.queue import get_arq_pool

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


def _build_detail(ev: Any) -> EvaluationDetail:
    """Construct EvaluationDetail from an ORM Evaluation with annotations loaded."""
    annotations = [AnnotationRead.model_validate(a) for a in (ev.annotations or [])]
    indicator_results = [IndicatorResult(**ir) for ir in (ev.indicator_results or [])]
    compared_ids = (ev.job_stats or {}).get("compared_evaluation_ids", [])
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
            "compared_evaluation_ids": [uuid.UUID(eid) for eid in compared_ids],
            "annotations": sorted_annotations,
            "indicator_results": indicator_results,
        }
    )


# ---- Evaluations ----


@router.post("/evaluations", response_model=TriggerResponse, status_code=202)
async def trigger_evaluation(
    body: TriggerRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    arq_pool: ArqRedis = Depends(get_arq_pool),  # noqa: B008
) -> TriggerResponse:
    """Trigger a single asset evaluation."""
    asset_repo = AssetRepository(session)
    slo_link_repo = AssetSLOLinkRepository(session)
    sli_repo = SLIRepository(session)
    slo_repo = SLORepository(session)
    ds_repo = DataSourceRepository(session)

    try:
        ctx = await resolve_single_trigger(
            asset_name=body.asset_name,
            slo_name=body.slo_name,
            asset_repo=asset_repo,
            slo_link_repo=slo_link_repo,
            sli_repo=sli_repo,
            slo_repo=slo_repo,
            ds_repo=ds_repo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    eval_repo = EvaluationRepository(session)
    ev = await eval_repo.create_pending(
        name=body.test_name,
        period_start=body.period_start,
        period_end=body.period_end,
        ingestion_mode="pull",
        asset_snapshot={"name": ctx.asset_name, "tags": ctx.asset_labels},
        metadata=body.metadata,
        asset_id=ctx.asset_id,
        slo_name=ctx.slo_name,
        slo_version=ctx.slo_version,
        sli_name=ctx.sli_name,
        sli_version=ctx.sli_version,
        data_source_name=ctx.data_source_name,
        adapter_used=ctx.adapter_type,
    )
    await session.commit()
    await arq_pool.enqueue_job("run_evaluation_job", str(ev.id))
    return TriggerResponse(id=ev.id, status="pending")


@router.post("/evaluations/batch", response_model=BatchTriggerResponse, status_code=202)
async def trigger_batch(
    body: BatchTriggerRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    arq_pool: ArqRedis = Depends(get_arq_pool),  # noqa: B008
) -> BatchTriggerResponse:
    """Trigger evaluations for all assets in a group."""
    group_repo = AssetGroupRepository(session)
    group = await group_repo.get_by_name(body.group_name)
    if group is None:
        raise HTTPException(status_code=404, detail=f"asset group '{body.group_name}' not found")

    asset_repo = AssetRepository(session)
    slo_link_repo = AssetSLOLinkRepository(session)
    sli_repo = SLIRepository(session)
    slo_repo = SLORepository(session)
    ds_repo = DataSourceRepository(session)
    eval_repo = EvaluationRepository(session)

    # Collect all SLO links for group members + group-level links
    group_link_repo = AssetGroupSLOLinkRepository(session)
    group_links = await group_link_repo.list_by_group(group.id)

    evaluation_ids: list[uuid.UUID] = []
    for member in group.members:
        # Get asset-level SLO links
        asset = await asset_repo.get_by_name(member.asset_name)
        if asset is None:
            continue
        asset_links = await slo_link_repo.list_by_asset(asset.id)
        # Combine asset links + group links (deduplicate by slo_name)
        all_links: dict[str, AssetSLOLink | AssetGroupSLOLink] = {
            lnk.slo_name: lnk for lnk in asset_links
        }
        for gl in group_links:
            if gl.slo_name not in all_links:
                all_links[gl.slo_name] = gl

        for slo_name in all_links:
            try:
                ctx = await resolve_single_trigger(
                    asset_name=asset.name,
                    slo_name=slo_name,
                    asset_repo=asset_repo,
                    slo_link_repo=slo_link_repo,
                    sli_repo=sli_repo,
                    slo_repo=slo_repo,
                    ds_repo=ds_repo,
                )
            except ValueError:
                continue

            ev = await eval_repo.create_pending(
                name=body.test_name,
                period_start=body.period_start,
                period_end=body.period_end,
                ingestion_mode="pull",
                asset_snapshot={"name": ctx.asset_name, "tags": ctx.asset_labels},
                metadata=body.metadata,
                asset_id=ctx.asset_id,
                slo_name=ctx.slo_name,
                slo_version=ctx.slo_version,
                sli_name=ctx.sli_name,
                sli_version=ctx.sli_version,
                data_source_name=ctx.data_source_name,
                adapter_used=ctx.adapter_type,
            )
            evaluation_ids.append(ev.id)

    # Create batch record
    batch = EvaluationBatch(
        evaluation_ids=[str(eid) for eid in evaluation_ids],
        trigger_params={
            "group_name": body.group_name,
            "test_name": body.test_name,
            "period_start": body.period_start.isoformat(),
            "period_end": body.period_end.isoformat(),
        },
    )
    session.add(batch)
    await session.commit()

    for eid in evaluation_ids:
        await arq_pool.enqueue_job("run_evaluation_job", str(eid))

    return BatchTriggerResponse(
        batch_id=batch.id,
        evaluation_ids=evaluation_ids,
        status="pending",
    )


@router.get("/evaluations", response_model=PagedResponse[EvaluationSummary])
async def list_evaluations(
    asset_name: str | None = None,
    slo_name: str | None = None,
    result: str | None = None,
    date: str | None = None,
    group_name: str | None = None,
    from_ts: datetime | None = Query(default=None, alias="from"),  # noqa: B008
    to_ts: datetime | None = Query(default=None, alias="to"),  # noqa: B008
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> PagedResponse[EvaluationSummary]:
    """List evaluations with optional filters."""
    if date and (from_ts or to_ts):
        raise HTTPException(
            status_code=422,
            detail="date and from/to filters are mutually exclusive",
        )
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
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        offset=offset,
    )
    items = [
        _build_summary(ev, annotation_count=count_map.get(ev.id, 0), latest_ann=None)
        for ev in evals
    ]
    return PagedResponse(items=items, total=total)


@router.get("/evaluations/metric-heatmap", response_model=MetricHeatmapResponse)
async def get_metric_heatmap(
    asset_name: str,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MetricHeatmapResponse:
    """Return a metric x evaluation heatmap grid for an asset."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(asset_name)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"asset '{asset_name}' not found")
    eval_repo = EvaluationRepository(session)
    evals = await eval_repo.get_metric_heatmap(asset_id=asset.id, limit=limit)
    # Build slots (timestamps) and collect all unique metrics
    slots: list[datetime] = []
    metric_set: dict[str, str] = {}  # name -> display_name
    cells: list[HeatmapCell] = []
    for ev in reversed(evals):  # oldest first for display
        slots.append(ev.period_start)
        for ir in ev.indicator_results or []:
            metric_name = ir.get("metric", "")
            if metric_name not in metric_set:
                metric_set[metric_name] = ir.get("display_name", metric_name)
            cells.append(
                HeatmapCell(
                    slot=ev.period_start,
                    metric=metric_name,
                    display_name=ir.get("display_name", metric_name),
                    result=ir.get("status", "error"),
                    score=ir.get("score", 0.0),
                    eval_id=ev.id,
                )
            )
    return MetricHeatmapResponse(
        asset_name=asset_name,
        slots=slots,
        metrics=[HeatmapMetric(name=k, display_name=v) for k, v in metric_set.items()],
        cells=cells,
    )


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


@router.patch("/evaluations/{eval_id}/pin-baseline", response_model=EvaluationDetail)
async def pin_baseline(
    eval_id: uuid.UUID,
    body: PinBaselineRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EvaluationDetail:
    """Pin an evaluation as the new baseline for future comparisons."""
    repo = EvaluationRepository(session)
    ev = await repo.get_by_id(eval_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="evaluation not found")
    if ev.status != "completed":
        raise HTTPException(status_code=409, detail="only completed evaluations can be pinned")
    if ev.invalidated:
        raise HTTPException(status_code=409, detail="cannot pin an invalidated evaluation")
    updated = await repo.pin_baseline(eval_id, reason=body.reason, author=body.author)
    return _build_detail(updated)


@router.patch("/evaluations/{eval_id}/unpin-baseline", response_model=EvaluationDetail)
async def unpin_baseline(
    eval_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EvaluationDetail:
    """Remove baseline pin from an evaluation."""
    repo = EvaluationRepository(session)
    ev = await repo.get_by_id(eval_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="evaluation not found")
    updated = await repo.unpin_baseline(eval_id)
    return _build_detail(updated)


@router.patch("/evaluations/{eval_id}/override-status", response_model=EvaluationDetail)
async def override_status(
    eval_id: uuid.UUID,
    body: OverrideStatusRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EvaluationDetail:
    """Override the evaluation result."""
    repo = EvaluationRepository(session)
    ev = await repo.get_by_id(eval_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="evaluation not found")
    if ev.status != "completed":
        raise HTTPException(status_code=409, detail="only completed evaluations can be overridden")
    if body.new_result not in ("pass", "warning", "fail"):
        raise HTTPException(status_code=422, detail="new_result must be pass, warning, or fail")
    updated = await repo.override_status(
        eval_id, new_result=body.new_result, reason=body.reason, author=body.author
    )
    return _build_detail(updated)


@router.patch("/evaluations/{eval_id}/restore-override", response_model=EvaluationDetail)
async def restore_override(
    eval_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EvaluationDetail:
    """Restore the original evaluation result."""
    repo = EvaluationRepository(session)
    ev = await repo.get_by_id(eval_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="evaluation not found")
    if ev.original_result is None:
        raise HTTPException(status_code=409, detail="evaluation has no override to restore")
    updated = await repo.restore_override(eval_id)
    return _build_detail(updated)


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
    metric: str,
    eval_id: uuid.UUID | None = None,
    asset_name: str | None = None,
    slo_name: str | None = None,
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[TrendPoint]:
    """Return time-series trend data for a specific metric.

    Exactly one of eval_id or (asset_name + slo_name) must be provided.
    """
    has_eval = eval_id is not None
    has_any_asset_param = asset_name is not None or slo_name is not None

    if has_eval and has_any_asset_param:
        raise HTTPException(
            status_code=422,
            detail="provide either eval_id or (asset_name + slo_name), not both",
        )
    if not has_eval and not has_any_asset_param:
        raise HTTPException(
            status_code=422,
            detail="provide either eval_id or (asset_name + slo_name)",
        )
    if has_any_asset_param and (asset_name is None or slo_name is None):
        raise HTTPException(
            status_code=422,
            detail="both asset_name and slo_name are required when not using eval_id",
        )

    eval_repo = EvaluationRepository(session)

    if eval_id is not None:
        ev = await eval_repo.get_by_id(eval_id)
        if ev is None:
            raise_not_found("evaluation", str(eval_id))
        if ev.asset_id is None:
            raise HTTPException(status_code=422, detail="evaluation has no associated asset")
        if ev.slo_name is None:
            raise HTTPException(status_code=422, detail="evaluation has no associated slo")
        resolved_asset_id = ev.asset_id
        resolved_slo_name = ev.slo_name
    else:
        assert asset_name is not None  # guarded by has_any_asset_param checks above
        assert slo_name is not None  # guarded by has_any_asset_param checks above
        asset_repo = AssetRepository(session)
        asset = await asset_repo.get_by_name(asset_name)
        if asset is None:
            raise_not_found("asset", asset_name)
        resolved_asset_id = asset.id
        resolved_slo_name = slo_name

    points = await eval_repo.get_trend_by_domain(
        asset_id=resolved_asset_id,
        slo_name=resolved_slo_name,
        metric_name=metric,
        limit=limit,
    )
    return [TrendPoint(**p) for p in points]
