"""TimescaleDB shaper — raw latency rows + per-second counter/gauge metrics."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pandas as pd

from slo_generator.raw import RawChunk
from slo_generator.shapers.base import BaseShaper


class TimescaleDBShaper(BaseShaper):
    """Shapes RawChunk into TimescaleDB-ready rows.

    Emits two DataFrames per chunk:
    1. Metrics table (counter/gauge): timestamp, metric, service, host, value
       - http_requests_total, http_errors_total, cpu_usage_percent, memory_usage_bytes
    2. Latencies table: timestamp, service, host, latency_ms
       - One row per individual request latency

    TimescaleDB computes exact percentiles at query time using
    percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms).
    """

    def shape(self, raw_chunk: RawChunk) -> Iterator[pd.DataFrame]:
        """Emit metrics rows and individual latency rows as separate DataFrames."""
        metric_rows: list[dict[str, Any]] = []
        latency_rows: list[dict[str, Any]] = []

        for sample in raw_chunk:
            ts = sample.timestamp
            service = sample.service
            host = sample.host
            base = {"timestamp": ts, "service": service, "host": host}

            metric_rows.append(
                {**base, "metric": "http_requests_total", "value": sample.request_count}
            )
            metric_rows.append({**base, "metric": "http_errors_total", "value": sample.error_count})
            metric_rows.append({**base, "metric": "cpu_usage_percent", "value": sample.cpu_percent})
            metric_rows.append(
                {**base, "metric": "memory_usage_bytes", "value": sample.memory_bytes}
            )

            latency_rows.extend({**base, "latency_ms": lat_ms} for lat_ms in sample.latencies_ms)

        if metric_rows:
            yield pd.DataFrame(
                metric_rows,
                columns=["timestamp", "metric", "service", "host", "value"],
            )
        if latency_rows:
            yield pd.DataFrame(
                latency_rows,
                columns=["timestamp", "service", "host", "latency_ms"],
            )
