"""FastAPI router for evaluations, annotations, and trend."""

from __future__ import annotations

import uuid
from datetime import datetime

from arq.connections import ArqRedis
from fastapi import (  # HTTPException: BaselinePinConflictError dict detail
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
)

from tropek.modules.assets.service import AssetService
from tropek.modules.common.exceptions import ConflictError, DomainValidationError, NotFoundError
from tropek.modules.common.schemas import PagedResponse
from tropek.modules.quality_gate.repositories.annotation_category import SystemCategoryError
from tropek.modules.quality_gate.schemas import (
    AnnotationCategoryCreate,
    AnnotationCategoryRead,
    AnnotationCategoryUpdate,
    AnnotationCreate,
    AnnotationHide,
    AnnotationRead,
    AnnotationUpdate,
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
    InvalidateRequest,
    MetricHeatmapResponse,
    OverrideStatusRequest,
    PinBaselineRequest,
    TrendPoint,
)
from tropek.modules.quality_gate.schemas.heatmap import HeatmapColumnFragment
from tropek.modules.quality_gate.schemas.re_evaluation import (
    ReEvaluateRequest,
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
from tropek.modules.quality_gate.workflows.re_evaluation.re_evaluation_service import re_evaluate
from tropek.modules.quality_gate.workflows.trigger.trigger_service import TriggerService
from tropek.queue import get_arq_pool

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
        raise NotFoundError('asset', asset_name)
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
    """Return a grouped metric heatmap — one column per parent EvaluationRun.

    Read path: run a cheap list query for the candidate run ids in the window,
    MGET the Redis column cache for those ids, fall through to the heavy DB
    build only for runs that missed the cache, assemble the final response
    from the combined fragments, and write newly built fragments back to the
    cache. ``cache=false`` bypasses Redis entirely — no reads, no writes.
    """
    asset = await repos.asset_repo.get_by_name(asset_name)
    if asset is None:
        raise NotFoundError('asset', asset_name)

    # Cheap query: which runs live in the window? This becomes the cache-key
    # inventory for the MGET below.
    candidate_runs = await repos.trend_repo.list_runs_for_heatmap(
        asset_id=asset.id,
        eval_name=evaluation_name,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    candidate_run_ids = [run.id for run in candidate_runs]

    # Read whatever is already cached (unless the caller opted out).
    active_cache = column_cache if cache else None
    fragments_by_id: dict[str, HeatmapColumnFragment] = {}
    if active_cache is not None:
        fragments_by_id = await active_cache.get_many(candidate_run_ids)

    # Anything missing from the cache gets rebuilt from the DB. When
    # cache=false this rebuilds everything — pure bypass.
    missing_ids = [run_id for run_id in candidate_run_ids if str(run_id) not in fragments_by_id]
    if missing_ids:
        missing_runs = await repos.trend_repo.get_grouped_metric_heatmap(asset_id=asset.id, run_id_filter=missing_ids)
        # has_notes is overlaid below from the fresh note-state query, so
        # any placeholder works here.
        rebuilt_fragments = [build_column_fragment(run, has_notes=False) for run in missing_runs]
        for fragment in rebuilt_fragments:
            fragments_by_id[str(fragment.evaluation_run_id)] = fragment
        if active_cache is not None:
            await active_cache.set_many(rebuilt_fragments)

    # Fresh note state for every column — annotations do not invalidate the
    # column cache, so they are overlaid onto each fragment at assembly time.
    noted_run_ids = await repos.trend_repo.get_run_ids_with_notes(candidate_run_ids)

    # Assemble in canonical column order (oldest → newest, with eval_name as
    # the tie-breaker) so the cached path matches the legacy wrapper exactly.
    ordered_runs = sorted(candidate_runs, key=lambda r: (r.period_start, r.eval_name or ''))
    ordered_fragments: list[HeatmapColumnFragment] = []
    for run in ordered_runs:
        fragment = fragments_by_id[str(run.id)]
        ordered_fragments.append(
            fragment.model_copy(
                update={'column': fragment.column.model_copy(update={'has_notes': run.id in noted_run_ids})}
            )
        )

    return assemble_grouped_response(asset_name, ordered_fragments)


@router.post('/evaluations/re-evaluate', response_model=ReEvaluateResponse)
async def re_evaluate_evaluations(
    body: ReEvaluateRequest,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> ReEvaluateResponse:
    """Re-evaluate completed evaluations from stored SLI values."""
    try:
        return await re_evaluate(body, repos)
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
    '/evaluations/trend-annotations',
    response_model=dict[str, list[AnnotationRead]],
)
async def get_trend_annotations(
    asset_name: str = Query(alias='asset'),
    slo_name: str = Query(alias='slo'),
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
        raise NotFoundError('evaluation', str(eval_id))
    if ev.status != 'completed':
        raise ConflictError('evaluation', str(eval_id), 'only completed evaluations can be pinned')
    if ev.invalidated:
        raise ConflictError('evaluation', str(eval_id), 'cannot pin an invalidated evaluation')
    updated = await repos.eval_repo.pin_baseline(eval_id, reason=body.reason, author=body.author)
    if updated is None:
        raise NotFoundError('evaluation', str(eval_id))
    return build_detail(updated)


@router.patch('/evaluations/{eval_id}/unpin-baseline', response_model=EvaluationDetail)
async def unpin_baseline(
    eval_id: uuid.UUID,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationDetail:
    """Remove baseline pin from an evaluation."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    updated = await repos.eval_repo.unpin_baseline(eval_id)
    if updated is None:
        raise NotFoundError('evaluation', str(eval_id))
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
        raise NotFoundError('evaluation', str(eval_id))
    if ev.status != 'completed':
        raise ConflictError('evaluation', str(eval_id), 'only completed evaluations can be overridden')
    if body.new_result not in ('pass', 'warning', 'fail'):
        raise DomainValidationError('new_result must be pass, warning, or fail')
    updated = await repos.eval_repo.override_status(
        eval_id, new_result=body.new_result, reason=body.reason, author=body.author
    )
    if updated is None:
        raise NotFoundError('evaluation', str(eval_id))
    return build_detail(updated)


@router.patch('/evaluations/{eval_id}/restore-override', response_model=EvaluationDetail)
async def restore_override(
    eval_id: uuid.UUID,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> EvaluationDetail:
    """Restore the original evaluation result."""
    ev = await repos.eval_repo.get_by_id(eval_id)
    if ev is None:
        raise NotFoundError('evaluation', str(eval_id))
    if ev.original_result is None:
        raise ConflictError('evaluation', str(eval_id), 'has no override to restore')
    updated = await repos.eval_repo.restore_override(eval_id)
    if updated is None:
        raise NotFoundError('evaluation', str(eval_id))
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
    """Add an SLO-level annotation to a single SLOEvaluation."""
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


@router.post(
    '/evaluations/run/{run_id}/annotations',
    response_model=AnnotationRead,
    status_code=201,
)
async def create_run_annotation(
    run_id: uuid.UUID,
    body: AnnotationCreate,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> AnnotationRead:
    """Add a run-level (column-level) annotation to an EvaluationRun."""
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
        raise DomainValidationError('provide either eval_id or (asset_name + slo_name), not both')
    if not has_eval and not has_any_asset_param:
        raise DomainValidationError('provide either eval_id or (asset_name + slo_name)')
    if has_any_asset_param and (asset_name is None or slo_name is None):
        raise DomainValidationError('both asset_name and slo_name are required when not using eval_id')

    if eval_id is not None:
        ev = await repos.eval_repo.get_by_id(eval_id)
        if ev is None:
            raise NotFoundError('evaluation', str(eval_id))
        if ev.asset_id is None:
            raise DomainValidationError('evaluation has no associated asset')
        if ev.slo_name is None:
            raise DomainValidationError('evaluation has no associated slo')
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
