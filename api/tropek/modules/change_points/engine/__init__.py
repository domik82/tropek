"""E-Divisive change point detection engine.

Derived from Apache Otava (https://github.com/apache/otava).
See NOTICE file in this directory for attribution.

Algorithm: "Hunter: Using Change Point Detection to Hunt for Performance
Regressions" by Fleming et al. (https://doi.org/10.1145/3578244.3583719).
"""

from tropek.modules.change_points.engine.analysis import (
    TTestSignificanceTester,
    TTestStats,
    merge,
    split,
)
from tropek.modules.change_points.engine.base import (
    CandidateChangePoint,
    ChangePoint,
    fill_missing,
)
from tropek.modules.change_points.engine.calculator import PairDistanceCalculator
from tropek.modules.change_points.engine.detector import ChangePointDetector

__all__ = [
    'CandidateChangePoint',
    'ChangePoint',
    'ChangePointDetector',
    'PairDistanceCalculator',
    'TTestSignificanceTester',
    'TTestStats',
    'fill_missing',
    'merge',
    'split',
]
