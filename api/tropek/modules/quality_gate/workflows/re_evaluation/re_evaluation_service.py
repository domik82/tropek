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
from tropek.modules.quality_gate.repositories.baseline import BaselineRepository
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.repositories.indicator import IndicatorRepository, build_indicator_row_dicts
from tropek.modules.quality_gate.schemas.re_evaluation import (
    ReEvalResultItem,
    ReEvaluateRequest,
    ReEvaluateResponse,
)
from tropek.modules.quality_gate.shared.dependencies import QualityGateRepos
from tropek.modules.quality_gate.shared.exceptions import BaselinePinConflictError
from tropek.modules.quality_gate.workflows.execution.evaluation_helpers import build_slo_model, compute_baselines
from tropek.modules.quality_gate.workflows.presentation.heatmap_cache import HeatmapColumnCache
from tropek.modules.quality_gate.workflows.trigger.trigger_resolver import resolve_all_slos_for_asset
from tropek.modules.sli_registry.repository import SLIRepository

# Earliest possible timezone-aware datetime for "no lower bound" queries
_DATETIME_MIN = datetime.min.replace(tzinfo=UTC)


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
    note_group_id: uuid.UUID,
    note_group_name: str,
    heatmap_cache: HeatmapColumnCache | None = None,
) -> None:
    """Overwrite evaluation result from re-evaluation, preserving original on first call."""
    result = await session.execute(
        select(SLOEvaluation).options(selectinload(SLOEvaluation.annotations)).where(SLOEvaluation.id == ev.id)
    )
    fresh_ev = result.scalar_one_or_none()
    if fresh_ev is None:
        return

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
    }
    if slo_version is not None:
        values['slo_version'] = slo_version

    await session.execute(update(SLOEvaluation).where(SLOEvaluation.id == ev.id).values(**values))

    annotation_content = f'{slo_name}: {old_result} \u2192 {new_result}, score {old_score} \u2192 {new_score}'
    if cache:
        await cache.invalidate(f'baseline:{fresh_ev.asset_id}:{fresh_ev.slo_name}')
    if heatmap_cache is not None:
        await heatmap_cache.delete(fresh_ev.evaluation_id)
    ann_repo = AnnotationRepository(session, cache=cache)
    await ann_repo.add_annotation(
        ev.id,
        content=annotation_content,
        author='system',
        category='re-evaluation',
        note_group_id=note_group_id,
        note_group_name=note_group_name,
    )

    if new_engine_results and slo_objectives:
        indicator_repo = IndicatorRepository(session)
        await indicator_repo.delete_for_evaluation(ev.id)
        obj_lookup = {obj.sli: obj.id for obj in slo_objectives}
        rows = build_indicator_row_dicts(
            evaluation_id=ev.id,
            indicator_results=new_engine_results,
            obj_lookup=obj_lookup,
        )
        if rows:
            await indicator_repo.bulk_insert(ev.id, rows)


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

    When ``request.slo_name`` is provided, only that SLO is re-evaluated.
    When omitted, all SLOs assigned to the asset are re-evaluated (same
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
    if request.slo_name is not None:
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

    # Re-evaluate each SLO
    all_results: list[ReEvalResultItem] = []
    single_slo_version: int | None = None
    for slo_name in slo_names:
        slo_version, results = await _re_evaluate_single_slo(
            request, slo_name, asset.id, repos,
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
