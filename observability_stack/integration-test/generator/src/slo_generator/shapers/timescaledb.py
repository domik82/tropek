"""TimescaleDB shaper — 1s resolution, histogram as p50/p99 summary rows."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pandas as pd

from slo_generator.shapers.base import BaseShaper


class TimescaleDBShaper(BaseShaper):
    """Shapes profile DataFrames into TimescaleDB-ready metric rows.

    Preserves 1-second resolution (no downsampling).  Histograms are emitted
    as pre-computed p50 and p99 summary rows — no individual buckets.

    Output columns (exactly 5): timestamp, metric, service, host, value
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

            base = {"service": service, "host": host, "timestamp": timestamp}

            all_rows.append({**base, "metric": "http_requests_total", "value": throughput})
            all_rows.append({**base, "metric": "http_errors_total", "value": errors})
            all_rows.append({**base, "metric": "http_request_duration_seconds_p50", "value": p50})
            all_rows.append({**base, "metric": "http_request_duration_seconds_p99", "value": p99})
            all_rows.append({**base, "metric": "cpu_usage_percent", "value": cpu})
            all_rows.append({**base, "metric": "memory_usage_bytes", "value": memory})

        if all_rows:
            # Emit with exactly the 5 required columns in a stable order
            df = pd.DataFrame(all_rows, columns=["timestamp", "metric", "service", "host", "value"])
            yield df
