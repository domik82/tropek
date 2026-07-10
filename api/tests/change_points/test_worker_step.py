"""Unit tests for the change point worker step orchestration logic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from tropek.modules.change_points.detector import ChangePointResult, Transition
from tropek.modules.change_points.models import (
    ChangePointInputs,
    DetectedBatch,
    EnabledObjective,
    MetricSeries,
)
from tropek.modules.change_points.repository import ChangePointInsertParams, ResolvedConfig
from tropek.modules.change_points.worker_step import (
    _same_regime,
    detect_change_points_for_objectives,
    extract_metric_series,
    load_change_point_inputs,
    persist_detected_change_points,
)

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
    snap.slo_name = 'perf-slo'
    snap.evaluation_name = 'load-test'
    snap.period_start = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    snap.period_end = datetime(2026, 4, 10, 12, 30, tzinfo=UTC)
    snap.slo_version = 3
    snap.compare_to = None
    return snap


def _default_config(*, enabled: bool = True) -> ResolvedConfig:
    return ResolvedConfig(
        enabled=enabled,
        higher_is_better=False,
        window_size=30,
        max_pvalue=0.001,
        min_magnitude=0.0,
        min_sample_size=10,
        pvalue_strict_threshold=0.05,
        pvalue_moderate_threshold=0.5,
    )


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

    def test_local_segment_scale_rejects_large_jump(self) -> None:
        """With local-segment (not full-series) stats, a small std must not absorb a large jump.

        Regression guard: post_segment_mean/std now carry ADJACENT-segment semantics — a
        previous change point with a tight local post-segment (mean=11.5M, std=1000.0) must
        not suppress a later candidate whose post-segment mean has shifted to 13.3M.
        """
        assert _same_regime(11_500_000.0, 1000.0, 13_300_000.0) is False


class TestRegimeConsolidation:
    """Same-regime change points are suppressed at the persist seam."""

    @staticmethod
    def _batch(detected: list[ChangePointResult]) -> DetectedBatch:
        series = MetricSeries(
            values=[100.0] * 15,
            timestamps=[datetime(2026, 4, i + 1, 12, 0, tzinfo=UTC) for i in range(15)],
            period_ends=[datetime(2026, 4, i + 1, 12, 30, tzinfo=UTC) for i in range(15)],
            evaluation_run_ids=[uuid.uuid4() for _ in range(15)],
        )
        return DetectedBatch(
            metric_name='response_time_p95',
            indicator_result_id=uuid.uuid4(),
            series=series,
            detected=detected,
        )

    @staticmethod
    def _detected() -> list[ChangePointResult]:
        return [
            ChangePointResult(
                position=13,
                timestamp=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
                detector='e_divisive',
                direction='regression',
                change_relative_pct=50.0,
                change_absolute=50.0,
                pvalue=0.0001,
                pre_segment_mean=100.0,
                post_segment_mean=150.0,
                post_segment_std=20.0,
            )
        ]

    async def test_suppresses_same_regime_change_point(self) -> None:
        """A new change point with similar post_segment_mean is suppressed."""
        session = AsyncMock()
        with patch('tropek.modules.change_points.worker_step.ChangePointRepository') as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.has_nearby_change_point = AsyncMock(return_value=False)
            mock_repo.insert_change_point = AsyncMock()
            previous_cp = MagicMock()
            previous_cp.direction = 'regression'
            previous_cp.post_segment_mean = 148.0
            previous_cp.post_segment_std = 25.0
            mock_repo.get_latest_change_point = AsyncMock(return_value=previous_cp)

            await persist_detected_change_points(
                session=session,
                snapshot=_make_snapshot(),
                comparison_name='load-test',
                detected_batches=[self._batch(self._detected())],
                log=MagicMock(),
            )

            mock_repo.insert_change_point.assert_not_called()

    async def test_allows_different_regime_change_point(self) -> None:
        """A change point with post_segment_mean outside the noise band is inserted."""
        session = AsyncMock()
        with patch('tropek.modules.change_points.worker_step.ChangePointRepository') as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.has_nearby_change_point = AsyncMock(return_value=False)
            mock_repo.insert_change_point = AsyncMock()
            previous_cp = MagicMock()
            previous_cp.direction = 'regression'
            previous_cp.post_segment_mean = 100.0
            previous_cp.post_segment_std = 10.0
            mock_repo.get_latest_change_point = AsyncMock(return_value=previous_cp)

            await persist_detected_change_points(
                session=session,
                snapshot=_make_snapshot(),
                comparison_name='load-test',
                detected_batches=[self._batch(self._detected())],
                log=MagicMock(),
            )

            mock_repo.insert_change_point.assert_called_once()


class TestTransitionPersistence:
    """A transition candidate (appeared/vanished, no relative pct) must persist correctly."""

    async def test_transition_candidate_persists_transition_and_null_pct(self) -> None:
        """A candidate with change_relative_pct=None and transition=APPEARED flows through intact."""
        session = AsyncMock()
        series = MetricSeries(
            values=[0.0] * 10 + [100.0] * 5,
            timestamps=[datetime(2026, 4, i + 1, 12, 0, tzinfo=UTC) for i in range(15)],
            period_ends=[datetime(2026, 4, i + 1, 12, 30, tzinfo=UTC) for i in range(15)],
            evaluation_run_ids=[uuid.uuid4() for _ in range(15)],
        )
        detected = [
            ChangePointResult(
                position=13,
                timestamp=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
                detector='e_divisive',
                direction='regression',
                change_relative_pct=None,
                change_absolute=100.0,
                pvalue=0.0001,
                pre_segment_mean=0.0,
                post_segment_mean=100.0,
                post_segment_std=0.0,
                transition=Transition.APPEARED,
            )
        ]
        batch = DetectedBatch(
            metric_name='response_time_p95',
            indicator_result_id=uuid.uuid4(),
            series=series,
            detected=detected,
        )
        with patch('tropek.modules.change_points.worker_step.ChangePointRepository') as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.has_nearby_change_point = AsyncMock(return_value=False)
            mock_repo.get_latest_change_point = AsyncMock(return_value=None)
            mock_repo.insert_change_point = AsyncMock()

            await persist_detected_change_points(
                session=session,
                snapshot=_make_snapshot(),
                comparison_name='load-test',
                detected_batches=[batch],
                log=MagicMock(),
            )

            mock_repo.insert_change_point.assert_called_once()
            inserted_params = mock_repo.insert_change_point.call_args.args[0]
            assert isinstance(inserted_params, ChangePointInsertParams)
            assert inserted_params.change_relative_pct is None
            assert inserted_params.transition == Transition.APPEARED


class TestExtractMetricSeries:
    """Pure extraction from pre-loaded baseline history (no DB)."""

    @staticmethod
    def _history_desc() -> list[MagicMock]:
        # period_start day 1..5, returned DESC (most recent first) like get_evaluation_baselines
        history: list[MagicMock] = []
        for day in (5, 4, 3, 2, 1):
            evaluation = MagicMock()
            evaluation.period_start = datetime(2026, 4, day, 12, 0, tzinfo=UTC)
            evaluation.period_end = datetime(2026, 4, day, 12, 30, tzinfo=UTC)
            evaluation.evaluation_id = uuid.uuid4()
            row = MagicMock()
            row.objective = MagicMock()
            row.objective.sli = 'response_time_p95'
            row.value = float(day * 10)
            evaluation.indicator_rows = [row]
            history.append(evaluation)
        return history

    def test_slices_to_window_and_sorts_ascending(self) -> None:
        series = extract_metric_series(
            history_evals=self._history_desc(),
            metric_name='response_time_p95',
            window_size=3,
        )
        # most-recent 3 (days 5,4,3) then ascending -> days 3,4,5 -> values 30,40,50
        assert series.values == [30.0, 40.0, 50.0]
        assert series.timestamps[0] == datetime(2026, 4, 3, 12, 0, tzinfo=UTC)

    def test_ignores_other_metrics_and_none_values(self) -> None:
        history = self._history_desc()
        history[0].indicator_rows[0].objective.sli = 'other_metric'  # day 5 excluded
        history[1].indicator_rows[0].value = None  # day 4 excluded
        series = extract_metric_series(
            history_evals=history,
            metric_name='response_time_p95',
            window_size=5,
        )
        assert series.values == [10.0, 20.0, 30.0]  # days 1,2,3 ascending


def _make_multi_slo_def(metric_names: list[str]) -> MagicMock:
    objectives = []
    for metric_name in metric_names:
        objective = MagicMock()
        objective.sli = metric_name
        objectives.append(objective)
    slo = MagicMock()
    slo.objectives = objectives
    return slo


def _make_indicator_row(metric_name: str) -> MagicMock:
    indicator_row = MagicMock()
    indicator_row.objective = MagicMock()
    indicator_row.objective.sli = metric_name
    indicator_row.id = uuid.uuid4()
    return indicator_row


class TestLoadChangePointInputs:
    """Read phase: one baseline fetch per SLO."""

    async def test_fetches_history_once_with_max_window(self) -> None:
        session = AsyncMock()
        snapshot = _make_snapshot()
        metric_names = ['m_a', 'm_b', 'm_c']
        slo_def = _make_multi_slo_def(metric_names)
        indicator_rows = [_make_indicator_row(name) for name in metric_names]

        configs = [
            _default_config(),  # window_size 30
            ResolvedConfig(
                enabled=True,
                higher_is_better=False,
                window_size=60,
                max_pvalue=0.001,
                min_magnitude=0.0,
                min_sample_size=10,
                pvalue_strict_threshold=0.05,
                pvalue_moderate_threshold=0.5,
            ),
            ResolvedConfig(
                enabled=True,
                higher_is_better=False,
                window_size=45,
                max_pvalue=0.001,
                min_magnitude=0.0,
                min_sample_size=10,
                pvalue_strict_threshold=0.05,
                pvalue_moderate_threshold=0.5,
            ),
        ]

        with (
            patch('tropek.modules.change_points.worker_step.ChangePointRepository') as mock_repo_cls,
            patch('tropek.modules.change_points.worker_step.ConfigurationRepository') as mock_config_cls,
            patch('tropek.modules.change_points.worker_step.BaselineRepository') as mock_baseline_cls,
        ):
            mock_config_cls.return_value.get_change_point_defaults = AsyncMock(return_value=_SYSTEM_DEFAULTS)
            mock_repo_cls.resolve_from_objective = MagicMock(side_effect=configs)
            mock_baseline = mock_baseline_cls.return_value
            mock_baseline.get_evaluation_baselines = AsyncMock(return_value=[])

            cp_inputs = await load_change_point_inputs(
                session=session,
                snapshot=snapshot,
                slo_def=slo_def,
                indicator_rows=indicator_rows,
            )

            mock_baseline.get_evaluation_baselines.assert_called_once()
            call_kwargs = mock_baseline.get_evaluation_baselines.call_args.kwargs
            assert call_kwargs['limit'] == 60
            assert call_kwargs['evaluation_name'] == snapshot.evaluation_name
            assert cp_inputs is not None
            assert len(cp_inputs.enabled_objectives) == 3

    async def test_returns_none_for_cross_series(self) -> None:
        session = AsyncMock()
        snapshot = _make_snapshot()
        snapshot.compare_to = {'evaluation_name': 'a-different-series'}
        slo_def = _make_multi_slo_def(['m_a'])
        cp_inputs = await load_change_point_inputs(
            session=session,
            snapshot=snapshot,
            slo_def=slo_def,
            indicator_rows=[_make_indicator_row('m_a')],
        )
        assert cp_inputs is None

    async def test_returns_none_when_no_enabled_objectives(self) -> None:
        session = AsyncMock()
        snapshot = _make_snapshot()
        slo_def = _make_multi_slo_def(['m_a'])
        with (
            patch('tropek.modules.change_points.worker_step.ChangePointRepository') as mock_repo_cls,
            patch('tropek.modules.change_points.worker_step.ConfigurationRepository') as mock_config_cls,
        ):
            mock_config_cls.return_value.get_change_point_defaults = AsyncMock(return_value=_SYSTEM_DEFAULTS)
            mock_repo_cls.resolve_from_objective = MagicMock(return_value=_default_config(enabled=False))
            cp_inputs = await load_change_point_inputs(
                session=session,
                snapshot=snapshot,
                slo_def=slo_def,
                indicator_rows=[_make_indicator_row('m_a')],
            )
        assert cp_inputs is None


class TestDetectChangePointsForObjectives:
    """Compute phase: pure, no DB session."""

    def _inputs(self, metric_names: list[str]) -> ChangePointInputs:
        enabled = [
            EnabledObjective(metric_name=name, resolved=_default_config(), indicator_result_id=uuid.uuid4())
            for name in metric_names
        ]
        history: list[MagicMock] = []
        for i in range(15):
            evaluation = MagicMock()
            evaluation.period_start = datetime(2026, 4, i + 1, 12, 0, tzinfo=UTC)
            evaluation.period_end = datetime(2026, 4, i + 1, 12, 30, tzinfo=UTC)
            evaluation.evaluation_id = uuid.uuid4()
            rows = []
            for name in metric_names:
                row = MagicMock()
                row.objective = MagicMock()
                row.objective.sli = name
                row.value = 100.0 + (50.0 if i >= 10 else 0.0)
                rows.append(row)
            evaluation.indicator_rows = rows
            history.append(evaluation)
        return ChangePointInputs(
            comparison_name='load-test',
            enabled_objectives=enabled,
            shared_history=list(reversed(history)),
        )

    def _one_detection(self) -> list[ChangePointResult]:
        return [
            ChangePointResult(
                position=13,
                timestamp=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
                detector='e_divisive',
                direction='regression',
                change_relative_pct=50.0,
                change_absolute=50.0,
                pvalue=0.0001,
                pre_segment_mean=100.0,
                post_segment_mean=150.0,
                post_segment_std=20.0,
            )
        ]

    def test_returns_batch_only_for_metrics_with_detections(self) -> None:
        cp_inputs = self._inputs(['m_a', 'm_b'])
        log = MagicMock()
        with patch('tropek.modules.change_points.worker_step.detect_change_points') as mock_detect:
            mock_detect.side_effect = [self._one_detection(), []]
            batches = detect_change_points_for_objectives(cp_inputs, log=log)
        assert len(batches) == 1
        assert batches[0].metric_name == 'm_a'

    def test_skips_metric_with_insufficient_history(self) -> None:
        cp_inputs = self._inputs(['m_a'])
        cp_inputs.enabled_objectives[0] = EnabledObjective(
            metric_name='m_a',
            resolved=ResolvedConfig(
                enabled=True,
                higher_is_better=False,
                window_size=30,
                max_pvalue=0.001,
                min_magnitude=0.0,
                min_sample_size=999,
                pvalue_strict_threshold=0.05,
                pvalue_moderate_threshold=0.5,
            ),
            indicator_result_id=uuid.uuid4(),
        )
        log = MagicMock()
        with patch('tropek.modules.change_points.worker_step.detect_change_points') as mock_detect:
            batches = detect_change_points_for_objectives(cp_inputs, log=log)
            mock_detect.assert_not_called()
        assert batches == []

    def test_isolates_failing_metric(self) -> None:
        cp_inputs = self._inputs(['m_a', 'm_b'])
        log = MagicMock()
        with patch('tropek.modules.change_points.worker_step.detect_change_points') as mock_detect:
            mock_detect.side_effect = [ValueError('boom'), self._one_detection()]
            batches = detect_change_points_for_objectives(cp_inputs, log=log)
        assert len(batches) == 1
        assert batches[0].metric_name == 'm_b'


class TestPersistDetectedChangePoints:
    """Write phase: dedup + insert per batch."""

    def _batch(self) -> DetectedBatch:
        series = MetricSeries(
            values=[100.0] * 15,
            timestamps=[datetime(2026, 4, i + 1, 12, 0, tzinfo=UTC) for i in range(15)],
            period_ends=[datetime(2026, 4, i + 1, 12, 30, tzinfo=UTC) for i in range(15)],
            evaluation_run_ids=[uuid.uuid4() for _ in range(15)],
        )
        detected = [
            ChangePointResult(
                position=13,
                timestamp=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
                detector='e_divisive',
                direction='regression',
                change_relative_pct=50.0,
                change_absolute=50.0,
                pvalue=0.0001,
                pre_segment_mean=100.0,
                post_segment_mean=150.0,
                post_segment_std=20.0,
            )
        ]
        return DetectedBatch(
            metric_name='response_time_p95',
            indicator_result_id=uuid.uuid4(),
            series=series,
            detected=detected,
        )

    async def test_dedup_prevents_insert(self) -> None:
        session = AsyncMock()
        snapshot = _make_snapshot()
        with patch('tropek.modules.change_points.worker_step.ChangePointRepository') as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.has_nearby_change_point = AsyncMock(return_value=True)
            mock_repo.insert_change_point = AsyncMock()
            await persist_detected_change_points(
                session=session,
                snapshot=snapshot,
                comparison_name='load-test',
                detected_batches=[self._batch()],
                log=MagicMock(),
            )
            mock_repo.insert_change_point.assert_not_called()

    async def test_inserts_new_change_point(self) -> None:
        session = AsyncMock()
        snapshot = _make_snapshot()
        with patch('tropek.modules.change_points.worker_step.ChangePointRepository') as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.has_nearby_change_point = AsyncMock(return_value=False)
            mock_repo.get_latest_change_point = AsyncMock(return_value=None)
            mock_repo.insert_change_point = AsyncMock()
            await persist_detected_change_points(
                session=session,
                snapshot=snapshot,
                comparison_name='load-test',
                detected_batches=[self._batch()],
                log=MagicMock(),
            )
            mock_repo.insert_change_point.assert_called_once()
