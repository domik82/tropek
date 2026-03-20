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


def build_summary(
    ev: object, annotation_count: int, latest_ann: object | None
) -> EvaluationSummary:
    """Transform ORM Evaluation into API summary schema."""
    indicator_results: list[dict[str, Any]] = getattr(ev, "indicator_results", []) or []
    top_failures = [
        FailingIndicator(
            metric=ind["metric"],
            display_name=ind.get("display_name", ind["metric"]),
            value=ind["value"],
            threshold=(ind.get("pass_targets") or [{}])[0].get("criteria", ""),
        )
        for ind in indicator_results
        if ind.get("status") == "fail"
    ]
    job_stats = getattr(ev, "job_stats", None) or {}
    return EvaluationSummary.model_validate(
        {
            **ev.__dict__,
            "original_score": job_stats.get("original_score"),
            "annotation_count": annotation_count,
            "latest_annotation": latest_ann,
            "top_failures": top_failures,
        }
    )


def build_detail(ev: Any) -> EvaluationDetail:
    """Transform ORM Evaluation with annotations into API detail schema."""
    annotations = [
        AnnotationRead.model_validate(a) for a in (ev.annotations or []) if a.hidden_at is None
    ]
    indicator_results = [IndicatorResult(**ir) for ir in (ev.indicator_results or [])]
    job_stats_detail = ev.job_stats or {}
    compared_ids = job_stats_detail.get("compared_evaluation_ids", [])
    top_failures = [
        FailingIndicator(
            metric=ind.metric,
            display_name=ind.display_name,
            value=ind.value,
            threshold=(ind.pass_targets or [{}])[0].get("criteria", ""),
        )
        for ind in indicator_results
        if ind.status == "fail"
    ]
    sorted_annotations = sorted(annotations, key=lambda a: a.created_at)
    return EvaluationDetail.model_validate(
        {
            **ev.__dict__,
            "original_score": job_stats_detail.get("original_score"),
            "annotation_count": len(annotations),
            "latest_annotation": sorted_annotations[-1] if sorted_annotations else None,
            "top_failures": top_failures,
            "compared_evaluation_ids": [uuid.UUID(eid) for eid in compared_ids],
            "annotations": sorted_annotations,
            "indicator_results": indicator_results,
        }
    )
