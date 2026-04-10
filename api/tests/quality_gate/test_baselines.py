"""Tests for baseline aggregation logic in worker._resolve_baselines.

These tests exercise the inline baseline aggregation algorithm before it is
extracted into evaluation_helpers.compute_baselines (Task 7).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

from app.modules.quality_gate.worker import _resolve_baselines


def _make_slo(*, num_comparisons: int = 1, aggregate_function: str = 'avg') -> MagicMock:
    slo = MagicMock()
    slo.comparison.number_of_comparison_results = num_comparisons
    slo.comparison.include_result_with_score.value = 'pass'
    slo.comparison.aggregate_function = aggregate_function
    return slo


def _make_ev(asset_id: uuid.UUID | None = None, slo_name: str = 'perf-slo') -> MagicMock:
    ev = MagicMock()
    ev.asset_id = asset_id or uuid.uuid4()
    ev.slo_name = slo_name
    ev.period_start = '2026-03-15T10:00:00'
    return ev


def _make_baseline_eval(
    eval_id: str,
    indicators: list[tuple[str, float | None]],
) -> MagicMock:
    ev = MagicMock()
    ev.id = eval_id
    rows = []
    for sli, value in indicators:
        row = MagicMock()
        row.objective = MagicMock()
        row.objective.sli = sli
        row.value = value
        rows.append(row)
    ev.indicator_rows = rows
    return ev


async def test_resolve_baselines_no_comparisons() -> None:
    """Returns empty when number_of_comparison_results <= 0."""
    slo = _make_slo(num_comparisons=0)
    ev = _make_ev()
    baseline_repo = AsyncMock()

    baselines, ids = await _resolve_baselines(baseline_repo, slo, ev, ['rt'])

    assert baselines == {}
    assert ids == []
    baseline_repo.get_evaluation_baselines.assert_not_awaited()


async def test_resolve_baselines_aggregates_per_metric() -> None:
    """Collects values from baseline evals and aggregates with avg."""
    slo = _make_slo(num_comparisons=2, aggregate_function='avg')
    ev = _make_ev()

    baseline_repo = AsyncMock()
    baseline_repo.get_evaluation_baselines.return_value = [
        _make_baseline_eval('ev1', [('rt', 100.0), ('err', 0.5)]),
        _make_baseline_eval('ev2', [('rt', 200.0), ('err', 0.3)]),
    ]

    baselines, ids = await _resolve_baselines(
        baseline_repo, slo, ev, ['rt', 'err'],
    )

    assert ids == ['ev1', 'ev2']
    assert baselines['rt'] == 150.0
    assert baselines['err'] == 0.4


async def test_resolve_baselines_skips_none_values() -> None:
    """None indicator values are excluded from aggregation."""
    slo = _make_slo(num_comparisons=1)
    ev = _make_ev()

    baseline_repo = AsyncMock()
    baseline_repo.get_evaluation_baselines.return_value = [
        _make_baseline_eval('ev1', [('rt', 100.0), ('err', None)]),
    ]

    baselines, ids = await _resolve_baselines(
        baseline_repo, slo, ev, ['rt', 'err'],
    )

    assert baselines['rt'] == 100.0
    assert 'err' not in baselines


async def test_resolve_baselines_returns_compared_ids() -> None:
    """compared_eval_ids list matches baseline eval IDs."""
    slo = _make_slo(num_comparisons=3)
    ev = _make_ev()

    baseline_repo = AsyncMock()
    baseline_repo.get_evaluation_baselines.return_value = [
        _make_baseline_eval('aaa', [('rt', 50.0)]),
        _make_baseline_eval('bbb', [('rt', 60.0)]),
    ]

    _, ids = await _resolve_baselines(
        baseline_repo, slo, ev, ['rt'],
    )

    assert ids == ['aaa', 'bbb']
