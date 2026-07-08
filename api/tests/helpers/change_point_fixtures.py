"""Fixture scenarios for change point display-magnitude tests (tropek issue #64).

Each scenario pairs a raw value series with the expected detected change points,
where expected values are the CORRECT (fixed) behavior: adjacent-segment means
gated by the engine's min_magnitude check, not full-series split means.

Expected values were measured against the real E-Divisive engine's adjacent-segment
stats (``TTestStats.mean_1``/``mean_2``) — treat them as ground truth.
"""

from __future__ import annotations

from pydantic import BaseModel


class ExpectedChangePoint(BaseModel):
    """A single expected change point within a scenario."""

    position: int
    direction: str
    expected_pct: float | None
    transition: str | None = None


class ChangePointScenario(BaseModel):
    """A named value series plus the change points expected from it."""

    name: str
    values: list[float]
    expected: list[ExpectedChangePoint]


DILUTED_LOCAL_SHIFT = ChangePointScenario(
    name='diluted_local_shift',
    values=[13.6e6] * 40 + [11.5e6] * 8 + [13.3e6] * 12,
    expected=[
        ExpectedChangePoint(position=40, direction='improvement', expected_pct=-15.44),
        ExpectedChangePoint(position=48, direction='regression', expected_pct=15.65),
    ],
)

ZERO_ORIGIN_APPEAR = ChangePointScenario(
    name='zero_origin_appear',
    values=[0.0] * 24 + [500.0] * 24,
    expected=[
        ExpectedChangePoint(position=24, direction='regression', expected_pct=None, transition='appeared'),
    ],
)

VANISH = ChangePointScenario(
    name='vanish',
    values=[500.0] * 24 + [0.0] * 24,
    expected=[
        ExpectedChangePoint(position=24, direction='improvement', expected_pct=None, transition='vanished'),
    ],
)

INCREASE_BELOW_GATE = ChangePointScenario(
    name='increase_below_gate',
    values=[100.0] * 24 + [102.95] * 24,
    expected=[],
)

DECREASE_NEAR_GATE = ChangePointScenario(
    name='decrease_near_gate',
    values=[100.0] * 24 + [97.05] * 24,
    expected=[
        ExpectedChangePoint(position=24, direction='improvement', expected_pct=-2.95),
    ],
)

ALL_SCENARIOS = [
    DILUTED_LOCAL_SHIFT,
    ZERO_ORIGIN_APPEAR,
    VANISH,
    INCREASE_BELOW_GATE,
    DECREASE_NEAR_GATE,
]
