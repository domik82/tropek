"""FastAPI router for evaluations, annotations, and trend."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from arq.connections import ArqRedis
from fastapi import (  # HTTPException: BaselinePinConflictError dict detail
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
)
from pydantic import AfterValidator

from tropek.config import get_settings
from tropek.db.retry import run_with_deadlock_retry
from tropek.modules.assets.service import AssetService
from tropek.modules.change_points.detector import Direction
from tropek.modules.change_points.repository import ChangePointKey, ChangePointRepository
from tropek.modules.change_points.schemas import ChangePointMarker
from tropek.modules.common.exceptions import ConflictError, DomainValidationError, NotFoundError
from tropek.modules.common.schemas import PagedResponse, SafeQueryStr, reject_null_bytes
from tropek.modules.quality_gate.repositories.annotation_category import SystemCategoryError
from tropek.modules.quality_gate.schemas import (
    AnnotationCategoryCreate,
    AnnotationCategoryRead,
    AnnotationCategoryUpdate,
    AnnotationCreate,
    AnnotationHide,
    AnnotationRead,
    AnnotationUpdate,
    BulkActionResponse,
    BulkActionResult,
    EvaluateBatchRequest,
    EvaluateBatchResponse,
    EvaluateSingleRequest,
    EvaluateSingleResponse,
    EvaluationDetail,
    EvaluationNameEntry,
    EvaluationSummary,
    GroupedMetricHeatmapResponse,
    HeatmapCell,
    HeatmapMetric,
    InvalidateManyRequest,
    InvalidateRequest,
    MetricHeatmapResponse,
    OverrideStatusManyRequest,
    OverrideStatusRequest,
    PinBaselineManyRequest,
    PinBaselineRequest,
    RestoreManyRequest,
    RestoreOverrideManyRequest,
    TrendPoint,
    UnpinBaselineManyRequest,
)
from tropek.modules.quality_gate.schemas.heatmap import HeatmapColumnFragment
from tropek.modules.quality_gate.schemas.re_evaluation import (
    ReEvaluateFromBaselineRequest,
    ReEvaluateFromDateRequest,
    ReEvaluateFromEvaluationRequest,
    ReEvaluateResponse,
)
from tropek.modules.quality_gate.shared.dependencies import (
    QualityGateRepos,
    get_heatmap_column_cache,
    get_qg_repos,
)
from tropek.modules.quality_gate.shared.exceptions import BaselinePinConflictError
from tropek.modules.quality_gate.workflows.presentation.heatmap_cache import HeatmapColumnCache
from tropek.modules.quality_gate.workflows.presentation.presenter import (
    assemble_grouped_response,
    build_column_fragment,
    build_detail,
    build_summary,
)
from tropek.modules.quality_gate.workflows.re_evaluation.re_evaluation_service import (
    re_evaluate_from_baseline,
    re_evaluate_from_date,
    re_evaluate_from_evaluation,
)
from tropek.modules.quality_gate.workflows.trigger.trigger_service import TriggerService
from tropek.queue import get_arq_pool

router = APIRouter()


# ---- Trigger ----


@router.post('/evaluations', response_model=EvaluateSingleResponse, status_code=201)
async def trigger_evaluation(
    body: EvaluateSingleRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> EvaluateSingleResponse:
    """Trigger evaluation for all SLOs bound to an asset (new URL: POST /evaluations)."""
    service = TriggerService(repos, arq_pool)
    return await service.trigger_evaluate(body)


@router.post('/evaluations/batch', response_model=EvaluateBatchResponse, status_code=201)
async def trigger_evaluation_batch(
    body: EvaluateBatchRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> EvaluateBatchResponse:
    """Trigger batch evaluations (new URL: POST /evaluations/batch)."""
    service = TriggerService(repos, arq_pool)
    return await service.trigger_evaluate_batch(body)


# ---- Evaluations ----


@router.get('/evaluations', response_model=PagedResponse[EvaluationSummary])
async def list_evaluations(
    asset_name: SafeQueryStr | None = None,
    slo_name: SafeQueryStr | None = None,
    evaluation_name: list[SafeQueryStr] | None = Query(default=None),
    result: SafeQueryStr | None = None,
    date: SafeQueryStr | None = None,
    group_name: SafeQueryStr | None = None,
    from_ts: datetime | None = Query(
        default=None,
        alias='from',
        json_schema_extra={'anyOf': [{'format': 'date-time', 'type': 'string'}]},
    ),
    to_ts: datetime | None = Query(
        default=None,
        alias='to',
        json_schema_extra={'anyOf': [{'format': 'date-time', 'type': 'string'}]},
    ),
    limit: int = Query(default=200, ge=0, le=500),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> PagedResponse[EvaluationSummary]:
    """List evaluations with optional filters."""
    if date and (from_ts or to_ts):
        raise DomainValidationError('date and from/to filters are mutually exclusive')

    asset_service = AssetService(repos.asset_repo, repos.asset_group_repo)
    scope = await asset_service.resolve_asset_ids(asset_name, group_name)

    evals, total, count_map, latest_map = await repos.eval_repo.list_with_counts(
        asset_id=scope.asset_id,
        slo_name=slo_name,
        evaluation_name=evaluation_name,
        result=result,
        date_prefix=date,
        asset_ids=scope.asset_ids,
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


async def _enrich_heatmap_with_change_points(
    repos: QualityGateRepos,
    ordered_runs: list[Any],
    response: GroupedMetricHeatmapResponse,
) -> GroupedMetricHeatmapResponse:
    if not ordered_runs:
        return response
    change_point_repo = ChangePointRepository(repos.session)
    period_starts = [run.period_start for run in ordered_runs]
    change_point_lookup = await change_point_repo.get_change_points_for_evaluations(
        asset_id=ordered_runs[0].asset_id,
        period_starts=period_starts,
    )
    if change_point_lookup:
        run_by_id = {run.id: run for run in ordered_runs}
        for group in response.groups:
            for cell in group.cells:
                run = run_by_id.get(cell.evaluation_id)
                if run is None:
                    continue
                key = ChangePointKey(group.slo_name, cell.metric, cell.period_start, run.period_end, run.eval_name)
                change_point = change_point_lookup.get(key)
                if change_point is not None:
                    cell.change_point = ChangePointMarker(
                        direction=Direction(change_point.direction),
                        change_relative_pct=change_point.change_relative_pct,
                    )
    return response


@router.get('/evaluations/heatmap', response_model=GroupedMetricHeatmapResponse)
async def get_grouped_metric_heatmap_new(
    asset_name: SafeQueryStr,
    evaluation_name: list[SafeQueryStr] | None = Query(default=None),
    from_ts: datetime | None = Query(
        default=None,
        alias='from',
        json_schema_extra={'anyOf': [{'format': 'date-time', 'type': 'string'}]},
    ),
    to_ts: datetime | None = Query(
        default=None,
        alias='to',
        json_schema_extra={'anyOf': [{'format': 'date-time', 'type': 'string'}]},
    ),
    cache: bool = Query(
        default=True,
        description=(
            'When false, bypass the Redis column cache entirely: read every '
            'column from the DB, build every fragment, do not write back. '
            'Used for debugging and for the cache-correctness property test.'
        ),
    ),
    repos: QualityGateRepos = Depends(get_qg_repos),
    column_cache: HeatmapColumnCache | None = Depends(get_heatmap_column_cache),
) -> GroupedMetricHeatmapResponse:
    """Return a grouped metric heatmap (new URL: GET /evaluations/heatmap)."""
    asset = await repos.asset_repo.get_by_name(asset_name)
    if asset is None:
        raise NotFoundError('asset', asset_name)

    candidate_runs = await repos.trend_repo.list_runs_for_heatmap(
        asset_id=asset.id,
        eval_name=evaluation_name,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    candidate_run_ids = [run.id for run in candidate_runs]

    active_cache = column_cache if cache else None
    fragments_by_id: dict[str, HeatmapColumnFragment] = {}
    if active_cache is not None:
        fragments_by_id = await active_cache.get_many(candidate_run_ids)

    missing_ids = [run_id for run_id in candidate_run_ids if str(run_id) not in fragments_by_id]
    if missing_ids:
        missing_runs = await repos.trend_repo.get_grouped_metric_heatmap(asset_id=asset.id, run_id_filter=missing_ids)
        rebuilt_fragments = [build_column_fragment(run, has_notes=False) for run in missing_runs]
        for fragment in rebuilt_fragments:
            fragments_by_id[str(fragment.evaluation_run_id)] = fragment
        if active_cache is not None:
            await active_cache.set_many(rebuilt_fragments)

    noted_run_ids = await repos.trend_repo.get_run_ids_with_notes(candidate_run_ids)

    ordered_runs = sorted(candidate_runs, key=lambda r: (r.period_start, r.eval_name or ''))
    ordered_fragments: list[HeatmapColumnFragment] = []
    for run in ordered_runs:
        fragment = fragments_by_id[str(run.id)]
        ordered_fragments.append(
            fragment.model_copy(
                update={'column': fragment.column.model_copy(update={'has_notes': run.id in noted_run_ids})}
            )
        )

    response = assemble_grouped_response(asset_name, ordered_fragments)

    response = await _enrich_heatmap_with_change_points(repos, ordered_runs, response)

    return response


@router.delete('/evaluations/heatmap/cache', status_code=200)
async def flush_heatmap_cache(
    column_cache: HeatmapColumnCache | None = Depends(get_heatmap_column_cache),
) -> dict[str, int]:
    """Delete all cached heatmap column fragments, forcing a full rebuild on next request."""
    if column_cache is None:
        return {'deleted': 0}
    deleted = await column_cache.flush_all()
    return {'deleted': deleted}


@router.get('/evaluations/heatmap/by-metric', response_model=MetricHeatmapResponse)
async def get_metric_heatmap_new(
    asset_name: SafeQueryStr,
    evaluation_name: list[SafeQueryStr] | None = Query(default=None),
    from_ts: datetime | None = Query(
        default=None,
        alias='from',
        json_schema_extra={'anyOf': [{'format': 'date-time', 'type': 'string'}]},
    ),
    to_ts: datetime | None = Query(
        default=None,
        alias='to',
        json_schema_extra={'anyOf': [{'format': 'date-time', 'type': 'string'}]},
    ),
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> MetricHeatmapResponse:
    """Return a metric x evaluation heatmap grid (new URL: GET /evaluations/heatmap/by-metric)."""
    asset = await repos.asset_repo.get_by_name(asset_name)
    if asset is None:
        raise NotFoundError('asset', asset_name)
    evals = await repos.trend_repo.get_metric_heatmap(
        asset_id=asset.id,
        evaluation_name=evaluation_name,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    slots: list[datetime] = []
    metric_set: dict[str, str] = {}
    cells: list[HeatmapCell] = []
    score_metric = '__score__'
    for ev in reversed(evals):
        slots.append(ev.period_start)
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
        metrics=[
            *[HeatmapMetric(name=k, display_name=v) for k, v in metric_set.items()],
            HeatmapMetric(name=score_metric, display_name='Score'),
        ],
        cells=cells,
    )


@router.post('/evaluations/re-evaluate/from-date', response_model=ReEvaluateResponse)
async def re_evaluate_from_date_endpoint(
    body: ReEvaluateFromDateRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> ReEvaluateResponse:
    """Re-evaluate from a fixed start date (new split endpoint)."""
    try:
        return await re_evaluate_from_date(body, repos)
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
        raise DomainValidationError(str(e)) from e


@router.post('/evaluations/re-evaluate/from-baseline', response_model=ReEvaluateResponse)
async def re_evaluate_from_baseline_endpoint(
    body: ReEvaluateFromBaselineRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> ReEvaluateResponse:
    """Re-evaluate from the most recently pinned baseline (new split endpoint)."""
    try:
        return await re_evaluate_from_baseline(body, repos)
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
        raise DomainValidationError(str(e)) from e


@router.post(
    '/evaluations/re-evaluate/from-evaluation/{evaluation_id}',
    response_model=ReEvaluateResponse,
)
async def re_evaluate_from_evaluation_endpoint(
    evaluation_id: uuid.UUID,
    body: ReEvaluateFromEvaluationRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> ReEvaluateResponse:
    """Re-evaluate from the period_start of the given evaluation (new split endpoint)."""
    try:
        return await re_evaluate_from_evaluation(body, evaluation_id, repos)
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
        raise DomainValidationError(str(e)) from e


@router.get('/evaluations/names', response_model=list[EvaluationNameEntry])
async def list_evaluation_names(
    asset_name: SafeQueryStr | None = None,
    group_name: SafeQueryStr | None = None,
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
    '/evaluations/trend-annotations',
    response_model=dict[str, list[AnnotationRead]],
)
async def get_trend_annotations(
    asset_name: Annotated[
        str,
        Query(alias='asset', pattern=r'^[^\x00]*$'),
        AfterValidator(reject_null_bytes),
    ],
    slo_name: Annotated[
        str,
        Query(alias='slo', pattern=r'^[^\x00]*$'),
        AfterValidator(reject_null_bytes),
    ],
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> dict[str, list[AnnotationRead]]:
    """Return annotations for every point in an (asset, slo) trend, keyed by slo_evaluation_id.

    Trend points are identified by slo_evaluation_id, so the response keys match.
    Run-level annotations are fanned out across every slo_evaluation_id whose
    parent run they belong to; SLO-level annotations are keyed directly.
    """
    asset = await repos.asset_repo.get_by_name(asset_name)
    if asset is None:
        raise NotFoundError('asset', asset_name)

    annotations, run_to_slo_evals = await repos.annotation_repo.list_for_trend(
        asset_id=asset.id,
        slo_name=slo_name,
    )

    out: dict[str, list[AnnotationRead]] = {}
    for ann in annotations:
        read = AnnotationRead.model_validate(ann)
        if ann.slo_evaluation_id is not None:
            out.setdefault(str(ann.slo_evaluation_id), []).append(read)
        elif ann.evaluation_run_id is not None:
            for slo_eval_id in run_to_slo_evals.get(ann.evaluation_run_id, []):
                out.setdefault(str(slo_eval_id), []).append(read)
    return out


@router.get(
    '/evaluations/column-annotations',
    response_model=list[AnnotationRead],
)
async def get_column_annotations(
    evaluation_id: uuid.UUID = Query(...),
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> list[AnnotationRead]:
    """Return all non-hidden annotations for one evaluation run.

    Unions run-level notes (new column-level UI form) with the notes attached to each
    child SLO evaluation (per-SLO re-eval deltas). Sorted oldest-first by created_at.
    """
    run = await repos.eval_run_repo.get_by_id(evaluation_id)
    if run is None:
        raise NotFoundError('evaluation run', str(evaluation_id))
    slo_evals = await repos.eval_repo.get_by_run_id(evaluation_id)
    run_annotations = await repos.annotation_repo.list_for_run(evaluation_id)
    merged = list(run_annotations)
    merged.extend(ann for slo_eval in slo_evals for ann in slo_eval.annotations if ann.hidden_at is None)
    merged.sort(key=lambda a: a.created_at)
    return [AnnotationRead.model_validate(ann) for ann in merged]


# ---- Note categories ----


@router.get('/note-categories', response_model=list[AnnotationCategoryRead])
async def list_note_categories(
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> list[AnnotationCategoryRead]:
    """Return all annotation categories, alphabetically sorted."""
    rows = await repos.category_repo.list_all()
    return [AnnotationCategoryRead.model_validate(r) for r in rows]


@router.post('/note-categories', response_model=AnnotationCategoryRead, status_code=201)
async def create_note_category(
    body: AnnotationCategoryCreate,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> AnnotationCategoryRead:
    """Create a new user-defined annotation category."""
    created = await repos.category_repo.create(
        name=body.name,
        label=body.label,
        color=body.color.value,
        show_on_graph=body.show_on_graph,
    )
    return AnnotationCategoryRead.model_validate(created)


@router.patch('/note-categories/{category_id}', response_model=AnnotationCategoryRead)
async def update_note_category(
    category_id: uuid.UUID,
    body: AnnotationCategoryUpdate,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> AnnotationCategoryRead:
    """Patch an annotation category; renaming system rows returns 409."""
    try:
        updated = await repos.category_repo.update(
            category_id,
            name=body.name,
            label=body.label,
            color=body.color.value if body.color else None,
            show_on_graph=body.show_on_graph,
        )
    except SystemCategoryError as exc:
        raise ConflictError('annotation_category', str(category_id), str(exc)) from exc
    except LookupError as exc:
        raise NotFoundError('annotation_category', str(category_id)) from exc
    return AnnotationCategoryRead.model_validate(updated)


@router.delete('/note-categories/{category_id}', status_code=204)
async def delete_note_category(
    category_id: uuid.UUID,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> Response:
    """Delete a non-system category; returns the reassigned annotation count in a header."""
    try:
        reassigned = await repos.category_repo.delete(category_id)
    except SystemCategoryError as exc:
        raise ConflictError('annotation_category', str(category_id), str(exc)) from exc
    except LookupError as exc:
        raise NotFoundError('annotation_category', str(category_id)) from exc
    return Response(status_code=204, headers={'X-Reassigned-Annotations': str(reassigned)})


# ---- Trend ----


@router.get('/assets/{asset_name}/slos/{slo_name:path}/trend', response_model=list[TrendPoint])
async def get_trend_by_asset_slo(
    asset_name: str,
    slo_name: str,
    metric: str,
    from_ts: datetime = Query(alias='from'),
    to_ts: datetime | None = Query(
        default=None,
        alias='to',
        json_schema_extra={'anyOf': [{'format': 'date-time', 'type': 'string'}]},
    ),
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> list[TrendPoint]:
    """Return time-series trend data for a metric scoped to a specific asset + SLO."""
    asset = await repos.asset_repo.get_by_name(asset_name)
    if asset is None:
        raise NotFoundError('asset', asset_name)
    change_point_repo = ChangePointRepository(repos.session)
    change_point_lookup = await change_point_repo.get_change_points_for_range(
        asset_id=asset.id,
        slo_name=slo_name,
        metric_name=metric,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    points = await repos.trend_repo.get_trend_by_domain(
        asset_id=asset.id,
        slo_name=slo_name,
        metric_name=metric,
        from_ts=from_ts,
        to_ts=to_ts,
        change_point_lookup=change_point_lookup,
    )
    return [TrendPoint(**p) for p in points]


@router.get('/evaluation/{eval_id}/trend', response_model=list[TrendPoint])
async def get_trend_by_evaluation(
    eval_id: uuid.UUID,
    metric: str,
    from_ts: datetime = Query(alias='from'),
    to_ts: datetime | None = Query(
        default=None,
        alias='to',
        json_schema_extra={'anyOf': [{'format': 'date-time', 'type': 'string'}]},
    ),
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> list[TrendPoint]:
    """Return time-series trend data for a metric scoped to the asset+SLO of one evaluation."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    if ev.asset_id is None:
        raise DomainValidationError('evaluation has no associated asset')
    if ev.slo_name is None:
        raise DomainValidationError('evaluation has no associated slo')
    change_point_repo = ChangePointRepository(repos.session)
    change_point_lookup = await change_point_repo.get_change_points_for_range(
        asset_id=ev.asset_id,
        slo_name=ev.slo_name,
        metric_name=metric,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    points = await repos.trend_repo.get_trend_by_domain(
        asset_id=ev.asset_id,
        slo_name=ev.slo_name,
        metric_name=metric,
        from_ts=from_ts,
        to_ts=to_ts,
        change_point_lookup=change_point_lookup,
    )
    return [TrendPoint(**p) for p in points]


# ---- New singular single-resource routes ----


@router.get('/evaluation/{eval_id}', response_model=EvaluationDetail)
async def get_evaluation_singular(
    eval_id: uuid.UUID,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationDetail:
    """Get full evaluation detail (new singular URL: GET /evaluation/{id})."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    return build_detail(ev)


# ---- Bulk (batch) evaluation actions ----


def _bulk_response(requested_ids: list[uuid.UUID], affected_rows: list[Any]) -> BulkActionResponse:
    """Build a BulkActionResponse from the requested ids and the affected rows.

    Ids that were not applied (unknown, or skipped by a precondition such as
    "not completed") are reported in ``not_found``; they do not fail the batch.
    """
    affected_ids = {row.id for row in affected_rows}
    results = [BulkActionResult(evaluation_id=row.id, status='success') for row in affected_rows]
    not_found = [eval_id for eval_id in requested_ids if eval_id not in affected_ids]
    return BulkActionResponse(results=results, updated=len(results), not_found=not_found)


@router.patch('/evaluations/invalidate', response_model=BulkActionResponse)
async def invalidate_evaluations_bulk(
    body: InvalidateManyRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> BulkActionResponse:
    """Invalidate a batch of evaluations in a single atomic statement."""
    rows = await run_with_deadlock_retry(
        repos.session,
        lambda: repos.eval_repo.invalidate_many(body.evaluation_ids, note=body.note),
        settings=get_settings().quality_gate.invalidate,
    )
    return _bulk_response(body.evaluation_ids, rows)


@router.patch('/evaluations/restore', response_model=BulkActionResponse)
async def restore_evaluations_bulk(
    body: RestoreManyRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> BulkActionResponse:
    """Clear the invalidation flag on a batch of evaluations."""
    rows = await run_with_deadlock_retry(
        repos.session,
        lambda: repos.eval_repo.restore_many(body.evaluation_ids),
        settings=get_settings().quality_gate.invalidate,
    )
    return _bulk_response(body.evaluation_ids, rows)


@router.patch('/evaluations/override-status', response_model=BulkActionResponse)
async def override_status_evaluations_bulk(
    body: OverrideStatusManyRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> BulkActionResponse:
    """Override the result of a batch of completed evaluations."""
    rows = await run_with_deadlock_retry(
        repos.session,
        lambda: repos.eval_repo.override_status_many(
            body.evaluation_ids,
            new_result=body.new_result,
            reason=body.reason,
            author=body.author,
        ),
        settings=get_settings().quality_gate.invalidate,
    )
    return _bulk_response(body.evaluation_ids, rows)


@router.patch('/evaluations/restore-override', response_model=BulkActionResponse)
async def restore_override_evaluations_bulk(
    body: RestoreOverrideManyRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> BulkActionResponse:
    """Restore the original result on a batch of overridden evaluations."""
    rows = await run_with_deadlock_retry(
        repos.session,
        lambda: repos.eval_repo.restore_override_many(body.evaluation_ids),
        settings=get_settings().quality_gate.invalidate,
    )
    return _bulk_response(body.evaluation_ids, rows)


@router.patch('/evaluations/pin-baseline', response_model=BulkActionResponse)
async def pin_baseline_evaluations_bulk(
    body: PinBaselineManyRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> BulkActionResponse:
    """Pin a batch of completed, non-invalidated evaluations as baselines."""
    rows = await run_with_deadlock_retry(
        repos.session,
        lambda: repos.eval_repo.pin_baseline_many(
            body.evaluation_ids,
            reason=body.reason,
            author=body.author,
        ),
        settings=get_settings().quality_gate.invalidate,
    )
    return _bulk_response(body.evaluation_ids, rows)


@router.patch('/evaluations/unpin-baseline', response_model=BulkActionResponse)
async def unpin_baseline_evaluations_bulk(
    body: UnpinBaselineManyRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> BulkActionResponse:
    """Remove the baseline pin from a batch of evaluations."""
    rows = await run_with_deadlock_retry(
        repos.session,
        lambda: repos.eval_repo.unpin_baseline_many(body.evaluation_ids),
        settings=get_settings().quality_gate.invalidate,
    )
    return _bulk_response(body.evaluation_ids, rows)


@router.patch('/evaluation/{eval_id}/invalidate', response_model=EvaluationSummary)
async def invalidate_evaluation_singular(
    eval_id: uuid.UUID,
    body: InvalidateRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationSummary:
    """Mark an evaluation as invalidated (new singular URL)."""
    ev = await run_with_deadlock_retry(
        repos.session,
        lambda: repos.eval_repo.invalidate(eval_id, note=body.invalidation_note),
        settings=get_settings().quality_gate.invalidate,
    )
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    return build_summary(ev, annotation_count=0, latest_ann=None)


@router.patch('/evaluation/{eval_id}/restore', response_model=EvaluationSummary)
async def restore_evaluation_singular(
    eval_id: uuid.UUID,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationSummary:
    """Clear invalidation flag on an evaluation (new singular URL)."""
    ev = await run_with_deadlock_retry(
        repos.session,
        lambda: repos.eval_repo.restore(eval_id),
        settings=get_settings().quality_gate.invalidate,
    )
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    return build_summary(ev, annotation_count=0, latest_ann=None)


@router.patch('/evaluation/{eval_id}/pin-baseline', response_model=EvaluationDetail)
async def pin_baseline_singular(
    eval_id: uuid.UUID,
    body: PinBaselineRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationDetail:
    """Pin an evaluation as the new baseline (new singular URL)."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    if ev.status != 'completed':
        raise ConflictError('evaluation', str(eval_id), 'only completed evaluations can be pinned')
    if ev.invalidated:
        raise ConflictError('evaluation', str(eval_id), 'cannot pin an invalidated evaluation')
    updated = await repos.eval_repo.pin_baseline(eval_id, reason=body.reason, author=body.author)
    if updated is None:
        raise NotFoundError('evaluation', str(eval_id))
    return build_detail(updated)


@router.patch('/evaluation/{eval_id}/unpin-baseline', response_model=EvaluationDetail)
async def unpin_baseline_singular(
    eval_id: uuid.UUID,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationDetail:
    """Remove baseline pin from an evaluation (new singular URL)."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    updated = await repos.eval_repo.unpin_baseline(eval_id)
    if updated is None:
        raise NotFoundError('evaluation', str(eval_id))
    return build_detail(updated)


@router.patch('/evaluation/{eval_id}/override-status', response_model=EvaluationDetail)
async def override_status_singular(
    eval_id: uuid.UUID,
    body: OverrideStatusRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationDetail:
    """Override the evaluation result (new singular URL)."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    if ev.status != 'completed':
        raise ConflictError('evaluation', str(eval_id), 'only completed evaluations can be overridden')
    updated = await repos.eval_repo.override_status(
        eval_id, new_result=body.new_result, reason=body.reason, author=body.author
    )
    if updated is None:
        raise NotFoundError('evaluation', str(eval_id))
    return build_detail(updated)


@router.patch('/evaluation/{eval_id}/restore-override', response_model=EvaluationDetail)
async def restore_override_singular(
    eval_id: uuid.UUID,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationDetail:
    """Restore the original evaluation result (new singular URL)."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    if ev.original_result is None:
        raise ConflictError('evaluation', str(eval_id), 'has no override to restore')
    updated = await repos.eval_repo.restore_override(eval_id)
    if updated is None:
        raise NotFoundError('evaluation', str(eval_id))
    return build_detail(updated)


@router.get('/evaluation/{eval_id}/annotations', response_model=list[AnnotationRead])
async def list_annotations_singular(
    eval_id: uuid.UUID,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> list[AnnotationRead]:
    """List all annotations for an evaluation (new singular URL)."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    return [AnnotationRead.model_validate(a) for a in ev.annotations if a.hidden_at is None]


@router.post('/evaluation/{eval_id}/annotations', response_model=AnnotationRead, status_code=201)
async def create_annotation_singular(
    eval_id: uuid.UUID,
    body: AnnotationCreate,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> AnnotationRead:
    """Add an SLO-level annotation to a single SLOEvaluation (new singular URL)."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    created = await repos.annotation_repo.add_annotation(
        eval_id,
        content=body.content,
        author=body.author,
        category_id=body.category_id,
        tags=body.tags,
    )
    fetched = await repos.annotation_repo.get_annotation_by_id(created.id)
    assert fetched is not None
    return AnnotationRead.model_validate(fetched)


@router.patch('/evaluation/{eval_id}/annotations/{ann_id}', response_model=AnnotationRead)
async def update_annotation_singular(
    eval_id: uuid.UUID,
    ann_id: uuid.UUID,
    body: AnnotationUpdate,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> AnnotationRead:
    """Update an annotation (new singular URL)."""
    ann = await repos.annotation_repo.update_annotation(ann_id, **body.model_dump(exclude_unset=True))
    if ann is None:
        raise NotFoundError('annotation', str(ann_id))
    return AnnotationRead.model_validate(ann)


@router.post(
    '/evaluation/{eval_id}/annotations/{ann_id}/hide',
    response_model=AnnotationRead,
)
async def hide_annotation_singular(
    eval_id: uuid.UUID,
    ann_id: uuid.UUID,
    body: AnnotationHide,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> AnnotationRead:
    """Soft-delete (hide) an annotation (new singular URL)."""
    ann = await repos.annotation_repo.hide_annotation(ann_id, reason=body.reason, author=body.author)
    if ann is None:
        raise NotFoundError('annotation', str(ann_id))
    return AnnotationRead.model_validate(ann)


@router.post(
    '/evaluation-run/{run_id}/annotations',
    response_model=AnnotationRead,
    status_code=201,
)
async def create_run_annotation_new(
    run_id: uuid.UUID,
    body: AnnotationCreate,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> AnnotationRead:
    """Add a run-level annotation to an EvaluationRun (new URL: /evaluation-run/{id}/annotations)."""
    run = await repos.eval_run_repo.get_by_id(run_id)
    if run is None:
        raise NotFoundError('evaluation run', str(run_id))
    created = await repos.annotation_repo.add_run_annotation(
        run_id,
        content=body.content,
        author=body.author,
        category_id=body.category_id,
        tags=body.tags,
    )
    fetched = await repos.annotation_repo.get_annotation_by_id(created.id)
    assert fetched is not None
    return AnnotationRead.model_validate(fetched)
