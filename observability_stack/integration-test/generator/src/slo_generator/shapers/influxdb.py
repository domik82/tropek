"""InfluxDB shaper — raw latency points + per-second counter/gauge measurements."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pandas as pd

from slo_generator.raw import RawChunk
from slo_generator.shapers.base import BaseShaper


class InfluxDBShaper(BaseShaper):
    """Shapes RawChunk into InfluxDB line-protocol-style metric rows.

    Emits two types of data:
    1. Counter/gauge measurements (per-second, one row per sample):
       - http_requests_total, http_errors_total, cpu_usage_percent, memory_usage_bytes
    2. Individual latency points (one row per request):
       - http_request_latency with latency_ms field

    InfluxDB computes exact percentiles at query time using
    percentile("latency_ms", 99).
    """

    def shape(self, raw_chunk: RawChunk) -> Iterator[pd.DataFrame]:
        """Emit counter/gauge rows and individual latency point rows."""
        counter_rows: list[dict[str, Any]] = []
        latency_rows: list[dict[str, Any]] = []

        for sample in raw_chunk:
            ts = sample.timestamp
            service = sample.service
            host = sample.host

            # Counter/gauge measurements (per-second)
            counter_rows.append(
                {
                    "timestamp": ts,
                    "measurement": "http_requests_total",
                    "service": service,
                    "host": host,
                    "value": sample.request_count,
                    "status_code": "200",
                }
            )
            counter_rows.append(
                {
                    "timestamp": ts,
                    "measurement": "http_errors_total",
                    "service": service,
                    "host": host,
                    "value": sample.error_count,
                    "status_code": pd.NA,
                }
            )
            counter_rows.append(
                {
                    "timestamp": ts,
                    "measurement": "cpu_usage_percent",
                    "service": service,
                    "host": host,
                    "value": sample.cpu_percent,
                    "status_code": pd.NA,
                }
            )
            counter_rows.append(
                {
                    "timestamp": ts,
                    "measurement": "memory_usage_bytes",
                    "service": service,
                    "host": host,
                    "value": sample.memory_bytes,
                    "status_code": pd.NA,
                }
            )

            # Individual latency points
            latency_rows.extend(
                {
                    "timestamp": ts,
                    "measurement": "http_request_latency",
                    "service": service,
                    "host": host,
                    "value": lat_ms,
                    "status_code": pd.NA,
                }
                for lat_ms in sample.latencies_ms
            )

        all_rows = counter_rows + latency_rows
        if all_rows:
            yield pd.DataFrame(all_rows)
