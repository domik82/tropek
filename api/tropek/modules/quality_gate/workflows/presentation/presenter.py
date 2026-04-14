"""Evaluation presenter — transform ORM models into API response schemas."""

from __future__ import annotations

import uuid
from typing import Any, NamedTuple

from tropek.db.models import EvaluationRun, IndicatorResultRow, SLOEvaluation
from tropek.modules.quality_gate.evaluation_engine.constants import RESULT_RANK
from tropek.modules.quality_gate.evaluation_engine.criteria import ParsedCriteria, parse_criteria_string
from tropek.modules.quality_gate.schemas import (
    AnnotationRead,
    EvaluationColumn,
    EvaluationDetail,
    EvaluationSummary,
    FailingIndicator,
    GroupedMetricHeatmapResponse,
    HeatmapCellGrouped,
    HeatmapMetric,
    HeatmapSloGroupSection,
    HeatmapSummaryCell,
    IndicatorResult,
)
from tropek.modules.quality_gate.schemas.evaluations import PassTarget
from tropek.modules.quality_gate.schemas.heatmap import (
    HeatmapColumnFragment,
    HeatmapColumnSloFragment,
)
from tropek.modules.quality_gate.workflows.presentation.target_resolver import (
    resolve_targets,
    resolve_targets_from_parsed,
)


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
    return resolve_targets(
        criteria,
        value=row.value,
        compared_value=row.compared_value,
    )


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


def _slo_summary_result(slo_eval: SLOEvaluation | None) -> str:
    """Derive the display result for a single SLO evaluation column."""
    if not slo_eval:
        return 'none'
    if slo_eval.invalidated:
        return 'invalidated'
    return slo_eval.result or 'none'


def assemble_grouped_response(
    asset_name: str,
    fragments: list[HeatmapColumnFragment],
) -> GroupedMetricHeatmapResponse:
    """Merge per-run fragments (in column order) into a full grouped heatmap response.

    Fragments must already be sorted oldest → newest.
    """
    columns = [fragment.column for fragment in fragments]
    composite = [fragment.composite_summary for fragment in fragments]

    # Collect groups in order of first appearance.
    slo_order: list[str] = []
    groups_by_name: dict[str, dict[str, Any]] = {}
    for column_index, fragment in enumerate(fragments):
        for slo_part in fragment.per_slo:
            if slo_part.slo_name not in groups_by_name:
                slo_order.append(slo_part.slo_name)
                groups_by_name[slo_part.slo_name] = {
                    'slo_display_name': slo_part.slo_display_name,
                    'metrics_by_name': {metric.name: metric for metric in slo_part.metrics},
                    'cells': [],
                    'summary_by_col': {},
                }
            entry = groups_by_name[slo_part.slo_name]
            for metric in slo_part.metrics:
                entry['metrics_by_name'].setdefault(metric.name, metric)
            entry['cells'].extend(slo_part.cells)
            entry['summary_by_col'][column_index] = slo_part.summary

    groups: list[HeatmapSloGroupSection] = []
    for slo_name in slo_order:
        entry = groups_by_name[slo_name]
        summary = [
            entry['summary_by_col'].get(column_index) or _empty_summary_for_run(fragments[column_index])
            for column_index in range(len(fragments))
        ]
        groups.append(
            HeatmapSloGroupSection(
                slo_name=slo_name,
                slo_display_name=entry['slo_display_name'],
                metrics=list(entry['metrics_by_name'].values()),
                cells=entry['cells'],
                summary=summary,
            )
        )

    return GroupedMetricHeatmapResponse(
        asset_name=asset_name,
        columns=columns,
        groups=groups,
        composite=composite,
    )


def _empty_summary_for_run(fragment: HeatmapColumnFragment) -> HeatmapSummaryCell:
    """Placeholder summary cell for a column where a given SLO did not run."""
    return HeatmapSummaryCell(
        evaluation_id=fragment.column.evaluation_id,
        period_start=fragment.column.period_start,
        result='none',
        score=0.0,
        invalidated=False,
        invalidation_note=None,
    )


def build_grouped_heatmap_response(
    asset_name: str,
    runs: list[EvaluationRun],
    noted_run_ids: set[uuid.UUID] | None = None,
) -> GroupedMetricHeatmapResponse:
    """Build GroupedMetricHeatmapResponse by delegating to fragment builder + assembler.

    Assumes each run already has slo_evaluations + indicator_rows eager-loaded.
    Runs must arrive in DESC order (newest first) — this function reverses to ASC.

    For runs that exist in the Redis column cache, the read path should fetch
    fragments directly and skip this function — it's retained for the cache
    miss fallback and for the ``cache=false`` bypass.
    """
    runs_asc = sorted(runs, key=lambda r: (r.period_start, r.eval_name or ''))
    noted = noted_run_ids or set()
    fragments = [build_column_fragment(run, has_notes=run.id in noted) for run in runs_asc]
    return assemble_grouped_response(asset_name, fragments)


class _ParsedObjectiveCriteria(NamedTuple):
    """Cache entry for a single objective's parsed criteria, reused per-cell."""

    raw_pass: list[str] | None
    parsed_pass: list[ParsedCriteria] | None
    raw_warning: list[str] | None
    parsed_warning: list[ParsedCriteria] | None


def _parse_objective_criteria(objective: Any) -> _ParsedObjectiveCriteria:
    """Parse an objective's pass + warning criteria strings exactly once."""
    raw_pass = list(objective.pass_threshold) if objective.pass_threshold else None
    raw_warning = list(objective.warning_threshold) if objective.warning_threshold else None
    parsed_pass = [parse_criteria_string(raw) for raw in raw_pass] if raw_pass is not None else None
    parsed_warning = [parse_criteria_string(raw) for raw in raw_warning] if raw_warning is not None else None
    return _ParsedObjectiveCriteria(
        raw_pass=raw_pass,
        parsed_pass=parsed_pass,
        raw_warning=raw_warning,
        parsed_warning=parsed_warning,
    )


def build_column_fragment(
    run: EvaluationRun,
    *,
    has_notes: bool,
) -> HeatmapColumnFragment:
    """Build one heatmap column fragment for a single EvaluationRun.

    Cached independently in Redis per (schema_version, run.id). Criteria
    strings are parsed exactly once per unique objective within this fragment
    via a per-call cache keyed on ``id(objective)`` — safe because
    ``IndicatorResultRow.objective`` is a joined-loaded ``SLOObjective``
    relationship, so the same Python object is reused across rows within one
    SQLAlchemy session.
    """
    parsed_cache: dict[int, _ParsedObjectiveCriteria] = {}
    per_slo: list[HeatmapColumnSloFragment] = []

    for slo_eval in run.slo_evaluations or []:
        metrics: dict[str, str] = {}
        cells: list[HeatmapCellGrouped] = []
        sli_metadata = slo_eval.job_stats.get('sli_metadata', {}) if slo_eval.job_stats else {}

        for row in slo_eval.indicator_rows or []:
            objective = row.objective
            metric_name = objective.sli
            display_name = objective.display_name or metric_name
            if metric_name not in metrics:
                metrics[metric_name] = display_name

            cache_key = id(objective)
            entry = parsed_cache.get(cache_key)
            if entry is None:
                entry = _parse_objective_criteria(objective)
                parsed_cache[cache_key] = entry

            cells.append(
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
                    pass_targets=resolve_targets_from_parsed(
                        entry.parsed_pass,
                        entry.raw_pass,
                        value=row.value,
                        compared_value=row.compared_value,
                    ),
                    warning_targets=resolve_targets_from_parsed(
                        entry.parsed_warning,
                        entry.raw_warning,
                        value=row.value,
                        compared_value=row.compared_value,
                    ),
                    tab_group=objective.tab_group,
                    aggregation=sli_metadata.get(metric_name, {}).get('mode'),
                )
            )

        slo_score = (
            slo_eval.achieved_points / slo_eval.total_points * 100
            if slo_eval.total_points and slo_eval.achieved_points is not None
            else 0.0
        )
        per_slo.append(
            HeatmapColumnSloFragment(
                slo_name=slo_eval.slo_name,
                slo_display_name=getattr(slo_eval, 'slo_display_name', None),
                metrics=[
                    HeatmapMetric(name=metric_name, display_name=display_name)
                    for metric_name, display_name in metrics.items()
                ],
                cells=cells,
                summary=HeatmapSummaryCell(
                    evaluation_id=run.id,
                    period_start=run.period_start,
                    result=_slo_summary_result(slo_eval),
                    score=round(slo_score, 2),
                    total_score_pass_threshold=(
                        slo_eval.job_stats.get('total_score_pass_threshold') if slo_eval.job_stats else None
                    ),
                    total_score_warning_threshold=(
                        slo_eval.job_stats.get('total_score_warning_threshold') if slo_eval.job_stats else None
                    ),
                    sli_metadata=sli_metadata or None,
                    slo_version=slo_eval.slo_version,
                    sli_version=slo_eval.sli_version,
                    invalidated=slo_eval.invalidated,
                    invalidation_note=slo_eval.invalidation_note,
                ),
            )
        )

    return HeatmapColumnFragment(
        evaluation_run_id=run.id,
        column=EvaluationColumn(
            evaluation_id=run.id,
            period_start=run.period_start,
            period_end=run.period_end,
            eval_name=run.eval_name,
            has_notes=has_notes,
        ),
        per_slo=per_slo,
        composite_summary=_build_composite_summary_for_run(run),
    )


def _build_composite_summary_for_run(run: EvaluationRun) -> HeatmapSummaryCell:
    """Build one composite summary cell for a single run.

    Worst-case across all SLOs for this run, producing one cell of the
    Overall row in the grouped heatmap response.
    """
    total_points = run.total_points
    achieved_points = run.achieved_points
    run_score = round(achieved_points / total_points * 100, 2) if total_points and achieved_points is not None else 0.0
    slo_evaluations = run.slo_evaluations or []
    all_invalidated = bool(slo_evaluations) and all(slo_eval.invalidated for slo_eval in slo_evaluations)
    return HeatmapSummaryCell(
        evaluation_id=run.id,
        period_start=run.period_start,
        result='invalidated' if all_invalidated else (run.result or 'none'),
        score=run_score,
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
