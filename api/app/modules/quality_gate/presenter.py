"""Evaluation presenter — transform ORM models into API response schemas."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.quality_gate.schemas import (
    AnnotationRead,
    EvaluationDetail,
    EvaluationSummary,
    FailingIndicator,
    IndicatorResult,
)
from app.modules.quality_gate.target_resolver import resolve_targets


def _indicators_from_orm_rows(rows: list) -> list[IndicatorResult]:  # type: ignore[type-arg]
    """Build IndicatorResult schema objects from ORM IndicatorResultRow with joined objectives."""
    results: list[IndicatorResult] = []
    for row in rows:
        obj = row.objective
        results.append(
            IndicatorResult(
                metric=obj.sli,
                display_name=obj.display_name,
                tab_group=getattr(obj, "tab_group", None),
                value=row.value,
                compared_value=row.compared_value,
                change_absolute=row.change_absolute,
                change_relative_pct=row.change_relative_pct,
                aggregation=None,
                status=row.status,
                score=row.score,
                weight=obj.weight,
                key_sli=obj.key_sli,
                pass_targets=resolve_targets(
                    list(obj.pass_criteria) if obj.pass_criteria else None,
                    value=row.value,
                    compared_value=row.compared_value,
                ),
                warning_targets=resolve_targets(
                    list(obj.warning_criteria) if obj.warning_criteria else None,
                    value=row.value,
                    compared_value=row.compared_value,
                ),
            )
        )
    return results


def _indicators_from_jsonb(dicts: list[dict[str, Any]]) -> list[IndicatorResult]:
    """Build IndicatorResult schema objects from JSONB dicts (legacy path)."""
    return [IndicatorResult(**ir) for ir in dicts]


def _get_indicator_results(ev: object) -> list[IndicatorResult]:
    """Get indicator results from either ORM rows (new) or JSONB dicts (legacy)."""
    orm_rows = getattr(ev, "indicator_rows", None)
    if orm_rows:
        return _indicators_from_orm_rows(orm_rows)
    jsonb = getattr(ev, "indicator_results", []) or []
    if jsonb:
        return _indicators_from_jsonb(jsonb)
    return []


def _top_failures(indicators: list[IndicatorResult]) -> list[FailingIndicator]:
    """Extract failing indicators into top_failures list."""
    return [
        FailingIndicator(
            metric=ind.metric,
            display_name=ind.display_name,
            value=ind.value,
            threshold=(ind.pass_targets or [{}])[0].get("criteria", ""),
        )
        for ind in indicators
        if ind.status == "fail"
    ]


def build_summary(
    ev: object, annotation_count: int, latest_ann: object | None
) -> EvaluationSummary:
    """Transform ORM Evaluation into API summary schema."""
    indicators = _get_indicator_results(ev)
    job_stats = getattr(ev, "job_stats", None) or {}
    return EvaluationSummary.model_validate(
        {
            **ev.__dict__,
            "original_score": job_stats.get("original_score"),
            "annotation_count": annotation_count,
            "latest_annotation": latest_ann,
            "top_failures": _top_failures(indicators),
        }
    )


def build_detail(ev: Any) -> EvaluationDetail:
    """Transform ORM Evaluation with annotations into API detail schema."""
    annotations = [
        AnnotationRead.model_validate(a) for a in (ev.annotations or []) if a.hidden_at is None
    ]
    indicators = _get_indicator_results(ev)
    job_stats_detail = ev.job_stats or {}
    compared_ids = job_stats_detail.get("compared_evaluation_ids", [])
    sorted_annotations = sorted(annotations, key=lambda a: a.created_at)
    return EvaluationDetail.model_validate(
        {
            **ev.__dict__,
            "original_score": job_stats_detail.get("original_score"),
            "annotation_count": len(annotations),
            "latest_annotation": sorted_annotations[-1] if sorted_annotations else None,
            "top_failures": _top_failures(indicators),
            "compared_evaluation_ids": [uuid.UUID(eid) for eid in compared_ids],
            "annotations": sorted_annotations,
            "indicator_results": indicators,
        }
    )
