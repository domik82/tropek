"""Aggregation method enum — single source of truth for method names."""

from enum import StrEnum


class AggregationMethod(StrEnum):
    """Statistical aggregation methods available in aggregated query mode.

    StrEnum values ARE strings, so AggregationMethod.P99 == 'p99' is True.
    Works transparently with JSON, Pydantic, dict keys, and f-strings.
    """

    MIN = 'min'
    MEAN = 'mean'
    MAX = 'max'
    STD = 'std'
    SUM = 'sum'
    MEDIAN = 'median'
    P75 = 'p75'
    P90 = 'p90'
    P95 = 'p95'
    P99 = 'p99'
