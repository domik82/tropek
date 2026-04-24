"""Fault-isolated change point detection step for the evaluation worker.

Runs after SLO scoring and SLI value writes. If this step fails,
the evaluation result is already saved — detection failure is non-fatal.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import IndicatorResultRow, SLODefinition
from tropek.modules.change_points.detector import detect_change_points
from tropek.modules.change_points.directionality import is_higher_better
from tropek.modules.change_points.repository import ChangePointRepository, ResolvedConfig
from tropek.modules.quality_gate.repositories.baseline import BaselineRepository

logger = structlog.get_logger()


async def run_change_point_detection(
    *,
    session: AsyncSession,
    snapshot: Any,
    slo_def: SLODefinition,
    indicator_rows: list[IndicatorResultRow],
    cache: Any | None = None,
) -> None:
    """Run Otava change point detection for each enabled metric.

    Uses BaselineRepository for history scoping (pin-aware, version-aware).
    Dedup-checks against existing change_points before inserting.
    """
    log = logger.bind(
        evaluation_id=str(snapshot.eval_id),
        slo_name=snapshot.slo_name,
    )

    objective_lookup = {obj.sli: obj for obj in slo_def.objectives}
    indicator_lookup = {
        row.objective.sli: row
        for row in indicator_rows
        if row.objective
    }

    metric_names = list(objective_lookup.keys())
    change_point_repo = ChangePointRepository(session)
    resolved_configs = await change_point_repo.resolve_configs_for_metrics(
        slo_name=snapshot.slo_name,
        metric_names=metric_names,
    )

    baseline_repo = BaselineRepository(session, cache=cache)

    for metric_name, config in resolved_configs.items():
        if not config.enabled:
            continue

        objective = objective_lookup.get(metric_name)
        if not objective:
            continue

        indicator_row = indicator_lookup.get(metric_name)
        if not indicator_row:
            continue

        try:
            await _detect_for_metric(
                log=log,
                baseline_repo=baseline_repo,
                change_point_repo=change_point_repo,
                snapshot=snapshot,
                metric_name=metric_name,
                indicator_result_id=indicator_row.id,
                pass_threshold=list(objective.pass_threshold),
                config=config,
            )
        except Exception:
            log.warning(
                "change point detection failed for metric",
                metric=metric_name,
                exc_info=True,
            )


async def _detect_for_metric(
    *,
    log: Any,
    baseline_repo: BaselineRepository,
    change_point_repo: ChangePointRepository,
    snapshot: Any,
    metric_name: str,
    indicator_result_id: uuid.UUID,
    pass_threshold: list[str],
    config: ResolvedConfig,
) -> None:
    """Run detection for a single metric using baseline-scoped history."""
    history_evals = await baseline_repo.get_evaluation_baselines(
        asset_id=snapshot.asset_id,
        slo_name=snapshot.slo_name,
        period_start_before=snapshot.period_end,
        include_result_with_score="all",
        limit=config.window_size,
    )

    values: list[float] = []
    timestamps: list[datetime] = []

    for evaluation in sorted(history_evals, key=lambda ev: ev.period_start):
        for row in evaluation.indicator_rows or []:
            if row.objective and row.objective.sli == metric_name and row.value is not None:
                values.append(float(row.value))
                timestamps.append(evaluation.period_start)

    if len(values) < config.min_sample_size:
        log.debug(
            "insufficient history for change point detection",
            metric=metric_name,
            sample_count=len(values),
            min_required=config.min_sample_size,
        )
        return

    higher_is_better = is_higher_better(pass_threshold)

    detected = detect_change_points(
        values=values,
        timestamps=timestamps,
        higher_is_better=higher_is_better,
        window_size=config.window_size,
        max_pvalue=config.max_pvalue,
        min_magnitude=config.min_magnitude,
        min_sample_size=config.min_sample_size,
    )

    if not detected:
        return

    latest_cp = detected[-1]

    if latest_cp.position < len(values) - 3:
        return

    detection_index = latest_cp.position
    nearby_indices = range(
        max(0, detection_index - 2),
        min(len(timestamps), detection_index + 3),
    )
    nearby_timestamps = [timestamps[i] for i in nearby_indices]

    has_existing = await change_point_repo.has_nearby_change_point(
        asset_id=snapshot.asset_id,
        slo_name=snapshot.slo_name,
        metric_name=metric_name,
        period_start=latest_cp.timestamp,
        nearby_timestamps=nearby_timestamps,
    )

    if has_existing:
        log.debug("change point deduped", metric=metric_name, position=latest_cp.position)
        return

    await change_point_repo.insert_change_point(
        indicator_result_id=indicator_result_id,
        asset_id=snapshot.asset_id,
        slo_name=snapshot.slo_name,
        metric_name=metric_name,
        period_start=latest_cp.timestamp,
        detector=latest_cp.detector,
        direction=latest_cp.direction,
        change_relative_pct=latest_cp.change_relative_pct,
        change_absolute=latest_cp.change_absolute,
        t_statistic=latest_cp.pvalue,
        pre_segment_mean=latest_cp.pre_segment_mean,
        post_segment_mean=latest_cp.post_segment_mean,
    )

    log.info(
        "change point detected",
        metric=metric_name,
        direction=latest_cp.direction,
        magnitude_pct=latest_cp.change_relative_pct,
    )
