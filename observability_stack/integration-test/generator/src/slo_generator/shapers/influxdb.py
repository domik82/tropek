"""InfluxDB shaper — 1s resolution, delta counters with rate field."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pandas as pd

from slo_generator.shapers.base import BaseShaper


class InfluxDBShaper(BaseShaper):
    """Shapes profile DataFrames into InfluxDB line-protocol-style metric rows.

    Preserves 1-second resolution (no downsampling).  Counter metrics include
    a ``rate`` field (value is already a per-second rate from the profile).
    Histogram latency metrics are emitted as p50 and p99 summary measurements.

    Output columns: timestamp, measurement, service, host, value, rate, le, status_code
    """

    def shape(self, profile_chunk: pd.DataFrame) -> Iterator[pd.DataFrame]:
        """Emit one row per profile row per metric (1s resolution)."""
        all_rows: list[dict[str, Any]] = []

        for _, row in profile_chunk.iterrows():
            timestamp = row["timestamp"]
            service = str(row["service"])
            host = str(row["host"])

            throughput = float(row["throughput_rps"])
            error_rate = float(row["error_rate"])
            errors = throughput * error_rate
            p50 = float(row["p50_latency"])
            p99 = float(row["p99_latency"])
            cpu = float(row["cpu_percent"])
            memory = float(row["memory_bytes"])

            # Counter: http_requests_total (value = rate already in rps)
            all_rows.append(
                {
                    "timestamp": timestamp,
                    "measurement": "http_requests_total",
                    "service": service,
                    "host": host,
                    "value": throughput,
                    "rate": throughput,
                    "le": pd.NA,
                    "status_code": "200",
                }
            )

            # Counter: http_errors_total
            all_rows.append(
                {
                    "timestamp": timestamp,
                    "measurement": "http_errors_total",
                    "service": service,
                    "host": host,
                    "value": errors,
                    "rate": errors,
                    "le": pd.NA,
                    "status_code": pd.NA,
                }
            )

            # Gauge: latency p50 (histogram summary — no rate)
            all_rows.append(
                {
                    "timestamp": timestamp,
                    "measurement": "http_request_duration_seconds_p50",
                    "service": service,
                    "host": host,
                    "value": p50,
                    "rate": pd.NA,
                    "le": pd.NA,
                    "status_code": pd.NA,
                }
            )

            # Gauge: latency p99 (histogram summary — no rate)
            all_rows.append(
                {
                    "timestamp": timestamp,
                    "measurement": "http_request_duration_seconds_p99",
                    "service": service,
                    "host": host,
                    "value": p99,
                    "rate": pd.NA,
                    "le": pd.NA,
                    "status_code": pd.NA,
                }
            )

            # Gauge: cpu
            all_rows.append(
                {
                    "timestamp": timestamp,
                    "measurement": "cpu_usage_percent",
                    "service": service,
                    "host": host,
                    "value": cpu,
                    "rate": pd.NA,
                    "le": pd.NA,
                    "status_code": pd.NA,
                }
            )

            # Gauge: memory
            all_rows.append(
                {
                    "timestamp": timestamp,
                    "measurement": "memory_usage_bytes",
                    "service": service,
                    "host": host,
                    "value": memory,
                    "rate": pd.NA,
                    "le": pd.NA,
                    "status_code": pd.NA,
                }
            )

        if all_rows:
            yield pd.DataFrame(all_rows)
