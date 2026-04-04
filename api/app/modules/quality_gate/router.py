"""FastAPI router for evaluations, annotations, and trend."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvaluationRun
from app.db.session import get_session
from app.modules.common.exceptions import NotFoundError
from app.modules.common.schemas import PagedResponse
from app.modules.quality_gate.dependencies import QualityGateRepos, get_qg_repos
from app.modules.quality_gate.presenter import build_detail, build_summary
from app.modules.quality_gate.re_evaluator import re_evaluate
from app.modules.quality_gate.schemas import (
    AnnotationCreate,
    AnnotationHide,
    AnnotationRead,
    AnnotationUpdate,
    EvaluateBatchRequest,
    EvaluateBatchResponse,
    EvaluateSingleRequest,
    EvaluateSingleResponse,
    EvaluationColumn,
    EvaluationDetail,
    EvaluationNameEntry,
    EvaluationSummary,
    GroupedMetricHeatmapResponse,
    HeatmapCell,
    HeatmapCellGrouped,
    HeatmapMetric,
    HeatmapSummaryCell,
    InvalidateRequest,
    MetricHeatmapResponse,
    OverrideStatusRequest,
    PinBaselineRequest,
    SloGroup,
    TrendPoint,
)
from app.modules.quality_gate.schemas.re_evaluation import (
    BaselinePinConflictError,
    ReEvaluateRequest,
    ReEvaluateResponse,
)
from app.modules.quality_gate.target_resolver import resolve_targets
from app.modules.quality_gate.trigger_service import TriggerService
from app.queue import get_arq_pool

router = APIRouter()


# ---- Trigger ----


@router.post('/evaluate', response_model=EvaluateSingleResponse, status_code=201)
async def evaluate_asset(
    body: EvaluateSingleRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> EvaluateSingleResponse:
    """Trigger evaluation for all SLOs bound to an asset."""
    service = TriggerService(repos, arq_pool)
    return await service.trigger_evaluate(body)


@router.post('/evaluate/batch', response_model=EvaluateBatchResponse, status_code=201)
async def evaluate_batch(
    body: EvaluateBatchRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> EvaluateBatchResponse:
    """Trigger batch evaluations (by_date or by_asset mode)."""
    service = TriggerService(repos, arq_pool)
    return await service.trigger_evaluate_batch(body)


# ---- Evaluations ----


@router.get('/evaluations', response_model=PagedResponse[EvaluationSummary])
async def list_evaluations(  # noqa: PLR0913
    asset_name: str | None = None,
    slo_name: str | None = None,
    evaluation_name: list[str] | None = Query(default=None),
    result: str | None = None,
    date: str | None = None,
    group_name: str | None = None,
    from_ts: datetime | None = Query(default=None, alias='from'),
    to_ts: datetime | None = Query(default=None, alias='to'),
    limit: int = Query(default=200, le=500),
    offset: int = 0,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> PagedResponse[EvaluationSummary]:
    """List evaluations with optional filters."""
    if date and (from_ts or to_ts):
        raise HTTPException(
            status_code=422,
            detail='date and from/to filters are mutually exclusive',
        )
    resolved_asset_id: uuid.UUID | None = None
    asset_ids: list[uuid.UUID] | None = None

    if asset_name:
        asset = await repos.asset_repo.get_by_name(asset_name)
        if asset is None:
            raise NotFoundError('asset', asset_name)
        resolved_asset_id = asset.id

    if group_name:
        group = await repos.asset_group_repo.get_by_name(group_name)
        if group:
            asset_ids = [m.asset_id for m in group.members]

    evals, total, count_map, latest_map = await repos.eval_repo.list_with_counts(
        asset_id=resolved_asset_id,
        slo_name=slo_name,
        evaluation_name=evaluation_name,
        result=result,
        date_prefix=date,
        asset_ids=asset_ids,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        offset=offset,
    )
    items = [
        build_summary(
            ev,
            annotation_count=count_map.get(ev.id, 0),
            latest_ann=latest_map.get(ev.id),
        )
        for ev in evals
    ]
    return PagedResponse(items=items, total=total)


_RESULT_RANK: dict[str, int] = {'pass': 0, 'warning': 1, 'fail': 2, 'error': 3, 'invalidated': 4}


def _worst_result(results: list[str]) -> str:
    """Return the worst result in `results`, defaulting to 'none' if empty."""
    if not results:
        return 'none'
    return max(results, key=lambda r: _RESULT_RANK.get(r, -1))


def _build_grouped_heatmap_response(
    asset_name: str,
    runs: list[EvaluationRun],
) -> GroupedMetricHeatmapResponse:
    """Build GroupedMetricHeatmapResponse from a list of EvaluationRun rows.

    Assumes each run already has slo_evaluations + indicator_rows eager-loaded.
    Runs must arrive in DESC order (newest first) — this function reverses to ASC.
    """
    runs_asc = sorted(runs, key=lambda r: r.period_start)
    n = len(runs_asc)

    columns = [
        EvaluationColumn(
            evaluation_id=run.id,
            period_start=run.period_start,
            period_end=run.period_end,
            eval_name=run.eval_name,
        )
        for run in runs_asc
    ]
    col_idx: dict[uuid.UUID, int] = {run.id: i for i, run in enumerate(runs_asc)}

    # slo_name → {metrics, cells, per_col_results, per_col: xi → slo_eval}
    slo_data: dict[str, dict[str, Any]] = {}

    for run in runs_asc:
        xi = col_idx[run.id]
        for slo_eval in run.slo_evaluations or []:
            sn = slo_eval.slo_name
            if sn not in slo_data:
                slo_data[sn] = {
                    'metrics': {},
                    'cells': [],
                    'per_col': {},
                }
            sd = slo_data[sn]
            sd['per_col'][xi] = slo_eval
            for row in slo_eval.indicator_rows or []:
                obj = row.objective
                mn = obj.sli
                dn = obj.display_name or mn
                if mn not in sd['metrics']:
                    sd['metrics'][mn] = dn
                sli_meta = slo_eval.job_stats.get('sli_metadata', {})
                sd['cells'].append(
                    HeatmapCellGrouped(
                        evaluation_id=run.id,
                        slo_evaluation_id=slo_eval.id,
                        period_start=run.period_start,
                        metric=mn,
                        display_name=dn,
                        result='invalidated' if slo_eval.invalidated else row.status,
                        score=row.score,
                        value=row.value,
                        compared_value=row.compared_value,
                        change_relative_pct=row.change_relative_pct,
                        weight=obj.weight,
                        key_sli=obj.key_sli,
                        pass_targets=resolve_targets(
                            list(obj.pass_threshold) if obj.pass_threshold else None,
                            value=row.value,
                            compared_value=row.compared_value,
                        ),
                        warning_targets=resolve_targets(
                            list(obj.warning_threshold) if obj.warning_threshold else None,
                            value=row.value,
                            compared_value=row.compared_value,
                        ),
                        tab_group=obj.tab_group,
                        aggregation=sli_meta.get(mn, {}).get('mode'),
                    )
                )

    groups = []
    for sn, sd in slo_data.items():
        summary = []
        for xi in range(n):
            slo_ev = sd['per_col'].get(xi)
            result = (
                'invalidated' if slo_ev and slo_ev.invalidated
                else slo_ev.result if slo_ev and slo_ev.result
                else 'none'
            )
            score = (
                slo_ev.achieved_points / slo_ev.total_points * 100
                if slo_ev and slo_ev.total_points
                else 0.0
            )
            summary.append(
                HeatmapSummaryCell(
                    evaluation_id=runs_asc[xi].id,
                    period_start=runs_asc[xi].period_start,
                    result=result,
                    score=round(score, 2),
                    total_score_pass_threshold=(
                        slo_ev.job_stats.get('total_score_pass_threshold') if slo_ev else None
                    ),
                    total_score_warning_threshold=(
                        slo_ev.job_stats.get('total_score_warning_threshold') if slo_ev else None
                    ),
                    sli_metadata=slo_ev.job_stats.get('sli_metadata') if slo_ev else None,
                    invalidated=slo_ev.invalidated if slo_ev else False,
                    invalidation_note=slo_ev.invalidation_note if slo_ev else None,
                )
            )
        groups.append(
            SloGroup(
                slo_name=sn,
                metrics=[HeatmapMetric(name=mn, display_name=dn) for mn, dn in sd['metrics'].items()],
                cells=sd['cells'],
                summary=summary,
            )
        )

    composite = []
    for xi in range(n):
        run = runs_asc[xi]
        tp = run.total_points
        ap = run.achieved_points
        run_score = round(ap / tp * 100, 2) if tp and ap is not None else 0.0
        all_invalidated = run.slo_evaluations and all(
            se.invalidated for se in run.slo_evaluations
        )
        composite.append(
            HeatmapSummaryCell(
                evaluation_id=run.id,
                period_start=run.period_start,
                result='invalidated' if all_invalidated else (run.result or 'none'),
                score=run_score,
            )
        )

    return GroupedMetricHeatmapResponse(
        asset_name=asset_name,
        columns=columns,
        groups=groups,
        composite=composite,
    )


@router.get('/evaluations/metric-heatmap', response_model=MetricHeatmapResponse)
async def get_metric_heatmap(
    asset_name: str,
    evaluation_name: list[str] | None = Query(default=None),
    from_ts: datetime | None = Query(default=None, alias='from'),
    to_ts: datetime | None = Query(default=None, alias='to'),
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> MetricHeatmapResponse:
    """Return a metric x evaluation heatmap grid for an asset."""
    asset = await repos.asset_repo.get_by_name(asset_name)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"asset '{asset_name}' not found")
    evals = await repos.trend_repo.get_metric_heatmap(
        asset_id=asset.id,
        evaluation_name=evaluation_name,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    # Build slots (timestamps) and collect all unique metrics
    slots: list[datetime] = []
    metric_set: dict[str, str] = {}  # name -> display_name
    cells: list[HeatmapCell] = []
    score_metric = '__score__'
    for ev in reversed(evals):  # oldest first for display
        slots.append(ev.period_start)
        # Overall evaluation score row
        cells.append(
            HeatmapCell(
                slot=ev.period_start,
                metric=score_metric,
                display_name='Score',
                result='invalidated' if ev.invalidated else (ev.result or 'none'),
                score=ev.score or 0.0,
                eval_id=ev.id,
                evaluation_name=ev.evaluation_name,
            )
        )
        for row in ev.indicator_rows or []:
            obj = row.objective
            metric_name = obj.sli
            display = obj.display_name or metric_name
            if metric_name not in metric_set:
                metric_set[metric_name] = display
            cells.append(
                HeatmapCell(
                    slot=ev.period_start,
                    metric=metric_name,
                    display_name=display,
                    result=(
                        'invalidated'
                        if ev.invalidated
                        else (ev.result or row.status)
                        if ev.original_result is not None
                        else row.status
                    ),
                    score=row.score,
                    eval_id=ev.id,
                    evaluation_name=ev.evaluation_name,
                )
            )
    return MetricHeatmapResponse(
        asset_name=asset_name,
        slots=slots,
        # Score must be LAST: ECharts category axis renders bottom-to-top,
        # so the last metric appears at the top of the heatmap.
        # See also: ui/src/components/charts/HeatmapChart.tsx (yAxis)
        metrics=[
            *[HeatmapMetric(name=k, display_name=v) for k, v in metric_set.items()],
            HeatmapMetric(name=score_metric, display_name='Score'),
        ],
        cells=cells,
    )


@router.get('/evaluate/metric-heatmap', response_model=GroupedMetricHeatmapResponse)
async def get_grouped_metric_heatmap(
    asset_name: str,
    evaluation_name: list[str] | None = Query(default=None),
    from_ts: datetime | None = Query(default=None, alias='from'),
    to_ts: datetime | None = Query(default=None, alias='to'),
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> GroupedMetricHeatmapResponse:
    """Return a grouped metric heatmap — one column per parent EvaluationRun."""
    asset = await repos.asset_repo.get_by_name(asset_name)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"asset '{asset_name}' not found")
    runs = await repos.trend_repo.get_grouped_metric_heatmap(
        asset_id=asset.id,
        eval_name=evaluation_name,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    return _build_grouped_heatmap_response(asset_name, runs)


@router.post('/evaluations/re-evaluate', response_model=ReEvaluateResponse)
async def re_evaluate_evaluations(
    body: ReEvaluateRequest,
    session: AsyncSession = Depends(get_session),
) -> ReEvaluateResponse:
    """Re-evaluate completed evaluations from stored SLI values."""
    try:
        return await re_evaluate(body, session)
    except BaselinePinConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={
                'detail': str(e),
                'pin_date': e.pin_date.isoformat(),
                'pin_evaluation_id': str(e.pin_evaluation_id),
            },
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get('/evaluations/names', response_model=list[EvaluationNameEntry])
async def list_evaluation_names(
    asset_name: str | None = None,
    group_name: str | None = None,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> list[EvaluationNameEntry]:
    """Return distinct evaluation names with count and last-run date."""
    resolved_asset_id = None
    asset_ids = None
    if asset_name:
        asset = await repos.asset_repo.get_by_name(asset_name)
        if asset is None:
            return []
        resolved_asset_id = asset.id
    if group_name:
        group = await repos.asset_group_repo.get_by_name(group_name)
        if group:
            asset_ids = [m.asset_id for m in (group.members or [])]
        else:
            return []
    rows = await repos.eval_repo.list_evaluation_names(
        asset_id=resolved_asset_id,
        asset_ids=asset_ids,
    )
    return [EvaluationNameEntry(name=name, count=count, last_run=last_run) for name, count, last_run in rows]


@router.get(
    '/evaluations/column-annotations',
    response_model=list[AnnotationRead],
)
async def get_column_annotations(
    evaluation_id: uuid.UUID = Query(...),
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> list[AnnotationRead]:
    """Return all non-hidden annotations across all SLOs for one evaluation run."""
    run = await repos.eval_run_repo.get_by_id(evaluation_id)
    if run is None:
        raise NotFoundError('evaluation run', str(evaluation_id))
    slo_evals = await repos.eval_repo.get_by_run_id(evaluation_id)
    annotations: list[AnnotationRead] = []
    annotations.extend(
        AnnotationRead.model_validate(ann)
        for slo_eval in slo_evals
        for ann in slo_eval.annotations
        if ann.hidden_at is None
    )
    return annotations


@router.get('/evaluations/{eval_id}', response_model=EvaluationDetail)
async def get_evaluation(
    eval_id: uuid.UUID,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationDetail:
    """Get full evaluation detail including annotations and indicator results."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    return build_detail(ev)


@router.patch('/evaluations/{eval_id}/invalidate', response_model=EvaluationSummary)
async def invalidate_evaluation(
    eval_id: uuid.UUID,
    body: InvalidateRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationSummary:
    """Mark an evaluation as invalidated."""
    ev = await repos.eval_repo.invalidate(eval_id, note=body.invalidation_note)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    return build_summary(ev, annotation_count=0, latest_ann=None)


@router.patch('/evaluations/{eval_id}/restore', response_model=EvaluationSummary)
async def restore_evaluation(
    eval_id: uuid.UUID,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationSummary:
    """Clear invalidation flag on an evaluation."""
    ev = await repos.eval_repo.restore(eval_id)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    return build_summary(ev, annotation_count=0, latest_ann=None)


@router.patch('/evaluations/{eval_id}/pin-baseline', response_model=EvaluationDetail)
async def pin_baseline(
    eval_id: uuid.UUID,
    body: PinBaselineRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationDetail:
    """Pin an evaluation as the new baseline for future comparisons."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise HTTPException(status_code=404, detail='evaluation not found')
    if ev.status != 'completed':
        raise HTTPException(status_code=409, detail='only completed evaluations can be pinned')
    if ev.invalidated:
        raise HTTPException(status_code=409, detail='cannot pin an invalidated evaluation')
    updated = await repos.eval_repo.pin_baseline(eval_id, reason=body.reason, author=body.author)
    return build_detail(updated)


@router.patch('/evaluations/{eval_id}/unpin-baseline', response_model=EvaluationDetail)
async def unpin_baseline(
    eval_id: uuid.UUID,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationDetail:
    """Remove baseline pin from an evaluation."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise HTTPException(status_code=404, detail='evaluation not found')
    updated = await repos.eval_repo.unpin_baseline(eval_id)
    return build_detail(updated)


@router.patch('/evaluations/{eval_id}/override-status', response_model=EvaluationDetail)
async def override_status(
    eval_id: uuid.UUID,
    body: OverrideStatusRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationDetail:
    """Override the evaluation result."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise HTTPException(status_code=404, detail='evaluation not found')
    if ev.status != 'completed':
        raise HTTPException(status_code=409, detail='only completed evaluations can be overridden')
    if body.new_result not in ('pass', 'warning', 'fail'):
        raise HTTPException(status_code=422, detail='new_result must be pass, warning, or fail')
    updated = await repos.eval_repo.override_status(
        eval_id, new_result=body.new_result, reason=body.reason, author=body.author
    )
    return build_detail(updated)


@router.patch('/evaluations/{eval_id}/restore-override', response_model=EvaluationDetail)
async def restore_override(
    eval_id: uuid.UUID,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationDetail:
    """Restore the original evaluation result."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise HTTPException(status_code=404, detail='evaluation not found')
    if ev.original_result is None:
        raise HTTPException(status_code=409, detail='evaluation has no override to restore')
    updated = await repos.eval_repo.restore_override(eval_id)
    return build_detail(updated)




# ---- Annotations ----


@router.get('/evaluations/{eval_id}/annotations', response_model=list[AnnotationRead])
async def list_annotations(
    eval_id: uuid.UUID,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> list[AnnotationRead]:
    """List all annotations for an evaluation."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    return [AnnotationRead.model_validate(a) for a in ev.annotations if a.hidden_at is None]


@router.post('/evaluations/{eval_id}/annotations', response_model=AnnotationRead, status_code=201)
async def create_annotation(
    eval_id: uuid.UUID,
    body: AnnotationCreate,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> AnnotationRead:
    """Add an annotation to an evaluation."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    ann = await repos.annotation_repo.add_annotation(
        eval_id,
        content=body.content,
        author=body.author,
        category=body.category,
        tags=body.tags,
    )
    return AnnotationRead.model_validate(ann)


@router.patch('/evaluations/{eval_id}/annotations/{ann_id}', response_model=AnnotationRead)
async def update_annotation(
    eval_id: uuid.UUID,
    ann_id: uuid.UUID,
    body: AnnotationUpdate,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> AnnotationRead:
    """Update an annotation."""
    ann = await repos.annotation_repo.update_annotation(ann_id, **body.model_dump(exclude_unset=True))
    if ann is None:
        raise NotFoundError('annotation', str(ann_id))
    return AnnotationRead.model_validate(ann)


@router.post(
    '/evaluations/{eval_id}/annotations/{ann_id}/hide',
    response_model=AnnotationRead,
)
async def hide_annotation(
    eval_id: uuid.UUID,
    ann_id: uuid.UUID,
    body: AnnotationHide,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> AnnotationRead:
    """Soft-delete (hide) an annotation."""
    ann = await repos.annotation_repo.hide_annotation(ann_id, reason=body.reason, author=body.author)
    if ann is None:
        raise NotFoundError('annotation', str(ann_id))
    return AnnotationRead.model_validate(ann)


# ---- Trend ----


@router.get('/trend', response_model=list[TrendPoint])
async def get_trend(
    metric: str,
    eval_id: uuid.UUID | None = None,
    asset_name: str | None = None,
    slo_name: str | None = None,
    from_ts: datetime = Query(alias='from'),
    to_ts: datetime | None = Query(default=None, alias='to'),
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> list[TrendPoint]:
    """Return time-series trend data for a specific metric.

    Exactly one of eval_id or (asset_name + slo_name) must be provided.
    The ``from`` parameter is required; ``to`` defaults to now.
    """
    has_eval = eval_id is not None
    has_any_asset_param = asset_name is not None or slo_name is not None

    if has_eval and has_any_asset_param:
        raise HTTPException(
            status_code=422,
            detail='provide either eval_id or (asset_name + slo_name), not both',
        )
    if not has_eval and not has_any_asset_param:
        raise HTTPException(
            status_code=422,
            detail='provide either eval_id or (asset_name + slo_name)',
        )
    if has_any_asset_param and (asset_name is None or slo_name is None):
        raise HTTPException(
            status_code=422,
            detail='both asset_name and slo_name are required when not using eval_id',
        )

    if eval_id is not None:
        ev = await repos.eval_repo.get_by_id(eval_id)
        if ev is None:
            raise NotFoundError('evaluation', str(eval_id))
        if ev.asset_id is None:
            raise HTTPException(status_code=422, detail='evaluation has no associated asset')
        if ev.slo_name is None:
            raise HTTPException(status_code=422, detail='evaluation has no associated slo')
        resolved_asset_id = ev.asset_id
        resolved_slo_name = ev.slo_name
    else:
        assert asset_name is not None  # guarded by has_any_asset_param checks above
        assert slo_name is not None  # guarded by has_any_asset_param checks above
        asset = await repos.asset_repo.get_by_name(asset_name)
        if asset is None:
            raise NotFoundError('asset', asset_name)
        resolved_asset_id = asset.id
        resolved_slo_name = slo_name

    points = await repos.trend_repo.get_trend_by_domain(
        asset_id=resolved_asset_id,
        slo_name=resolved_slo_name,
        metric_name=metric,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    return [TrendPoint(**p) for p in points]
