"""Unit tests for build_column_fragment — single-run fragment construction
with per-objective parse-once criteria caching."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from tropek.modules.quality_gate.workflows.presentation import presenter


def _objective(sli: str, pass_: list[str], warn: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        sli=sli,
        display_name=sli,
        weight=1,
        key_sli=False,
        pass_threshold=pass_,
        warning_threshold=warn,
        tab_group=None,
    )


def _indicator_row(
    obj: SimpleNamespace,
    value: float,
    compared: float,
    status: str = 'pass',
) -> SimpleNamespace:
    return SimpleNamespace(
        objective=obj,
        status=status,
        score=100.0 if status == 'pass' else 60.0,
        value=value,
        compared_value=compared,
        change_relative_pct=((value - compared) / compared) * 100,
    )


def _slo_eval(slo_name: str, rows: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        slo_name=slo_name,
        slo_version=1,
        sli_version=1,
        result='pass',
        invalidated=False,
        invalidation_note=None,
        indicator_rows=rows,
        achieved_points=len(rows),
        total_points=len(rows),
        score=100.0,
        job_stats={'sli_metadata': {}},
    )


def _run(slo_evals: list[SimpleNamespace]) -> SimpleNamespace:
    total_points = sum(len(slo_eval.indicator_rows) for slo_eval in slo_evals)
    return SimpleNamespace(
        id=uuid.uuid4(),
        period_start=datetime(2026, 4, 1, tzinfo=UTC),
        period_end=datetime(2026, 4, 1, 0, 15, tzinfo=UTC),
        eval_name='daily',
        result='pass',
        achieved_points=total_points,
        total_points=total_points,
        slo_evaluations=slo_evals,
    )


def test_build_column_fragment_returns_one_fragment_per_run() -> None:
    objective = _objective('latency', ['<600'], ['<800'])
    run = _run([_slo_eval('slo-a', [_indicator_row(objective, 500, 400)])])
    fragment = presenter.build_column_fragment(run, has_notes=False)
    assert fragment.evaluation_run_id == run.id
    assert fragment.schema_version == 1
    assert len(fragment.per_slo) == 1
    assert fragment.per_slo[0].slo_name == 'slo-a'
    assert len(fragment.per_slo[0].cells) == 1
    cell = fragment.per_slo[0].cells[0]
    assert cell.pass_targets is not None
    assert cell.pass_targets[0].criteria == '<600'


def test_build_column_fragment_parses_each_criteria_once() -> None:
    """Parse cache: a run with 6 cells under one objective should parse the
    objective's two criteria strings exactly twice (once each), not twelve."""
    objective = _objective('latency', ['<600'], ['<800'])
    rows = [_indicator_row(objective, 400 + i * 50, 400) for i in range(6)]
    run = _run([_slo_eval('slo-a', rows)])

    parse_call_count = {'count': 0}
    original_parse = presenter.parse_criteria_string

    def counting_parse(raw: str) -> object:
        parse_call_count['count'] += 1
        return original_parse(raw)

    with patch.object(presenter, 'parse_criteria_string', side_effect=counting_parse):
        presenter.build_column_fragment(run, has_notes=False)

    assert parse_call_count['count'] == 2, (
        f'expected 2 parses (one per unique criteria string), '
        f'got {parse_call_count["count"]} — parse-once cache is not working'
    )


def test_build_column_fragment_invalidated_slo_collapses_result_to_invalidated() -> None:
    objective = _objective('latency', ['<600'], ['<800'])
    slo_eval = _slo_eval('slo-a', [_indicator_row(objective, 500, 400)])
    slo_eval.invalidated = True
    slo_eval.invalidation_note = 'bad data'
    run = _run([slo_eval])
    fragment = presenter.build_column_fragment(run, has_notes=False)
    assert fragment.per_slo[0].cells[0].result == 'invalidated'


def test_build_column_fragment_preserves_slo_and_sli_versions() -> None:
    """Regression guard: HeatmapSummaryCell.slo_version and sli_version must be
    populated by the fragment builder, or the cached path returns null for both
    and silently regresses the SLI breakdown UI."""
    objective = _objective('latency', ['<600'], ['<800'])
    slo_eval = _slo_eval('slo-a', [_indicator_row(objective, 500, 400)])
    slo_eval.slo_version = 3
    slo_eval.sli_version = 2
    run = _run([slo_eval])
    fragment = presenter.build_column_fragment(run, has_notes=False)
    summary = fragment.per_slo[0].summary
    assert summary.slo_version == 3
    assert summary.sli_version == 2


def test_build_column_fragment_criteria_scoped_per_row_not_hoisted() -> None:
    """Two rows under the same SLO with DIFFERENT objectives (simulating an
    SLO-version edit mid-window) must each carry their own criteria. No hoisting."""
    objective_v1 = _objective('latency', ['<600'], ['<800'])
    objective_v2 = _objective('latency', ['<500'], ['<700'])
    run = _run(
        [
            _slo_eval(
                'slo-a',
                [
                    _indicator_row(objective_v1, 550, 500),
                    _indicator_row(objective_v2, 550, 500),
                ],
            )
        ]
    )
    fragment = presenter.build_column_fragment(run, has_notes=False)
    cells = fragment.per_slo[0].cells
    assert cells[0].pass_targets is not None
    assert cells[0].pass_targets[0].criteria == '<600'
    assert cells[1].pass_targets is not None
    assert cells[1].pass_targets[0].criteria == '<500'
