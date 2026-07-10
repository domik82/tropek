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
from tropek.modules.change_points.detector import ChangePointResult, detect_change_points
from tropek.modules.change_points.models import (
    ChangePointInputs,
    DetectedBatch,
    EnabledObjective,
    MetricSeries,
)
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


def extract_metric_series(
    *,
    history_evals: list[Any],
    metric_name: str,
    window_size: int,
) -> MetricSeries:
    """Extract one metric's time series from pre-loaded baseline history.

    ``history_evals`` is ordered period_start DESC (as returned by
    ``get_evaluation_baselines``). Take the most-recent ``window_size``
    evaluations, order them ascending, and pull the matching metric value.
    """
    windowed = history_evals[:window_size]

    values: list[float] = []
    timestamps: list[datetime] = []
    period_ends: list[datetime | None] = []
    evaluation_run_ids: list[uuid.UUID] = []

    for evaluation in sorted(windowed, key=lambda evaluation: evaluation.period_start):
        for row in evaluation.indicator_rows or []:
            if row.objective and row.objective.sli == metric_name and row.value is not None:
                values.append(float(row.value))
                timestamps.append(evaluation.period_start)
                period_ends.append(evaluation.period_end)
                evaluation_run_ids.append(evaluation.evaluation_id)
                break

    return MetricSeries(
        values=values,
        timestamps=timestamps,
        period_ends=period_ends,
        evaluation_run_ids=evaluation_run_ids,
    )


async def load_change_point_inputs(
    *,
    session: AsyncSession,
    snapshot: EvaluationSnapshot,
    slo_def: SLODefinition,
    indicator_rows: list[IndicatorResultRow],
    cache: Any | None = None,
) -> ChangePointInputs | None:
    """Read phase: resolve enabled objectives and fetch baseline history once.

    Returns None for a cross-series comparison or when no objective is enabled.
    """
    comparison_name = resolve_comparison_name(snapshot.compare_to, snapshot.evaluation_name)
    if comparison_name != snapshot.evaluation_name:
        return None

    indicator_lookup = {row.objective.sli: row for row in indicator_rows if row.objective}

    config_repo = ConfigurationRepository(session)
    system_defaults = await config_repo.get_change_point_defaults()

    enabled_objectives: list[EnabledObjective] = []
    for objective in slo_def.objectives:
        indicator_row = indicator_lookup.get(objective.sli)
        if not indicator_row:
            continue
        resolved = ChangePointRepository.resolve_from_objective(objective, system_defaults)
        if not resolved.enabled:
            continue
        enabled_objectives.append(
            EnabledObjective(
                metric_name=objective.sli,
                resolved=resolved,
                indicator_result_id=indicator_row.id,
            )
        )

    if not enabled_objectives:
        return None

    max_window = max(objective.resolved.window_size for objective in enabled_objectives)
    baseline_repo = BaselineRepository(session, cache=cache)
    shared_history = await baseline_repo.get_evaluation_baselines(
        asset_id=snapshot.asset_id,
        slo_name=snapshot.slo_name,
        period_start_before=snapshot.period_end,
        include_result_with_score='all',
        limit=max_window,
        evaluation_name=comparison_name,
    )

    return ChangePointInputs(
        comparison_name=comparison_name,
        enabled_objectives=enabled_objectives,
        shared_history=list(shared_history),
    )


def detect_change_points_for_objectives(
    cp_inputs: ChangePointInputs,
    *,
    log: Any,
) -> list[DetectedBatch]:
    """Compute phase: run detection per objective. Pure — holds no DB session."""
    batches: list[DetectedBatch] = []
    for objective in cp_inputs.enabled_objectives:
        try:
            series = extract_metric_series(
                history_evals=cp_inputs.shared_history,
                metric_name=objective.metric_name,
                window_size=objective.resolved.window_size,
            )
            if len(series.values) < objective.resolved.min_sample_size:
                log.debug(
                    'insufficient history for change point detection',
                    metric=objective.metric_name,
                    sample_count=len(series.values),
                    min_required=objective.resolved.min_sample_size,
                )
                continue

            detected = detect_change_points(
                values=series.values,
                timestamps=series.timestamps,
                higher_is_better=objective.resolved.higher_is_better,
                window_size=objective.resolved.window_size,
                max_pvalue=objective.resolved.max_pvalue,
                min_magnitude=objective.resolved.min_magnitude,
                min_sample_size=objective.resolved.min_sample_size,
                pvalue_strict_threshold=objective.resolved.pvalue_strict_threshold,
                pvalue_moderate_threshold=objective.resolved.pvalue_moderate_threshold,
            )
            if detected:
                batches.append(
                    DetectedBatch(
                        metric_name=objective.metric_name,
                        indicator_result_id=objective.indicator_result_id,
                        series=series,
                        detected=detected,
                    )
                )
        except (OSError, ValueError, TypeError, RuntimeError, LookupError):
            log.warning(
                'change point detection failed for metric',
                metric=objective.metric_name,
                exc_info=True,
            )
    return batches


async def _persist_change_points(
    *,
    log: Any,
    change_point_repo: ChangePointRepository,
    detected: list[ChangePointResult],
    series: MetricSeries,
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
    timestamps = series.timestamps
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

        candidate_period_end = (
            series.period_ends[detection_index] if detection_index < len(series.period_ends) else snapshot.period_end
        )
        shifted_eval_run_id = (
            series.evaluation_run_ids[detection_index]
            if detection_index < len(series.evaluation_run_ids)
            else snapshot.parent_run_id
        )

        await change_point_repo.insert_change_point(
            ChangePointInsertParams(
                indicator_result_id=indicator_result_id,
                evaluation_run_id=shifted_eval_run_id,
                found_by_evaluation_id=snapshot.parent_run_id,
                asset_id=snapshot.asset_id,
                slo_name=snapshot.slo_name,
                metric_name=metric_name,
                period_start=candidate.timestamp,
                period_end=candidate_period_end,
                detector=candidate.detector,
                direction=candidate.direction,
                change_relative_pct=candidate.change_relative_pct,
                change_absolute=candidate.change_absolute,
                pvalue=candidate.pvalue,
                pre_segment_mean=candidate.pre_segment_mean,
                post_segment_mean=candidate.post_segment_mean,
                post_segment_std=candidate.post_segment_std,
                transition=candidate.transition,
            )
        )

        batch_timestamps.add(candidate.timestamp)
        log.info(
            'change point detected',
            metric=metric_name,
            direction=candidate.direction,
            magnitude_pct=candidate.change_relative_pct,
        )


async def persist_detected_change_points(
    *,
    session: AsyncSession,
    snapshot: EvaluationSnapshot,
    comparison_name: str,
    detected_batches: list[DetectedBatch],
    log: Any,
) -> None:
    """Write phase: dedup and insert detected change points, one batch per metric."""
    change_point_repo = ChangePointRepository(session)
    for batch in detected_batches:
        await _persist_change_points(
            log=log,
            change_point_repo=change_point_repo,
            detected=batch.detected,
            series=batch.series,
            snapshot=snapshot,
            metric_name=batch.metric_name,
            indicator_result_id=batch.indicator_result_id,
            comparison_name=comparison_name,
        )
