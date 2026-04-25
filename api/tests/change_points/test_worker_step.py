"""Unit tests for the change point worker step orchestration logic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tropek.modules.change_points.repository import ResolvedConfig
from tropek.modules.change_points.worker_step import _same_regime, run_change_point_detection


def _make_snapshot() -> MagicMock:
    snap = MagicMock()
    snap.eval_id = uuid.uuid4()
    snap.asset_id = uuid.uuid4()
    snap.slo_name = "perf-slo"
    snap.period_start = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    snap.period_end = datetime(2026, 4, 10, 12, 30, tzinfo=UTC)
    snap.slo_version = 3
    return snap


def _make_slo_def() -> MagicMock:
    objective = MagicMock()
    objective.sli = "response_time_p95"
    objective.display_name = "Response Time P95"
    objective.pass_threshold = ["<600"]
    objective.warning_threshold = ["<1000"]

    slo = MagicMock()
    slo.objectives = [objective]
    slo.comparable_from_version = 1
    return slo


def _default_config(*, enabled: bool = True) -> ResolvedConfig:
    return ResolvedConfig(
        enabled=enabled,
        window_size=30,
        max_pvalue=0.001,
        min_magnitude=0.0,
        min_sample_size=10,
    )


class TestWorkerStep:
    """Tests for the fault-isolated worker step."""

    @pytest.fixture()
    def snapshot(self) -> MagicMock:
        return _make_snapshot()

    @pytest.fixture()
    def slo_def(self) -> MagicMock:
        return _make_slo_def()

    async def test_resolves_configs_even_with_no_indicator_rows(
        self, snapshot: MagicMock, slo_def: MagicMock
    ) -> None:
        """No indicator rows → resolver is still called, nothing inserted."""
        session = AsyncMock()

        with patch(
            "tropek.modules.change_points.worker_step.ChangePointRepository"
        ) as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.resolve_configs_for_metrics = AsyncMock(
                return_value={"response_time_p95": _default_config()}
            )

            await run_change_point_detection(
                session=session,
                snapshot=snapshot,
                slo_def=slo_def,
                indicator_rows=[],
            )

            mock_repo.resolve_configs_for_metrics.assert_called_once()

    async def test_skips_disabled_metric(
        self, snapshot: MagicMock, slo_def: MagicMock
    ) -> None:
        """Override row with enabled=False → skip that metric entirely."""
        session = AsyncMock()

        with patch(
            "tropek.modules.change_points.worker_step.ChangePointRepository"
        ) as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.resolve_configs_for_metrics = AsyncMock(
                return_value={"response_time_p95": _default_config(enabled=False)}
            )
            mock_repo.has_nearby_change_point = AsyncMock()

            await run_change_point_detection(
                session=session,
                snapshot=snapshot,
                slo_def=slo_def,
                indicator_rows=[],
            )

            mock_repo.has_nearby_change_point.assert_not_called()

    async def test_skips_metric_without_indicator_row(
        self, snapshot: MagicMock, slo_def: MagicMock
    ) -> None:
        """If the metric has no matching indicator row, skip detection."""
        session = AsyncMock()
        indicator_row = MagicMock()
        indicator_row.objective = MagicMock()
        indicator_row.objective.sli = "different_metric"
        indicator_row.id = uuid.uuid4()

        with (
            patch(
                "tropek.modules.change_points.worker_step.ChangePointRepository"
            ) as mock_repo_cls,
            patch(
                "tropek.modules.change_points.worker_step.BaselineRepository"
            ),
        ):
            mock_repo = mock_repo_cls.return_value
            mock_repo.resolve_configs_for_metrics = AsyncMock(
                return_value={"response_time_p95": _default_config()}
            )
            mock_repo.has_nearby_change_point = AsyncMock()

            await run_change_point_detection(
                session=session,
                snapshot=snapshot,
                slo_def=slo_def,
                indicator_rows=[indicator_row],
            )

            mock_repo.has_nearby_change_point.assert_not_called()

    async def test_skips_when_insufficient_history(
        self, snapshot: MagicMock, slo_def: MagicMock
    ) -> None:
        """History shorter than min_sample_size → skip detection."""
        session = AsyncMock()
        indicator_row = MagicMock()
        indicator_row.objective = MagicMock()
        indicator_row.objective.sli = "response_time_p95"
        indicator_row.id = uuid.uuid4()

        with (
            patch(
                "tropek.modules.change_points.worker_step.ChangePointRepository"
            ) as mock_repo_cls,
            patch(
                "tropek.modules.change_points.worker_step.BaselineRepository"
            ) as mock_baseline_cls,
        ):
            mock_repo = mock_repo_cls.return_value
            mock_repo.resolve_configs_for_metrics = AsyncMock(
                return_value={"response_time_p95": _default_config()}
            )
            mock_repo.has_nearby_change_point = AsyncMock()

            mock_baseline = mock_baseline_cls.return_value
            mock_baseline.get_evaluation_baselines = AsyncMock(return_value=[])

            await run_change_point_detection(
                session=session,
                snapshot=snapshot,
                slo_def=slo_def,
                indicator_rows=[indicator_row],
            )

            mock_repo.has_nearby_change_point.assert_not_called()

    async def test_dedup_prevents_duplicate_insert(
        self, snapshot: MagicMock, slo_def: MagicMock
    ) -> None:
        """If a nearby change point exists, skip insertion."""
        session = AsyncMock()
        indicator_row = MagicMock()
        indicator_row.objective = MagicMock()
        indicator_row.objective.sli = "response_time_p95"
        indicator_row.id = uuid.uuid4()

        baseline_evals = []
        for i in range(15):
            eval_mock = MagicMock()
            eval_mock.period_start = datetime(2026, 4, i + 1, 12, 0, tzinfo=UTC)
            row_mock = MagicMock()
            row_mock.objective = MagicMock()
            row_mock.objective.sli = "response_time_p95"
            row_mock.value = 100.0 + (50.0 if i >= 10 else 0.0)
            eval_mock.indicator_rows = [row_mock]
            baseline_evals.append(eval_mock)

        with (
            patch(
                "tropek.modules.change_points.worker_step.ChangePointRepository"
            ) as mock_repo_cls,
            patch(
                "tropek.modules.change_points.worker_step.BaselineRepository"
            ) as mock_baseline_cls,
            patch(
                "tropek.modules.change_points.worker_step.detect_change_points"
            ) as mock_detect,
        ):
            mock_repo = mock_repo_cls.return_value
            mock_repo.resolve_configs_for_metrics = AsyncMock(
                return_value={"response_time_p95": _default_config()}
            )
            mock_repo.has_nearby_change_point = AsyncMock(return_value=True)
            mock_repo.insert_change_point = AsyncMock()

            mock_baseline = mock_baseline_cls.return_value
            mock_baseline.get_evaluation_baselines = AsyncMock(return_value=baseline_evals)

            from tropek.modules.change_points.detector import ChangePointResult

            mock_detect.return_value = [
                ChangePointResult(
                    position=13,
                    timestamp=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
                    detector="e_divisive",
                    direction="regression",
                    change_relative_pct=50.0,
                    change_absolute=50.0,
                    pvalue=0.0001,
                    pre_segment_mean=100.0,
                    post_segment_mean=150.0,
                )
            ]

            await run_change_point_detection(
                session=session,
                snapshot=snapshot,
                slo_def=slo_def,
                indicator_rows=[indicator_row],
            )

            mock_repo.insert_change_point.assert_not_called()


class TestSameRegime:
    """Tests for the _same_regime helper."""

    def test_identical_means(self) -> None:
        assert _same_regime(500.0, 500.0) is True

    def test_within_threshold(self) -> None:
        assert _same_regime(500.0, 520.0) is True

    def test_exceeds_threshold(self) -> None:
        assert _same_regime(500.0, 600.0) is False

    def test_both_zero(self) -> None:
        assert _same_regime(0.0, 0.0) is True

    def test_one_zero(self) -> None:
        assert _same_regime(0.0, 100.0) is False

    def test_symmetric(self) -> None:
        assert _same_regime(500.0, 520.0) == _same_regime(520.0, 500.0)

    def test_negative_values(self) -> None:
        assert _same_regime(-500.0, -520.0) is True
        assert _same_regime(-500.0, -100.0) is False


class TestRegimeConsolidation:
    """Tests that same-regime change points are suppressed."""

    @pytest.fixture()
    def snapshot(self) -> MagicMock:
        return _make_snapshot()

    @pytest.fixture()
    def slo_def(self) -> MagicMock:
        return _make_slo_def()

    async def test_suppresses_same_regime_change_point(
        self, snapshot: MagicMock, slo_def: MagicMock
    ) -> None:
        """A new change point with similar post_segment_mean is suppressed."""
        session = AsyncMock()
        indicator_row = MagicMock()
        indicator_row.objective = MagicMock()
        indicator_row.objective.sli = "response_time_p95"
        indicator_row.id = uuid.uuid4()

        baseline_evals = []
        for i in range(15):
            eval_mock = MagicMock()
            eval_mock.period_start = datetime(2026, 4, i + 1, 12, 0, tzinfo=UTC)
            row_mock = MagicMock()
            row_mock.objective = MagicMock()
            row_mock.objective.sli = "response_time_p95"
            row_mock.value = 100.0 + (50.0 if i >= 10 else 0.0)
            eval_mock.indicator_rows = [row_mock]
            baseline_evals.append(eval_mock)

        with (
            patch(
                "tropek.modules.change_points.worker_step.ChangePointRepository"
            ) as mock_repo_cls,
            patch(
                "tropek.modules.change_points.worker_step.BaselineRepository"
            ) as mock_baseline_cls,
            patch(
                "tropek.modules.change_points.worker_step.detect_change_points"
            ) as mock_detect,
        ):
            mock_repo = mock_repo_cls.return_value
            mock_repo.resolve_configs_for_metrics = AsyncMock(
                return_value={"response_time_p95": _default_config()}
            )
            mock_repo.has_nearby_change_point = AsyncMock(return_value=False)
            mock_repo.insert_change_point = AsyncMock()

            previous_cp = MagicMock()
            previous_cp.post_segment_mean = 148.0
            mock_repo.get_latest_change_point = AsyncMock(return_value=previous_cp)

            mock_baseline = mock_baseline_cls.return_value
            mock_baseline.get_evaluation_baselines = AsyncMock(
                return_value=baseline_evals
            )

            from tropek.modules.change_points.detector import ChangePointResult

            mock_detect.return_value = [
                ChangePointResult(
                    position=13,
                    timestamp=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
                    detector="e_divisive",
                    direction="regression",
                    change_relative_pct=50.0,
                    change_absolute=50.0,
                    pvalue=0.0001,
                    pre_segment_mean=100.0,
                    post_segment_mean=150.0,
                )
            ]

            await run_change_point_detection(
                session=session,
                snapshot=snapshot,
                slo_def=slo_def,
                indicator_rows=[indicator_row],
            )

            mock_repo.insert_change_point.assert_not_called()

    async def test_allows_different_regime_change_point(
        self, snapshot: MagicMock, slo_def: MagicMock
    ) -> None:
        """A change point with a meaningfully different post_segment_mean is inserted."""
        session = AsyncMock()
        indicator_row = MagicMock()
        indicator_row.objective = MagicMock()
        indicator_row.objective.sli = "response_time_p95"
        indicator_row.id = uuid.uuid4()

        baseline_evals = []
        for i in range(15):
            eval_mock = MagicMock()
            eval_mock.period_start = datetime(2026, 4, i + 1, 12, 0, tzinfo=UTC)
            row_mock = MagicMock()
            row_mock.objective = MagicMock()
            row_mock.objective.sli = "response_time_p95"
            row_mock.value = 100.0 + (50.0 if i >= 10 else 0.0)
            eval_mock.indicator_rows = [row_mock]
            baseline_evals.append(eval_mock)

        with (
            patch(
                "tropek.modules.change_points.worker_step.ChangePointRepository"
            ) as mock_repo_cls,
            patch(
                "tropek.modules.change_points.worker_step.BaselineRepository"
            ) as mock_baseline_cls,
            patch(
                "tropek.modules.change_points.worker_step.detect_change_points"
            ) as mock_detect,
        ):
            mock_repo = mock_repo_cls.return_value
            mock_repo.resolve_configs_for_metrics = AsyncMock(
                return_value={"response_time_p95": _default_config()}
            )
            mock_repo.has_nearby_change_point = AsyncMock(return_value=False)
            mock_repo.insert_change_point = AsyncMock()

            previous_cp = MagicMock()
            previous_cp.post_segment_mean = 100.0
            mock_repo.get_latest_change_point = AsyncMock(return_value=previous_cp)

            mock_baseline = mock_baseline_cls.return_value
            mock_baseline.get_evaluation_baselines = AsyncMock(
                return_value=baseline_evals
            )

            from tropek.modules.change_points.detector import ChangePointResult

            mock_detect.return_value = [
                ChangePointResult(
                    position=13,
                    timestamp=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
                    detector="e_divisive",
                    direction="regression",
                    change_relative_pct=50.0,
                    change_absolute=50.0,
                    pvalue=0.0001,
                    pre_segment_mean=100.0,
                    post_segment_mean=150.0,
                )
            ]

            await run_change_point_detection(
                session=session,
                snapshot=snapshot,
                slo_def=slo_def,
                indicator_rows=[indicator_row],
            )

            mock_repo.insert_change_point.assert_called_once()
