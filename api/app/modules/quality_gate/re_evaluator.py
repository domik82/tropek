"""Re-evaluation service — re-scores historical evaluations against a new SLO version."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Evaluation, IndicatorResultRow, SLODefinition
from app.modules.assets.repository import AssetRepository
from app.modules.quality_gate.baseline_repository import BaselineRepository
from app.modules.quality_gate.params import ReEvalUpdateParams
from app.modules.quality_gate.engine.criteria import aggregate_values
from app.modules.quality_gate.engine.evaluator import evaluate
from app.modules.quality_gate.engine.slo_models import SLO
from app.modules.quality_gate.engine.slo_parser import build_slo
from app.modules.quality_gate.re_evaluation_schemas import (
    ReEvalResultItem,
    ReEvaluateRequest,
    ReEvaluateResponse,
)
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_registry.repository import SLORepository

# Earliest possible timezone-aware datetime for "no lower bound" queries
_DATETIME_MIN = datetime.min.replace(tzinfo=UTC)


def _metrics_from_indicator_rows(
    indicator_rows: list[IndicatorResultRow],
) -> dict[str, float | None]:
    """Extract metric name -> value mapping from normalized indicator rows."""
    return {row.objective.sli: row.value for row in indicator_rows}


def _build_slo_model(slo_def: SLODefinition) -> SLO:
    """Build the engine SLO model from a database SLO definition."""
    objectives_dicts = [
        {
            "sli": obj.sli,
            "display_name": obj.display_name,
            "weight": obj.weight,
            "key_sli": obj.key_sli,
            "pass_criteria": list(obj.pass_criteria),
            "warning_criteria": list(obj.warning_criteria),
        }
        for obj in slo_def.objectives
    ]
    return build_slo(
        objectives=objectives_dicts,
        total_score_pass_pct=slo_def.total_score_pass_pct,
        total_score_warning_pct=slo_def.total_score_warning_pct,
        comparison=slo_def.comparison,
    )


def _compute_baselines(
    baseline_evals: list[Evaluation],
    slo_model: SLO,
) -> tuple[dict[str, float | None], list[str]]:
    """Aggregate baseline values from a set of baseline evaluations.

    Returns:
        Tuple of (metric -> aggregated baseline value, list of compared eval IDs).
    """
    if not baseline_evals:
        return {}, []

    compared_ids = [str(ev.id) for ev in baseline_evals]

    # Collect per-metric values from all baseline evaluations
    metric_values: dict[str, list[float]] = {}
    for ev in baseline_evals:
        for row in ev.indicator_rows or []:
            metric = row.objective.sli
            if metric is not None and row.value is not None:
                metric_values.setdefault(metric, []).append(float(row.value))

    # Aggregate each metric using the SLO's aggregate function
    baselines: dict[str, float | None] = {}
    for metric, values in metric_values.items():
        baselines[metric] = aggregate_values(values, slo_model.comparison.aggregate_function)

    return baselines, compared_ids


async def _resolve_from_date(
    request: ReEvaluateRequest,
    asset_id: uuid.UUID,
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
        slo_name=request.slo_name,
        from_date=_DATETIME_MIN,
    )
    for ev in reversed(recent_evals):
        if ev.baseline_pinned_at is not None and ev.baseline_unpinned_at is None:
            return ev.period_start

    raise ValueError("no evaluation with pinned baseline found")


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


async def _rescore_single(  # noqa: PLR0913
    ev: Evaluation,
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
    dry_run: bool,
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
    )

    baselines, compared_ids = _compute_baselines(baseline_evals, slo_model)
    eval_result = evaluate(slo_model, metrics, baselines, compared_ids)

    old_result = ev.result or "error"
    old_score = ev.score if ev.score is not None else 0.0

    if not dry_run:
        await baseline_repo.update_reeval_result(
            ReEvalUpdateParams(
                eval_id=ev.id,
                new_result=eval_result.result,
                new_score=eval_result.score,
                new_engine_results=eval_result.indicator_results,
                slo_objectives=slo_def.objectives,
                old_result=old_result,
                old_score=old_score,
                slo_version=slo_version,
            )
        )

    return ReEvalResultItem(
        id=ev.id,
        evaluation_name=ev.evaluation_name,
        period_start=ev.period_start,
        period_end=ev.period_end,
        old_result=old_result,
        new_result=eval_result.result,
        old_score=old_score,
        new_score=eval_result.score,
    )


async def re_evaluate(
    request: ReEvaluateRequest,
    session: AsyncSession,
) -> ReEvaluateResponse:
    """Re-evaluate historical evaluations against a (possibly new) SLO version.

    Args:
        request: Validated re-evaluation request parameters.
        session: Active async database session.

    Returns:
        ReEvaluateResponse with per-evaluation before/after results.

    Raises:
        ValueError: If asset, SLO, or baseline anchor cannot be found.
    """
    asset_repo = AssetRepository(session)
    slo_repo = SLORepository(session)
    sli_repo = SLIRepository(session)
    eval_repo = EvaluationRepository(session)
    baseline_repo = BaselineRepository(session)

    # Resolve asset
    asset = await asset_repo.get_by_name(request.asset_name)
    if asset is None:
        raise ValueError(f"asset '{request.asset_name}' not found")

    # Load SLO definition (specified version or latest)
    if request.slo_version is not None:
        slo_def = await slo_repo.get_version(request.slo_name, request.slo_version)
    else:
        slo_def = await slo_repo.get_latest(request.slo_name)
    if slo_def is None:
        raise ValueError(f"slo '{request.slo_name}' not found")

    slo_model = _build_slo_model(slo_def)

    # Determine window start
    from_date = await _resolve_from_date(request, asset.id, eval_repo, baseline_repo)

    # Load evaluations to re-process (chronological order)
    evals_to_process = await baseline_repo.load_evaluations_for_reeval(
        asset_id=asset.id,
        slo_name=request.slo_name,
        from_date=from_date,
    )
    if not evals_to_process:
        return ReEvaluateResponse(
            affected_evaluations=0, slo_version_used=slo_def.version, results=[]
        )

    # Determine default SLI version range from the first eval
    first = evals_to_process[0]
    default_sli_range = await _resolve_sli_version_range(
        first.sli_name, first.sli_version, sli_repo
    )

    # Seed eligible IDs from pre-window baselines
    pre_baselines = await baseline_repo.get_reeval_baselines(
        asset_id=asset.id,
        slo_name=request.slo_name,
        period_start_before=from_date,
        include_result_with_score=slo_model.comparison.include_result_with_score.value,
        limit=slo_model.comparison.number_of_comparison_results,
        sli_version_range=default_sli_range,
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
            asset_id=asset.id,
            slo_name=request.slo_name,
            default_sli_version_range=default_sli_range,
            baseline_repo=baseline_repo,
            sli_repo=sli_repo,
            dry_run=request.dry_run,
        )
        eligible_ids.append(ev.id)
        results.append(item)

    return ReEvaluateResponse(
        affected_evaluations=len(results),
        slo_version_used=slo_def.version,
        results=results,
    )
