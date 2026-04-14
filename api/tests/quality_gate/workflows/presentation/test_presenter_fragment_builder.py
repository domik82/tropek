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


def test_assemble_grouped_response_merges_fragments_by_slo_name() -> None:
    obj = _objective('latency', ['<600'], ['<800'])
    run1 = _run([_slo_eval('slo-a', [_indicator_row(obj, 500, 400)])])
    run2 = _run([_slo_eval('slo-a', [_indicator_row(obj, 550, 400)])])
    fragment_one = presenter.build_column_fragment(run1, has_notes=False)
    fragment_two = presenter.build_column_fragment(run2, has_notes=True)
    response = presenter.assemble_grouped_response(asset_name='svc', fragments=[fragment_one, fragment_two])
    assert response.asset_name == 'svc'
    assert len(response.columns) == 2
    assert response.columns[0].has_notes is False
    assert response.columns[1].has_notes is True
    assert len(response.groups) == 1
    group = response.groups[0]
    assert group.slo_name == 'slo-a'
    assert len(group.cells) == 2
    assert len(group.summary) == 2
    assert len(response.composite) == 2


def test_assemble_grouped_response_orders_slos_alphabetically() -> None:
    """Stable alphabetical ordering required so cache=true and cache=false
    responses are byte-identical regardless of which run got built first."""
    obj = _objective('latency', ['<600'], ['<800'])
    # run1 has only slo-b (alphabetically later); run2 has slo-a and slo-b.
    # Even though slo-b appears first chronologically, slo-a must come first.
    run1 = _run([_slo_eval('slo-b', [_indicator_row(obj, 500, 400)])])
    run2 = _run(
        [
            _slo_eval('slo-a', [_indicator_row(obj, 500, 400)]),
            _slo_eval('slo-b', [_indicator_row(obj, 500, 400)]),
        ]
    )
    fragment_one = presenter.build_column_fragment(run1, has_notes=False)
    fragment_two = presenter.build_column_fragment(run2, has_notes=False)
    response = presenter.assemble_grouped_response('svc', fragments=[fragment_one, fragment_two])
    assert [g.slo_name for g in response.groups] == ['slo-a', 'slo-b']
    # slo-a only has cells from run2; its summary is padded for run1
    slo_a_group = next(g for g in response.groups if g.slo_name == 'slo-a')
    assert len(slo_a_group.cells) == 1
    assert len(slo_a_group.summary) == 2
    assert slo_a_group.summary[0].result == 'none'
