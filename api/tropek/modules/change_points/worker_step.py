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
from tropek.modules.change_points.repository import (
    ChangePointInsertParams,
    ChangePointRepository,
    ResolvedConfig,
)
from tropek.modules.configuration.repository import ConfigurationRepository
from tropek.modules.quality_gate.repositories.baseline import BaselineRepository

logger = structlog.get_logger()

REGIME_STD_MULTIPLIER = 2.0


def _same_regime(
    previous_mean: float,
    previous_std: float,
    current_mean: float,
) -> bool:
    """Return True if the new post-segment mean falls within the previous regime's noise band.

    Uses the standard deviation of the previous change point's post-segment
    to define the noise band. If the new mean is within k standard deviations
    of the previous mean, the metric hasn't meaningfully shifted — it's still
    the same regime.
    """
    if previous_std <= 0:
        return previous_mean == current_mean
    return abs(current_mean - previous_mean) < REGIME_STD_MULTIPLIER * previous_std


async def run_change_point_detection(
    *,
    session: AsyncSession,
    snapshot: Any,
    slo_def: SLODefinition,
    indicator_rows: list[IndicatorResultRow],
    cache: Any | None = None,
) -> None:
    """Run Otava change point detection for each enabled metric."""
    log = logger.bind(
        evaluation_id=str(snapshot.eval_id),
        slo_name=snapshot.slo_name,
    )

    indicator_lookup = {
        row.objective.sli: row
        for row in indicator_rows
        if row.objective
    }

    config_repo = ConfigurationRepository(session)
    system_defaults = await config_repo.get_change_point_defaults()

    change_point_repo = ChangePointRepository(session)
    baseline_repo = BaselineRepository(session, cache=cache)

    for objective in slo_def.objectives:
        indicator_row = indicator_lookup.get(objective.sli)
        if not indicator_row:
            continue

        resolved = ChangePointRepository.resolve_from_objective(objective, system_defaults)
        if not resolved.enabled:
            continue

        try:
            await _detect_for_metric(
                log=log,
                baseline_repo=baseline_repo,
                change_point_repo=change_point_repo,
                snapshot=snapshot,
                metric_name=objective.sli,
                indicator_result_id=indicator_row.id,
                higher_is_better=resolved.higher_is_better,
                config=resolved,
            )
        except (OSError, ValueError, TypeError, RuntimeError, LookupError):
            log.warning(
                "change point detection failed for metric",
                metric=objective.sli,
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
    higher_is_better: bool,
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
                break

    if len(values) < config.min_sample_size:
        log.debug(
            "insufficient history for change point detection",
            metric=metric_name,
            sample_count=len(values),
            min_required=config.min_sample_size,
        )
        return

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

    previous_cp = await change_point_repo.get_latest_change_point(
        asset_id=snapshot.asset_id,
        slo_name=snapshot.slo_name,
        metric_name=metric_name,
    )
    if previous_cp and _same_regime(
        previous_cp.post_segment_mean,
        previous_cp.post_segment_std,
        latest_cp.post_segment_mean,
    ):
        log.debug(
            "change point suppressed — same regime as previous",
            metric=metric_name,
            previous_mean=previous_cp.post_segment_mean,
            previous_std=previous_cp.post_segment_std,
            current_mean=latest_cp.post_segment_mean,
        )
        return

    await change_point_repo.insert_change_point(
        ChangePointInsertParams(
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
            post_segment_std=latest_cp.post_segment_std,
        )
    )

    log.info(
        "change point detected",
        metric=metric_name,
        direction=latest_cp.direction,
        magnitude_pct=latest_cp.change_relative_pct,
    )
