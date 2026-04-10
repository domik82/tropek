"""Evaluation presenter — transform ORM models into API response schemas."""

from __future__ import annotations

import uuid
from typing import Any

from app.db.models import EvaluationRun
from app.modules.quality_gate.engine.constants import RESULT_RANK
from app.modules.quality_gate.schemas import (
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
from app.modules.quality_gate.target_resolver import resolve_targets


def _read_stored_targets(
    row: Any,
    obj: Any,
    *,
    is_pass: bool,
) -> list[dict[str, Any]] | None:
    """Read targets from stored JSONB, falling back to resolve_targets for old rows."""
    stored = getattr(row, 'targets', None)
    if stored is not None:
        key = 'pass' if is_pass else 'warn'
        result: list[dict[str, Any]] | None = stored.get(key)
        return result
    criteria = list(obj.pass_threshold) if is_pass else list(obj.warning_threshold)
    if not criteria:
        return None
    return resolve_targets(
        criteria,
        value=row.value,
        compared_value=row.compared_value,
    )


def _indicators_from_orm_rows(rows: list) -> list[IndicatorResult]:  # type: ignore[type-arg]
    """Build IndicatorResult schema objects from ORM IndicatorResultRow with joined objectives."""
    results: list[IndicatorResult] = []
    for row in rows:
        obj = row.objective
        results.append(
            IndicatorResult(
                metric=obj.sli,
                display_name=obj.display_name,
                tab_group=getattr(obj, 'tab_group', None),
                value=row.value,
                compared_value=row.compared_value,
                change_absolute=row.change_absolute,
                change_relative_pct=row.change_relative_pct,
                aggregation=None,
                status=row.status,
                score=row.score,
                weight=obj.weight,
                key_sli=obj.key_sli,
                pass_targets=_read_stored_targets(row, obj, is_pass=True),
                warning_targets=_read_stored_targets(row, obj, is_pass=False),
            )
        )
    return results


def _get_indicator_results(ev: object) -> list[IndicatorResult]:
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
            threshold=(ind.pass_targets or [{}])[0].get('criteria', ''),
        )
        for ind in indicators
        if ind.status == 'fail'
    ]


def build_summary(ev: object, annotation_count: int, latest_ann: object | None) -> EvaluationSummary:
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
    n = len(runs_asc)

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
    col_idx: dict[uuid.UUID, int] = {run.id: i for i, run in enumerate(runs_asc)}

    slo_data: dict[str, dict[str, Any]] = {}

    for run in runs_asc:
        xi = col_idx[run.id]
        for slo_eval in run.slo_evaluations or []:
            sn = slo_eval.slo_name
            if sn not in slo_data:
                slo_data[sn] = {
                    'metrics': {},
                    'cells': [],
                    'per_col': {},
                }
            sd = slo_data[sn]
            sd['per_col'][xi] = slo_eval
            for row in slo_eval.indicator_rows or []:
                obj = row.objective
                mn = obj.sli
                dn = obj.display_name or mn
                if mn not in sd['metrics']:
                    sd['metrics'][mn] = dn
                sli_meta = slo_eval.job_stats.get('sli_metadata', {})
                sd['cells'].append(
                    HeatmapCellGrouped(
                        evaluation_id=run.id,
                        slo_evaluation_id=slo_eval.id,
                        period_start=run.period_start,
                        metric=mn,
                        display_name=dn,
                        result='invalidated' if slo_eval.invalidated else row.status,
                        score=row.score,
                        value=row.value,
                        compared_value=row.compared_value,
                        change_relative_pct=row.change_relative_pct,
                        weight=obj.weight,
                        key_sli=obj.key_sli,
                        pass_targets=resolve_targets(
                            list(obj.pass_threshold) if obj.pass_threshold else None,
                            value=row.value,
                            compared_value=row.compared_value,
                        ),
                        warning_targets=resolve_targets(
                            list(obj.warning_threshold) if obj.warning_threshold else None,
                            value=row.value,
                            compared_value=row.compared_value,
                        ),
                        tab_group=obj.tab_group,
                        aggregation=sli_meta.get(mn, {}).get('mode'),
                    )
                )

    groups = []
    for sn, sd in sorted(slo_data.items()):
        summary = []
        for xi in range(n):
            slo_ev = sd['per_col'].get(xi)
            result = (
                'invalidated' if slo_ev and slo_ev.invalidated
                else slo_ev.result if slo_ev and slo_ev.result
                else 'none'
            )
            score = (
                slo_ev.achieved_points / slo_ev.total_points * 100
                if slo_ev and slo_ev.total_points
                else 0.0
            )
            summary.append(
                HeatmapSummaryCell(
                    evaluation_id=runs_asc[xi].id,
                    period_start=runs_asc[xi].period_start,
                    result=result,
                    score=round(score, 2),
                    total_score_pass_threshold=(
                        slo_ev.job_stats.get('total_score_pass_threshold') if slo_ev else None
                    ),
                    total_score_warning_threshold=(
                        slo_ev.job_stats.get('total_score_warning_threshold') if slo_ev else None
                    ),
                    sli_metadata=slo_ev.job_stats.get('sli_metadata') if slo_ev else None,
                    invalidated=slo_ev.invalidated if slo_ev else False,
                    invalidation_note=slo_ev.invalidation_note if slo_ev else None,
                )
            )
        groups.append(
            SloGroup(
                slo_name=sn,
                metrics=[HeatmapMetric(name=mn, display_name=dn) for mn, dn in sd['metrics'].items()],
                cells=sd['cells'],
                summary=summary,
            )
        )

    composite = []
    for xi in range(n):
        run = runs_asc[xi]
        tp = run.total_points
        ap = run.achieved_points
        run_score = round(ap / tp * 100, 2) if tp and ap is not None else 0.0
        all_invalidated = run.slo_evaluations and all(
            se.invalidated for se in run.slo_evaluations
        )
        composite.append(
            HeatmapSummaryCell(
                evaluation_id=run.id,
                period_start=run.period_start,
                result='invalidated' if all_invalidated else (run.result or 'none'),
                score=run_score,
            )
        )

    return GroupedMetricHeatmapResponse(
        asset_name=asset_name,
        columns=columns,
        groups=groups,
        composite=composite,
    )


def build_detail(ev: Any) -> EvaluationDetail:
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
