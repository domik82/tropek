"""Common enums and message types for the TROPEK API."""

from enum import StrEnum

from pydantic import BaseModel


class Direction(StrEnum):
    """Evaluation trend direction."""

    REGRESSION = 'regression'
    IMPROVEMENT = 'improvement'


class AggregateFunction(StrEnum):
    """Aggregation function for SLI values."""

    AVG = 'avg'
    P50 = 'p50'
    P90 = 'p90'
    P95 = 'p95'
    P99 = 'p99'


class AggregationMethod(StrEnum):
    """Aggregation method for comparison baseline calculation."""

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


class CategoryColor(StrEnum):
    """Color category for UI rendering."""

    SKY = 'sky'
    GREEN = 'green'
    AMBER = 'amber'
    RED = 'red'
    PURPLE = 'purple'
    PINK = 'pink'
    SLATE = 'slate'
    GRAY = 'gray'


class ErrorMessage(BaseModel):
    """API error response."""

    detail: str


class TagKeyCount(BaseModel):
    """Tag key with occurrence count."""

    key: str
    count: int


class TagValueCount(BaseModel):
    """Tag value with occurrence count."""

    value: str
    count: int
