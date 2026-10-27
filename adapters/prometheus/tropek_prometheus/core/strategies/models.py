"""Models shared by the query strategies."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

ErrorKind = Literal['transient', 'data']


class ChunkFailure(BaseModel):
    """One chunk of a range fetch that did not return data."""

    model_config = ConfigDict(frozen=True)

    message: str
    transient: bool


class RangeFetch(BaseModel):
    """The outcome of fetching one metric's window as a list of chunks."""

    model_config = ConfigDict(frozen=True)

    values: list[float]
    series_count: int
    chunks_total: int
    failures: list[ChunkFailure]

    @property
    def chunks_failed(self) -> int:
        """Number of chunks that returned no data."""
        return len(self.failures)

    @property
    def error_kind(self) -> ErrorKind:
        """``'transient'`` only when every failed chunk may succeed on retry, else ``'data'``.

        A fetch without failures also reports ``'data'``; callers check ``chunks_failed`` before using it.
        """
        if self.failures and all(failure.transient for failure in self.failures):
            return 'transient'
        return 'data'

    @property
    def last_failure_message(self) -> str | None:
        """Message of the last failed chunk in chunk order, or ``None`` when every chunk succeeded."""
        return self.failures[-1].message if self.failures else None


class IndicatorOutcome(BaseModel):
    """The result of one indicator: a value, or the error that prevented one."""

    model_config = ConfigDict(frozen=True)

    value: float | None
    error: str | None = None
    error_kind: ErrorKind | None = None

    @model_validator(mode='after')
    def _kind_goes_with_error(self) -> IndicatorOutcome:
        if (self.error is None) != (self.error_kind is None):
            raise ValueError('error_kind must be set exactly when error is set')
        return self


class AggregatedMetadata(BaseModel):
    """Sample coverage of an aggregated query, stored beside its results."""

    model_config = ConfigDict(frozen=True)

    mode: Literal['aggregated']
    expected_samples: int
    actual_samples: int
    missing_pct: float
    chunks_failed: int
    chunks_total: int


class StrategyResult(BaseModel):
    """What a query strategy returns: one outcome per indicator, plus optional metadata."""

    model_config = ConfigDict(frozen=True)

    indicators: dict[str, IndicatorOutcome]
    metadata: AggregatedMetadata | None = None
