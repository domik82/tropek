"""Aggregated query strategy — fetches time-series via query_range, computes statistics."""

from __future__ import annotations

import asyncio
import logging
import math
import re
from datetime import datetime, timedelta
from typing import Any

from app.core.methods import AggregationMethod
from app.core.prometheus_client import PrometheusClient, PrometheusQueryError
from app.core.stats import compute_statistics
from app.core.variable_substitutor import UnresolvedVariableError, substitute

logger = logging.getLogger(__name__)

_DURATION_RE = re.compile(r'^(\d+)([smhd])$')
_DURATION_MULTIPLIERS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}


def _parse_duration_seconds(duration: str) -> int:
    """Parse a Prometheus-style duration string (e.g. '4h', '1m') to seconds."""
    match = _DURATION_RE.match(duration)
    if not match:
        raise ValueError(f'invalid duration format: {duration}')
    return int(match.group(1)) * _DURATION_MULTIPLIERS[match.group(2)]


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
            values = {f'{sli_name}.{m}': None for m in methods}
            errors = {f'{sli_name}.{m}': error_msg for m in methods}
            return values, errors, None

        # Fetch data (with chunking for long time ranges)
        all_values, chunks_failed = await self._fetch_range(
            query=query, start=start, end=end, step=interval
        )

        # Compute expected sample count
        interval_seconds = _parse_duration_seconds(interval)
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        eval_window_seconds = (end_dt - start_dt).total_seconds()
        expected_samples = max(1, int(eval_window_seconds / interval_seconds))

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
        missing_pct = (
            round((1 - actual_samples / expected_samples) * 100, 1)
            if expected_samples > 0
            else 0.0
        )
        metadata: dict[str, Any] = {
            'mode': 'aggregated',
            'expected_samples': expected_samples,
            'actual_samples': actual_samples,
            'missing_pct': missing_pct,
            'chunks_failed': chunks_failed,
        }

        logger.info(
            'aggregated result: sli=%s methods=%s actual=%d/%d chunks_failed=%d',
            sli_name, methods, actual_samples, expected_samples, chunks_failed,
        )
        return values, errors, metadata

    async def _fetch_range(
        self, *, query: str, start: str, end: str, step: str
    ) -> tuple[list[float], int]:
        """Fetch range data, chunking if the window exceeds chunk_size.

        Returns (all_values, chunks_failed_count).
        """
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        window_seconds = (end_dt - start_dt).total_seconds()

        if window_seconds <= self._chunk_size_seconds:
            try:
                values = await self._client.range_query(
                    query, start=start, end=end, step=step
                )
                return values, 0
            except PrometheusQueryError:
                logger.exception('range query failed: query=%s', query)
                return [], 1

        # Split into chunks
        chunks: list[tuple[str, str]] = []
        chunk_start = start_dt
        while chunk_start < end_dt:
            chunk_end = min(chunk_start + timedelta(seconds=self._chunk_size_seconds), end_dt)
            chunks.append((chunk_start.isoformat(), chunk_end.isoformat()))
            chunk_start = chunk_end

        all_values: list[float] = []
        chunks_failed = 0

        # Process chunks with limited parallelism
        sem = asyncio.Semaphore(self._parallel_chunks)

        async def _fetch_chunk(c_start: str, c_end: str) -> list[float] | None:
            async with sem:
                try:
                    return await self._client.range_query(
                        query, start=c_start, end=c_end, step=step
                    )
                except PrometheusQueryError:
                    logger.exception(
                        'chunk failed: query=%s start=%s end=%s', query, c_start, c_end
                    )
                    return None

        tasks = [_fetch_chunk(cs, ce) for cs, ce in chunks]
        results = await asyncio.gather(*tasks)

        for chunk_result in results:
            if chunk_result is None:
                chunks_failed += 1
            else:
                all_values.extend(chunk_result)

        return all_values, chunks_failed
