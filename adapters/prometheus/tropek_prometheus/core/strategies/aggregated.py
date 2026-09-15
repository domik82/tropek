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
    ) -> tuple[dict[str, float | None], dict[str, str], dict[str, Any] | None]:
        """Execute an aggregated query: fetch range data, compute stats."""
        query_template = query_spec['query_template']
        interval = query_spec['interval']
        method_strings: list[str] = query_spec['methods']
        methods = [AggregationMethod(m) for m in method_strings]

        # Reject an inverted window before querying. Prometheus refuses it anyway, and the sample
        # expectation below would go negative and clamp to 1, dressing the failure up as a
        # coverage percentage instead of an error.
        if datetime.fromisoformat(end) <= datetime.fromisoformat(start):
            logger.warning('window end is not after its start: sli=%s start=%s end=%s', sli_name, start, end)
            error_msg = f'window end must be after start: start={start} end={end}'
            bad_window_values: dict[str, float | None] = {f'{sli_name}.{m}': None for m in methods}
            bad_window_errors: dict[str, str] = {f'{sli_name}.{m}': error_msg for m in methods}
            return bad_window_values, bad_window_errors, None

        # Substitute variables with $interval override
        try:
            query = substitute(
                query_template,
                variables,
                start_iso=start,
                end_iso=end,
                interval_override=interval,
            )
        except UnresolvedVariableError as exc:
            logger.warning('variable substitution failed: sli=%s error=%s', sli_name, exc)
            error_msg = str(exc)
            early_values: dict[str, float | None] = {f'{sli_name}.{m}': None for m in methods}
            early_errors: dict[str, str] = {f'{sli_name}.{m}': error_msg for m in methods}
            return early_values, early_errors, None

        # Fetch data (with chunking for long time ranges)
        all_values, chunks_failed, series_count = await self._fetch_range(
            sli_name=sli_name,
            query=query,
            start=start,
            end=end,
            step=interval,
        )

        # Compute expected sample count. query_range evaluates at both endpoints, so a window of
        # N steps yields N+1 points; without the +1 a fully covered window reports negative missing_pct.
        interval_seconds = _parse_duration_seconds(interval)
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        eval_window_seconds = (end_dt - start_dt).total_seconds()
        points_per_series = max(1, int(eval_window_seconds / interval_seconds) + 1)
        # `actual_samples` counts every point of every series, so the expectation has to cover the
        # same ground: a query with no aggregation operator fans out to one series per instance or
        # label combination. A query matching nothing still expects one series' worth of points, so
        # that an empty result reads as fully missing rather than as a vacuous 0/0.
        expected_samples = points_per_series * max(1, series_count)

        # Filter NaN for actual count (stats module also filters, but we need count for metadata)
        actual_samples = sum(1 for v in all_values if not math.isnan(v))

        # Compute statistics
        stats = compute_statistics(all_values, methods)

        # Build result dicts — keys are plain strings for JSON serialization
        values: dict[str, float | None] = {}
        errors: dict[str, str] = {}
        for method in methods:
            key = f'{sli_name}.{method}'
            val = stats[method]
            values[key] = val
            if val is None:
                errors[key] = 'no valid data points'

        # Build metadata
        missing_pct = round((1 - actual_samples / expected_samples) * 100, 1)
        metadata: dict[str, Any] = {
            'mode': 'aggregated',
            'expected_samples': expected_samples,
            'actual_samples': actual_samples,
            'missing_pct': missing_pct,
            'chunks_failed': chunks_failed,
        }

        logger.info(
            'aggregated result: sli=%s methods=%s actual=%d/%d chunks_failed=%d',
            sli_name,
            methods,
            actual_samples,
            expected_samples,
            chunks_failed,
        )
        return values, errors, metadata

    async def _fetch_range(
        self,
        *,
        sli_name: str,
        query: str,
        start: str,
        end: str,
        step: str,
    ) -> tuple[list[float], int, int]:
        """Fetch range data, chunking if the window exceeds chunk_size.

        Returns (all_values, chunks_failed_count, series_count). ``series_count`` is the widest
        fan-out seen across chunks, so callers can scale a per-series expectation to match the
        flattened values.
        """
        step_seconds = _parse_duration_seconds(step)
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        window_seconds = (end_dt - start_dt).total_seconds()

        if window_seconds <= self._chunk_size_seconds:
            try:
                series = await self._client.range_query_series(query, start=start, end=end, step=step)
                return [value for bucket in series for value in bucket], 0, len(series)
            except PrometheusQueryError as exc:
                logger.warning(
                    'range query returned no data: sli=%s query=%s start=%s end=%s error=%s',
                    sli_name,
                    query,
                    start,
                    end,
                    exc,
                )
                return [], 1, 0

        # Split into chunks. Each chunk's query_range evaluates at both its endpoints, so the next
        # chunk starts one step past the previous chunk's end — otherwise the shared instant comes
        # back twice, inflating the sample count and over-weighting that point in every statistic.
        chunks: list[tuple[str, str]] = []
        chunk_start = start_dt
        while chunk_start <= end_dt:
            chunk_end = min(chunk_start + timedelta(seconds=self._chunk_size_seconds), end_dt)
            chunks.append((chunk_start.isoformat(), chunk_end.isoformat()))
            chunk_start = chunk_end + timedelta(seconds=step_seconds)

        all_values: list[float] = []
        chunks_failed = 0

        # Process chunks with limited parallelism
        sem = asyncio.Semaphore(self._parallel_chunks)

        async def _fetch_chunk(c_start: str, c_end: str) -> list[list[float]] | None:
            async with sem:
                try:
                    return await self._client.range_query_series(query, start=c_start, end=c_end, step=step)
                except PrometheusQueryError as exc:
                    logger.warning(
                        'chunk returned no data: sli=%s query=%s start=%s end=%s error=%s',
                        sli_name,
                        query,
                        c_start,
                        c_end,
                        exc,
                    )
                    return None

        tasks = [_fetch_chunk(cs, ce) for cs, ce in chunks]
        results = await asyncio.gather(*tasks)

        series_count = 0
        for chunk_result in results:
            if chunk_result is None:
                chunks_failed += 1
            else:
                series_count = max(series_count, len(chunk_result))
                all_values.extend(value for bucket in chunk_result for value in bucket)

        return all_values, chunks_failed, series_count
