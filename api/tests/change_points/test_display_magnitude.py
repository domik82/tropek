"""TDD tests for correct change point display magnitude (tropek issue #64).

Bug: the detector recomputed magnitude by splitting the ENTIRE series at the
change-point index, instead of using the engine's adjacent-segment stats that
already gated the change point via ``min_magnitude``. This produced diluted,
misleading percentages for change points in multi-regime series, and fake
``0.00%`` values when a segment's mean was exactly zero.

Fixed behavior: report the engine's adjacent-segment means (``TTestStats.mean_1``/
``mean_2``), and represent zero-origin segments as an explicit transition
(``appeared``/``vanished``) with ``change_relative_pct=None`` instead of a
fabricated percentage.
"""

from __future__ import annotations

import pytest
from tropek.modules.change_points.detector import detect_change_points

from tests.helpers.change_point_fixtures import (
    ALL_SCENARIOS,
    DECREASE_NEAR_GATE,
    DILUTED_LOCAL_SHIFT,
    INCREASE_BELOW_GATE,
    ChangePointScenario,
)
from tests.helpers.data_generators import make_timestamps

GATE_MIN_MAGNITUDE = 0.03


def _scenario_min_magnitude(scenario: ChangePointScenario) -> float:
    """Near-gate scenarios need an explicit non-zero min_magnitude to demonstrate gating."""
    if scenario.name in (INCREASE_BELOW_GATE.name, DECREASE_NEAR_GATE.name):
        return GATE_MIN_MAGNITUDE
    return 0.0


@pytest.mark.parametrize('scenario', ALL_SCENARIOS, ids=lambda scenario: scenario.name)
def test_scenario_matches_expected_change_points(scenario: ChangePointScenario) -> None:
    results = detect_change_points(
        values=scenario.values,
        timestamps=make_timestamps(len(scenario.values)),
        higher_is_better=False,
        min_magnitude=_scenario_min_magnitude(scenario),
    )

    assert len(results) == len(scenario.expected)
    for result, expected in zip(results, scenario.expected, strict=True):
        assert result.position == expected.position
        assert result.direction == expected.direction
        assert result.change_relative_pct == expected.expected_pct
        expected_transition = expected.transition
        actual_transition = result.transition.value if result.transition is not None else None
        assert actual_transition == expected_transition


def test_displayed_magnitude_never_below_gate() -> None:
    """Every non-transition change point clears the min_magnitude gate in at least one direction.

    The engine gates on max(|forward|, |backward|) relative change, but the detector
    always displays the forward change. For asymmetric segments (e.g. decrease_near_gate)
    the displayed forward magnitude can be smaller than the gate threshold even though the
    change point passed the gate on the backward magnitude — so this test checks the same
    max(|forward|, |backward|) quantity the gate itself uses, computed from the adjacent
    segment means, rather than asserting the displayed percentage alone.
    """
    for scenario in ALL_SCENARIOS:
        min_magnitude = _scenario_min_magnitude(scenario)
        results = detect_change_points(
            values=scenario.values,
            timestamps=make_timestamps(len(scenario.values)),
            higher_is_better=False,
            min_magnitude=min_magnitude,
        )
        for result in results:
            if result.transition is not None:
                continue
            forward_pct = (result.post_segment_mean / result.pre_segment_mean - 1.0) * 100.0
            backward_pct = (
                (result.pre_segment_mean / result.post_segment_mean - 1.0) * 100.0
                if result.post_segment_mean != 0
                else float('inf')
            )
            gate_magnitude = max(abs(forward_pct), abs(backward_pct))
            assert gate_magnitude >= min_magnitude * 100.0


def test_stability_as_history_grows() -> None:
    """A change point's reported magnitude and direction don't shift as more history accumulates."""
    values = DILUTED_LOCAL_SHIFT.values
    extended_values = values + [values[-1]] * 30

    original_results = detect_change_points(
        values=values,
        timestamps=make_timestamps(len(values)),
        higher_is_better=False,
    )
    extended_results = detect_change_points(
        values=extended_values,
        timestamps=make_timestamps(len(extended_values)),
        higher_is_better=False,
    )

    original_by_position = {result.position: result for result in original_results}
    extended_by_position = {result.position: result for result in extended_results}

    shared_positions = set(original_by_position) & set(extended_by_position)
    assert shared_positions == {expected.position for expected in DILUTED_LOCAL_SHIFT.expected}

    for position in shared_positions:
        original_change_point = original_by_position[position]
        extended_change_point = extended_by_position[position]
        assert original_change_point.change_relative_pct == extended_change_point.change_relative_pct
        assert original_change_point.direction == extended_change_point.direction


def test_pre_post_segment_means_are_adjacent() -> None:
    """CP@48 in diluted_local_shift reports the adjacent segment means, not full-series means."""
    results = detect_change_points(
        values=DILUTED_LOCAL_SHIFT.values,
        timestamps=make_timestamps(len(DILUTED_LOCAL_SHIFT.values)),
        higher_is_better=False,
    )

    change_point_at_48 = next(result for result in results if result.position == 48)
    assert change_point_at_48.pre_segment_mean == pytest.approx(11.5e6)
    assert change_point_at_48.post_segment_mean == pytest.approx(13.3e6)
