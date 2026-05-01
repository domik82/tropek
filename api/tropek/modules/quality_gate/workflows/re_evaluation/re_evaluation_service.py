"""Re-evaluation service — re-scores historical evaluations against a new SLO version."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tropek.cache.redis_cache import RedisCache
from tropek.db.models import IndicatorResultRow, SLODefinition, SLOEvaluation
from tropek.modules.quality_gate.evaluation_engine.evaluator import evaluate
from tropek.modules.quality_gate.evaluation_engine.slo_models import SLO
from tropek.modules.quality_gate.repositories.annotation import AnnotationRepository
from tropek.modules.quality_gate.repositories.annotation_category import (
    AnnotationCategoryRepository,
)
from tropek.modules.quality_gate.repositories.baseline import BaselineRepository
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.repositories.indicator import IndicatorRepository, build_indicator_row_dicts
from tropek.modules.quality_gate.schemas.re_evaluation import (
    AssetScope,
    EvalNamesSelector,
    ReEvalResultItem,
    ReEvaluateFromBaselineRequest,
    ReEvaluateFromDateRequest,
    ReEvaluateFromEvaluationRequest,
    ReEvaluateRequest,
    ReEvaluateResponse,
    Scope,
    Selector,
    SloSelector,
)
from tropek.modules.quality_gate.shared.dependencies import QualityGateRepos
from tropek.modules.quality_gate.shared.exceptions import BaselinePinConflictError
from tropek.modules.quality_gate.workflows.execution.evaluation_helpers import build_slo_model, compute_baselines
from tropek.modules.quality_gate.workflows.presentation.heatmap_cache import HeatmapColumnCache
from tropek.modules.quality_gate.workflows.trigger.trigger_resolver import resolve_all_slos_for_asset
from tropek.modules.sli_registry.repository import SLIRepository

# Earliest possible timezone-aware datetime for "no lower bound" queries
_DATETIME_MIN = datetime.min.replace(tzinfo=UTC)

# Seeded annotation category used for automatic re-evaluation notes.
RE_EVALUATION_CATEGORY_NAME = 're-evaluation'


def _metrics_from_indicator_rows(
    indicator_rows: list[IndicatorResultRow],
) -> dict[str, float | None]:
    """Extract metric name -> value mapping from normalized indicator rows."""
    return {row.objective.sli: row.value for row in indicator_rows}


async def _resolve_from_date(
    request: ReEvaluateRequest,
    asset_id: uuid.UUID,
    slo_name: str,
    eval_repo: EvaluationRepository,
    baseline_repo: BaselineRepository,
) -> datetime:
    """Determine the starting timestamp for the re-evaluation window."""
    if request.from_date is not None:
        return request.from_date

    if request.from_evaluation_id is not None:
        anchor_eval = await eval_repo.get_by_id(request.from_evaluation_id)
        if anchor_eval is None:
            raise ValueError(f"evaluation '{request.from_evaluation_id}' not found")
        return anchor_eval.period_start

    # from_baseline: find the most recent evaluation with an active baseline pin
    recent_evals = await baseline_repo.load_evaluations_for_reeval(
        asset_id=asset_id,
        slo_name=slo_name,
        from_date=_DATETIME_MIN,
    )
    for ev in reversed(recent_evals):
        if ev.baseline_pinned_at is not None and ev.baseline_unpinned_at is None:
            return ev.period_start

    raise ValueError(f"no evaluation with pinned baseline found for slo '{slo_name}'")


async def _resolve_pin_conflict(
    request: ReEvaluateRequest,
    from_date: datetime,
    asset_id: uuid.UUID,
    slo_name: str,
    baseline_repo: BaselineRepository,
) -> tuple[datetime, bool]:
    """Check for baseline pin conflict and apply the chosen strategy.

    Returns:
        Tuple of (possibly adjusted from_date, skip_pin flag).

    Raises:
        BaselinePinConflictError: When conflict exists and no strategy was provided.
    """
    if request.from_baseline:
        return from_date, False

    pin_info = await baseline_repo.get_active_pin(asset_id=asset_id, slo_name=slo_name)
    if pin_info is None:
        return from_date, False

    pin_date, pin_eval_id = pin_info
    if from_date >= pin_date:
        return from_date, False

    if request.pin_strategy is None:
        raise BaselinePinConflictError(pin_date, pin_eval_id)
    if request.pin_strategy == 'skip_to_pin':
        return pin_date, False
    # ignore_pin
    return from_date, True


async def _resolve_sli_version_range(
    sli_name: str | None,
    sli_version: int | None,
    sli_repo: SLIRepository,
) -> tuple[int, int] | None:
    """Look up comparable_from_version for an SLI, returning a version range or None."""
    if not sli_name or not sli_version:
        return None
    sli_def = await sli_repo.get_version(sli_name, sli_version)
    if sli_def is None:
        return None
    return (sli_def.comparable_from_version, sli_def.version)


async def _load_fresh_evaluation(session: AsyncSession, evaluation_id: uuid.UUID) -> SLOEvaluation | None:
    """Reload an evaluation with its annotations eagerly loaded."""
    result = await session.execute(
        select(SLOEvaluation).options(selectinload(SLOEvaluation.annotations)).where(SLOEvaluation.id == evaluation_id)
    )
    return result.scalar_one_or_none()


async def _update_evaluation_row(
    session: AsyncSession,
    *,
    fresh_ev: SLOEvaluation,
    new_result: str,
    new_score: float,
    old_result: str,
    old_score: float,
    slo_version: int,
) -> None:
    """Update the SLOEvaluation row with new result/score and re-eval job stats."""
    stats = dict(fresh_ev.job_stats)
    if 'original_result' not in stats:
        stats['original_result'] = old_result
        stats['original_score'] = old_score
    stats['re_evaluated_at'] = datetime.now(tz=UTC).isoformat()
    stats['re_eval_slo_version'] = slo_version

    values: dict[str, Any] = {
        'result': new_result,
        'score': new_score,
        'job_stats': stats,
        'slo_version': slo_version,
    }
    await session.execute(update(SLOEvaluation).where(SLOEvaluation.id == fresh_ev.id).values(**values))


async def _invalidate_caches(
    fresh_ev: SLOEvaluation,
    cache: RedisCache | None,
    heatmap_cache: HeatmapColumnCache | None,
) -> None:
    """Drop stale baseline and heatmap caches tied to the re-scored evaluation."""
    if cache:
        await cache.invalidate(f'baseline:{fresh_ev.asset_id}:{fresh_ev.slo_name}')
    if heatmap_cache is not None:
        await heatmap_cache.delete(fresh_ev.evaluation_id)


async def _add_reeval_annotation(  # noqa: PLR0913
    session: AsyncSession,
    *,
    evaluation_id: uuid.UUID,
    slo_name: str,
    new_result: str,
    new_score: float,
    old_result: str,
    old_score: float,
    re_eval_category_id: uuid.UUID,
    note_group_id: uuid.UUID,
    note_group_name: str,
    cache: RedisCache | None,
) -> None:
    """Record an automatic 're-evaluation' annotation describing the result change."""
    content = f'{slo_name}: {old_result} \u2192 {new_result}, score {old_score} \u2192 {new_score}'
    ann_repo = AnnotationRepository(session, cache=cache)
    await ann_repo.add_annotation(
        evaluation_id,
        content=content,
        author='system',
        category_id=re_eval_category_id,
        note_group_id=note_group_id,
        note_group_name=note_group_name,
    )


async def _replace_indicator_rows(
    session: AsyncSession,
    *,
    evaluation_id: uuid.UUID,
    new_engine_results: list[Any],
    slo_objectives: list[Any],
) -> None:
    """Replace stored indicator rows with freshly computed ones."""
    indicator_repo = IndicatorRepository(session)
    await indicator_repo.delete_for_evaluation(evaluation_id)
    obj_lookup = {obj.sli: obj.id for obj in slo_objectives}
    rows = build_indicator_row_dicts(
        evaluation_id=evaluation_id,
        indicator_results=new_engine_results,
        obj_lookup=obj_lookup,
    )
    if rows:
        await indicator_repo.bulk_insert(evaluation_id, rows)


async def _persist_reeval_result(  # noqa: PLR0913
    session: AsyncSession,
    *,
    ev: SLOEvaluation,
    slo_name: str,
    new_result: str,
    new_score: float,
    old_result: str,
    old_score: float,
    slo_version: int,
    new_engine_results: list[Any] | None,
    slo_objectives: list[Any] | None,
    cache: RedisCache | None,
    re_eval_category_id: uuid.UUID,
    note_group_id: uuid.UUID,
    note_group_name: str,
    heatmap_cache: HeatmapColumnCache | None = None,
) -> None:
    """Overwrite evaluation result from re-evaluation, preserving original on first call."""
    fresh_ev = await _load_fresh_evaluation(session, ev.id)
    if fresh_ev is None:
        return

    await _update_evaluation_row(
        session,
        fresh_ev=fresh_ev,
        new_result=new_result,
        new_score=new_score,
        old_result=old_result,
        old_score=old_score,
        slo_version=slo_version,
    )
    await _invalidate_caches(fresh_ev, cache, heatmap_cache)
    await _add_reeval_annotation(
        session,
        evaluation_id=ev.id,
        slo_name=slo_name,
        new_result=new_result,
        new_score=new_score,
        old_result=old_result,
        old_score=old_score,
        re_eval_category_id=re_eval_category_id,
        note_group_id=note_group_id,
        note_group_name=note_group_name,
        cache=cache,
    )
    if new_engine_results and slo_objectives:
        await _replace_indicator_rows(
            session,
            evaluation_id=ev.id,
            new_engine_results=new_engine_results,
            slo_objectives=slo_objectives,
        )


async def _rescore_single(  # noqa: PLR0913
    ev: SLOEvaluation,
    *,
    slo_model: SLO,
    slo_def: SLODefinition,
    slo_version: int,
    eligible_ids: list[uuid.UUID],
    asset_id: uuid.UUID,
    slo_name: str,
    default_sli_version_range: tuple[int, int] | None,
    baseline_repo: BaselineRepository,
    sli_repo: SLIRepository,
    session: AsyncSession,
    cache: RedisCache | None,
    dry_run: bool,
    re_eval_category_id: uuid.UUID,
    skip_pin_filter: bool = False,
    note_group_id: uuid.UUID | None = None,
    note_group_name: str | None = None,
    heatmap_cache: HeatmapColumnCache | None = None,
) -> ReEvalResultItem:
    """Re-score a single evaluation and optionally persist the update."""
    metrics = _metrics_from_indicator_rows(ev.indicator_rows)

    eval_sli_range = await _resolve_sli_version_range(ev.sli_name, ev.sli_version, sli_repo)
    sli_range = eval_sli_range or default_sli_version_range

    baseline_evals = await baseline_repo.get_reeval_baselines(
        asset_id=asset_id,
        slo_name=slo_name,
        period_start_before=ev.period_start,
        include_result_with_score=slo_model.comparison.include_result_with_score.value,
        limit=slo_model.comparison.number_of_comparison_results,
        sli_version_range=sli_range,
        restrict_to_ids=eligible_ids if eligible_ids else None,
        skip_pin_filter=skip_pin_filter,
    )

    baselines, compared_ids = compute_baselines(baseline_evals, slo_model.comparison.aggregate_function)
    eval_result = evaluate(slo_model, metrics, baselines, compared_ids)

    old_result = ev.result or 'error'
    old_score = ev.score if ev.score is not None else 0.0

    if not dry_run and note_group_id and note_group_name:
        await _persist_reeval_result(
            session,
            ev=ev,
            slo_name=slo_name,
            new_result=eval_result.result,
            new_score=eval_result.score,
            old_result=old_result,
            old_score=old_score,
            slo_version=slo_version,
            new_engine_results=eval_result.indicator_results,
            slo_objectives=slo_def.objectives,
            cache=cache,
            re_eval_category_id=re_eval_category_id,
            note_group_id=note_group_id,
            note_group_name=note_group_name,
            heatmap_cache=heatmap_cache,
        )

    return ReEvalResultItem(
        id=ev.id,
        evaluation_name=ev.evaluation_name,
        slo_name=slo_name,
        slo_version=slo_version,
        period_start=ev.period_start,
        period_end=ev.period_end,
        old_result=old_result,
        new_result=eval_result.result,
        old_score=old_score,
        new_score=eval_result.score,
    )


async def _re_evaluate_single_slo(
    request: ReEvaluateRequest,
    slo_name: str,
    asset_id: uuid.UUID,
    repos: QualityGateRepos,
    *,
    re_eval_category_id: uuid.UUID,
    note_group_id: uuid.UUID,
    note_group_name: str,
) -> tuple[int, list[ReEvalResultItem]]:
    """Re-evaluate all evaluations for a single SLO. Returns (slo_version, results)."""
    session = repos.session
    slo_repo = repos.slo_repo
    sli_repo = repos.sli_def_repo
    eval_repo = repos.eval_repo
    baseline_repo = repos.baseline_repo
    cache = repos.cache
    heatmap_cache = repos.heatmap_cache

    # Load SLO definition (specified version or latest)
    if request.slo_version is not None:
        slo_def = await slo_repo.get_version(slo_name, request.slo_version)
    else:
        slo_def = await slo_repo.get_latest(slo_name)
    if slo_def is None:
        raise ValueError(f"slo '{slo_name}' not found")

    slo_model = build_slo_model(slo_def)

    # Determine window start
    from_date = await _resolve_from_date(request, asset_id, slo_name, eval_repo, baseline_repo)

    # Detect baseline pin conflict
    from_date, skip_pin = await _resolve_pin_conflict(request, from_date, asset_id, slo_name, baseline_repo)

    # Load evaluations to re-process (chronological order)
    evals_to_process = await baseline_repo.load_evaluations_for_reeval(
        asset_id=asset_id,
        slo_name=slo_name,
        from_date=from_date,
    )
    if not evals_to_process:
        return slo_def.version, []

    # Determine default SLI version range from the first eval
    first = evals_to_process[0]
    default_sli_range = await _resolve_sli_version_range(first.sli_name, first.sli_version, sli_repo)

    # Seed eligible IDs from pre-window baselines
    pre_baselines = await baseline_repo.get_reeval_baselines(
        asset_id=asset_id,
        slo_name=slo_name,
        period_start_before=from_date,
        include_result_with_score=slo_model.comparison.include_result_with_score.value,
        limit=slo_model.comparison.number_of_comparison_results,
        sli_version_range=default_sli_range,
        skip_pin_filter=skip_pin,
    )
    eligible_ids: list[uuid.UUID] = [ev.id for ev in pre_baselines]

    # Re-evaluate each in chronological order with cascading baselines
    results: list[ReEvalResultItem] = []
    for ev in evals_to_process:
        item = await _rescore_single(
            ev,
            slo_model=slo_model,
            slo_def=slo_def,
            slo_version=slo_def.version,
            eligible_ids=eligible_ids,
            asset_id=asset_id,
            slo_name=slo_name,
            default_sli_version_range=default_sli_range,
            baseline_repo=baseline_repo,
            sli_repo=sli_repo,
            session=session,
            cache=cache,
            dry_run=request.dry_run,
            re_eval_category_id=re_eval_category_id,
            skip_pin_filter=skip_pin,
            note_group_id=note_group_id,
            note_group_name=note_group_name,
            heatmap_cache=heatmap_cache,
        )
        eligible_ids.append(ev.id)
        results.append(item)

    return slo_def.version, results


async def re_evaluate(
    request: ReEvaluateRequest,
    repos: QualityGateRepos,
) -> ReEvaluateResponse:
    """Re-evaluate historical evaluations against a (possibly new) SLO version.

    When ``request.slo_names`` is provided, only the listed SLOs are re-evaluated.
    When ``request.slo_name`` is provided, only that single SLO is re-evaluated.
    When both are omitted, all SLOs assigned to the asset are re-evaluated (same
    resolution logic as POST /evaluate).

    Args:
        request: Validated re-evaluation request parameters.
        repos: Repository bundle with cache-aware instances.

    Returns:
        ReEvaluateResponse with per-evaluation before/after results.

    Raises:
        ValueError: If asset, SLO, or baseline anchor cannot be found.
    """
    asset_repo = repos.asset_repo

    # Resolve asset
    asset = await asset_repo.get_by_name(request.asset_name)
    if asset is None:
        raise ValueError(f"asset '{request.asset_name}' not found")

    # Determine which SLOs to re-evaluate
    if request.slo_names is not None:
        slo_names = list(request.slo_names)
    elif request.slo_name is not None:
        slo_names = [request.slo_name]
    else:
        group_ids = await repos.asset_group_repo.list_group_ids_for_asset(asset.id)
        slo_names = await resolve_all_slos_for_asset(
            asset_id=asset.id,
            assignment_repo=repos.assignment_repo,
            group_ids=group_ids,
        )
        if not slo_names:
            raise ValueError(f"no slo assignments found for asset '{request.asset_name}'")

    # Build a single note group for the entire re-eval action
    note_group_id = uuid.uuid4()
    slo_label = slo_names[0] if len(slo_names) == 1 else f'{len(slo_names)} SLOs'
    note_group_name = f're-evaluation \u2014 {slo_label}'

    # Resolve the re-evaluation annotation category once for the whole action
    category_repo = AnnotationCategoryRepository(repos.session)
    re_eval_category = await category_repo.get_by_name(RE_EVALUATION_CATEGORY_NAME)
    if re_eval_category is None:
        raise RuntimeError(f"seeded '{RE_EVALUATION_CATEGORY_NAME}' category missing")

    # Re-evaluate each SLO
    all_results: list[ReEvalResultItem] = []
    single_slo_version: int | None = None
    for slo_name in slo_names:
        slo_version, results = await _re_evaluate_single_slo(
            request,
            slo_name,
            asset.id,
            repos,
            re_eval_category_id=re_eval_category.id,
            note_group_id=note_group_id,
            note_group_name=note_group_name,
        )
        all_results.extend(results)
        if len(slo_names) == 1:
            single_slo_version = slo_version

    return ReEvaluateResponse(
        affected_evaluations=len(all_results),
        slo_version_used=single_slo_version,
        results=all_results,
    )


def _scope_to_asset_name(scope: Scope) -> str:
    """Extract asset_name from a Scope discriminated union.

    Only AssetScope is supported; GroupScope requires a different code path that
    iterates over group members — not yet implemented in the split endpoints.
    """
    if isinstance(scope, AssetScope):
        return scope.asset_name
    raise ValueError('group scope is not yet supported on split re-evaluate endpoints')


def _selector_to_slo_fields(
    selector: Selector | None,
) -> tuple[str | None, list[str] | None]:
    """Return (slo_name, slo_names) from the new selector union.

    Returns a pair that maps directly onto the legacy ReEvaluateRequest fields.
    """
    if selector is None:
        return None, None
    if isinstance(selector, SloSelector):
        return selector.slo_name, None
    # EvalNamesSelector — the legacy request uses slo_names; interpretation
    # of evaluation_names as SLO names preserves backward-compatible behaviour.
    assert isinstance(selector, EvalNamesSelector)
    return None, list(selector.evaluation_names)


async def re_evaluate_from_date(
    body: ReEvaluateFromDateRequest,
    repos: QualityGateRepos,
) -> ReEvaluateResponse:
    """Bridge for POST /evaluations/re-evaluate/from-date."""
    asset_name = _scope_to_asset_name(body.scope)
    slo_name, slo_names = _selector_to_slo_fields(body.selector)
    legacy_request = ReEvaluateRequest(
        asset_name=asset_name,
        slo_name=slo_name,
        slo_names=slo_names,
        from_date=body.from_date,
        from_baseline=False,
        from_evaluation_id=None,
        slo_version=body.slo_version,
        dry_run=body.dry_run,
        pin_strategy=body.pin_strategy,
    )
    return await re_evaluate(legacy_request, repos)


async def re_evaluate_from_baseline(
    body: ReEvaluateFromBaselineRequest,
    repos: QualityGateRepos,
) -> ReEvaluateResponse:
    """Bridge for POST /evaluations/re-evaluate/from-baseline."""
    asset_name = _scope_to_asset_name(body.scope)
    slo_name, slo_names = _selector_to_slo_fields(body.selector)
    legacy_request = ReEvaluateRequest(
        asset_name=asset_name,
        slo_name=slo_name,
        slo_names=slo_names,
        from_date=None,
        from_baseline=True,
        from_evaluation_id=None,
        slo_version=body.slo_version,
        dry_run=body.dry_run,
        pin_strategy=body.pin_strategy,
    )
    return await re_evaluate(legacy_request, repos)


async def re_evaluate_from_evaluation(
    body: ReEvaluateFromEvaluationRequest,
    evaluation_id: uuid.UUID,
    repos: QualityGateRepos,
) -> ReEvaluateResponse:
    """Bridge for POST /evaluations/re-evaluate/from-evaluation/{evaluation_id}."""
    asset_name = _scope_to_asset_name(body.scope)
    slo_name, slo_names = _selector_to_slo_fields(body.selector)
    legacy_request = ReEvaluateRequest(
        asset_name=asset_name,
        slo_name=slo_name,
        slo_names=slo_names,
        from_date=None,
        from_baseline=False,
        from_evaluation_id=evaluation_id,
        slo_version=body.slo_version,
        dry_run=body.dry_run,
        pin_strategy=body.pin_strategy,
    )
    return await re_evaluate(legacy_request, repos)
