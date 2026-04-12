"""Evaluation presenter — transform ORM models into API response schemas."""

from __future__ import annotations

import uuid
from typing import Any

from tropek.db.models import EvaluationRun, IndicatorResultRow, SLOEvaluation
from tropek.modules.quality_gate.evaluation_engine.constants import RESULT_RANK
from tropek.modules.quality_gate.schemas import (
    AnnotationRead,
    EvaluationColumn,
    EvaluationDetail,
    EvaluationSummary,
    FailingIndicator,
    GroupedMetricHeatmapResponse,
    HeatmapCellGrouped,
    HeatmapMetric,
    HeatmapSummaryCell,
    IndicatorResult,
    SloGroup,
)
from tropek.modules.quality_gate.schemas.evaluations import PassTarget
from tropek.modules.quality_gate.workflows.presentation.target_resolver import resolve_targets


def _read_stored_targets(
    row: Any,
    objective: Any,
    *,
    is_pass: bool,
) -> list[PassTarget] | None:
    """Read targets from stored JSONB, falling back to resolve_targets for old rows."""
    stored = getattr(row, 'targets', None)
    if stored is not None:
        key = 'pass' if is_pass else 'warn'
        raw_targets = stored.get(key)
        if raw_targets is None:
            return None
        return [PassTarget.model_validate(entry) for entry in raw_targets]
    criteria = list(objective.pass_threshold) if is_pass else list(objective.warning_threshold)
    if not criteria:
        return None
    resolved = resolve_targets(
        criteria,
        value=row.value,
        compared_value=row.compared_value,
    )
    if resolved is None:
        return None
    return [PassTarget.model_validate(entry) for entry in resolved]


def _indicators_from_orm_rows(rows: list[IndicatorResultRow]) -> list[IndicatorResult]:
    """Build IndicatorResult schema objects from ORM IndicatorResultRow with joined objectives."""
    results: list[IndicatorResult] = []
    for row in rows:
        objective = row.objective
        results.append(
            IndicatorResult(
                metric=objective.sli,
                display_name=objective.display_name,
                tab_group=getattr(objective, 'tab_group', None),
                value=row.value,
                compared_value=row.compared_value,
                change_absolute=row.change_absolute,
                change_relative_pct=row.change_relative_pct,
                aggregation=None,
                status=row.status,
                score=row.score,
                weight=objective.weight,
                key_sli=objective.key_sli,
                pass_targets=_read_stored_targets(row, objective, is_pass=True),
                warning_targets=_read_stored_targets(row, objective, is_pass=False),
            )
        )
    return results


def _get_indicator_results(ev: SLOEvaluation) -> list[IndicatorResult]:
    """Get indicator results from ORM rows."""
    orm_rows = getattr(ev, 'indicator_rows', None)
    if orm_rows:
        return _indicators_from_orm_rows(orm_rows)
    return []


def _top_failures(indicators: list[IndicatorResult]) -> list[FailingIndicator]:
    """Extract failing indicators into top_failures list."""
    return [
        FailingIndicator(
            metric=ind.metric,
            display_name=ind.display_name,
            value=ind.value,
            threshold=ind.pass_targets[0].criteria if ind.pass_targets else '',
        )
        for ind in indicators
        if ind.status == 'fail'
    ]


def build_summary(ev: SLOEvaluation, annotation_count: int, latest_ann: object | None) -> EvaluationSummary:
    """Transform ORM Evaluation into API summary schema."""
    indicators = _get_indicator_results(ev)
    job_stats = getattr(ev, 'job_stats', None) or {}
    return EvaluationSummary.model_validate(
        {
            **ev.__dict__,
            'original_score': job_stats.get('original_score'),
            'annotation_count': annotation_count,
            'latest_annotation': latest_ann,
            'top_failures': _top_failures(indicators),
        }
    )


def worst_result(results: list[str]) -> str:
    """Return the worst result in `results`, defaulting to 'none' if empty."""
    if not results:
        return 'none'
    return max(results, key=lambda r: RESULT_RANK.get(r, -1))


def _collect_slo_heatmap_data(
    runs_asc: list[EvaluationRun],
    column_index_by_run_id: dict[uuid.UUID, int],
) -> dict[str, dict[str, Any]]:
    """Walk runs and collect per-SLO metrics, cells, and column mappings."""
    slo_data: dict[str, dict[str, Any]] = {}

    for run in runs_asc:
        column_index = column_index_by_run_id[run.id]
        for slo_eval in run.slo_evaluations or []:
            slo_name = slo_eval.slo_name
            if slo_name not in slo_data:
                slo_data[slo_name] = {
                    'metrics': {},
                    'cells': [],
                    'per_col': {},
                }
            entry = slo_data[slo_name]
            entry['per_col'][column_index] = slo_eval
            for row in slo_eval.indicator_rows or []:
                objective = row.objective
                metric_name = objective.sli
                display_name = objective.display_name or metric_name
                if metric_name not in entry['metrics']:
                    entry['metrics'][metric_name] = display_name
                sli_metadata = slo_eval.job_stats.get('sli_metadata', {})
                entry['cells'].append(
                    HeatmapCellGrouped(
                        evaluation_id=run.id,
                        slo_evaluation_id=slo_eval.id,
                        period_start=run.period_start,
                        metric=metric_name,
                        display_name=display_name,
                        result='invalidated' if slo_eval.invalidated else row.status,
                        score=row.score,
                        value=row.value,
                        compared_value=row.compared_value,
                        change_relative_pct=row.change_relative_pct,
                        weight=objective.weight,
                        key_sli=objective.key_sli,
                        pass_targets=resolve_targets(
                            list(objective.pass_threshold) if objective.pass_threshold else None,
                            value=row.value,
                            compared_value=row.compared_value,
                        ),
                        warning_targets=resolve_targets(
                            list(objective.warning_threshold)
                            if objective.warning_threshold
                            else None,
                            value=row.value,
                            compared_value=row.compared_value,
                        ),
                        tab_group=objective.tab_group,
                        aggregation=sli_metadata.get(metric_name, {}).get('mode'),
                    )
                )

    return slo_data


def _slo_summary_result(slo_eval: SLOEvaluation | None) -> str:
    """Derive the display result for a single SLO evaluation column."""
    if not slo_eval:
        return 'none'
    if slo_eval.invalidated:
        return 'invalidated'
    return slo_eval.result or 'none'


def _build_slo_groups(
    slo_data: dict[str, dict[str, Any]],
    runs_asc: list[EvaluationRun],
) -> list[SloGroup]:
    """Build SloGroup list with per-column summary cells from collected SLO data."""
    column_count = len(runs_asc)
    groups = []

    for slo_name, entry in sorted(slo_data.items()):
        summary = []
        for column_index in range(column_count):
            slo_eval = entry['per_col'].get(column_index)
            result = _slo_summary_result(slo_eval)
            score = (
                slo_eval.achieved_points / slo_eval.total_points * 100
                if slo_eval and slo_eval.total_points
                else 0.0
            )
            summary.append(
                HeatmapSummaryCell(
                    evaluation_id=runs_asc[column_index].id,
                    period_start=runs_asc[column_index].period_start,
                    result=result,
                    score=round(score, 2),
                    total_score_pass_threshold=(
                        slo_eval.job_stats.get('total_score_pass_threshold') if slo_eval else None
                    ),
                    total_score_warning_threshold=(
                        slo_eval.job_stats.get('total_score_warning_threshold')
                        if slo_eval
                        else None
                    ),
                    sli_metadata=slo_eval.job_stats.get('sli_metadata') if slo_eval else None,
                    invalidated=slo_eval.invalidated if slo_eval else False,
                    invalidation_note=slo_eval.invalidation_note if slo_eval else None,
                )
            )
        groups.append(
            SloGroup(
                slo_name=slo_name,
                metrics=[
                    HeatmapMetric(name=metric_name, display_name=display_name)
                    for metric_name, display_name in entry['metrics'].items()
                ],
                cells=entry['cells'],
                summary=summary,
            )
        )

    return groups


def _build_composite_summary(runs_asc: list[EvaluationRun]) -> list[HeatmapSummaryCell]:
    """Build the top-level composite summary row across all runs."""
    composite = []
    for run in runs_asc:
        total_points = run.total_points
        achieved_points = run.achieved_points
        run_score = (
            round(achieved_points / total_points * 100, 2)
            if total_points and achieved_points is not None
            else 0.0
        )
        all_invalidated = run.slo_evaluations and all(
            slo_eval.invalidated for slo_eval in run.slo_evaluations
        )
        composite.append(
            HeatmapSummaryCell(
                evaluation_id=run.id,
                period_start=run.period_start,
                result='invalidated' if all_invalidated else (run.result or 'none'),
                score=run_score,
            )
        )
    return composite


def build_grouped_heatmap_response(
    asset_name: str,
    runs: list[EvaluationRun],
    noted_run_ids: set[uuid.UUID] | None = None,
) -> GroupedMetricHeatmapResponse:
    """Build GroupedMetricHeatmapResponse from a list of EvaluationRun rows.

    Assumes each run already has slo_evaluations + indicator_rows eager-loaded.
    Runs must arrive in DESC order (newest first) — this function reverses to ASC.
    """
    runs_asc = sorted(runs, key=lambda r: (r.period_start, r.eval_name or ''))

    noted = noted_run_ids or set()
    columns = [
        EvaluationColumn(
            evaluation_id=run.id,
            period_start=run.period_start,
            period_end=run.period_end,
            eval_name=run.eval_name,
            has_notes=run.id in noted,
        )
        for run in runs_asc
    ]
    column_index_by_run_id: dict[uuid.UUID, int] = {
        run.id: index for index, run in enumerate(runs_asc)
    }

    slo_data = _collect_slo_heatmap_data(runs_asc, column_index_by_run_id)
    groups = _build_slo_groups(slo_data, runs_asc)
    composite = _build_composite_summary(runs_asc)

    return GroupedMetricHeatmapResponse(
        asset_name=asset_name,
        columns=columns,
        groups=groups,
        composite=composite,
    )


def build_detail(ev: SLOEvaluation) -> EvaluationDetail:
    """Transform ORM Evaluation with annotations into API detail schema."""
    annotations = [AnnotationRead.model_validate(a) for a in (ev.annotations or []) if a.hidden_at is None]
    indicators = _get_indicator_results(ev)
    job_stats_detail = ev.job_stats or {}
    compared_ids = job_stats_detail.get('compared_evaluation_ids', [])
    sorted_annotations = sorted(annotations, key=lambda a: a.created_at)
    return EvaluationDetail.model_validate(
        {
            **ev.__dict__,
            'original_score': job_stats_detail.get('original_score'),
            'annotation_count': len(annotations),
            'latest_annotation': sorted_annotations[-1] if sorted_annotations else None,
            'top_failures': _top_failures(indicators),
            'compared_evaluation_ids': [uuid.UUID(eid) for eid in compared_ids],
            'annotations': sorted_annotations,
            'indicator_results': indicators,
            'total_score_pass_threshold': job_stats_detail.get('total_score_pass_threshold'),
            'total_score_warning_threshold': job_stats_detail.get('total_score_warning_threshold'),
            'sli_metadata': job_stats_detail.get('sli_metadata'),
        }
    )
