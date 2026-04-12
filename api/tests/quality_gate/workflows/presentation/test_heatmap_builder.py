"""Unit tests for build_grouped_heatmap_response enriched fields."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from tropek.modules.quality_gate.workflows.presentation.presenter import build_grouped_heatmap_response


def _make_objective(
    *,
    sli: str = 'cpu_usage',
    display_name: str = 'CPU Usage',
    weight: int = 2,
    key_sli: bool = True,
    pass_threshold: list[str] | None = None,
    warning_threshold: list[str] | None = None,
    tab_group: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        sli=sli,
        display_name=display_name,
        weight=weight,
        key_sli=key_sli,
        pass_threshold=pass_threshold or ['<90'],
        warning_threshold=warning_threshold or ['<95'],
        tab_group=tab_group,
    )


def _make_indicator_row(
    *,
    objective: SimpleNamespace | None = None,
    value: float | None = 85.0,
    compared_value: float | None = 80.0,
    change_relative_pct: float | None = 6.25,
    status: str = 'pass',
    score: float = 2.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        objective=objective or _make_objective(),
        value=value,
        compared_value=compared_value,
        change_relative_pct=change_relative_pct,
        status=status,
        score=score,
    )


def _make_slo_eval(  # noqa: PLR0913 - test factory intentionally exposes many kwargs
    *,
    slo_name: str = 'latency-slo',
    run_id: uuid.UUID | None = None,
    invalidated: bool = False,
    invalidation_note: str | None = None,
    result: str = 'pass',
    achieved_points: int = 8,
    total_points: int = 10,
    job_stats: dict | None = None,
    indicator_rows: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        evaluation_id=run_id or uuid.uuid4(),
        slo_name=slo_name,
        invalidated=invalidated,
        invalidation_note=invalidation_note,
        result=result,
        achieved_points=achieved_points,
        total_points=total_points,
        job_stats=job_stats or {},
        indicator_rows=indicator_rows or [_make_indicator_row()],
    )


def _make_run(
    *,
    period_start: datetime | None = None,
    slo_evaluations: list | None = None,
    result: str = 'pass',
    achieved_points: int = 8,
    total_points: int = 10,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        period_start=period_start or datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
        period_end=(period_start or datetime(2026, 4, 1, 10, 0, tzinfo=UTC)),
        eval_name='daily',
        slo_evaluations=slo_evaluations,
        result=result,
        achieved_points=achieved_points,
        total_points=total_points,
    )


def test_cell_carries_indicator_detail() -> None:
    """HeatmapCellGrouped includes value, weight, targets from indicator row + objective."""
    obj = _make_objective(
        sli='resp_time',
        display_name='Response Time',
        weight=3,
        key_sli=True,
        pass_threshold=['<600'],
        warning_threshold=['<800'],
        tab_group='latency',
    )
    row = _make_indicator_row(
        objective=obj,
        value=550.0,
        compared_value=500.0,
        change_relative_pct=10.0,
        status='pass',
        score=3.0,
    )
    slo_eval = _make_slo_eval(indicator_rows=[row])
    run = _make_run(slo_evaluations=[slo_eval])

    resp = build_grouped_heatmap_response('test-asset', [run])

    assert len(resp.groups) == 1
    cell = resp.groups[0].cells[0]
    assert cell.value == 550.0
    assert cell.compared_value == 500.0
    assert cell.change_relative_pct == 10.0
    assert cell.weight == 3
    assert cell.key_sli is True
    assert cell.pass_targets is not None
    assert len(cell.pass_targets) == 1
    assert cell.pass_targets[0].criteria == '<600'
    assert cell.warning_targets is not None
    assert len(cell.warning_targets) == 1
    assert cell.warning_targets[0].criteria == '<800'
    assert cell.tab_group == 'latency'


def test_cell_aggregation_from_job_stats() -> None:
    """Aggregation mode is extracted from sli_metadata in job_stats."""
    obj = _make_objective(sli='cpu_usage')
    row = _make_indicator_row(objective=obj)
    slo_eval = _make_slo_eval(
        indicator_rows=[row],
        job_stats={
            'sli_metadata': {
                'cpu_usage': {
                    'mode': 'aggregated',
                    'expected_samples': 100,
                    'actual_samples': 100,
                    'missing_pct': 0.0,
                    'chunks_failed': 0,
                },
            },
        },
    )
    run = _make_run(slo_evaluations=[slo_eval])

    resp = build_grouped_heatmap_response('test-asset', [run])

    assert resp.groups[0].cells[0].aggregation == 'aggregated'


def test_cell_aggregation_none_when_no_metadata() -> None:
    """Aggregation is None when job_stats has no sli_metadata."""
    slo_eval = _make_slo_eval(job_stats={})
    run = _make_run(slo_evaluations=[slo_eval])

    resp = build_grouped_heatmap_response('test-asset', [run])

    assert resp.groups[0].cells[0].aggregation is None


def test_summary_carries_thresholds_and_metadata() -> None:
    """HeatmapSummaryCell includes pass/warning thresholds, sli_metadata, invalidation."""
    slo_eval = _make_slo_eval(
        job_stats={
            'total_score_pass_threshold': 90.0,
            'total_score_warning_threshold': 75.0,
            'sli_metadata': {
                'cpu_usage': {
                    'mode': 'aggregated',
                    'expected_samples': 100,
                    'actual_samples': 100,
                    'missing_pct': 0.0,
                    'chunks_failed': 0,
                },
            },
        },
    )
    run = _make_run(slo_evaluations=[slo_eval])

    resp = build_grouped_heatmap_response('test-asset', [run])

    summary = resp.groups[0].summary[0]
    assert summary.total_score_pass_threshold == 90.0
    assert summary.total_score_warning_threshold == 75.0
    assert summary.sli_metadata is not None
    assert summary.sli_metadata['cpu_usage'].mode == 'aggregated'
    assert summary.sli_metadata['cpu_usage'].expected_samples == 100
    assert summary.invalidated is False
    assert summary.invalidation_note is None


def test_summary_invalidated_flag() -> None:
    """Invalidated SLO evaluation propagates to summary cell."""
    slo_eval = _make_slo_eval(
        invalidated=True,
        invalidation_note='bad data',
    )
    run = _make_run(slo_evaluations=[slo_eval])

    resp = build_grouped_heatmap_response('test-asset', [run])

    summary = resp.groups[0].summary[0]
    assert summary.invalidated is True
    assert summary.invalidation_note == 'bad data'


def test_composite_row_defaults() -> None:
    """Composite row HeatmapSummaryCell uses defaults for new fields."""
    slo_eval = _make_slo_eval()
    run = _make_run(slo_evaluations=[slo_eval])

    resp = build_grouped_heatmap_response('test-asset', [run])

    composite = resp.composite[0]
    assert composite.total_score_pass_threshold is None
    assert composite.sli_metadata is None
    assert composite.invalidated is False


def test_has_notes_marks_columns_present_in_noted_set() -> None:
    """Columns whose run id is in noted_run_ids get has_notes=True; others False."""
    run_a = _make_run(
        period_start=datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
        slo_evaluations=[_make_slo_eval()],
    )
    run_b = _make_run(
        period_start=datetime(2026, 4, 1, 11, 0, tzinfo=UTC),
        slo_evaluations=[_make_slo_eval()],
    )
    run_c = _make_run(
        period_start=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
        slo_evaluations=[_make_slo_eval()],
    )

    resp = build_grouped_heatmap_response('test-asset', [run_a, run_b, run_c], noted_run_ids={run_a.id, run_c.id})

    by_id = {col.evaluation_id: col for col in resp.columns}
    assert by_id[run_a.id].has_notes is True
    assert by_id[run_b.id].has_notes is False
    assert by_id[run_c.id].has_notes is True


def test_has_notes_defaults_to_false_when_noted_run_ids_omitted() -> None:
    """When noted_run_ids is not provided, every column has has_notes=False."""
    run = _make_run(slo_evaluations=[_make_slo_eval()])

    resp = build_grouped_heatmap_response('test-asset', [run])

    assert all(col.has_notes is False for col in resp.columns)
