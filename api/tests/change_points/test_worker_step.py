"""Unit tests for the change point worker step orchestration logic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tropek.modules.change_points.detector import ChangePointResult
from tropek.modules.change_points.repository import ResolvedConfig
from tropek.modules.change_points.worker_step import _same_regime, run_change_point_detection

_SYSTEM_DEFAULTS = {
    'enabled': True,
    'higher_is_better': False,
    'window_size': 30,
    'max_pvalue': 0.001,
    'min_magnitude': 0.0,
    'min_sample_size': 10,
}


def _make_snapshot() -> MagicMock:
    snap = MagicMock()
    snap.eval_id = uuid.uuid4()
    snap.parent_run_id = uuid.uuid4()
    snap.asset_id = uuid.uuid4()
    snap.slo_name = "perf-slo"
    snap.evaluation_name = "load-test"
    snap.period_start = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    snap.period_end = datetime(2026, 4, 10, 12, 30, tzinfo=UTC)
    snap.slo_version = 3
    snap.compare_to = None
    return snap


def _make_slo_def() -> MagicMock:
    config = MagicMock()
    config.enabled = True
    config.higher_is_better = False
    config.window_size = 30
    config.max_pvalue = 0.001
    config.min_magnitude = 0.0
    config.min_sample_size = 10

    objective = MagicMock()
    objective.sli = "response_time_p95"
    objective.display_name = "Response Time P95"
    objective.pass_threshold = ["<600"]
    objective.warning_threshold = ["<1000"]
    objective.change_point_config = config

    slo = MagicMock()
    slo.objectives = [objective]
    slo.comparable_from_version = 1
    return slo


def _default_config(*, enabled: bool = True) -> ResolvedConfig:
    return ResolvedConfig(
        enabled=enabled,
        higher_is_better=False,
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
        """No indicator rows → defaults are still fetched, nothing inserted."""
        session = AsyncMock()

        with (
            patch("tropek.modules.change_points.worker_step.ChangePointRepository"),
            patch(
                "tropek.modules.change_points.worker_step.ConfigurationRepository"
            ) as mock_config_cls,
        ):
            mock_config = mock_config_cls.return_value
            mock_config.get_change_point_defaults = AsyncMock(return_value=_SYSTEM_DEFAULTS)

            await run_change_point_detection(
                session=session,
                snapshot=snapshot,
                slo_def=slo_def,
                indicator_rows=[],
            )

            mock_config.get_change_point_defaults.assert_called_once()

    async def test_skips_disabled_metric(
        self, snapshot: MagicMock, slo_def: MagicMock
    ) -> None:
        """Override row with enabled=False → skip that metric entirely."""
        session = AsyncMock()
        slo_def.objectives[0].change_point_config.enabled = False

        with (
            patch(
                "tropek.modules.change_points.worker_step.ChangePointRepository"
            ) as mock_repo_cls,
            patch(
                "tropek.modules.change_points.worker_step.ConfigurationRepository"
            ) as mock_config_cls,
        ):
            mock_config = mock_config_cls.return_value
            mock_config.get_change_point_defaults = AsyncMock(return_value=_SYSTEM_DEFAULTS)
            mock_repo = mock_repo_cls.return_value
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
                "tropek.modules.change_points.worker_step.ConfigurationRepository"
            ) as mock_config_cls,
            patch(
                "tropek.modules.change_points.worker_step.BaselineRepository"
            ),
        ):
            mock_config = mock_config_cls.return_value
            mock_config.get_change_point_defaults = AsyncMock(return_value=_SYSTEM_DEFAULTS)
            mock_repo = mock_repo_cls.return_value
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
                "tropek.modules.change_points.worker_step.ConfigurationRepository"
            ) as mock_config_cls,
            patch(
                "tropek.modules.change_points.worker_step.BaselineRepository"
            ) as mock_baseline_cls,
        ):
            mock_config = mock_config_cls.return_value
            mock_config.get_change_point_defaults = AsyncMock(return_value=_SYSTEM_DEFAULTS)
            mock_repo_cls.resolve_from_objective = MagicMock(return_value=_default_config())
            mock_repo = mock_repo_cls.return_value
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
                "tropek.modules.change_points.worker_step.ConfigurationRepository"
            ) as mock_config_cls,
            patch(
                "tropek.modules.change_points.worker_step.BaselineRepository"
            ) as mock_baseline_cls,
            patch(
                "tropek.modules.change_points.worker_step.detect_change_points"
            ) as mock_detect,
        ):
            mock_config = mock_config_cls.return_value
            mock_config.get_change_point_defaults = AsyncMock(return_value=_SYSTEM_DEFAULTS)
            mock_repo_cls.resolve_from_objective = MagicMock(return_value=_default_config())
            mock_repo = mock_repo_cls.return_value
            mock_repo.has_nearby_change_point = AsyncMock(return_value=True)
            mock_repo.insert_change_point = AsyncMock()

            mock_baseline = mock_baseline_cls.return_value
            mock_baseline.get_evaluation_baselines = AsyncMock(return_value=baseline_evals)

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
                    post_segment_std=20.0,
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
    """Tests for the _same_regime helper using std dev."""

    def test_within_two_std(self) -> None:
        # std=25, 2*25=50 → 520 is within 50 of 500
        assert _same_regime(500.0, 25.0, 520.0) is True

    def test_exceeds_two_std(self) -> None:
        # std=25, 2*25=50 → 600 is 100 away, exceeds band
        assert _same_regime(500.0, 25.0, 600.0) is False

    def test_exactly_at_boundary(self) -> None:
        # std=25, 2*25=50 → 550 is exactly at 2*std, should NOT match (strict <)
        assert _same_regime(500.0, 25.0, 550.0) is False

    def test_zero_std_same_mean(self) -> None:
        assert _same_regime(500.0, 0.0, 500.0) is True

    def test_zero_std_different_mean(self) -> None:
        assert _same_regime(500.0, 0.0, 501.0) is False

    def test_large_std_absorbs_big_difference(self) -> None:
        # std=100, 2*100=200 → 650 is within 200 of 500
        assert _same_regime(500.0, 100.0, 650.0) is True

    def test_small_std_rejects_small_difference(self) -> None:
        # std=5, 2*5=10 → 515 is 15 away, exceeds band
        assert _same_regime(500.0, 5.0, 515.0) is False


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
                "tropek.modules.change_points.worker_step.ConfigurationRepository"
            ) as mock_config_cls,
            patch(
                "tropek.modules.change_points.worker_step.BaselineRepository"
            ) as mock_baseline_cls,
            patch(
                "tropek.modules.change_points.worker_step.detect_change_points"
            ) as mock_detect,
        ):
            mock_config = mock_config_cls.return_value
            mock_config.get_change_point_defaults = AsyncMock(return_value=_SYSTEM_DEFAULTS)
            mock_repo_cls.resolve_from_objective = MagicMock(return_value=_default_config())
            mock_repo = mock_repo_cls.return_value
            mock_repo.has_nearby_change_point = AsyncMock(return_value=False)
            mock_repo.insert_change_point = AsyncMock()

            previous_cp = MagicMock()
            previous_cp.direction = 'regression'
            previous_cp.post_segment_mean = 148.0
            previous_cp.post_segment_std = 25.0
            mock_repo.get_latest_change_point = AsyncMock(return_value=previous_cp)

            mock_baseline = mock_baseline_cls.return_value
            mock_baseline.get_evaluation_baselines = AsyncMock(
                return_value=baseline_evals
            )

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
                    post_segment_std=20.0,
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
        """A change point with post_segment_mean outside the noise band is inserted."""
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
                "tropek.modules.change_points.worker_step.ConfigurationRepository"
            ) as mock_config_cls,
            patch(
                "tropek.modules.change_points.worker_step.BaselineRepository"
            ) as mock_baseline_cls,
            patch(
                "tropek.modules.change_points.worker_step.detect_change_points"
            ) as mock_detect,
        ):
            mock_config = mock_config_cls.return_value
            mock_config.get_change_point_defaults = AsyncMock(return_value=_SYSTEM_DEFAULTS)
            mock_repo_cls.resolve_from_objective = MagicMock(return_value=_default_config())
            mock_repo = mock_repo_cls.return_value
            mock_repo.has_nearby_change_point = AsyncMock(return_value=False)
            mock_repo.insert_change_point = AsyncMock()

            previous_cp = MagicMock()
            previous_cp.direction = 'regression'
            previous_cp.post_segment_mean = 100.0
            previous_cp.post_segment_std = 10.0
            mock_repo.get_latest_change_point = AsyncMock(return_value=previous_cp)

            mock_baseline = mock_baseline_cls.return_value
            mock_baseline.get_evaluation_baselines = AsyncMock(
                return_value=baseline_evals
            )

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
                    post_segment_std=20.0,
                )
            ]

            await run_change_point_detection(
                session=session,
                snapshot=snapshot,
                slo_def=slo_def,
                indicator_rows=[indicator_row],
            )

            mock_repo.insert_change_point.assert_called_once()
