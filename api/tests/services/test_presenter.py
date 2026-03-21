"""Unit tests for EvaluationPresenter (build_summary and build_detail)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.modules.quality_gate.presenter import build_detail, build_summary

_NOW = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)


def _make_evaluation(
    *,
    result: str = "pass",
    score: float = 95.0,
    invalidated: bool = False,
    original_result: str | None = None,
    indicator_results: list[dict] | None = None,
    job_stats: dict | None = None,
    annotations: list | None = None,
) -> SimpleNamespace:
    """Build a fake ORM Evaluation object for presenter tests."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        evaluation_name="nightly",
        period_start=_NOW,
        period_end=_NOW,
        status="completed",
        result=result,
        score=score,
        invalidated=invalidated,
        original_result=original_result,
        override_reason=None,
        override_author=None,
        invalidation_note=None,
        ingestion_mode="pull",
        asset_snapshot={"name": "vm-01", "tags": {}},
        variables={},
        asset_id=uuid.uuid4(),
        slo_name="perf-slo",
        slo_version=1,
        sli_name="system-sli",
        sli_version=1,
        data_source_name="prom-1",
        adapter_used="prometheus",
        baseline_pinned_at=None,
        baseline_unpinned_at=None,
        baseline_pin_reason=None,
        baseline_pin_author=None,
        started_at=_NOW,
        created_at=_NOW,
        updated_at=_NOW,
        indicator_results=indicator_results or [],
        job_stats=job_stats or {},
        annotations=annotations or [],
    )


def _make_annotation(
    content: str = "looks good",
    category: str | None = None,
) -> MagicMock:
    ann = MagicMock()
    ann.id = uuid.uuid4()
    ann.content = content
    ann.author = "tester"
    ann.category = category
    ann.meta = {}
    ann.hidden_at = None
    ann.hidden_by = None
    ann.hidden_reason = None
    ann.created_at = _NOW
    ann.updated_at = None
    return ann


def test_build_summary_standard_evaluation() -> None:
    ev = _make_evaluation()
    summary = build_summary(ev, annotation_count=0, latest_ann=None)
    assert summary.result == "pass"
    assert summary.score == 95.0
    assert summary.annotation_count == 0
    assert summary.latest_annotation is None
    assert summary.top_failures == []


def test_build_summary_with_failures() -> None:
    indicators = [
        {
            "metric": "response_time",
            "display_name": "Response Time",
            "value": 800.0,
            "status": "fail",
            "score": 0.0,
            "pass_targets": [{"criteria": "<600"}],
        },
        {
            "metric": "cpu_usage",
            "display_name": "CPU Usage",
            "value": 45.0,
            "status": "pass",
            "score": 1.0,
            "pass_targets": [{"criteria": "<80"}],
        },
    ]
    ev = _make_evaluation(result="fail", score=50.0, indicator_results=indicators)
    summary = build_summary(ev, annotation_count=0, latest_ann=None)
    assert len(summary.top_failures) == 1
    assert summary.top_failures[0].metric == "response_time"
    assert summary.top_failures[0].threshold == "<600"


def test_build_summary_with_annotation_count() -> None:
    ev = _make_evaluation()
    ann = _make_annotation()
    summary = build_summary(ev, annotation_count=3, latest_ann=ann)
    assert summary.annotation_count == 3
    assert summary.latest_annotation is not None


def test_build_summary_original_score_from_job_stats() -> None:
    ev = _make_evaluation(job_stats={"original_score": 75.0})
    summary = build_summary(ev, annotation_count=0, latest_ann=None)
    assert summary.original_score == 75.0


def test_build_detail_standard_evaluation() -> None:
    ev = _make_evaluation()
    detail = build_detail(ev)
    assert detail.result == "pass"
    assert detail.annotations == []
    assert detail.indicator_results == []
    assert detail.compared_evaluation_ids == []


def test_build_detail_with_annotations() -> None:
    ann1 = _make_annotation("first note")
    ann2 = _make_annotation("second note")
    ev = _make_evaluation(annotations=[ann1, ann2])
    detail = build_detail(ev)
    assert detail.annotation_count == 2
    assert len(detail.annotations) == 2


def test_build_detail_filters_hidden_annotations() -> None:
    visible = _make_annotation("visible")
    hidden = _make_annotation("hidden")
    hidden.hidden_at = _NOW
    ev = _make_evaluation(annotations=[visible, hidden])
    detail = build_detail(ev)
    assert detail.annotation_count == 1
    assert detail.annotations[0].content == "visible"


def test_build_detail_invalidated_evaluation() -> None:
    ev = _make_evaluation(invalidated=True)
    detail = build_detail(ev)
    assert detail.invalidated is True


def test_build_detail_overridden_evaluation() -> None:
    ev = _make_evaluation(result="pass", original_result="fail")
    detail = build_detail(ev)
    assert detail.result == "pass"
    assert detail.original_result == "fail"


def test_build_detail_compared_evaluation_ids() -> None:
    eid1 = str(uuid.uuid4())
    eid2 = str(uuid.uuid4())
    ev = _make_evaluation(job_stats={"compared_evaluation_ids": [eid1, eid2]})
    detail = build_detail(ev)
    assert len(detail.compared_evaluation_ids) == 2
    assert detail.compared_evaluation_ids[0] == uuid.UUID(eid1)


def test_build_detail_empty_indicator_results() -> None:
    ev = _make_evaluation(indicator_results=[])
    detail = build_detail(ev)
    assert detail.indicator_results == []
    assert detail.top_failures == []


def test_build_summary_no_pass_targets_in_failure() -> None:
    """Failing indicator without pass_targets -> threshold defaults to empty string."""
    ev = _make_evaluation(
        indicator_results=[
            {
                "metric": "cpu",
                "display_name": "CPU",
                "value": 99.0,
                "compared_value": None,
                "change_absolute": None,
                "change_relative_pct": None,
                "status": "fail",
                "score": 0.0,
                "weight": 1,
                "key_sli": False,
                "pass_targets": None,
                "warning_targets": None,
            },
        ]
    )
    summary = build_summary(ev, annotation_count=0, latest_ann=None)
    assert len(summary.top_failures) == 1
    assert summary.top_failures[0].threshold == ""


def test_build_detail_null_job_stats() -> None:
    """When job_stats is None, original_score is None and compared_evaluation_ids is empty."""
    ev = _make_evaluation()
    ev.job_stats = None  # bypass helper normalization to test true None path
    detail = build_detail(ev)
    assert detail.original_score is None
    assert detail.compared_evaluation_ids == []


def test_build_detail_combined_invalidated_and_overridden() -> None:
    """Both invalidated and override fields can coexist."""
    ev = _make_evaluation(
        invalidated=True,
        original_result="fail",
        result="pass",
    )
    # Set override fields directly — helper doesn't accept these as kwargs
    ev.override_reason = "Overridden before invalidation"
    ev.override_author = "alice"
    detail = build_detail(ev)
    assert detail.invalidated is True
    assert detail.original_result == "fail"
    assert detail.result == "pass"
    assert detail.override_author == "alice"


def test_build_detail_annotations_sorted_by_created_at() -> None:
    """Annotations in detail response must be sorted by created_at ascending."""
    ann_old = _make_annotation("First", "general")
    ann_old.created_at = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
    ann_new = _make_annotation("Second", "general")
    ann_new.created_at = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)
    ann_mid = _make_annotation("Middle", "general")
    ann_mid.created_at = datetime(2026, 3, 15, 11, 0, 0, tzinfo=UTC)

    ev = _make_evaluation(annotations=[ann_new, ann_old, ann_mid])
    detail = build_detail(ev)
    assert [a.content for a in detail.annotations] == ["First", "Middle", "Second"]


def test_build_detail_latest_annotation_is_most_recent() -> None:
    """latest_annotation in detail should be the most recent visible annotation."""
    ann_old = _make_annotation("Old", "general")
    ann_old.created_at = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
    ann_new = _make_annotation("New", "general")
    ann_new.created_at = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)

    ev = _make_evaluation(annotations=[ann_old, ann_new])
    detail = build_detail(ev)
    assert detail.latest_annotation is not None
    assert detail.latest_annotation.content == "New"
