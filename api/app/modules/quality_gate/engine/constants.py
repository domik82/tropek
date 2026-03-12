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


class CompareWith(StrEnum):
    """Selects how many previous evaluations are used as the comparison baseline."""

    SINGLE_RESULT = "single_result"
    SEVERAL_RESULTS = "several_results"


class IncludeResultWithScore(StrEnum):
    """Filter that determines which previous evaluations are eligible as baselines."""

    ALL = "all"
    PASS_OR_WARN = "pass_or_warn"
    PASS = "pass"


class AggregateFunction(StrEnum):
    """Aggregation function applied to a set of baseline values.

    Used in both :mod:`slo_parser` (SLO comparison defaults) and
    :mod:`criteria` (``aggregate_values`` implementation) — the single source
    of truth for valid function names across both modules.
    """

    AVG = "avg"
    P50 = "p50"
    P90 = "p90"
    P95 = "p95"
    P99 = "p99"
