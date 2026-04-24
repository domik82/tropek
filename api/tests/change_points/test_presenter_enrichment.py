"""Unit tests for change point enrichment in the heatmap presenter."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from tropek.modules.change_points.schemas import ChangePointMarker
from tropek.modules.quality_gate.workflows.presentation.presenter import (
    _resolve_change_point_marker,
)


def test_change_point_marker_serialization() -> None:
    """ChangePointMarker round-trips through JSON."""
    marker = ChangePointMarker(direction="regression", change_relative_pct=15.2)
    data = marker.model_dump()
    assert data == {"direction": "regression", "change_relative_pct": 15.2}
    restored = ChangePointMarker.model_validate(data)
    assert restored == marker


def test_resolve_returns_none_when_no_lookup() -> None:
    timestamp = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    result = _resolve_change_point_marker(None, "response_time", timestamp)
    assert result is None


def test_resolve_returns_none_when_no_match() -> None:
    timestamp = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    lookup: dict = {}
    result = _resolve_change_point_marker(lookup, "response_time", timestamp)
    assert result is None


def test_resolve_returns_marker_on_match() -> None:
    timestamp = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    change_point = MagicMock()
    change_point.direction = "regression"
    change_point.change_relative_pct = 25.5
    lookup = {("response_time", timestamp): change_point}

    result = _resolve_change_point_marker(lookup, "response_time", timestamp)

    assert result is not None
    assert result.direction == "regression"
    assert result.change_relative_pct == 25.5
