"""Aggregated query strategy — fetches time-series via query_range, computes statistics."""

from __future__ import annotations

import asyncio
import logging
import math
import re
from datetime import datetime, timedelta
from typing import Any

from tropek_prometheus.core.methods import AggregationMethod
from tropek_prometheus.core.prometheus_client import PrometheusClient, PrometheusQueryError
from tropek_prometheus.core.stats import compute_statistics
from tropek_prometheus.core.strategies.models import (
    AggregatedMetadata,
    ChunkFailure,
    ErrorKind,
    IndicatorOutcome,
    RangeFetch,
    StrategyResult,
)
from tropek_prometheus.core.variable_substitutor import UnresolvedVariableError, substitute

logger = logging.getLogger(__name__)

_DURATION_RE = re.compile(r'^(\d+)([smhd])$')
_DURATION_MULTIPLIERS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}


def _parse_duration_seconds(duration: str) -> int:
    """Parse a Prometheus-style duration string (e.g. '4h', '1m') to seconds.

    :param str duration: Duration such as ``30s``, ``1m``, ``4h`` or ``1d``.
    :returns: The duration in seconds.
    :rtype: int
    :raises ValueError: If the format is unrecognised, or the duration is zero.
    """
    match = _DURATION_RE.match(duration)
    if not match:
        raise ValueError(f'invalid duration format: {duration}')
    seconds = int(match.group(1)) * _DURATION_MULTIPLIERS[match.group(2)]
    if seconds <= 0:
        # A zero step divides by zero when sizing the expectation, and leaves the chunk loop
        # unable to advance past the window end.
        raise ValueError(f'duration must be greater than zero: {duration}')
    return seconds


def _error_for_every_method(
    sli_name: str,
    methods: list[AggregationMethod],
    message: str,
    error_kind: ErrorKind,
) -> dict[str, IndicatorOutcome]:
    """Build the outcomes that fail every method of an SLI with the same error.

    :param str sli_name: SLI the methods belong to.
    :param list[AggregationMethod] methods: Methods to fail.
    :param str message: Error message shared by every method.
    :param ErrorKind error_kind: ``transient`` when a retry may help, ``data`` otherwise.
    :returns: Failed outcomes keyed by ``<sli_name>.<method>``.
    :rtype: dict[str, IndicatorOutcome]
    """
    failed = IndicatorOutcome(value=None, error=message, error_kind=error_kind)
    return {f'{sli_name}.{method}': failed for method in methods}


def _sample_coverage(
    *,
    step_seconds: int,
    window_seconds: float,
    series_count: int,
    values: list[float],
) -> tuple[int, int, float]:
    """Compare the samples a window should hold with the ones that arrived.

    :param int step_seconds: Query step in seconds.
    :param float window_seconds: Length of the evaluated window in seconds.
    :param int series_count: Number of series the query fanned out to.
    :param list[float] values: Every point of every series; ``NaN`` points do not count as arrived.
    :returns: ``(expected_samples, actual_samples, missing_pct)``.
    :rtype: tuple[int, int, float]
    """
    # query_range evaluates at both endpoints, so a window of N steps yields N+1 points; without
    # the +1 a fully covered window reports negative missing_pct.
    points_per_series = max(1, int(window_seconds / step_seconds) + 1)
    # `actual_samples` counts every point of every series, so the expectation has to cover the
    # same ground: a query with no aggregation operator fans out to one series per instance or
    # label combination. A query matching nothing still expects one series' worth of points, so
    # that an empty result reads as fully missing rather than as a vacuous 0/0.
    expected_samples = points_per_series * max(1, series_count)
    # Filter NaN for actual count (stats module also filters, but we need count for metadata)
    actual_samples = sum(1 for value in values if not math.isnan(value))
    missing_pct = round((1 - actual_samples / expected_samples) * 100, 1)
    return expected_samples, actual_samples, missing_pct


class AggregatedQueryStrategy:
    """Fetches time-series via query_range, computes requested statistical methods."""

    def __init__(
        self,
        client: PrometheusClient,
        chunk_size: str = '4h',
        parallel_chunks: int = 3,
    ) -> None:
        self._client = client
        self._chunk_size_seconds = _parse_duration_seconds(chunk_size)
        self._parallel_chunks = parallel_chunks

    async def execute(
        self,
        *,
        sli_name: str,
        query_spec: dict[str, Any],
        variables: dict[str, str],
        start: str,
        end: str,
    ) -> StrategyResult:
        """Execute an aggregated query: fetch range data, compute stats.

        An incomplete fetch (any chunk failed) is an error for every method, never a statistic over
        partial data. Its kind is ``'transient'`` only when every failed chunk may succeed on retry.
        """
        query_template = query_spec['query_template']
        interval = query_spec['interval']
        method_strings: list[str] = query_spec['methods']
        methods = [AggregationMethod(method) for method in method_strings]

        # Reject an inverted window before querying. Prometheus refuses it anyway, and the sample
        # expectation below would go negative and clamp to 1, dressing the failure up as a
        # coverage percentage instead of an error.
        if datetime.fromisoformat(end) <= datetime.fromisoformat(start):
            logger.warning(f'window end is not after its start: sli={sli_name} start={start} end={end}')
            error_msg = f'window end must be after start: start={start} end={end}'
            return StrategyResult(indicators=_error_for_every_method(sli_name, methods, error_msg, 'data'))

        # Substitute variables with $interval override
        try:
            query = substitute(
                query_template,
                variables,
                start_iso=start,
                end_iso=end,
                interval_override=interval,
            )
        except UnresolvedVariableError as substitution_error:
            logger.warning(f'variable substitution failed: sli={sli_name} error={substitution_error}')
            return StrategyResult(
                indicators=_error_for_every_method(sli_name, methods, str(substitution_error), 'data')
            )

        # Fetch data (with chunking for long time ranges)
        fetch = await self._fetch_range(sli_name=sli_name, query=query, start=start, end=end, step=interval)

        window_seconds = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
        expected_samples, actual_samples, missing_pct = _sample_coverage(
            step_seconds=_parse_duration_seconds(interval),
            window_seconds=window_seconds,
            series_count=fetch.series_count,
            values=fetch.values,
        )

        # A statistic over partial data would be silently wrong, so an incomplete fetch is an error
        # for every method. A retry only helps when every failed chunk was transient. The metadata
        # still carries the sample counts of the chunks that did arrive, as every aggregated result does.
        metadata = AggregatedMetadata(
            mode='aggregated',
            expected_samples=expected_samples,
            actual_samples=actual_samples,
            missing_pct=missing_pct,
            chunks_failed=fetch.chunks_failed,
            chunks_total=fetch.chunks_total,
        )
        if fetch.chunks_failed:
            message = (
                f'incomplete data: {fetch.chunks_failed} of {fetch.chunks_total} chunks failed '
                f'(last: {fetch.last_failure_message})'
            )
            logger.warning(f'aggregated result incomplete: sli={sli_name} {message}')
            return StrategyResult(
                indicators=_error_for_every_method(sli_name, methods, message, fetch.error_kind),
                metadata=metadata,
            )

        # Compute statistics
        stats = compute_statistics(fetch.values, methods)

        indicators: dict[str, IndicatorOutcome] = {}
        for method in methods:
            statistic = stats[method]
            if statistic is None:
                indicators[f'{sli_name}.{method}'] = IndicatorOutcome(
                    value=None, error='no valid data points', error_kind='data'
                )
            else:
                indicators[f'{sli_name}.{method}'] = IndicatorOutcome(value=statistic)

        logger.info(
            f'aggregated result: sli={sli_name} methods={methods} actual={actual_samples}/{expected_samples} '
            f'chunks_failed={fetch.chunks_failed}'
        )
        return StrategyResult(indicators=indicators, metadata=metadata)

    @staticmethod
    def indicator_names(sli_name: str, query_spec: dict[str, Any]) -> list[str]:
        """Return the indicator names a query reports under: one per method for aggregated, else the SLI name.

        :param str sli_name: Name of the SLI.
        :param dict[str, Any] query_spec: The SLI's query specification.
        :returns: Indicator names the query's strategy would have produced results for.
        :rtype: list[str]
        """
        if query_spec.get('mode', 'raw') == 'aggregated':
            return [f'{sli_name}.{method}' for method in query_spec.get('methods', [])]
        return [sli_name]

    async def _fetch_range(
        self,
        *,
        sli_name: str,
        query: str,
        start: str,
        end: str,
        step: str,
    ) -> RangeFetch:
        """Fetch range data as a list of chunks; a window no longer than the chunk size is one chunk.

        ``series_count`` of the result is the widest fan-out seen across chunks, so callers can scale a
        per-series expectation to match the flattened values.
        """
        step_seconds = _parse_duration_seconds(step)
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)

        # Each chunk's query_range evaluates at both its endpoints, so the next chunk starts one step
        # past the previous chunk's end — otherwise the shared instant comes back twice, inflating the
        # sample count and over-weighting that point in every statistic.
        chunks: list[tuple[str, str]] = []
        chunk_start = start_dt
        while chunk_start <= end_dt:
            chunk_end = min(chunk_start + timedelta(seconds=self._chunk_size_seconds), end_dt)
            chunks.append((chunk_start.isoformat(), chunk_end.isoformat()))
            chunk_start = chunk_end + timedelta(seconds=step_seconds)

        # Process chunks with limited parallelism
        chunk_slots = asyncio.Semaphore(self._parallel_chunks)

        async def _fetch_chunk(chunk_start_iso: str, chunk_end_iso: str) -> list[list[float]] | PrometheusQueryError:
            async with chunk_slots:
                try:
                    return await self._client.range_query_series(
                        query, start=chunk_start_iso, end=chunk_end_iso, step=step
                    )
                except PrometheusQueryError as query_error:
                    logger.warning(
                        f'chunk returned no data: sli={sli_name} query={query} start={chunk_start_iso} '
                        f'end={chunk_end_iso} error={query_error}'
                    )
                    return query_error

        results = await asyncio.gather(
            *[_fetch_chunk(chunk_start_iso, chunk_end_iso) for chunk_start_iso, chunk_end_iso in chunks]
        )

        values: list[float] = []
        failures: list[ChunkFailure] = []
        series_count = 0
        for chunk_result in results:
            if isinstance(chunk_result, PrometheusQueryError):
                failures.append(ChunkFailure(message=str(chunk_result), transient=chunk_result.transient))
            else:
                series_count = max(series_count, len(chunk_result))
                values.extend(value for bucket in chunk_result for value in bucket)

        return RangeFetch(values=values, series_count=series_count, chunks_total=len(chunks), failures=failures)
