"""Unit tests for EvaluationPresenter (build_summary and build_detail)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from tropek.modules.quality_gate.workflows.presentation.presenter import build_detail, build_summary

_NOW = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)


def _make_evaluation(
    *,
    result: str = 'pass',
    score: float = 95.0,
    invalidated: bool = False,
    original_result: str | None = None,
    indicator_rows: list | None = None,
    job_stats: dict | None = None,
    annotations: list | None = None,
) -> SimpleNamespace:
    """Build a fake ORM Evaluation object for presenter tests."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        evaluation_id=uuid.uuid4(),
        evaluation_name='nightly',
        period_start=_NOW,
        period_end=_NOW,
        status='completed',
        result=result,
        score=score,
        invalidated=invalidated,
        original_result=original_result,
        override_reason=None,
        override_author=None,
        invalidation_note=None,
        ingestion_mode='pull',
        asset_snapshot={'name': 'vm-01', 'tags': {}},
        variables={},
        asset_id=uuid.uuid4(),
        slo_name='perf-slo',
        slo_version=1,
        sli_name='system-sli',
        sli_version=1,
        data_source_name='prom-1',
        adapter_used='prometheus',
        baseline_pinned_at=None,
        baseline_unpinned_at=None,
        baseline_pin_reason=None,
        baseline_pin_author=None,
        started_at=_NOW,
        created_at=_NOW,
        updated_at=_NOW,
        indicator_rows=indicator_rows or [],
        job_stats=job_stats or {},
        annotations=annotations or [],
    )


def _make_annotation(
    content: str = 'looks good',
    category: str | None = None,
) -> MagicMock:
    ann = MagicMock()
    ann.id = uuid.uuid4()
    ann.content = content
    ann.author = 'tester'
    ann.category = category
    ann.tags = {}
    ann.hidden_at = None
    ann.hidden_by = None
    ann.hidden_reason = None
    ann.created_at = _NOW
    ann.updated_at = None
    return ann


def test_build_summary_standard_evaluation() -> None:
    ev = _make_evaluation()
    summary = build_summary(ev, annotation_count=0, latest_ann=None)
    assert summary.result == 'pass'
    assert summary.score == 95.0
    assert summary.annotation_count == 0
    assert summary.latest_annotation is None
    assert summary.top_failures == []


def test_build_summary_with_failures() -> None:
    rows = [
        _make_indicator_row(
            sli='response_time',
            display_name='Response Time',
            value=800.0,
            status='fail',
            score=0.0,
            pass_threshold=['<600'],
        ),
        _make_indicator_row(
            sli='cpu_usage',
            display_name='CPU Usage',
            value=45.0,
            status='pass',
            score=1.0,
            pass_threshold=['<80'],
        ),
    ]
    ev = _make_evaluation(result='fail', score=50.0, indicator_rows=rows)
    summary = build_summary(ev, annotation_count=0, latest_ann=None)
    assert len(summary.top_failures) == 1
    assert summary.top_failures[0].metric == 'response_time'
    assert summary.top_failures[0].threshold == '<600'


def test_build_summary_with_annotation_count() -> None:
    ev = _make_evaluation()
    ann = _make_annotation()
    summary = build_summary(ev, annotation_count=3, latest_ann=ann)
    assert summary.annotation_count == 3
    assert summary.latest_annotation is not None


def test_build_summary_original_score_from_job_stats() -> None:
    ev = _make_evaluation(job_stats={'original_score': 75.0})
    summary = build_summary(ev, annotation_count=0, latest_ann=None)
    assert summary.original_score == 75.0


def test_build_detail_standard_evaluation() -> None:
    ev = _make_evaluation()
    detail = build_detail(ev)
    assert detail.result == 'pass'
    assert detail.annotations == []
    assert detail.indicator_results == []
    assert detail.compared_evaluation_ids == []


def test_build_detail_with_annotations() -> None:
    ann1 = _make_annotation('first note')
    ann2 = _make_annotation('second note')
    ev = _make_evaluation(annotations=[ann1, ann2])
    detail = build_detail(ev)
    assert detail.annotation_count == 2
    assert len(detail.annotations) == 2


def test_build_detail_filters_hidden_annotations() -> None:
    visible = _make_annotation('visible')
    hidden = _make_annotation('hidden')
    hidden.hidden_at = _NOW
    ev = _make_evaluation(annotations=[visible, hidden])
    detail = build_detail(ev)
    assert detail.annotation_count == 1
    assert detail.annotations[0].content == 'visible'


def test_build_detail_invalidated_evaluation() -> None:
    ev = _make_evaluation(invalidated=True)
    detail = build_detail(ev)
    assert detail.invalidated is True


def test_build_detail_overridden_evaluation() -> None:
    ev = _make_evaluation(result='pass', original_result='fail')
    detail = build_detail(ev)
    assert detail.result == 'pass'
    assert detail.original_result == 'fail'


def test_build_detail_compared_evaluation_ids() -> None:
    eid1 = str(uuid.uuid4())
    eid2 = str(uuid.uuid4())
    ev = _make_evaluation(job_stats={'compared_evaluation_ids': [eid1, eid2]})
    detail = build_detail(ev)
    assert len(detail.compared_evaluation_ids) == 2
    assert detail.compared_evaluation_ids[0] == uuid.UUID(eid1)


def test_build_detail_empty_indicator_results() -> None:
    ev = _make_evaluation(indicator_rows=[])
    detail = build_detail(ev)
    assert detail.indicator_results == []
    assert detail.top_failures == []


def test_build_summary_no_pass_targets_in_failure() -> None:
    """Failing indicator without pass_threshold -> threshold defaults to empty string."""
    rows = [
        _make_indicator_row(
            sli='cpu',
            display_name='CPU',
            value=99.0,
            compared_value=None,
            change_absolute=None,
            change_relative_pct=None,
            status='fail',
            score=0.0,
            weight=1,
            key_sli=False,
            pass_threshold=[],
            warning_threshold=[],
        ),
    ]
    ev = _make_evaluation(indicator_rows=rows)
    summary = build_summary(ev, annotation_count=0, latest_ann=None)
    assert len(summary.top_failures) == 1
    assert summary.top_failures[0].threshold == ''


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
        original_result='fail',
        result='pass',
    )
    # Set override fields directly — helper doesn't accept these as kwargs
    ev.override_reason = 'Overridden before invalidation'
    ev.override_author = 'alice'
    detail = build_detail(ev)
    assert detail.invalidated is True
    assert detail.original_result == 'fail'
    assert detail.result == 'pass'
    assert detail.override_author == 'alice'


def test_build_detail_annotations_sorted_by_created_at() -> None:
    """Annotations in detail response must be sorted by created_at ascending."""
    ann_old = _make_annotation('First', 'general')
    ann_old.created_at = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
    ann_new = _make_annotation('Second', 'general')
    ann_new.created_at = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)
    ann_mid = _make_annotation('Middle', 'general')
    ann_mid.created_at = datetime(2026, 3, 15, 11, 0, 0, tzinfo=UTC)

    ev = _make_evaluation(annotations=[ann_new, ann_old, ann_mid])
    detail = build_detail(ev)
    assert [a.content for a in detail.annotations] == ['First', 'Middle', 'Second']


def test_build_detail_latest_annotation_is_most_recent() -> None:
    """latest_annotation in detail should be the most recent visible annotation."""
    ann_old = _make_annotation('Old', 'general')
    ann_old.created_at = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
    ann_new = _make_annotation('New', 'general')
    ann_new.created_at = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)

    ev = _make_evaluation(annotations=[ann_old, ann_new])
    detail = build_detail(ev)
    assert detail.latest_annotation is not None
    assert detail.latest_annotation.content == 'New'


def _make_indicator_row(  # noqa: PLR0913
    *,
    sli: str = 'response_time',
    display_name: str = 'Response Time',
    tab_group: str | None = None,
    value: float | None = 580.0,
    compared_value: float | None = 500.0,
    change_absolute: float | None = 80.0,
    change_relative_pct: float | None = 16.0,
    status: str = 'pass',
    score: float = 1.0,
    weight: int = 1,
    key_sli: bool = False,
    pass_threshold: list[str] | None = None,
    warning_threshold: list[str] | None = None,
    targets: dict | None = None,
) -> SimpleNamespace:
    """Build a fake ORM IndicatorResultRow with joined objective."""
    objective = SimpleNamespace(
        sli=sli,
        display_name=display_name,
        tab_group=tab_group,
        weight=weight,
        key_sli=key_sli,
        pass_threshold=['<600'] if pass_threshold is None else pass_threshold,
        warning_threshold=[] if warning_threshold is None else warning_threshold,
    )
    return SimpleNamespace(
        value=value,
        compared_value=compared_value,
        change_absolute=change_absolute,
        change_relative_pct=change_relative_pct,
        status=status,
        score=score,
        objective=objective,
        targets=targets,
    )


def test_build_detail_from_orm_rows() -> None:
    """build_detail works with ORM indicator rows (new path)."""
    row_pass = _make_indicator_row(status='pass', value=580.0)
    row_fail = _make_indicator_row(
        sli='error_rate',
        display_name='Error Rate',
        status='fail',
        value=5.2,
        score=0.0,
        weight=2,
        pass_threshold=['<2'],
    )
    ev = _make_evaluation(indicator_rows=[row_pass, row_fail])
    detail = build_detail(ev)
    assert len(detail.indicator_results) == 2
    assert detail.indicator_results[0].metric == 'response_time'
    assert detail.indicator_results[1].status == 'fail'
    assert len(detail.top_failures) == 1
    assert detail.top_failures[0].metric == 'error_rate'


def test_build_detail_sli_metadata_from_job_stats() -> None:
    """sli_metadata from job_stats appears in the detail response."""
    ev = _make_evaluation(
        job_stats={
            'sli_metadata': {
                'cpu': {
                    'mode': 'aggregated',
                    'expected_samples': 100,
                    'actual_samples': 95,
                    'missing_pct': 5.0,
                    'chunks_failed': 0,
                },
            },
        },
    )
    detail = build_detail(ev)
    assert detail.sli_metadata is not None
    assert detail.sli_metadata['cpu'].expected_samples == 100
    assert detail.sli_metadata['cpu'].mode == 'aggregated'
    assert detail.sli_metadata['cpu'].missing_pct == 5.0


def test_build_detail_sli_metadata_none_when_absent() -> None:
    """sli_metadata is None when job_stats has no sli_metadata key."""
    ev = _make_evaluation()
    detail = build_detail(ev)
    assert detail.sli_metadata is None


def test_build_summary_from_orm_rows() -> None:
    """build_summary works with ORM indicator rows (new path)."""
    row_fail = _make_indicator_row(
        sli='error_rate',
        display_name='Error Rate',
        status='fail',
        value=5.2,
        score=0.0,
        pass_threshold=['<2'],
    )
    ev = _make_evaluation(indicator_rows=[row_fail])
    summary = build_summary(ev, annotation_count=0, latest_ann=None)
    assert len(summary.top_failures) == 1
    assert summary.top_failures[0].threshold == '<2'


def test_build_detail_uses_stored_targets() -> None:
    """When row has stored targets JSONB, presenter uses them instead of resolve_targets."""
    stored = {
        'pass': [
            {'criteria': '>0', 'target_value': 0.0, 'violated': False},
            {'criteria': '<=600', 'target_value': 600.0, 'violated': False},
        ],
        'warn': [
            {'criteria': '<=+15%', 'target_value': 575.0, 'violated': True},
        ],
    }
    row = _make_indicator_row(
        status='pass',
        value=580.0,
        targets=stored,
    )
    ev = _make_evaluation(indicator_rows=[row])
    detail = build_detail(ev)
    ind = detail.indicator_results[0]
    assert ind.pass_targets is not None
    assert [pt.model_dump() for pt in ind.pass_targets] == stored['pass']
    assert ind.warning_targets is not None
    assert [pt.model_dump() for pt in ind.warning_targets] == stored['warn']
