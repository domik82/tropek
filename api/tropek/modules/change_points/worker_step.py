"""Fault-isolated change point detection step for the evaluation worker.

Runs after SLO scoring and SLI value writes. If this step fails,
the evaluation result is already saved — detection failure is non-fatal.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import IndicatorResultRow, SLODefinition
from tropek.modules.change_points.detector import ChangePointResult, detect_change_points
from tropek.modules.change_points.repository import (
    ChangePointInsertParams,
    ChangePointRepository,
)
from tropek.modules.configuration.repository import ConfigurationRepository
from tropek.modules.quality_gate.repositories.baseline import BaselineRepository
from tropek.modules.quality_gate.workflows.execution.evaluation_executor import EvaluationSnapshot
from tropek.modules.quality_gate.workflows.execution.evaluation_helpers import resolve_comparison_name

logger = structlog.get_logger()

REGIME_STD_MULTIPLIER = 2.0


class MetricSeries(BaseModel):
    """Time-ordered metric values extracted from evaluation history."""

    values: list[float]
    timestamps: list[datetime]


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


async def gather_metric_series(
    *,
    baseline_repo: BaselineRepository,
    asset_id: uuid.UUID,
    slo_name: str,
    metric_name: str,
    period_end: datetime,
    evaluation_name: str,
    window_size: int,
) -> MetricSeries:
    """Query evaluation history and extract a single metric's time series."""
    history_evals = await baseline_repo.get_evaluation_baselines(
        asset_id=asset_id,
        slo_name=slo_name,
        period_start_before=period_end,
        include_result_with_score='all',
        limit=window_size,
        evaluation_name=evaluation_name,
    )

    values: list[float] = []
    timestamps: list[datetime] = []

    for evaluation in sorted(history_evals, key=lambda ev: ev.period_start):
        for row in evaluation.indicator_rows or []:
            if row.objective and row.objective.sli == metric_name and row.value is not None:
                values.append(float(row.value))
                timestamps.append(evaluation.period_start)
                break

    return MetricSeries(values=values, timestamps=timestamps)


async def run_change_point_detection(
    *,
    session: AsyncSession,
    snapshot: EvaluationSnapshot,
    slo_def: SLODefinition,
    indicator_rows: list[IndicatorResultRow],
    cache: Any | None = None,
) -> None:
    """Run Otava change point detection for each enabled metric.

    Called as a fault-isolated step after evaluation scoring. Iterates over
    each SLO objective, gathers the metric's historical time series, runs
    E-Divisive detection, and persists any new change points with dedup.

    Skips detection entirely when compare_to points to a different evaluation
    series, since cross-series change points are not statistically meaningful.
    """
    log = logger.bind(
        evaluation_id=str(snapshot.eval_id),
        slo_name=snapshot.slo_name,
    )

    comparison_name = resolve_comparison_name(
        snapshot.compare_to,
        snapshot.evaluation_name,
    )

    if comparison_name != snapshot.evaluation_name:
        log.debug(
            'skipping change point detection for cross-series comparison',
            evaluation_name=snapshot.evaluation_name,
            comparison_name=comparison_name,
        )
        return

    indicator_lookup = {row.objective.sli: row for row in indicator_rows if row.objective}

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
            series = await gather_metric_series(
                baseline_repo=baseline_repo,
                asset_id=snapshot.asset_id,
                slo_name=snapshot.slo_name,
                metric_name=objective.sli,
                period_end=snapshot.period_end,
                evaluation_name=comparison_name,
                window_size=resolved.window_size,
            )

            if len(series.values) < resolved.min_sample_size:
                log.debug(
                    'insufficient history for change point detection',
                    metric=objective.sli,
                    sample_count=len(series.values),
                    min_required=resolved.min_sample_size,
                )
                continue

            detected = detect_change_points(
                values=series.values,
                timestamps=series.timestamps,
                higher_is_better=resolved.higher_is_better,
                window_size=resolved.window_size,
                max_pvalue=resolved.max_pvalue,
                min_magnitude=resolved.min_magnitude,
                min_sample_size=resolved.min_sample_size,
                pvalue_strict_threshold=resolved.pvalue_strict_threshold,
                pvalue_moderate_threshold=resolved.pvalue_moderate_threshold,
            )

            if detected:
                await _persist_change_points(
                    log=log,
                    change_point_repo=change_point_repo,
                    detected=detected,
                    timestamps=series.timestamps,
                    snapshot=snapshot,
                    metric_name=objective.sli,
                    indicator_result_id=indicator_row.id,
                    comparison_name=comparison_name,
                )
        except (OSError, ValueError, TypeError, RuntimeError, LookupError):
            log.warning(
                'change point detection failed for metric',
                metric=objective.sli,
                exc_info=True,
            )


async def _persist_change_points(
    *,
    log: Any,
    change_point_repo: ChangePointRepository,
    detected: list[ChangePointResult],
    timestamps: list[datetime],
    snapshot: EvaluationSnapshot,
    metric_name: str,
    indicator_result_id: uuid.UUID,
    comparison_name: str,
) -> None:
    """Dedup and persist detected change points.

    For each candidate, checks for nearby existing change points (±1 ordinal position)
    and suppresses same-regime duplicates where the metric hasn't meaningfully shifted
    from the previous change point's post-segment.
    """
    batch_timestamps: set[datetime] = set()

    for candidate in detected:
        detection_index = candidate.position
        nearby_indices = range(
            max(0, detection_index - 1),
            min(len(timestamps), detection_index + 2),
        )
        nearby_timestamps = [timestamps[i] for i in nearby_indices if timestamps[i] not in batch_timestamps]

        has_existing = bool(nearby_timestamps) and await change_point_repo.has_nearby_change_point(
            asset_id=snapshot.asset_id,
            slo_name=snapshot.slo_name,
            metric_name=metric_name,
            period_start=candidate.timestamp,
            nearby_timestamps=nearby_timestamps,
            evaluation_name=comparison_name,
        )

        if has_existing:
            log.debug('change point deduped', metric=metric_name, position=candidate.position)
            continue

        previous_cp = await change_point_repo.get_latest_change_point(
            asset_id=snapshot.asset_id,
            slo_name=snapshot.slo_name,
            metric_name=metric_name,
            evaluation_name=comparison_name,
        )
        if (
            previous_cp
            and previous_cp.direction == candidate.direction
            and _same_regime(
                previous_cp.post_segment_mean,
                previous_cp.post_segment_std,
                candidate.post_segment_mean,
            )
        ):
            log.debug(
                'change point suppressed — same regime as previous',
                metric=metric_name,
                previous_mean=previous_cp.post_segment_mean,
                previous_std=previous_cp.post_segment_std,
                current_mean=candidate.post_segment_mean,
            )
            continue

        await change_point_repo.insert_change_point(
            ChangePointInsertParams(
                indicator_result_id=indicator_result_id,
                evaluation_run_id=snapshot.parent_run_id,
                asset_id=snapshot.asset_id,
                slo_name=snapshot.slo_name,
                metric_name=metric_name,
                period_start=candidate.timestamp,
                detector=candidate.detector,
                direction=candidate.direction,
                change_relative_pct=candidate.change_relative_pct,
                change_absolute=candidate.change_absolute,
                pvalue=candidate.pvalue,
                pre_segment_mean=candidate.pre_segment_mean,
                post_segment_mean=candidate.post_segment_mean,
                post_segment_std=candidate.post_segment_std,
            )
        )

        batch_timestamps.add(candidate.timestamp)
        log.info(
            'change point detected',
            metric=metric_name,
            direction=candidate.direction,
            magnitude_pct=candidate.change_relative_pct,
        )
