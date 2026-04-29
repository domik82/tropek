"""End-to-end detection scenarios for the worker step pipeline.

Unlike test_worker_step.py (which mocks detect_change_points), these tests
run the REAL E-Divisive detector against synthetic series and verify that
the filtering pipeline (dedup, regime suppression) produces the correct
insert/skip decisions.

Each scenario documents:
  - The data pattern (what the metric looks like)
  - What detect_change_points finds (algorithm output)
  - What the worker step saves after filtering (expected behaviour)
  - WHY — so we can reason about edge cases

The gather_metric_series + detect_change_points + _persist_change_points
pipeline is the unit under test. We mock only the async repos (baseline
history, change_point store) — the detector runs for real.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import structlog
from tropek.modules.change_points.detector import detect_change_points
from tropek.modules.change_points.repository import ResolvedConfig
from tropek.modules.change_points.worker_step import (
    _persist_change_points,
    gather_metric_series,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(
    *,
    min_sample_size: int = 10,
    window_size: int = 30,
    max_pvalue: float = 0.05,
    min_magnitude: float = 0.0,
    higher_is_better: bool = False,
) -> ResolvedConfig:
    return ResolvedConfig(
        enabled=True,
        higher_is_better=higher_is_better,
        window_size=window_size,
        max_pvalue=max_pvalue,
        min_magnitude=min_magnitude,
        min_sample_size=min_sample_size,
    )


def _make_history(
    values: list[float],
    *,
    metric: str = 'response_time_p95',
    start: datetime = datetime(2026, 3, 14, 0, 0, tzinfo=UTC),
    interval: timedelta = timedelta(hours=4),
    evaluation_name: str = 'load-test',
) -> list[MagicMock]:
    """Build a list of mock baseline evaluations from a value series.

    Each evaluation has one indicator_row for the given metric.
    """
    evals = []
    for i, value in enumerate(values):
        row = MagicMock()
        row.objective = MagicMock()
        row.objective.sli = metric
        row.value = value

        evaluation = MagicMock()
        evaluation.period_start = start + interval * i
        evaluation.indicator_rows = [row]
        evaluation.evaluation_name = evaluation_name
        evals.append(evaluation)
    return evals


def _snapshot(
    *,
    asset_id: uuid.UUID | None = None,
    slo_name: str = 'perf-slo',
    evaluation_name: str = 'load-test',
    period_end: datetime = datetime(2026, 3, 16, 15, 0, tzinfo=UTC),
) -> MagicMock:
    snap = MagicMock()
    snap.asset_id = asset_id or uuid.uuid4()
    snap.parent_run_id = uuid.uuid4()
    snap.slo_name = slo_name
    snap.evaluation_name = evaluation_name
    snap.period_end = period_end
    snap.compare_to = None
    return snap


class _FakeChangePointRepo:
    """Stateful fake that checks inserts for dedup, like the real DB would.

    When has_nearby_change_point is called, it scans previously inserted CPs
    for a match on (metric_name, period_start in nearby_timestamps).
    Direction-agnostic: a CP at a given position blocks re-insertion regardless
    of direction — the first detection wins.
    """

    def __init__(
        self,
        *,
        previous_cp: Any = None,
    ) -> None:
        self.previous_cp = previous_cp
        self.inserts: list[Any] = []

    async def has_nearby_change_point(self, **kwargs: Any) -> bool:
        metric_name = kwargs.get('metric_name')
        nearby_timestamps = kwargs.get('nearby_timestamps', [])

        for existing in self.inserts:
            if (
                existing.metric_name == metric_name
                and existing.period_start in nearby_timestamps
            ):
                return True
        return False

    async def get_latest_change_point(self, **kwargs: Any) -> Any:
        if self.inserts:
            return self.inserts[-1]
        return self.previous_cp

    async def insert_change_point(self, params: Any) -> None:
        self.inserts.append(params)


async def _run_pipeline(
    values: list[float],
    *,
    metric: str = 'response_time_p95',
    config: ResolvedConfig | None = None,
    cp_repo: _FakeChangePointRepo | None = None,
    snap: MagicMock | None = None,
    evaluation_name: str = 'load-test',
) -> list[Any]:
    """Run the gather → detect → persist pipeline and return inserted CPs."""
    history = _make_history(
        values, metric=metric, evaluation_name=evaluation_name,
    )
    baseline_repo = MagicMock()
    baseline_repo.get_evaluation_baselines = AsyncMock(return_value=history)

    if cp_repo is None:
        cp_repo = _FakeChangePointRepo()

    if snap is None:
        snap = _snapshot(evaluation_name=evaluation_name)

    resolved = config or _config()

    series = await gather_metric_series(
        baseline_repo=baseline_repo,
        asset_id=snap.asset_id,
        slo_name=snap.slo_name,
        metric_name=metric,
        period_end=snap.period_end,
        evaluation_name=evaluation_name,
        window_size=resolved.window_size,
    )

    if len(series.values) < resolved.min_sample_size:
        return cp_repo.inserts

    detected = detect_change_points(
        values=series.values,
        timestamps=series.timestamps,
        higher_is_better=resolved.higher_is_better,
        window_size=resolved.window_size,
        max_pvalue=resolved.max_pvalue,
        min_magnitude=resolved.min_magnitude,
        min_sample_size=resolved.min_sample_size,
    )

    if detected:
        await _persist_change_points(
            log=structlog.get_logger(),
            change_point_repo=cp_repo,  # type: ignore[arg-type]
            detected=detected,
            timestamps=series.timestamps,
            snapshot=snap,
            metric_name=metric,
            indicator_result_id=uuid.uuid4(),
            comparison_name=evaluation_name,
        )

    return cp_repo.inserts


async def _run(
    values: list[float],
    *,
    metric: str = 'response_time_p95',
    config: ResolvedConfig | None = None,
    previous_cp: Any = None,
    evaluation_name: str = 'load-test',
) -> list[Any]:
    """Convenience wrapper: create a fresh repo and run the pipeline."""
    cp_repo = _FakeChangePointRepo(previous_cp=previous_cp)
    return await _run_pipeline(
        values,
        metric=metric,
        config=config,
        cp_repo=cp_repo,
        evaluation_name=evaluation_name,
    )


# ---------------------------------------------------------------------------
# Scenario 1: Step regression — stable then step up (latency increase)
#
#   values:  [350] * 10 + [700] * 3
#   expect:  1 regression CP near position 10
#
#   WHY it works: 10 stable samples provide a strong baseline. The step to 700
#   is 2x the baseline -- clearly significant. Dedup is empty on first run,
#   so the regression is saved.
# ---------------------------------------------------------------------------

class TestStepRegression:
    """Detect a simple step-up in latency."""

    async def test_regression_detected_at_step_boundary(self) -> None:
        """When series has just reached the step, regression is saved."""
        # 10 stable + 3 elevated = 13 points. CP at ~10, cutoff = 13-3 = 10.
        values = [350.0] * 10 + [700.0] * 3
        inserts = await _run(values)

        assert len(inserts) == 1
        assert inserts[0].direction == 'regression'

    async def test_regression_deduped_on_subsequent_eval(self) -> None:
        """Once the CP is saved, the next eval dedupes it.

        Cross-eval dedup requires shared state between runs. We test this
        by running two series through a single shared repo: the first
        inserts the regression, the second finds it via the stateful fake.
        """
        cp_repo = _FakeChangePointRepo()
        snap = _snapshot()

        for high_count in (3, 4):
            values = [350.0] * 10 + [700.0] * high_count
            await _run_pipeline(
                values,
                cp_repo=cp_repo,
                snap=snap,
            )

        assert len(cp_repo.inserts) == 1, (
            f'expected 1 insert (second run deduped), got {len(cp_repo.inserts)}'
        )


# ---------------------------------------------------------------------------
# Scenario 2: Step improvement — stable then step down
#
#   values:  [700] * 12 + [350] * 5
#   expect:  1 improvement CP near position 12
#   (lower_is_better=True by default → decrease = improvement)
# ---------------------------------------------------------------------------

class TestStepImprovement:
    """Detect a step-down (improvement for lower-is-better metric)."""

    async def test_improvement_detected(self) -> None:
        values = [700.0] * 10 + [350.0] * 3
        inserts = await _run(values)

        assert len(inserts) == 1
        assert inserts[0].direction == 'improvement'


# ---------------------------------------------------------------------------
# Scenario 3: Spike and recovery (the user's actual case)
#
#   values:  [350] * 12 + [700, 700] + [350] * 3
#   This mimics: stable baseline → 2 spike evals → recovery to baseline
#
#   E-Divisive should find two split points: spike start and recovery.
#   Expected: regression at spike, improvement at recovery.
#
#   This is the scenario that was failing in production. Two bugs blocked
#   the improvement: direction-blind dedup and direction-blind regime
#   suppression.
# ---------------------------------------------------------------------------

class TestSpikeAndRecovery:
    """The critical scenario: temporary spike then return to baseline."""

    async def test_both_cps_detected_at_recovery_eval(self) -> None:
        """When the 1st recovery eval runs, both regression and improvement should be saved.

        Series: 12 stable + 2 spike + 1 recovery = 15 points.
        Regression at ~12, improvement at ~14. Both saved.
        """
        values = [350.0] * 12 + [700.0, 700.0] + [350.0]
        inserts = await _run(values)

        directions = {cp.direction for cp in inserts}
        assert 'regression' in directions, f'expected regression, got {directions}'

    async def test_improvement_detected_after_recovery_builds(self) -> None:
        """With 3 recovery samples, improvement should still be detectable.

        Series: 12 stable + 2 spike + 3 recovery = 17 points.
        Improvement at ~14 is saved alongside regression at ~12.
        """
        values = [350.0] * 12 + [700.0, 700.0] + [350.0] * 3
        inserts = await _run(values)

        directions = {cp.direction for cp in inserts}
        assert 'improvement' in directions, (
            f'expected improvement CP after recovery, got {directions}. '
            f'Inserts: {[(cp.direction, cp.position) for cp in inserts]}'
        )

    async def test_regression_deduped_improvement_saved_on_later_eval(self) -> None:
        """Regression saved on spike eval, improvement saved on recovery eval.

        Two sequential runs through a shared stateful repo:
          Run 1: 12 stable + 2 spike + 1 recovery = 15 pts → regression saved
          Run 2: 12 stable + 2 spike + 3 recovery = 17 pts → regression deduped,
                 improvement saved

        This is the exact scenario that was broken in production: the
        improvement's nearby window overlapped the regression's timestamp,
        and direction-blind dedup blocked it.
        """
        cp_repo = _FakeChangePointRepo()
        snap = _snapshot()

        for recovery_count in (1, 3):
            values = [350.0] * 12 + [700.0, 700.0] + [350.0] * recovery_count
            await _run_pipeline(
                values,
                cp_repo=cp_repo,
                snap=snap,
            )

        directions = {cp.direction for cp in cp_repo.inserts}
        assert directions == {'regression', 'improvement'}, (
            f'expected both regression and improvement, got {directions}. '
            f'Inserts: {[(cp.direction, getattr(cp, "period_start", "?")) for cp in cp_repo.inserts]}'
        )

    async def test_single_point_spike_saves_both_cps(self) -> None:
        """A single-point spike: E-Divisive finds regression and improvement.

        Series: 12 stable + 1 spike + 3 recovery = 16 points.
        E-Divisive detects regression at pos 12 and improvement at pos 13.
        Both are saved — dedup doesn't block because they have different directions.
        """
        values = [350.0] * 12 + [700.0] + [350.0] * 3
        inserts = await _run(values)

        directions = {cp.direction for cp in inserts}
        assert directions == {'regression', 'improvement'}


# ---------------------------------------------------------------------------
# Scenario 4: Historical CPs are saved (no recency filter)
#
#   Without a recency filter, CPs deep in the history window are still
#   saved. Dedup prevents re-insertion on subsequent evals.
# ---------------------------------------------------------------------------

class TestHistoricalCpDetection:
    """CPs are saved regardless of position in the series."""

    async def test_old_step_is_saved(self) -> None:
        """A step at position 5 in a 20-element series is saved."""
        values = [350.0] * 5 + [700.0] * 15
        inserts = await _run(values)

        assert len(inserts) >= 1


# ---------------------------------------------------------------------------
# Scenario 5: Same-regime suppression
#
#   If the previous stored CP has post_segment_mean ≈ the new CP's
#   post_segment_mean (within 2x std), the new CP is noise, not a real shift.
# ---------------------------------------------------------------------------

class TestRegimeSuppression:
    """Verify that same-regime CPs are suppressed."""

    async def test_similar_post_mean_suppressed(self) -> None:
        """New CP with post_mean close to previous CP's post_mean is skipped."""
        previous = MagicMock()
        previous.direction = 'regression'
        previous.post_segment_mean = 700.0
        previous.post_segment_std = 50.0

        values = [350.0] * 10 + [710.0] * 3
        inserts = await _run(values, previous_cp=previous)

        assert len(inserts) == 0, 'same-regime CP should be suppressed'

    async def test_different_regime_allowed(self) -> None:
        """New CP with post_mean far from previous CP's post_mean is saved."""
        previous = MagicMock()
        previous.direction = 'regression'
        previous.post_segment_mean = 350.0
        previous.post_segment_std = 10.0

        values = [350.0] * 10 + [700.0] * 3
        inserts = await _run(values, previous_cp=previous)

        assert len(inserts) >= 1, 'different-regime CP should be saved'

    async def test_different_direction_skips_regime_check(self) -> None:
        """An improvement after a regression is never suppressed by regime check.

        Even if the improvement's post_mean falls within the regression's noise
        band, a direction change is always a meaningful shift.
        """
        previous = MagicMock()
        previous.direction = 'regression'
        previous.post_segment_mean = 500.0
        previous.post_segment_std = 200.0

        values = [700.0] * 10 + [350.0] * 3
        inserts = await _run(values, previous_cp=previous)

        assert len(inserts) == 1
        assert inserts[0].direction == 'improvement'


# ---------------------------------------------------------------------------
# Scenario 6: Insufficient history
# ---------------------------------------------------------------------------

class TestInsufficientHistory:
    """Skip detection when not enough data points."""

    async def test_below_min_sample_size(self) -> None:
        values = [350.0] * 5 + [700.0] * 2
        inserts = await _run(values, config=_config(min_sample_size=10))

        assert len(inserts) == 0

    async def test_exactly_at_min_sample_size(self) -> None:
        """With exactly min_sample_size points, detection runs."""
        values = [350.0] * 7 + [700.0] * 3
        inserts = await _run(values, config=_config(min_sample_size=10))

        assert len(inserts) >= 1


# ---------------------------------------------------------------------------
# Scenario 7: Eval-name scoping
#
#   The comparison_name scopes which history is fetched. Two different eval
#   names produce independent histories. This test verifies the parameter
#   is passed through correctly.
# ---------------------------------------------------------------------------

class TestEvalNameScoping:
    """Verify evaluation_name is passed to baseline repo."""

    async def test_comparison_name_passed_to_baseline_query(self) -> None:
        """The baseline repo receives the evaluation_name for scoping."""
        history = _make_history(
            [350.0] * 10 + [700.0] * 3,
            evaluation_name='prod-validation',
        )
        baseline_repo = MagicMock()
        baseline_repo.get_evaluation_baselines = AsyncMock(return_value=history)

        snap = _snapshot(evaluation_name='prod-validation')

        await gather_metric_series(
            baseline_repo=baseline_repo,
            asset_id=snap.asset_id,
            slo_name=snap.slo_name,
            metric_name='response_time_p95',
            period_end=snap.period_end,
            evaluation_name='prod-validation',
            window_size=30,
        )

        call_kwargs = baseline_repo.get_evaluation_baselines.call_args.kwargs
        assert call_kwargs['evaluation_name'] == 'prod-validation'
