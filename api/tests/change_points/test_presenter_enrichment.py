"""Unit tests for change point enrichment in the heatmap presenter."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from tropek.modules.change_points.repository import ChangePointKey
from tropek.modules.change_points.schemas import ChangePointMarker
from tropek.modules.quality_gate.workflows.presentation.presenter import (
    _resolve_change_point_marker,
)

PERIOD_START = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
PERIOD_END = datetime(2026, 4, 10, 12, 10, tzinfo=UTC)


def test_change_point_marker_serialization() -> None:
    """ChangePointMarker round-trips through JSON."""
    marker = ChangePointMarker(direction='regression', change_relative_pct=15.2)
    data = marker.model_dump()
    assert data == {'direction': 'regression', 'change_relative_pct': 15.2}
    restored = ChangePointMarker.model_validate(data)
    assert restored == marker


def test_resolve_returns_none_when_no_lookup() -> None:
    result = _resolve_change_point_marker(
        None,
        'latency-slo',
        'response_time',
        PERIOD_START,
        PERIOD_END,
        'load-test',
    )
    assert result is None


def test_resolve_returns_none_when_no_match() -> None:
    lookup: dict = {}
    result = _resolve_change_point_marker(
        lookup,
        'latency-slo',
        'response_time',
        PERIOD_START,
        PERIOD_END,
        'load-test',
    )
    assert result is None


def test_resolve_returns_marker_on_match() -> None:
    change_point = MagicMock()
    change_point.direction = 'regression'
    change_point.change_relative_pct = 25.5
    key = ChangePointKey('latency-slo', 'response_time', PERIOD_START, PERIOD_END, 'load-test')
    lookup = {key: change_point}

    result = _resolve_change_point_marker(
        lookup,
        'latency-slo',
        'response_time',
        PERIOD_START,
        PERIOD_END,
        'load-test',
    )

    assert result is not None
    assert result.direction == 'regression'
    assert result.change_relative_pct == 25.5


def test_resolve_does_not_cross_evaluation_names() -> None:
    """A CP from one evaluation name must not match a different evaluation name."""
    change_point = MagicMock()
    change_point.direction = 'regression'
    change_point.change_relative_pct = 25.5
    key = ChangePointKey('latency-slo', 'response_time', PERIOD_START, PERIOD_END, 'canary')
    lookup = {key: change_point}

    result = _resolve_change_point_marker(
        lookup,
        'latency-slo',
        'response_time',
        PERIOD_START,
        PERIOD_END,
        'load-test',
    )
    assert result is None


def test_resolve_does_not_cross_slo_names() -> None:
    """A CP from one SLO must not match a different SLO."""
    change_point = MagicMock()
    change_point.direction = 'regression'
    change_point.change_relative_pct = 25.5
    key = ChangePointKey('throughput-slo', 'response_time', PERIOD_START, PERIOD_END, 'load-test')
    lookup = {key: change_point}

    result = _resolve_change_point_marker(
        lookup,
        'latency-slo',
        'response_time',
        PERIOD_START,
        PERIOD_END,
        'load-test',
    )
    assert result is None


def test_two_slos_same_metric_different_change_points() -> None:
    """Two SLOs sharing the same metric (cpu-usage) get distinct change points."""
    cp_xyz = MagicMock()
    cp_xyz.direction = 'regression'
    cp_xyz.change_relative_pct = 42.0

    cp_abc = MagicMock()
    cp_abc.direction = 'improvement'
    cp_abc.change_relative_pct = 10.0

    lookup = {
        ChangePointKey('XYZ', 'cpu-usage', PERIOD_START, PERIOD_END, 'daily'): cp_xyz,
        ChangePointKey('ABC', 'cpu-usage', PERIOD_START, PERIOD_END, 'daily'): cp_abc,
    }

    result_xyz = _resolve_change_point_marker(
        lookup,
        'XYZ',
        'cpu-usage',
        PERIOD_START,
        PERIOD_END,
        'daily',
    )
    result_abc = _resolve_change_point_marker(
        lookup,
        'ABC',
        'cpu-usage',
        PERIOD_START,
        PERIOD_END,
        'daily',
    )

    assert result_xyz is not None
    assert result_xyz.direction == 'regression'
    assert result_xyz.change_relative_pct == 42.0

    assert result_abc is not None
    assert result_abc.direction == 'improvement'
    assert result_abc.change_relative_pct == 10.0


def test_two_slos_same_metric_only_one_has_change_point() -> None:
    """SLO XYZ has a CP for cpu-usage but SLO ABC does not — ABC must get None."""
    cp_xyz = MagicMock()
    cp_xyz.direction = 'regression'
    cp_xyz.change_relative_pct = 30.0

    lookup = {
        ChangePointKey('XYZ', 'cpu-usage', PERIOD_START, PERIOD_END, 'daily'): cp_xyz,
    }

    result_xyz = _resolve_change_point_marker(
        lookup,
        'XYZ',
        'cpu-usage',
        PERIOD_START,
        PERIOD_END,
        'daily',
    )
    result_abc = _resolve_change_point_marker(
        lookup,
        'ABC',
        'cpu-usage',
        PERIOD_START,
        PERIOD_END,
        'daily',
    )

    assert result_xyz is not None
    assert result_xyz.change_relative_pct == 30.0
    assert result_abc is None


def test_same_period_start_different_period_end_isolated() -> None:
    """Two evals with same period_start but different period_end are distinct."""
    short_end = datetime(2026, 4, 10, 12, 10, tzinfo=UTC)
    long_end = datetime(2026, 4, 10, 13, 0, tzinfo=UTC)

    cp_short = MagicMock()
    cp_short.direction = 'regression'
    cp_short.change_relative_pct = 15.0

    cp_long = MagicMock()
    cp_long.direction = 'improvement'
    cp_long.change_relative_pct = 5.0

    lookup = {
        ChangePointKey('latency-slo', 'cpu-usage', PERIOD_START, short_end, 'perf-eval'): cp_short,
        ChangePointKey('latency-slo', 'cpu-usage', PERIOD_START, long_end, 'perf-eval'): cp_long,
    }

    result_short = _resolve_change_point_marker(
        lookup,
        'latency-slo',
        'cpu-usage',
        PERIOD_START,
        short_end,
        'perf-eval',
    )
    result_long = _resolve_change_point_marker(
        lookup,
        'latency-slo',
        'cpu-usage',
        PERIOD_START,
        long_end,
        'perf-eval',
    )

    assert result_short is not None
    assert result_short.direction == 'regression'
    assert result_long is not None
    assert result_long.direction == 'improvement'
