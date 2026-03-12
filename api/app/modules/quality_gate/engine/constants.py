"""String constants for the SLO evaluation engine.

All StrEnum values used across engine modules are defined here so that callers
can reference symbolic names instead of raw string literals.
"""

from __future__ import annotations

from enum import StrEnum


class CriteriaType(StrEnum):
    """Whether a criterion compares against a fixed value or a relative baseline."""

    FIXED = "fixed"
    RELATIVE = "relative"


class IndicatorStatus(StrEnum):
    """Result status of a single SLI evaluation."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    INFO = "info"
    ERROR = "error"


class EvaluationOutcome(StrEnum):
    """Overall result of a weighted SLO evaluation.

    Used as the ``result`` field on :class:`TotalScore` and
    :class:`EvaluationResult`.  Because it subclasses ``StrEnum``, comparisons
    with plain strings (e.g. ``outcome == "pass"``) work without casting.
    """

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
